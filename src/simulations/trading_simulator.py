"""Trading simulation engine that converts predictions into trade decisions."""
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.analysis import MarketRegime
from src.models.database import get_scoped_session
from src.models.entities import Entity
from src.models.predictions import Prediction
from src.models.trading_simulation import TradingSimulation
from src.services.market_data import MarketDataProvider
from src.services.prediction_performance_service import PredictionPerformanceService
from src.simulations.exit_strategy import ExitStrategyCalculator
from src.simulations.penny_stocks import (
    DEFAULT_MIN_VALID_PRICE_USD,
    DEFAULT_PENNY_THRESHOLD_USD,
    DEFAULT_ULTRA_PENNY_THRESHOLD_USD,
    is_penny_stock,
    is_ultra_penny_stock,
    min_valid_price,
    penny_config,
)
from src.simulations.risk_calculations import RiskCalculator, RiskInputs
from src.utils.json_helpers import clean_numpy_types, to_python_type
from src.utils.prediction_math import get_expected_return_pct, get_predicted_direction

logger = logging.getLogger(__name__)


class TradingSimulationEngine:
    """Simulate trades based on predictions and risk framework."""

    DEFAULT_SHARES = 100
    MIN_CONFIDENCE = 0.55
    MIN_EXPECTED_RETURN_PCT = 0.75
    MAX_RISK_SCORE = 0.65
    MAX_COST_RATIO = 0.70

    def __init__(
        self,
        market_data_provider: MarketDataProvider | None = None,
        performance_service: PredictionPerformanceService | None = None,
        risk_calculator: RiskCalculator | None = None,
        config_path: str | None = None,
    ):
        # Use shared market_data instance by default to centralize rate limiting
        from src.services.market_data import market_data as _global_market_data
        self.market_data_provider = market_data_provider or _global_market_data
        self.performance_service = performance_service or PredictionPerformanceService()
        self.risk_calculator = risk_calculator or RiskCalculator()
        self._market_cache: dict[str, dict] = {}
        self._market_cache_ttl = timedelta(minutes=10)

        # Load simulation parameters from config
        self.config = self._load_config(config_path)
        self._update_thresholds_from_config()

        # Initialize exit strategy calculator
        self.exit_calculator = ExitStrategyCalculator(config=self.config)

    def _load_config(self, config_path: str | None = None) -> dict:
        """Load simulation parameters from JSON config file."""
        if config_path is None:
            # Default path relative to project root
            config_path = Path(__file__).parent.parent.parent / "config" / "simulation_params.json"
        else:
            config_path = Path(config_path)

        try:
            with open(config_path) as f:
                config = json.load(f)
                logger.info(f"Loaded simulation config from {config_path}")
                return config
        except FileNotFoundError:
            logger.warning(f"Config file not found at {config_path}, using defaults")
            return self._get_default_config()
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}, using defaults")
            return self._get_default_config()

    def _get_default_config(self) -> dict:
        """Fallback default configuration if file not found."""
        return {
            "cost_parameters": {
                "commission": {"per_share": 0.005},
                "spread_bps": {"low_volatility": 4.0, "medium_volatility": 8.0, "high_volatility": 12.0},
                "slippage_bps": {"normal": 5.0, "high_volatility": 9.0},
                "market_impact_bps": {"small_order": 6.0, "medium_order": 12.0},
                "overnight_financing": {"long_position_bps_per_day": 1.1, "short_position_bps_per_day": 1.4},
                "short_borrow_costs": {"easy_to_borrow_annual_pct": 0.5},
                "regulatory_fees": {"sec_fee_bps": 0.278}
            },
            "position_constraints": {
                "max_position_size_pct": 10.0,
                "max_daily_volume_participation_pct": 5.0
            },
            "decision_thresholds": {
                "min_confidence": 0.55,
                "min_expected_return_pct": 0.75,
                "max_risk_score": 0.65,
                "max_cost_ratio": 0.70
            },
            # Penny-stock handling. This block used to be missing here while a
            # stray top-level "min_valid_price_usd" sat outside it - a key
            # nothing reads, since every lookup goes through
            # penny_stock_handling. Falling back to the shipped config's
            # values keeps the fallback path behaving like the real one.
            "penny_stock_handling": {
                "enabled": True,
                "price_threshold_usd": DEFAULT_PENNY_THRESHOLD_USD,
                "ultra_penny_threshold_usd": DEFAULT_ULTRA_PENNY_THRESHOLD_USD,
                "min_valid_price_usd": DEFAULT_MIN_VALID_PRICE_USD,
                "cost_method": "per_share_only",
                "max_cost_bps_cap": 1000,
            },
        }

    def _update_thresholds_from_config(self):
        """Update decision thresholds from loaded config."""
        thresholds = self.config.get("decision_thresholds", {})
        self.MIN_CONFIDENCE = thresholds.get("min_confidence", self.MIN_CONFIDENCE)
        self.MIN_EXPECTED_RETURN_PCT = thresholds.get("min_expected_return_pct", self.MIN_EXPECTED_RETURN_PCT)
        self.MAX_RISK_SCORE = thresholds.get("max_risk_score", self.MAX_RISK_SCORE)
        self.MAX_COST_RATIO = thresholds.get("max_cost_ratio", self.MAX_COST_RATIO)

    def _get_expected_return_pct(self, prediction: Prediction) -> float:
        """Expected return as a percentage (2.0 means +2%)."""
        return get_expected_return_pct(prediction)

    def _get_predicted_direction(self, prediction: Prediction) -> str:
        """Most likely direction for this prediction."""
        return get_predicted_direction(prediction)

    def _get_latest_regime(self, db: Session) -> MarketRegime | None:
        return db.query(MarketRegime).order_by(MarketRegime.created_at.desc()).first()

    def _regime_liquidity_stress(self, regime: MarketRegime | None) -> float:
        if not regime or not isinstance(regime.regime, dict):
            return 0.5
        liquidity = (regime.regime.get("liquidity") or "normal").lower()
        if liquidity == "stressed":
            return 0.8
        if liquidity == "abundant":
            return 0.2
        return 0.5

    def _is_penny_stock(self, price: float) -> bool:
        """Check if a stock qualifies as a penny stock based on configuration."""
        return is_penny_stock(self.config, price)

    def _is_ultra_penny_stock(self, price: float) -> bool:
        """Check if a stock qualifies as an ultra-penny stock (< $0.001)."""
        return is_ultra_penny_stock(self.config, price)

    def _calculate_dynamic_shares(self, price: float, base_shares: int = None) -> int:
        """
        Calculate appropriate number of shares based on price to achieve realistic position sizes.

        For ultra-penny stocks (< $0.001), use much higher share counts to ensure
        minimum position value is reasonable.

        Args:
            price: Current price per share
            base_shares: Base number of shares (default: DEFAULT_SHARES)

        Returns:
            Adjusted number of shares
        """
        if base_shares is None:
            base_shares = self.DEFAULT_SHARES

        if price <= 0:
            return base_shares

        penny_cfg = penny_config(self.config)

        # Ultra-penny stocks: scale up shares to achieve minimum position value
        if self._is_ultra_penny_stock(price):
            targets = penny_cfg.get("position_value_targets", {}).get("ultra_penny", {})
            target_position_value = targets.get("min_position_value_usd", 10.0)

            # Calculate shares needed to reach target position value
            shares_needed = int(target_position_value / price)

            # Cap at reasonable maximum (e.g., 10 million shares)
            max_shares = 10_000_000
            shares = min(shares_needed, max_shares)

            logger.info(f"Ultra-penny stock (${price:.6f}): using {shares:,} shares (target: ${shares * price:.2f} position)")
            return shares

        # Regular penny stocks: use moderate increase
        elif self._is_penny_stock(price):
            # For prices $0.001-$1.00, use modest multiplier
            multiplier = penny_cfg.get("penny_share_multiplier", 10)
            shares = base_shares * multiplier

            logger.info(f"Penny stock (${price:.4f}): using {shares:,} shares")
            return shares

        # Normal stocks: use base shares
        return base_shares

    def _estimate_penny_stock_costs(
        self,
        price: float,
        shares: int,
        cost_method: str,
        predicted_direction: str,
        horizon: str,
    ) -> tuple[float, dict]:
        """
        Estimate costs for penny stocks using alternative methods.

        Args:
            price: Current price per share
            shares: Number of shares to trade
            cost_method: Cost calculation method (per_share_only, flat_dollar, capped_bps)
            predicted_direction: Trade direction (for overnight/borrow costs)
            horizon: Prediction horizon (for time-based costs)

        Returns:
            Tuple of (total_bps, breakdown_dict with 'cost_method' field)
        """
        penny_cfg = penny_config(self.config)
        methods_config = penny_cfg.get("methods", {})

        position_value = price * shares
        if position_value <= 0:
            return 0.0, {"cost_method": "skipped_zero_value"}

        breakdown = {"cost_method": cost_method}

        if cost_method == "per_share_only":
            # Only use per-share commission, skip spread/slippage/etc
            method_config = methods_config.get("per_share_only", {})
            commission_per_share = method_config.get("commission_per_share", 0.005)
            min_commission = method_config.get("min_commission", 1.0)

            # For ultra-penny stocks with very high share counts, use only minimum commission
            # to avoid absurd costs (e.g., 100k shares * $0.005 = $500 is unrealistic)
            if shares > 10000:  # Ultra-high share count
                total_commission = min_commission
                logger.info(f"Ultra-high share count ({shares:,}) - using min commission only: ${min_commission}")
            else:
                total_commission = max(commission_per_share * shares, min_commission)

            commission_bps = (total_commission / position_value) * 10000

            # Add overnight and borrow costs (still relevant for penny stocks)
            overnight_bps = self._calculate_overnight_costs(predicted_direction, horizon)
            borrow_bps = self._calculate_borrow_costs(predicted_direction, horizon)

            total_bps = commission_bps + overnight_bps + borrow_bps

            breakdown.update({
                "commission_bps": round(commission_bps, 3),
                "spread_bps": 0.0,
                "slippage_bps": 0.0,
                "market_impact_bps": 0.0,
                "overnight_cost_bps": round(overnight_bps, 3),
                "borrow_cost_bps": round(borrow_bps, 3),
                "regulatory_bps": 0.0,
                "total_bps": round(total_bps, 3),
            })

        elif cost_method == "flat_dollar":
            # Use a flat dollar amount
            method_config = methods_config.get("flat_dollar", {})
            total_cost_usd = method_config.get("total_cost_usd", 5.0)

            total_bps = (total_cost_usd / position_value) * 10000

            breakdown.update({
                "commission_bps": 0.0,
                "spread_bps": 0.0,
                "slippage_bps": 0.0,
                "market_impact_bps": 0.0,
                "overnight_cost_bps": 0.0,
                "borrow_cost_bps": 0.0,
                "regulatory_bps": 0.0,
                "flat_cost_usd": total_cost_usd,
                "total_bps": round(total_bps, 3),
            })

        elif cost_method == "capped_bps":
            # Calculate normal BPS but cap at maximum
            method_config = methods_config.get("capped_bps", {})
            max_bps = method_config.get("max_bps", 1000)

            # Use standard calculation but will be capped
            cost_params = self.config.get("cost_parameters", {})
            commission_config = cost_params.get("commission", {})
            commission_per_share = commission_config.get("per_share", 0.005)
            min_commission = commission_config.get("min_commission", 1.0)

            total_commission = max(commission_per_share * shares, min_commission)
            commission_bps = min((total_commission / position_value) * 10000, max_bps / 2)

            # Simplified other costs for penny stocks
            spread_bps = min(20.0, max_bps / 10)
            slippage_bps = min(15.0, max_bps / 10)
            overnight_bps = self._calculate_overnight_costs(predicted_direction, horizon)
            borrow_bps = self._calculate_borrow_costs(predicted_direction, horizon)

            total_bps = min(
                commission_bps + spread_bps + slippage_bps + overnight_bps + borrow_bps,
                max_bps
            )

            breakdown.update({
                "commission_bps": round(commission_bps, 3),
                "spread_bps": round(spread_bps, 3),
                "slippage_bps": round(slippage_bps, 3),
                "market_impact_bps": 0.0,
                "overnight_cost_bps": round(overnight_bps, 3),
                "borrow_cost_bps": round(borrow_bps, 3),
                "regulatory_bps": 0.0,
                "max_bps_cap": max_bps,
                "total_bps": round(total_bps, 3),
            })
        else:
            # Fallback to per_share_only
            return self._estimate_penny_stock_costs(
                price, shares, "per_share_only", predicted_direction, horizon
            )

        # penny_stock_handling.max_cost_bps_cap is the config's declared ceiling
        # ("prevent unrealistic BPS calculations"), but only the capped_bps method
        # bounded its own total. per_share_only did not, so a $0.0001 share price
        # produced ~1,000,000 bps from the minimum commission alone. Apply the
        # ceiling to every method.
        max_cost_bps = penny_cfg.get("max_cost_bps_cap")
        if max_cost_bps is not None and total_bps > max_cost_bps:
            logger.warning(
                "Penny stock cost %.1f bps exceeds max_cost_bps_cap %s - capping",
                total_bps,
                max_cost_bps,
            )
            breakdown["uncapped_total_bps"] = round(total_bps, 3)
            breakdown["max_cost_bps_cap"] = max_cost_bps
            total_bps = float(max_cost_bps)
            breakdown["total_bps"] = total_bps

        return total_bps, breakdown

    def _estimate_costs_bps(
        self,
        price: float,
        volatility_regime: str,
        predicted_direction: str,
        horizon: str,
        shares: int = DEFAULT_SHARES,
        daily_volume: float | None = None,
    ) -> tuple[float, dict]:
        """
        Estimate comprehensive transaction costs in basis points.

        Args:
            price: Current price per share
            volatility_regime: Market volatility regime (low/medium/high/stressed)
            predicted_direction: Trade direction (up/down/flat) - affects overnight & borrow costs
            horizon: Prediction horizon (1d/5d/20d) - affects time-based costs
            shares: Number of shares to trade
            daily_volume: Average daily trading volume (for liquidity analysis)

        Returns:
            Tuple of (total_bps, breakdown_dict)
        """
        if price <= 0:
            return 0.0, {}

        # FIRST: Check for extremely small prices that are too cheap even for
        # penny stock handling - these are considered invalid/unreliable.
        # Same threshold the penny-stock classifiers use, so a price can never
        # be "too cheap to cost" and "a penny stock" at the same time.
        floor_price = min_valid_price(self.config)
        if price < floor_price:
            logger.warning(f"Price ${price:.6f} below min_valid_price_usd ${floor_price} - skipping cost estimation")
            return 0.0, {}

        # SECOND: Check if this is a penny stock (price between min_valid and threshold)
        # and use alternative cost calculation
        if self._is_penny_stock(price):
            cost_method = penny_config(self.config).get("cost_method", "per_share_only")
            logger.info(f"Penny stock detected (price: ${price:.4f}) - using '{cost_method}' cost method")
            return self._estimate_penny_stock_costs(
                price, shares, cost_method, predicted_direction, horizon
            )

        cost_params = self.config.get("cost_parameters", {})

        # 1. Commission costs
        commission_config = cost_params.get("commission", {})
        commission_per_share = commission_config.get("per_share", 0.005)
        min_commission = commission_config.get("min_commission", 1.0)
        commission = max(commission_per_share * shares, min_commission)
        commission_bps = (commission / (price * shares)) * 10000

        # 2. Spread costs (volatility-dependent)
        vol_key = (volatility_regime or "medium").lower()
        spread_config = cost_params.get("spread_bps", {})
        spread_bps = spread_config.get(f"{vol_key}_volatility", spread_config.get("medium_volatility", 8.0))

        # 3. Slippage costs
        slippage_config = cost_params.get("slippage_bps", {})
        slippage_bps = slippage_config.get("high_volatility", 9.0) if vol_key == "high" or vol_key == "stressed" else slippage_config.get("normal", 5.0)

        # 4. Market impact (volume-aware if daily_volume provided)
        impact_bps = self._calculate_market_impact(price, shares, daily_volume, vol_key)

        # 5. Overnight financing costs (time-based, direction-dependent)
        overnight_bps = self._calculate_overnight_costs(predicted_direction, horizon)

        # 6. Short borrow costs (only for short positions)
        borrow_bps = self._calculate_borrow_costs(predicted_direction, horizon)

        # 7. Regulatory fees (SEC + FINRA)
        regulatory_config = cost_params.get("regulatory_fees", {})
        sec_fee_bps = regulatory_config.get("sec_fee_bps", 0.278)
        finra_fee_bps = regulatory_config.get("finra_taf_bps", 0.013)
        regulatory_bps = sec_fee_bps + finra_fee_bps

        # Total costs
        total_bps = (
            commission_bps +
            spread_bps +
            slippage_bps +
            impact_bps +
            overnight_bps +
            borrow_bps +
            regulatory_bps
        )

        breakdown = {
            "commission_bps": round(commission_bps, 3),
            "spread_bps": round(spread_bps, 3),
            "slippage_bps": round(slippage_bps, 3),
            "market_impact_bps": round(impact_bps, 3),
            "overnight_cost_bps": round(overnight_bps, 3),
            "borrow_cost_bps": round(borrow_bps, 3),
            "regulatory_bps": round(regulatory_bps, 3),
            "total_bps": round(total_bps, 3),
        }
        return total_bps, breakdown

    def _calculate_market_impact(
        self,
        price: float,
        shares: int,
        daily_volume: float | None,
        vol_regime: str
    ) -> float:
        """Calculate dynamic market impact based on order size vs daily volume."""
        impact_config = self.config.get("cost_parameters", {}).get("market_impact_bps", {})

        if daily_volume and daily_volume > 0:
            # Volume-aware calculation
            participation_pct = (shares / daily_volume) * 100
            volume_threshold = impact_config.get("volume_threshold_pct", 1.0)

            if participation_pct <= volume_threshold:
                return impact_config.get("small_order", 6.0)
            elif participation_pct <= volume_threshold * 3:
                return impact_config.get("medium_order", 12.0)
            else:
                # Large order - exponential penalty
                base_impact = impact_config.get("large_order", 25.0)
                # Add penalty for stressed vol
                stress_multiplier = 1.5 if vol_regime == "stressed" else 1.0
                return base_impact * stress_multiplier
        else:
            # Fallback to simple share-based calculation
            return impact_config.get("small_order", 6.0) if shares <= 100 else impact_config.get("medium_order", 12.0)

    def _calculate_overnight_costs(self, predicted_direction: str, horizon: str) -> float:
        """Calculate overnight financing fees based on holding period."""
        financing_config = self.config.get("cost_parameters", {}).get("overnight_financing", {})

        # Convert horizon to days
        horizon_days = {"1d": 1, "5d": 5, "20d": 20}.get(horizon, 5)

        # Direction determines if long or short position
        if predicted_direction == "down":
            # Short position - higher overnight costs
            cost_per_day = financing_config.get("short_position_bps_per_day", 1.4)
        else:
            # Long position (up or flat)
            cost_per_day = financing_config.get("long_position_bps_per_day", 1.1)

        return cost_per_day * horizon_days

    def _calculate_borrow_costs(self, predicted_direction: str, horizon: str) -> float:
        """Calculate short-selling borrow costs (only applies to short positions)."""
        if predicted_direction != "down":
            return 0.0  # No borrow costs for long positions

        borrow_config = self.config.get("cost_parameters", {}).get("short_borrow_costs", {})

        # Assume "easy to borrow" for most liquid stocks
        # In production, this should be determined by stock-specific data
        annual_pct = borrow_config.get("easy_to_borrow_annual_pct", 0.5)

        # Convert to bps for the holding period
        horizon_days = {"1d": 1, "5d": 5, "20d": 20}.get(horizon, 5)
        borrow_bps = (annual_pct / 100) * (horizon_days / 365) * 10000

        return borrow_bps

    def _get_market_snapshot(self, ticker: str) -> dict | None:
        now = datetime.now(UTC)
        cached = self._market_cache.get(ticker)
        if cached and now - cached["timestamp"] <= self._market_cache_ttl:
            return cached["data"]

        data = self.market_data_provider.get_live_price(ticker)
        if not data:
            return None

        self._market_cache[ticker] = {"timestamp": now, "data": data}
        return data

    def _calculate_decision(
        self,
        predicted_direction: str,
        expected_return_pct: float,
        confidence: float,
        risk_score: float,
        cost_ratio: float,
        position_constraints: dict | None = None,
    ) -> tuple[str, dict]:
        """
        Calculate trading decision with position sizing constraints.

        Returns:
            Tuple of (decision, constraint_info)
        """
        constraint_info = {
            "blocked_by": [],
            "position_size_ok": True,
            "liquidity_ok": True,
            "risk_ok": True
        }

        # Standard decision thresholds
        if confidence < self.MIN_CONFIDENCE:
            constraint_info["blocked_by"].append(f"confidence ({confidence:.2%} < {self.MIN_CONFIDENCE:.2%})")
            return "hold", constraint_info

        if abs(expected_return_pct) < self.MIN_EXPECTED_RETURN_PCT:
            constraint_info["blocked_by"].append(f"expected_return ({abs(expected_return_pct):.2f}% < {self.MIN_EXPECTED_RETURN_PCT:.2f}%)")
            return "hold", constraint_info

        if risk_score is not None and risk_score > self.MAX_RISK_SCORE:
            constraint_info["blocked_by"].append(f"risk_score ({risk_score:.2f} > {self.MAX_RISK_SCORE:.2f})")
            constraint_info["risk_ok"] = False
            return "hold", constraint_info
        elif risk_score is None:
            # Missing risk score - treat as conservative hold
            constraint_info["blocked_by"].append("risk_score (N/A)")
            constraint_info["risk_ok"] = False
            return "hold", constraint_info

        if cost_ratio > self.MAX_COST_RATIO:
            constraint_info["blocked_by"].append(f"cost_ratio ({cost_ratio:.2f} > {self.MAX_COST_RATIO:.2f})")
            return "hold", constraint_info

        # Position sizing constraints (if provided)
        if position_constraints:
            position_size_pct = position_constraints.get("position_size_pct", 0)
            max_position_size = self.config.get("position_constraints", {}).get("max_position_size_pct", 10.0)

            if position_size_pct > max_position_size:
                constraint_info["blocked_by"].append(f"position_size ({position_size_pct:.1f}% > {max_position_size:.1f}%)")
                constraint_info["position_size_ok"] = False
                return "hold", constraint_info

            # Liquidity constraints
            daily_volume_usd = position_constraints.get("daily_volume_usd", 0)
            min_liquidity = self.config.get("position_constraints", {}).get("min_liquidity_usd", 100000)

            if daily_volume_usd > 0 and daily_volume_usd < min_liquidity:
                constraint_info["blocked_by"].append(f"liquidity (${daily_volume_usd:,.0f} < ${min_liquidity:,.0f})")
                constraint_info["liquidity_ok"] = False
                return "hold", constraint_info

        # All constraints passed - make direction-based decision
        if predicted_direction == "up" and expected_return_pct > 0:
            return "buy", constraint_info
        if predicted_direction == "down" and expected_return_pct < 0:
            return "sell", constraint_info

        return "hold", constraint_info

    def _resolve_actual_return(
        self,
        db: Session,
        prediction: Prediction,
        entity: Entity,
    ) -> tuple[dict | None, float | None]:
        """
        Resolve the actual return for a prediction.

        Tries live performance data first, then falls back to a saved
        PredictionOutcome record.

        Returns:
            Tuple of (performance dict or None, actual return pct or None)
        """
        performance = self.performance_service.get_prediction_performance(prediction, entity)
        actual_return_pct = performance.get("total_return_pct") if performance else None

        # FALLBACK: Check PredictionOutcome table if live data unavailable
        if actual_return_pct is None:
            from src.models.predictions import PredictionOutcome
            outcome = db.query(PredictionOutcome).filter(
                PredictionOutcome.prediction_id == prediction.prediction_id
            ).first()
            if outcome and outcome.actual_return is not None:
                actual_return_pct = outcome.actual_return
                logger.info(f"Using saved PredictionOutcome for {entity.entity_id}: {actual_return_pct:.2f}%")
            else:
                logger.warning(f"No actual return data available for {entity.entity_id} (prediction {prediction.prediction_id})")

        return performance, actual_return_pct

    def _reset_simulation_for_invalid_price(
        self,
        existing: TradingSimulation,
        prediction: Prediction,
        entity: Entity,
        price: float,
    ) -> TradingSimulation:
        """Clear an existing simulation's values when the market price is invalid or too small."""
        logger.warning(f"Invalid/too-small price for {entity.entity_id} ({price}) - clearing existing simulation values")
        existing.decision = "hold"
        existing.expected_return_pct = to_python_type(self._get_expected_return_pct(prediction))
        existing.actual_return_pct = None
        existing.divergence_pct = None
        existing.risk_score = None
        existing.confidence = to_python_type(prediction.confidence)
        existing.calibrated_confidence = to_python_type(prediction.calibrated_confidence)
        existing.transaction_cost_bps = 0.0
        existing.overnight_cost_bps = None
        existing.borrow_cost_bps = None
        existing.position_size_pct = 0.0
        existing.position_value_usd = 0.0
        existing.cost_breakdown = {}
        existing.risk_breakdown = {}
        # Exit levels were derived from a price we just rejected. Leaving them
        # in place showed a stale stop loss / take profit next to a cleared row.
        existing.stop_loss_price = None
        existing.stop_loss_pct = None
        existing.stop_loss_type = None
        existing.trailing_stop_price = None
        existing.take_profit_price = None
        existing.take_profit_pct = None
        existing.risk_reward_ratio = None
        existing.exit_strategy = {}
        existing.simulation_metadata = {"note": "skipped - invalid/too-small market price", "market_price": price}
        existing.created_at = datetime.now(UTC)
        return existing

    def simulate_prediction(
        self,
        db: Session,
        prediction: Prediction,
        entity: Entity,
        existing: TradingSimulation | None = None,
    ) -> TradingSimulation | None:
        """Create or update the simulation for one prediction.

        Args:
            existing: The stored simulation, when the caller has already looked
                it up. Saves a redundant query in batch runs; looked up here
                when omitted.
        """
        if not prediction or not entity:
            return None

        if existing is None:
            existing = self._find_simulation(db, prediction.prediction_id)

        predicted_direction = self._get_predicted_direction(prediction)
        expected_return_pct = self._get_expected_return_pct(prediction)
        confidence = prediction.calibrated_confidence or prediction.confidence or 0.0

        performance, actual_return_pct = self._resolve_actual_return(db, prediction, entity)

        # Calculate divergence only when actual data exists.
        # Don't default to expected - leave as None to indicate missing data.
        divergence_pct = None
        if actual_return_pct is not None:
            divergence_pct = expected_return_pct - actual_return_pct

        # Convert numpy types to Python native types for PostgreSQL compatibility
        actual_return_pct = to_python_type(actual_return_pct)
        divergence_pct = to_python_type(divergence_pct)
        expected_return_pct = to_python_type(expected_return_pct)
        confidence = to_python_type(confidence)

        regime = self._get_latest_regime(db)
        volatility_regime = None
        regime_confidence = None
        if regime:
            volatility_regime = (regime.regime or {}).get("volatility")
            regime_confidence = (regime.regime_probabilities or {}).get("current_regime_confidence")

        market_snapshot = self._get_market_snapshot(entity.entity_id)
        price = market_snapshot.get("price") if market_snapshot else 0.0
        daily_volume = market_snapshot.get("volume") if market_snapshot else None

        # Calculate dynamic share count based on price (higher shares for ultra-pennies)
        shares = self._calculate_dynamic_shares(price)

        total_cost_bps, cost_breakdown = self._estimate_costs_bps(
            price=price,
            volatility_regime=volatility_regime,
            predicted_direction=predicted_direction,
            horizon=prediction.horizon,
            shares=shares,
            daily_volume=daily_volume
        )

        # If cost_breakdown is empty it means price was invalid or unavailable
        if not cost_breakdown:
            # If we already have an existing simulation, clear its values to avoid showing stale/absurd numbers
            if existing:
                return self._reset_simulation_for_invalid_price(existing, prediction, entity, price)

            logger.warning(f"Skipping simulation for {entity.entity_id}: invalid or missing market price ({price})")
            return None
        expected_return_bps = abs(expected_return_pct) * 100.0
        cost_ratio = total_cost_bps / expected_return_bps if expected_return_bps > 0 else 1.0

        # Calculate risk-adjusted position size
        # Start with a FIXED DOLLAR AMOUNT baseline (not fixed shares!)
        assumed_portfolio_value = 5000  # $5k default portfolio
        baseline_dollar_position = 250  # $250 baseline position (5% of portfolio)
        baseline_position_size_pct = (baseline_dollar_position / assumed_portfolio_value) * 100

        # Calculate daily volume and initial metrics for risk calculation
        daily_volume_usd = (daily_volume * price) if daily_volume and price > 0 else 0

        # First, calculate risk WITHOUT position adjustment
        risk_inputs = RiskInputs(
            model_uncertainty=1.0 - min(max(confidence, 0.0), 1.0),
            divergence_pct=divergence_pct,
            volatility_regime=volatility_regime,
            liquidity_stress=self._regime_liquidity_stress(regime),
            regime_confidence=regime_confidence,
            transaction_cost_ratio=min(max(cost_ratio, 0.0), 1.0),
            market_impact_bps=cost_breakdown.get("market_impact_bps", 0.0),
            correlation_breakdown=None,
            position_size_pct=baseline_position_size_pct,
            daily_volume_usd=daily_volume_usd,
        )
        risk_result = self.risk_calculator.calculate(risk_inputs)

        # Now adjust position size based on risk score (INVERSE relationship)
        # Higher risk = smaller position
        # risk_result is a Dict with keys: risk_score, components, weights
        risk_score = risk_result["risk_score"]
        max_position_pct = self.config.get("position_constraints", {}).get("max_position_size_pct", 10.0)

        # Risk-adjusted position sizing: reduce position as risk increases
        # Formula: baseline * (1 - risk_score) with floor at 20% of baseline
        risk_adjustment_factor = max(0.2, 1.0 - risk_score)
        position_size_pct = baseline_position_size_pct * risk_adjustment_factor

        # Cap at max_position_pct
        position_size_pct = min(position_size_pct, max_position_pct)

        # Calculate actual position value based on adjusted size
        position_value = (assumed_portfolio_value * position_size_pct) / 100

        # Convert numeric values to Python native types for PostgreSQL
        risk_score = to_python_type(risk_result["risk_score"])
        position_size_pct = to_python_type(position_size_pct)
        position_value = to_python_type(position_value)
        total_cost_bps = to_python_type(total_cost_bps)

        position_constraints = {
            "position_size_pct": position_size_pct,
            "daily_volume_usd": daily_volume_usd,
        }

        decision, constraint_info = self._calculate_decision(
            predicted_direction=predicted_direction,
            expected_return_pct=expected_return_pct,
            confidence=confidence,
            risk_score=risk_score,
            cost_ratio=cost_ratio,
            position_constraints=position_constraints,
        )

        # Calculate exit strategy (stop loss and take profit)
        exit_strategy = self.exit_calculator.calculate_exit_levels(
            entry_price=price,
            direction=predicted_direction,
            volatility_regime=volatility_regime,
            risk_score=risk_score,
            confidence=confidence,
            horizon=prediction.horizon,
            market_data_provider=self.market_data_provider,
            ticker=entity.entity_id
        )

        simulation_payload = {
            "predicted_direction": predicted_direction,
            "actual_direction": performance.get("actual_direction") if performance else None,
            "strategy_result": performance.get("strategy_result") if performance else None,
            "market_snapshot": {
                "price": price,
                "change_percent": market_snapshot.get("change_percent") if market_snapshot else None,
                "timestamp": market_snapshot.get("timestamp").isoformat() if market_snapshot else None,
                "volume": daily_volume,
                "volume_usd": daily_volume_usd,
            },
            "position_info": {
                "shares": shares,
                "shares_base": self.DEFAULT_SHARES,
                "position_value_usd": position_value,
                "position_size_pct": position_size_pct,
                "assumed_portfolio_value": assumed_portfolio_value,
            },
            "constraints": constraint_info,
            "cost_details": {
                **cost_breakdown,
                "cost_ratio": cost_ratio,
                "expected_return_bps": expected_return_bps,
            },
            "penny_stock_info": {
                "is_penny_stock": self._is_penny_stock(price),
                "is_ultra_penny_stock": self._is_ultra_penny_stock(price),
                "price": price,
                "cost_method": cost_breakdown.get("cost_method", "standard"),
                "shares_used": shares,
                "shares_multiplier": shares / self.DEFAULT_SHARES if self.DEFAULT_SHARES > 0 else 1.0,
            },
            "exit_strategy": exit_strategy.get("exit_strategy_metadata", {})
        }

        if existing:
            existing.decision = decision
            existing.expected_return_pct = expected_return_pct
            existing.actual_return_pct = actual_return_pct
            existing.divergence_pct = divergence_pct
            existing.risk_score = risk_score
            existing.confidence = confidence
            existing.calibrated_confidence = to_python_type(prediction.calibrated_confidence)
            existing.transaction_cost_bps = total_cost_bps
            existing.overnight_cost_bps = to_python_type(cost_breakdown.get("overnight_cost_bps"))
            existing.borrow_cost_bps = to_python_type(cost_breakdown.get("borrow_cost_bps"))
            existing.position_size_pct = position_size_pct
            existing.position_value_usd = position_value
            existing.cost_breakdown = clean_numpy_types(cost_breakdown)
            existing.risk_breakdown = clean_numpy_types(risk_result["components"])
            # Exit strategy fields
            existing.stop_loss_price = to_python_type(exit_strategy.get("stop_loss_price"))
            existing.stop_loss_pct = to_python_type(exit_strategy.get("stop_loss_pct"))
            existing.stop_loss_type = exit_strategy.get("method")
            existing.trailing_stop_price = to_python_type(exit_strategy.get("trailing_stop_price"))
            existing.take_profit_price = to_python_type(exit_strategy.get("take_profit_price"))
            existing.take_profit_pct = to_python_type(exit_strategy.get("take_profit_pct"))
            existing.risk_reward_ratio = to_python_type(exit_strategy.get("risk_reward_ratio"))
            existing.exit_strategy = clean_numpy_types(exit_strategy)
            existing.simulation_metadata = clean_numpy_types(simulation_payload)
            existing.created_at = datetime.now(UTC)
            return existing

        simulation = TradingSimulation(
            prediction_id=prediction.prediction_id,
            entity_id=prediction.entity_id,
            horizon=prediction.horizon,
            decision=decision,
            expected_return_pct=expected_return_pct,
            actual_return_pct=actual_return_pct,
            divergence_pct=divergence_pct,
            risk_score=risk_score,
            confidence=confidence,
            calibrated_confidence=to_python_type(prediction.calibrated_confidence),
            transaction_cost_bps=total_cost_bps,
            overnight_cost_bps=to_python_type(cost_breakdown.get("overnight_cost_bps")),
            borrow_cost_bps=to_python_type(cost_breakdown.get("borrow_cost_bps")),
            position_size_pct=position_size_pct,
            position_value_usd=position_value,
            cost_breakdown=clean_numpy_types(cost_breakdown),
            risk_breakdown=clean_numpy_types(risk_result["components"]),
            # Exit strategy fields
            stop_loss_price=to_python_type(exit_strategy.get("stop_loss_price")),
            stop_loss_pct=to_python_type(exit_strategy.get("stop_loss_pct")),
            stop_loss_type=exit_strategy.get("method"),
            trailing_stop_price=to_python_type(exit_strategy.get("trailing_stop_price")),
            take_profit_price=to_python_type(exit_strategy.get("take_profit_price")),
            take_profit_pct=to_python_type(exit_strategy.get("take_profit_pct")),
            risk_reward_ratio=to_python_type(exit_strategy.get("risk_reward_ratio")),
            exit_strategy=clean_numpy_types(exit_strategy),
            simulation_metadata=clean_numpy_types(simulation_payload),
            created_at=datetime.now(UTC),
        )
        db.add(simulation)
        return simulation

    @staticmethod
    def _empty_stats() -> dict:
        return {"processed": 0, "created": 0, "updated": 0, "skipped": 0, "errors": 0}

    def _simulate_all(self, db: Session, predictions: list[Prediction]) -> dict:
        """Simulate every prediction in ``predictions``, tallying the outcome.

        One prediction failing never aborts the batch; it is counted as an
        error and processing continues.
        """
        stats = self._empty_stats()

        for prediction in predictions:
            try:
                entity = db.query(Entity).filter(
                    Entity.entity_id == prediction.entity_id
                ).first()
                if not entity:
                    logger.debug(
                        "No entity %s for prediction %s",
                        prediction.entity_id,
                        prediction.prediction_id,
                    )
                    stats["skipped"] += 1
                    continue

                # Looked up once and handed down, so simulate_prediction does
                # not repeat the same query.
                existing = self._find_simulation(db, prediction.prediction_id)

                simulation = self.simulate_prediction(db, prediction, entity, existing=existing)
                if not simulation:
                    logger.debug("Simulation skipped for prediction %s", prediction.prediction_id)
                    stats["skipped"] += 1
                    continue

                stats["processed"] += 1
                stats["updated" if existing else "created"] += 1
            except Exception as e:
                logger.error(
                    f"Error simulating prediction {prediction.prediction_id}: {e}",
                    exc_info=True,
                )
                stats["errors"] += 1

        return stats

    @staticmethod
    def _find_simulation(db: Session, prediction_id) -> TradingSimulation | None:
        """Return the stored simulation for a prediction, if any."""
        return db.query(TradingSimulation).filter(
            TradingSimulation.prediction_id == prediction_id
        ).first()

    def process_batch(self, limit: int = 50, lookback_days: int = 7) -> dict:
        """Simulate trades for recent predictions."""
        cutoff = datetime.now(UTC) - timedelta(days=lookback_days)

        with get_scoped_session() as db:
            predictions = db.query(Prediction).filter(
                Prediction.created_at >= cutoff
            ).order_by(Prediction.created_at.desc()).limit(limit).all()

            if not predictions:
                return self._empty_stats()

            return self._simulate_all(db, predictions)

    def get_statistics(self) -> dict:
        """Get simulation statistics."""
        with get_scoped_session() as db:
            # One grouped scan instead of four full-table COUNTs.
            counts = dict(
                db.query(TradingSimulation.decision, func.count())
                .group_by(TradingSimulation.decision)
                .all()
            )

            return {
                "total_simulations": sum(counts.values()),
                "buys": counts.get("buy", 0),
                "sells": counts.get("sell", 0),
                "holds": counts.get("hold", 0),
            }

    def delete_simulation(self, simulation_id: str) -> bool:
        """Delete a simulation by ID."""
        try:
            with get_scoped_session() as db:
                simulation = db.query(TradingSimulation).filter(
                    TradingSimulation.simulation_id == simulation_id
                ).first()
                if simulation:
                    db.delete(simulation)
                    db.commit()
                    logger.info(f"Deleted simulation {simulation_id}")
                    return True
                logger.warning(f"Simulation {simulation_id} not found")
                return False
        except Exception as e:
            logger.error(f"Error deleting simulation {simulation_id}: {e}")
            return False

    def refresh_simulation(self, simulation_id: str) -> bool:
        """Refresh/recalculate a simulation by ID."""
        try:
            with get_scoped_session() as db:
                simulation = db.query(TradingSimulation).filter(
                    TradingSimulation.simulation_id == simulation_id
                ).first()
                if not simulation:
                    logger.warning(f"Simulation {simulation_id} not found")
                    return False

                prediction = db.query(Prediction).filter(
                    Prediction.prediction_id == simulation.prediction_id
                ).first()
                if not prediction:
                    logger.warning(f"Prediction {simulation.prediction_id} not found")
                    return False

                entity = db.query(Entity).filter(
                    Entity.entity_id == prediction.entity_id
                ).first()
                if not entity:
                    logger.warning(f"Entity {prediction.entity_id} not found")
                    return False

                # Recalculate the simulation
                self.simulate_prediction(db, prediction, entity)
                db.commit()
                logger.info(f"Refreshed simulation {simulation_id}")
                return True
        except Exception as e:
            logger.error(f"Error refreshing simulation {simulation_id}: {e}")
            return False

    def create_simulations_from_predictions(
        self,
        prediction_ids: list[str] | None = None,
        entity_filter: list[str] | None = None,
        horizon_filter: str | None = None,
        date_range: tuple[datetime, datetime] | None = None,
        limit: int = 100,
    ) -> dict:
        """Create simulations from specific predictions or filters."""
        with get_scoped_session() as db:
            query = db.query(Prediction)

            if prediction_ids:
                query = query.filter(Prediction.prediction_id.in_(prediction_ids))
            else:
                if entity_filter:
                    query = query.filter(Prediction.entity_id.in_(entity_filter))
                    logger.info(f"Filtering by entities: {entity_filter}")
                if horizon_filter and horizon_filter != "all":
                    query = query.filter(Prediction.horizon == horizon_filter)
                    logger.info(f"Filtering by horizon: {horizon_filter}")
                if date_range and len(date_range) == 2:
                    start, end = date_range
                    if start:
                        query = query.filter(Prediction.created_at >= start)
                    if end:
                        query = query.filter(Prediction.created_at <= end)
                    logger.info(f"Filtering by date range: {start} to {end}")

            predictions = query.order_by(Prediction.created_at.desc()).limit(limit).all()

            logger.info(f"Found {len(predictions)} predictions matching filters (limit: {limit})")

            if not predictions:
                logger.warning("No predictions found matching the filters")
                return self._empty_stats()

            # get_scoped_session() commits on clean exit, so no commit here.
            return self._simulate_all(db, predictions)
