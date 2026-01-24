"""Agent 8.5: Trading Simulation Agent - Evaluate predictions vs market."""
import logging
from typing import Dict

from src.simulations.trading_simulator import TradingSimulationEngine

logger = logging.getLogger(__name__)


class TradingSimulationAgent:
    """Run trading simulations after predictions to create trade decisions."""

    def __init__(self):
        self.engine = TradingSimulationEngine()

    def process_batch(self, limit: int = 50, lookback_days: int = 7) -> Dict:
        """Process recent predictions into simulation decisions."""
        stats = self.engine.process_batch(limit=limit, lookback_days=lookback_days)
        logger.info(f"Trading simulation stats: {stats}")
        return stats

    def get_statistics(self) -> Dict:
        """Get overall simulation statistics."""
        return self.engine.get_statistics()

    def delete_simulation(self, simulation_id: str) -> bool:
        """Delete a simulation by ID."""
        return self.engine.delete_simulation(simulation_id)

    def refresh_simulation(self, simulation_id: str) -> bool:
        """Refresh/recalculate a simulation by ID."""
        return self.engine.refresh_simulation(simulation_id)

    def create_simulations(
        self,
        entity_filter=None,
        horizon_filter=None,
        date_range=None,
        limit: int = 100,
    ) -> Dict:
        """Create simulations from predictions with filters."""
        return self.engine.create_simulations_from_predictions(
            entity_filter=entity_filter,
            horizon_filter=horizon_filter,
            date_range=date_range,
            limit=limit,
        )
