"""Trading simulation engine that converts predictions into trade decisions."""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging

from sqlalchemy.orm import Session

from src.models.database import get_scoped_session
from src.models.predictions import Prediction
from src.models.entities import Entity
from src.models.analysis import MarketRegime
from src.models.trading_simulation import TradingSimulation
from src.services.prediction_performance_service import PredictionPerformanceService
from src.gui.tabs.charts.market_data import MarketDataProvider
from src.simulations.risk_calculations import RiskCalculator, RiskInputs

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
        market_data_provider: Optional[MarketDataProvider] = None,
        performance_service: Optional[PredictionPerformanceService] = None,
        risk_calculator: Optional[RiskCalculator] = None,
    ):
        self.market_data_provider = market_data_provider or MarketDataProvider()
        self.performance_service = performance_service or PredictionPerformanceService()
        self.risk_calculator = risk_calculator or RiskCalculator()
        self._market_cache: Dict[str, Dict] = {}
        self._market_cache_ttl = timedelta(minutes=10)

    def _get_expected_return_pct(self, prediction: Prediction) -> float:
        expected_return = prediction.expected_return or {}
        mean_value = expected_return.get("mean", 0.0) if isinstance(expected_return, dict) else 0.0
        # Heuristic: if value is in [-1, 1], treat as fraction and convert to percent.
        return float(mean_value * 100.0) if abs(mean_value) <= 1.0 else float(mean_value)

    def _get_predicted_direction(self, prediction: Prediction) -> str:
        probabilities = prediction.direction_probabilities or {}
        if not probabilities:
            return "flat"
        return max(probabilities, key=probabilities.get)

    def _get_latest_regime(self, db: Session) -> Optional[MarketRegime]:
        return db.query(MarketRegime).order_by(MarketRegime.created_at.desc()).first()

    def _regime_liquidity_stress(self, regime: Optional[MarketRegime]) -> float:
        if not regime or not isinstance(regime.regime, dict):
            return 0.5
        liquidity = (regime.regime.get("liquidity") or "normal").lower()
        if liquidity == "stressed":
            return 0.8
        if liquidity == "abundant":
            return 0.2
        return 0.5

    def _estimate_costs_bps(
        self,
        price: float,
        volatility_regime: str,
        shares: int = DEFAULT_SHARES,
    ) -> Tuple[float, Dict]:
        if price <= 0:
            return 0.0, {}

        commission_per_share = 0.005
        commission = commission_per_share * shares
        commission_bps = (commission / (price * shares)) * 10000

        vol_key = (volatility_regime or "medium").lower()
        spread_bps = 4.0 if vol_key == "low" else 8.0 if vol_key == "medium" else 12.0
        slippage_bps = 5.0 if vol_key != "high" else 9.0

        impact_bps = 6.0 if shares <= 100 else 12.0

        total_bps = commission_bps + spread_bps + slippage_bps + impact_bps
        breakdown = {
            "commission_bps": commission_bps,
            "spread_bps": spread_bps,
            "slippage_bps": slippage_bps,
            "market_impact_bps": impact_bps,
            "total_bps": total_bps,
        }
        return total_bps, breakdown

    def _get_market_snapshot(self, ticker: str) -> Optional[Dict]:
        now = datetime.utcnow()
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
    ) -> str:
        if confidence < self.MIN_CONFIDENCE:
            return "hold"
        if abs(expected_return_pct) < self.MIN_EXPECTED_RETURN_PCT:
            return "hold"
        if risk_score > self.MAX_RISK_SCORE:
            return "hold"
        if cost_ratio > self.MAX_COST_RATIO:
            return "hold"

        if predicted_direction == "up" and expected_return_pct > 0:
            return "buy"
        if predicted_direction == "down" and expected_return_pct < 0:
            return "sell"
        return "hold"

    def simulate_prediction(
        self,
        db: Session,
        prediction: Prediction,
        entity: Entity,
    ) -> Optional[TradingSimulation]:
        if not prediction or not entity:
            return None

        existing = db.query(TradingSimulation).filter(
            TradingSimulation.prediction_id == prediction.prediction_id
        ).first()

        predicted_direction = self._get_predicted_direction(prediction)
        expected_return_pct = self._get_expected_return_pct(prediction)
        confidence = prediction.calibrated_confidence or prediction.confidence or 0.0

        performance = self.performance_service.get_prediction_performance(prediction, entity)
        actual_return_pct = performance.get("total_return_pct") if performance else None
        divergence_pct = None
        if actual_return_pct is not None:
            divergence_pct = expected_return_pct - actual_return_pct
        else:
            divergence_pct = expected_return_pct

        regime = self._get_latest_regime(db)
        volatility_regime = None
        regime_confidence = None
        if regime:
            volatility_regime = (regime.regime or {}).get("volatility")
            regime_confidence = (regime.regime_probabilities or {}).get("current_regime_confidence")

        market_snapshot = self._get_market_snapshot(entity.entity_id)
        price = market_snapshot.get("price") if market_snapshot else 0.0
        total_cost_bps, cost_breakdown = self._estimate_costs_bps(price, volatility_regime)
        expected_return_bps = abs(expected_return_pct) * 100.0
        cost_ratio = total_cost_bps / expected_return_bps if expected_return_bps > 0 else 1.0

        risk_inputs = RiskInputs(
            model_uncertainty=1.0 - min(max(confidence, 0.0), 1.0),
            divergence_pct=divergence_pct,
            volatility_regime=volatility_regime,
            liquidity_stress=self._regime_liquidity_stress(regime),
            regime_confidence=regime_confidence,
            transaction_cost_ratio=min(max(cost_ratio, 0.0), 1.0),
            market_impact_bps=cost_breakdown.get("market_impact_bps", 0.0),
            correlation_breakdown=None,
        )
        risk_result = self.risk_calculator.calculate(risk_inputs)

        decision = self._calculate_decision(
            predicted_direction=predicted_direction,
            expected_return_pct=expected_return_pct,
            confidence=confidence,
            risk_score=risk_result["risk_score"],
            cost_ratio=cost_ratio,
        )

        simulation_payload = {
            "predicted_direction": predicted_direction,
            "actual_direction": performance.get("actual_direction") if performance else None,
            "strategy_result": performance.get("strategy_result") if performance else None,
            "market_snapshot": {
                "price": price,
                "change_percent": market_snapshot.get("change_percent") if market_snapshot else None,
                "timestamp": market_snapshot.get("timestamp").isoformat() if market_snapshot else None,
            },
        }

        if existing:
            existing.decision = decision
            existing.expected_return_pct = expected_return_pct
            existing.actual_return_pct = actual_return_pct
            existing.divergence_pct = divergence_pct
            existing.risk_score = risk_result["risk_score"]
            existing.confidence = prediction.confidence
            existing.calibrated_confidence = prediction.calibrated_confidence
            existing.transaction_cost_bps = total_cost_bps
            existing.cost_breakdown = cost_breakdown
            existing.risk_breakdown = risk_result["components"]
            existing.simulation_metadata = simulation_payload
            existing.created_at = datetime.utcnow()
            return existing

        simulation = TradingSimulation(
            prediction_id=prediction.prediction_id,
            entity_id=prediction.entity_id,
            horizon=prediction.horizon,
            decision=decision,
            expected_return_pct=expected_return_pct,
            actual_return_pct=actual_return_pct,
            divergence_pct=divergence_pct,
            risk_score=risk_result["risk_score"],
            confidence=prediction.confidence,
            calibrated_confidence=prediction.calibrated_confidence,
            transaction_cost_bps=total_cost_bps,
            cost_breakdown=cost_breakdown,
            risk_breakdown=risk_result["components"],
            simulation_metadata=simulation_payload,
            created_at=datetime.utcnow(),
        )
        db.add(simulation)
        return simulation

    def process_batch(self, limit: int = 50, lookback_days: int = 7) -> Dict:
        """Simulate trades for recent predictions."""
        cutoff = datetime.utcnow() - timedelta(days=lookback_days)
        stats = {
            "processed": 0,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
        }

        with get_scoped_session() as db:
            predictions = db.query(Prediction).filter(
                Prediction.created_at >= cutoff
            ).order_by(Prediction.created_at.desc()).limit(limit).all()

            if not predictions:
                return stats

            for prediction in predictions:
                try:
                    entity = db.query(Entity).filter(
                        Entity.entity_id == prediction.entity_id
                    ).first()
                    if not entity:
                        stats["skipped"] += 1
                        continue

                    existing = db.query(TradingSimulation).filter(
                        TradingSimulation.prediction_id == prediction.prediction_id
                    ).first()

                    simulation = self.simulate_prediction(db, prediction, entity)
                    if not simulation:
                        stats["skipped"] += 1
                        continue

                    stats["processed"] += 1
                    if existing:
                        stats["updated"] += 1
                    else:
                        stats["created"] += 1
                except Exception as e:
                    logger.error(f"Error simulating prediction {prediction.prediction_id}: {e}")
                    stats["errors"] += 1

        return stats

    def get_statistics(self) -> Dict:
        """Get simulation statistics."""
        with get_scoped_session() as db:
            total = db.query(TradingSimulation).count()
            buys = db.query(TradingSimulation).filter(TradingSimulation.decision == "buy").count()
            sells = db.query(TradingSimulation).filter(TradingSimulation.decision == "sell").count()
            holds = db.query(TradingSimulation).filter(TradingSimulation.decision == "hold").count()

            return {
                "total_simulations": total,
                "buys": buys,
                "sells": sells,
                "holds": holds,
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
        prediction_ids: Optional[List[str]] = None,
        entity_filter: Optional[List[str]] = None,
        horizon_filter: Optional[str] = None,
        date_range: Optional[Tuple[datetime, datetime]] = None,
        limit: int = 100,
    ) -> Dict:
        """Create simulations from specific predictions or filters."""
        stats = {
            "processed": 0,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
        }

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
                return stats

            for prediction in predictions:
                try:
                    entity = db.query(Entity).filter(
                        Entity.entity_id == prediction.entity_id
                    ).first()
                    if not entity:
                        logger.warning(f"Entity not found for prediction {prediction.prediction_id}, entity_id: {prediction.entity_id}")
                        stats["skipped"] += 1
                        continue

                    existing = db.query(TradingSimulation).filter(
                        TradingSimulation.prediction_id == prediction.prediction_id
                    ).first()

                    simulation = self.simulate_prediction(db, prediction, entity)
                    if not simulation:
                        logger.debug(f"Simulation skipped for prediction {prediction.prediction_id}")
                        stats["skipped"] += 1
                        continue

                    stats["processed"] += 1
                    if existing:
                        stats["updated"] += 1
                        logger.debug(f"Updated simulation for prediction {prediction.prediction_id}")
                    else:
                        stats["created"] += 1
                        logger.debug(f"Created simulation for prediction {prediction.prediction_id}")
                except Exception as e:
                    logger.error(f"Error simulating prediction {prediction.prediction_id}: {e}", exc_info=True)
                    stats["errors"] += 1

            db.commit()

        return stats
