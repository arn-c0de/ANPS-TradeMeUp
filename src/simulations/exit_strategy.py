"""Exit strategy calculations for stop loss and take profit levels."""
from typing import Dict, Optional, Tuple
import logging
from datetime import datetime, timezone, timedelta
import numpy as np

logger = logging.getLogger(__name__)


class ExitStrategyCalculator:
    """Calculate stop loss and take profit levels using various methods."""

    def __init__(self, config: Dict):
        """
        Initialize exit strategy calculator with configuration.
        
        Args:
            config: Simulation configuration dictionary
        """
        self.config = config
        self.sl_tp_config = config.get("stop_loss_take_profit", {})
        self.enabled = self.sl_tp_config.get("enabled", True)
        self.default_method = self.sl_tp_config.get("default_method", "atr_based")

    def calculate_exit_levels(
        self,
        entry_price: float,
        direction: str,
        volatility_regime: Optional[str],
        risk_score: float,
        confidence: float,
        horizon: str,
        market_data_provider,
        ticker: str,
    ) -> Dict:
        """
        Calculate comprehensive exit strategy (stop loss and take profit).
        
        Args:
            entry_price: Entry price for the position
            direction: Predicted direction (up/down/flat)
            volatility_regime: Market volatility regime (low/medium/high/stressed)
            risk_score: Risk score from risk calculator (0-1)
            confidence: Model confidence (0-1)
            horizon: Prediction horizon (1d/5d/20d)
            market_data_provider: Provider for market data
            ticker: Stock ticker symbol
            
        Returns:
            Dictionary with stop loss and take profit levels
        """
        if not self.enabled or entry_price <= 0:
            return self._get_empty_exit_strategy()

        # Determine which method to use
        method = self.default_method
        
        # Try ATR-based first (most realistic)
        if method == "atr_based":
            result = self._calculate_atr_based_exits(
                entry_price, direction, volatility_regime, horizon,
                market_data_provider, ticker
            )
            # Fallback to risk-adjusted if ATR calculation fails
            if result["stop_loss_price"] is None:
                logger.info(f"ATR calculation failed for {ticker}, falling back to risk-adjusted")
                result = self._calculate_risk_adjusted_exits(
                    entry_price, direction, risk_score, confidence, horizon
                )
        elif method == "risk_adjusted":
            result = self._calculate_risk_adjusted_exits(
                entry_price, direction, risk_score, confidence, horizon
            )
        else:
            # Percentage-based fallback
            result = self._calculate_percentage_based_exits(
                entry_price, direction, horizon
            )

        # Apply penny stock adjustments if needed
        if self._is_penny_stock(entry_price):
            result = self._apply_penny_stock_adjustments(result, entry_price)

        # Calculate trailing stop if enabled
        if self.sl_tp_config.get("trailing_stop", {}).get("enabled", True):
            result["trailing_stop_price"] = self._calculate_trailing_stop(
                entry_price, direction, result["stop_loss_pct"]
            )

        # Add metadata
        result["exit_strategy_metadata"] = {
            "method_used": result.get("method", "unknown"),
            "volatility_regime": volatility_regime,
            "risk_score": risk_score,
            "confidence": confidence,
            "horizon": horizon,
            "is_penny_stock": self._is_penny_stock(entry_price),
            "calculation_timestamp": datetime.now(timezone.utc).isoformat()
        }

        return result

    def _calculate_atr_based_exits(
        self,
        entry_price: float,
        direction: str,
        volatility_regime: Optional[str],
        horizon: str,
        market_data_provider,
        ticker: str,
    ) -> Dict:
        """
        Calculate ATR-based stop loss and take profit.
        
        Uses Average True Range to adapt stops to each stock's volatility.
        """
        atr_config = self.sl_tp_config.get("atr_based", {})
        atr_period = atr_config.get("atr_period_days", 14)
        
        # Get historical data for ATR calculation
        try:
            # Fetch historical data (need enough for ATR calculation)
            hist_data = market_data_provider.get_historical_data(
                ticker, 
                period="1mo",  # Get 1 month to have enough data
                interval="1d"
            )
            
            if hist_data is None or len(hist_data) < atr_period:
                logger.warning(f"Insufficient historical data for ATR calculation: {ticker}")
                return {"stop_loss_price": None, "take_profit_price": None}
            
            # Calculate ATR (Average True Range)
            atr = self._calculate_atr(hist_data, period=atr_period)
            
            if atr is None or atr <= 0:
                logger.warning(f"Invalid ATR calculated for {ticker}: {atr}")
                return {"stop_loss_price": None, "take_profit_price": None}
            
            # Get volatility regime multipliers
            vol_key = (volatility_regime or "unknown").lower()
            sl_multipliers = atr_config.get("atr_multiplier_stop_loss", {})
            tp_multipliers = atr_config.get("atr_multiplier_take_profit", {})
            
            sl_multiplier = sl_multipliers.get(vol_key, sl_multipliers.get("unknown", 2.0))
            tp_multiplier = tp_multipliers.get(vol_key, tp_multipliers.get("unknown", 3.0))
            
            # Calculate stop loss and take profit distances
            sl_distance = atr * sl_multiplier
            tp_distance = atr * tp_multiplier
            
            # Convert to percentages
            sl_pct = (sl_distance / entry_price) * 100
            tp_pct = (tp_distance / entry_price) * 100
            
            # Calculate prices based on direction
            if direction == "up":
                stop_loss_price = entry_price - sl_distance
                take_profit_price = entry_price + tp_distance
            elif direction == "down":
                stop_loss_price = entry_price + sl_distance
                take_profit_price = entry_price - tp_distance
            else:  # flat
                # For flat predictions, use symmetric stops
                stop_loss_price = entry_price - sl_distance
                take_profit_price = entry_price + tp_distance
            
            # Ensure prices are positive
            stop_loss_price = max(stop_loss_price, entry_price * 0.01)  # Min 1% of entry
            take_profit_price = max(take_profit_price, entry_price * 0.01)
            
            # Calculate risk/reward ratio
            risk = abs(entry_price - stop_loss_price)
            reward = abs(take_profit_price - entry_price)
            risk_reward_ratio = reward / risk if risk > 0 else 0
            
            logger.info(
                f"ATR-based exits for {ticker}: ATR={atr:.4f}, "
                f"SL={stop_loss_price:.4f} (-{sl_pct:.2f}%), "
                f"TP={take_profit_price:.4f} (+{tp_pct:.2f}%), "
                f"R:R={risk_reward_ratio:.2f}"
            )
            
            return {
                "stop_loss_price": stop_loss_price,
                "stop_loss_pct": sl_pct,
                "take_profit_price": take_profit_price,
                "take_profit_pct": tp_pct,
                "risk_reward_ratio": risk_reward_ratio,
                "method": "atr_based",
                "atr_value": atr,
                "atr_multiplier_sl": sl_multiplier,
                "atr_multiplier_tp": tp_multiplier,
            }
            
        except Exception as e:
            logger.error(f"Error calculating ATR-based exits for {ticker}: {e}")
            return {"stop_loss_price": None, "take_profit_price": None}

    def _calculate_atr(self, hist_data, period: int = 14) -> Optional[float]:
        """
        Calculate Average True Range (ATR).
        
        Args:
            hist_data: DataFrame with High, Low, Close columns
            period: ATR period (default 14 days)
            
        Returns:
            ATR value or None if calculation fails
        """
        try:
            # Ensure we have required columns
            if not all(col in hist_data.columns for col in ['High', 'Low', 'Close']):
                logger.warning("Missing required columns for ATR calculation")
                return None
            
            if len(hist_data) < period:
                return None
            
            # Calculate True Range components
            high_low = hist_data['High'] - hist_data['Low']
            high_close = abs(hist_data['High'] - hist_data['Close'].shift())
            low_close = abs(hist_data['Low'] - hist_data['Close'].shift())
            
            # True Range is the maximum of the three
            true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            
            # ATR is the moving average of True Range
            atr = true_range.rolling(window=period).mean().iloc[-1]
            
            return float(atr) if not pd.isna(atr) else None
            
        except Exception as e:
            logger.error(f"Error in ATR calculation: {e}")
            return None

    def _calculate_risk_adjusted_exits(
        self,
        entry_price: float,
        direction: str,
        risk_score: float,
        confidence: float,
        horizon: str,
    ) -> Dict:
        """
        Calculate risk-adjusted stop loss and take profit.
        
        Higher risk = tighter stops, lower risk = wider stops.
        """
        risk_config = self.sl_tp_config.get("risk_adjusted", {})
        
        base_sl_pct = risk_config.get("base_stop_loss_pct", 2.0)
        base_tp_pct = risk_config.get("base_take_profit_pct", 4.0)
        
        # Risk adjustment: High risk = tighter stops (0.5x), Low risk = wider stops (2.0x)
        min_multiplier = risk_config.get("risk_multiplier_min", 0.5)
        max_multiplier = risk_config.get("risk_multiplier_max", 2.0)
        
        # Invert risk score: high risk_score (0.8) -> tight stops (0.7x)
        # Low risk_score (0.2) -> wide stops (1.8x)
        risk_multiplier = max_multiplier - (risk_score * (max_multiplier - min_multiplier))
        
        # Confidence adjustment (optional)
        confidence_adj_enabled = risk_config.get("confidence_adjustment_enabled", True)
        if confidence_adj_enabled:
            confidence_factor = risk_config.get("confidence_adjustment_factor", 0.2)
            # High confidence = slightly wider stops
            confidence_adjustment = 1.0 + (confidence - 0.5) * confidence_factor
            risk_multiplier *= confidence_adjustment
        
        # Calculate adjusted percentages
        sl_pct = base_sl_pct * risk_multiplier
        tp_pct = base_tp_pct * risk_multiplier
        
        # Horizon adjustment - longer horizon = wider stops
        horizon_multipliers = {"1d": 0.7, "5d": 1.0, "20d": 1.5}
        horizon_mult = horizon_multipliers.get(horizon, 1.0)
        sl_pct *= horizon_mult
        tp_pct *= horizon_mult
        
        # Calculate prices based on direction
        sl_distance = entry_price * (sl_pct / 100)
        tp_distance = entry_price * (tp_pct / 100)
        
        if direction == "up":
            stop_loss_price = entry_price - sl_distance
            take_profit_price = entry_price + tp_distance
        elif direction == "down":
            stop_loss_price = entry_price + sl_distance
            take_profit_price = entry_price - tp_distance
        else:  # flat
            stop_loss_price = entry_price - sl_distance
            take_profit_price = entry_price + tp_distance
        
        # Ensure positive prices
        stop_loss_price = max(stop_loss_price, entry_price * 0.01)
        take_profit_price = max(take_profit_price, entry_price * 0.01)
        
        # Calculate risk/reward ratio
        risk = abs(entry_price - stop_loss_price)
        reward = abs(take_profit_price - entry_price)
        risk_reward_ratio = reward / risk if risk > 0 else 0
        
        logger.info(
            f"Risk-adjusted exits: Entry=${entry_price:.4f}, "
            f"Risk={risk_score:.2f}, Conf={confidence:.2f}, "
            f"SL={stop_loss_price:.4f} (-{sl_pct:.2f}%), "
            f"TP={take_profit_price:.4f} (+{tp_pct:.2f}%), "
            f"R:R={risk_reward_ratio:.2f}"
        )
        
        return {
            "stop_loss_price": stop_loss_price,
            "stop_loss_pct": sl_pct,
            "take_profit_price": take_profit_price,
            "take_profit_pct": tp_pct,
            "risk_reward_ratio": risk_reward_ratio,
            "method": "risk_adjusted",
            "risk_multiplier": risk_multiplier,
            "confidence_adjustment": confidence_adjustment if confidence_adj_enabled else 1.0,
        }

    def _calculate_percentage_based_exits(
        self,
        entry_price: float,
        direction: str,
        horizon: str,
    ) -> Dict:
        """
        Calculate simple percentage-based stop loss and take profit.
        
        Fallback method when other methods are unavailable.
        """
        pct_config = self.sl_tp_config.get("percentage_based", {})
        
        # Check for horizon-specific settings
        by_horizon = pct_config.get("by_horizon", {})
        horizon_settings = by_horizon.get(horizon, {})
        
        if horizon_settings:
            sl_pct = horizon_settings.get("stop_loss_pct", 2.0)
            tp_pct = horizon_settings.get("take_profit_pct", 4.0)
        else:
            sl_pct = pct_config.get("default_stop_loss_pct", 2.0)
            tp_pct = pct_config.get("default_take_profit_pct", 4.0)
        
        # Calculate prices
        sl_distance = entry_price * (sl_pct / 100)
        tp_distance = entry_price * (tp_pct / 100)
        
        if direction == "up":
            stop_loss_price = entry_price - sl_distance
            take_profit_price = entry_price + tp_distance
        elif direction == "down":
            stop_loss_price = entry_price + sl_distance
            take_profit_price = entry_price - tp_distance
        else:
            stop_loss_price = entry_price - sl_distance
            take_profit_price = entry_price + tp_distance
        
        # Ensure positive prices
        stop_loss_price = max(stop_loss_price, entry_price * 0.01)
        take_profit_price = max(take_profit_price, entry_price * 0.01)
        
        # Calculate risk/reward ratio
        risk = abs(entry_price - stop_loss_price)
        reward = abs(take_profit_price - entry_price)
        risk_reward_ratio = reward / risk if risk > 0 else 0
        
        return {
            "stop_loss_price": stop_loss_price,
            "stop_loss_pct": sl_pct,
            "take_profit_price": take_profit_price,
            "take_profit_pct": tp_pct,
            "risk_reward_ratio": risk_reward_ratio,
            "method": "percentage_based",
        }

    def _apply_penny_stock_adjustments(self, result: Dict, entry_price: float) -> Dict:
        """
        Apply special adjustments for penny stocks.
        
        Penny stocks need wider stops due to higher volatility and wider spreads.
        """
        penny_config = self.sl_tp_config.get("penny_stock_adjustments", {})
        
        if not penny_config.get("enabled", True):
            return result
        
        is_ultra_penny = self._is_ultra_penny_stock(entry_price)
        
        # Get multiplier
        if is_ultra_penny:
            multiplier = penny_config.get("ultra_penny_multiplier", 2.0)
        else:
            multiplier = penny_config.get("penny_stock_multiplier", 1.5)
        
        # Apply multiplier to percentages
        result["stop_loss_pct"] = result.get("stop_loss_pct", 2.0) * multiplier
        result["take_profit_pct"] = result.get("take_profit_pct", 4.0) * multiplier
        
        # Enforce min/max limits
        min_sl = penny_config.get("min_stop_loss_pct", 5.0)
        max_sl = penny_config.get("max_stop_loss_pct", 15.0)
        
        result["stop_loss_pct"] = max(min_sl, min(max_sl, result["stop_loss_pct"]))
        
        # Recalculate prices
        sl_distance = entry_price * (result["stop_loss_pct"] / 100)
        tp_distance = entry_price * (result["take_profit_pct"] / 100)
        
        # Direction is encoded in the sign of the existing calculation
        if result.get("stop_loss_price", 0) < entry_price:
            # Long position
            result["stop_loss_price"] = entry_price - sl_distance
            result["take_profit_price"] = entry_price + tp_distance
        else:
            # Short position
            result["stop_loss_price"] = entry_price + sl_distance
            result["take_profit_price"] = entry_price - tp_distance
        
        # Recalculate risk/reward
        risk = abs(entry_price - result["stop_loss_price"])
        reward = abs(result["take_profit_price"] - entry_price)
        result["risk_reward_ratio"] = reward / risk if risk > 0 else 0
        
        result["penny_stock_adjusted"] = True
        result["penny_stock_multiplier"] = multiplier
        
        logger.info(
            f"Applied penny stock adjustment: multiplier={multiplier:.1f}x, "
            f"SL={result['stop_loss_pct']:.2f}%, TP={result['take_profit_pct']:.2f}%"
        )
        
        return result

    def _calculate_trailing_stop(
        self,
        entry_price: float,
        direction: str,
        stop_loss_pct: float,
    ) -> Optional[float]:
        """
        Calculate initial trailing stop price.
        
        The trailing stop activates after reaching profit threshold and
        trails the price by a specified distance.
        """
        trailing_config = self.sl_tp_config.get("trailing_stop", {})
        
        if not trailing_config.get("enabled", True):
            return None
        
        trail_distance_pct = trailing_config.get("trail_distance_pct", 1.5)
        trail_distance = entry_price * (trail_distance_pct / 100)
        
        # Initial trailing stop is same as regular stop loss
        # It will adjust dynamically as price moves favorably
        if direction == "up":
            trailing_stop = entry_price - trail_distance
        elif direction == "down":
            trailing_stop = entry_price + trail_distance
        else:
            trailing_stop = entry_price - trail_distance
        
        return max(trailing_stop, entry_price * 0.01)

    def _is_penny_stock(self, price: float) -> bool:
        """Check if stock is a penny stock (< $1.00)."""
        penny_config = self.config.get("penny_stock_handling", {})
        if not penny_config.get("enabled", False):
            return False
        threshold = penny_config.get("price_threshold_usd", 1.0)
        min_valid = penny_config.get("min_valid_price_usd", 0.00001)
        return min_valid < price <= threshold

    def _is_ultra_penny_stock(self, price: float) -> bool:
        """Check if stock is ultra-penny (< $0.001)."""
        penny_config = self.config.get("penny_stock_handling", {})
        if not penny_config.get("enabled", False):
            return False
        ultra_threshold = penny_config.get("ultra_penny_threshold_usd", 0.001)
        min_valid = penny_config.get("min_valid_price_usd", 0.00001)
        return min_valid < price < ultra_threshold

    def _get_empty_exit_strategy(self) -> Dict:
        """Return empty exit strategy when calculation is not possible."""
        return {
            "stop_loss_price": None,
            "stop_loss_pct": None,
            "take_profit_price": None,
            "take_profit_pct": None,
            "risk_reward_ratio": None,
            "trailing_stop_price": None,
            "method": "none",
            "exit_strategy_metadata": {}
        }


# Import pandas here to avoid circular imports
try:
    import pandas as pd
except ImportError:
    logger.warning("pandas not available, ATR calculation will be limited")
    pd = None
