"""Portfolio-level risk aggregation and analysis."""
from dataclasses import dataclass
from typing import Dict, List, Optional
import logging
import numpy as np
from datetime import datetime

from sqlalchemy.orm import Session
from src.models.trading_simulation import TradingSimulation
from src.models.entities import Entity

logger = logging.getLogger(__name__)


@dataclass
class PortfolioRiskMetrics:
    """Portfolio-level risk metrics."""

    total_exposure_usd: float
    total_positions: int
    active_buy_positions: int
    active_sell_positions: int
    avg_risk_score: float
    max_risk_score: float
    portfolio_var_95: float
    portfolio_cvar_95: float
    total_leverage: float
    sector_concentrations: Dict[str, float]
    position_size_violations: int
    liquidity_violations: int
    high_risk_positions: List[str]


class PortfolioRiskCalculator:
    """Calculate portfolio-level risk metrics aggregating individual simulations."""

    def __init__(self, assumed_portfolio_value: float = 100000):
        """
        Initialize portfolio risk calculator.

        Args:
            assumed_portfolio_value: Total portfolio value in USD for position sizing calculations
        """
        self.portfolio_value = assumed_portfolio_value

    def calculate_portfolio_risk(
        self,
        db: Session,
        active_only: bool = True,
        min_confidence: float = 0.0,
        horizon_filter: Optional[str] = None
    ) -> PortfolioRiskMetrics:
        """
        Calculate comprehensive portfolio risk metrics.

        Args:
            db: Database session
            active_only: Only include BUY/SELL decisions (exclude HOLD)
            min_confidence: Minimum confidence threshold
            horizon_filter: Optional horizon filter (1d, 5d, 20d)

        Returns:
            PortfolioRiskMetrics with aggregated risk data
        """
        # Query simulations
        query = db.query(TradingSimulation)

        if active_only:
            query = query.filter(TradingSimulation.decision.in_(["buy", "sell"]))

        if horizon_filter:
            query = query.filter(TradingSimulation.horizon == horizon_filter)

        if min_confidence > 0:
            query = query.filter(TradingSimulation.confidence >= min_confidence)

        simulations = query.all()

        if not simulations:
            return self._empty_metrics()

        # Calculate aggregated metrics
        total_positions = len(simulations)
        buy_positions = sum(1 for s in simulations if s.decision == "buy")
        sell_positions = sum(1 for s in simulations if s.decision == "sell")

        # Risk scores
        risk_scores = [s.risk_score for s in simulations if s.risk_score is not None]
        avg_risk = np.mean(risk_scores) if risk_scores else 0.0
        max_risk = max(risk_scores) if risk_scores else 0.0

        # Expected returns for VaR calculation
        expected_returns = [s.expected_return_pct for s in simulations if s.expected_return_pct is not None]
        var_95, cvar_95 = self._calculate_var_cvar(expected_returns)

        # Exposure and leverage
        total_exposure = self._calculate_total_exposure(simulations)
        total_leverage = total_exposure / self.portfolio_value if self.portfolio_value > 0 else 0.0

        # Sector concentrations
        sector_concentrations = self._calculate_sector_concentrations(db, simulations)

        # Violations
        position_violations = self._count_position_violations(simulations)
        liquidity_violations = self._count_liquidity_violations(simulations)

        # High risk positions
        high_risk_positions = [
            s.entity_id
            for s in simulations
            if s.risk_score and s.risk_score > 0.7
        ]

        return PortfolioRiskMetrics(
            total_exposure_usd=total_exposure,
            total_positions=total_positions,
            active_buy_positions=buy_positions,
            active_sell_positions=sell_positions,
            avg_risk_score=float(avg_risk),
            max_risk_score=float(max_risk),
            portfolio_var_95=var_95,
            portfolio_cvar_95=cvar_95,
            total_leverage=total_leverage,
            sector_concentrations=sector_concentrations,
            position_size_violations=position_violations,
            liquidity_violations=liquidity_violations,
            high_risk_positions=high_risk_positions
        )

    def _empty_metrics(self) -> PortfolioRiskMetrics:
        """Return empty metrics when no simulations found."""
        return PortfolioRiskMetrics(
            total_exposure_usd=0.0,
            total_positions=0,
            active_buy_positions=0,
            active_sell_positions=0,
            avg_risk_score=0.0,
            max_risk_score=0.0,
            portfolio_var_95=0.0,
            portfolio_cvar_95=0.0,
            total_leverage=0.0,
            sector_concentrations={},
            position_size_violations=0,
            liquidity_violations=0,
            high_risk_positions=[]
        )

    def _calculate_var_cvar(
        self,
        returns: List[float],
        confidence_level: float = 0.95
    ) -> tuple[float, float]:
        """
        Calculate Value at Risk (VaR) and Conditional VaR (CVaR) at specified confidence level.

        VaR: Maximum expected loss at given confidence level
        CVaR: Average loss in worst (1-confidence_level)% of scenarios

        Args:
            returns: List of expected returns (percentages)
            confidence_level: Confidence level (default 95%)

        Returns:
            Tuple of (VaR, CVaR)
        """
        if not returns or len(returns) < 2:
            return 0.0, 0.0

        returns_array = np.array(returns)

        # VaR: percentile at (1 - confidence_level)
        var = np.percentile(returns_array, (1 - confidence_level) * 100)

        # CVaR: mean of returns below VaR threshold
        tail_returns = returns_array[returns_array <= var]
        cvar = np.mean(tail_returns) if len(tail_returns) > 0 else var

        return float(var), float(cvar)

    def _calculate_total_exposure(self, simulations: List[TradingSimulation]) -> float:
        """
        Calculate total portfolio exposure in USD.

        Assumes DEFAULT_SHARES (100) per position and extracts price from simulation_metadata.
        """
        from src.simulations.trading_simulator import TradingSimulationEngine

        total_exposure = 0.0
        default_shares = TradingSimulationEngine.DEFAULT_SHARES

        for sim in simulations:
            if sim.decision not in ["buy", "sell"]:
                continue

            metadata = sim.simulation_metadata or {}
            market_snapshot = metadata.get("market_snapshot", {})
            price = market_snapshot.get("price", 0.0)

            if price > 0:
                position_value = price * default_shares
                total_exposure += position_value

        return total_exposure

    def _calculate_sector_concentrations(
        self,
        db: Session,
        simulations: List[TradingSimulation]
    ) -> Dict[str, float]:
        """
        Calculate sector concentration as percentage of total exposure.

        Returns dict mapping sector -> percentage of total exposure
        """
        from src.simulations.trading_simulator import TradingSimulationEngine

        sector_exposure = {}
        total_exposure = 0.0
        default_shares = TradingSimulationEngine.DEFAULT_SHARES

        for sim in simulations:
            if sim.decision not in ["buy", "sell"]:
                continue

            # Get entity to determine sector
            entity = db.query(Entity).filter(Entity.entity_id == sim.entity_id).first()
            if not entity:
                continue

            sector = entity.metadata.get("sector", "Unknown") if entity.metadata else "Unknown"

            # Calculate position value
            metadata = sim.simulation_metadata or {}
            market_snapshot = metadata.get("market_snapshot", {})
            price = market_snapshot.get("price", 0.0)

            if price > 0:
                position_value = price * default_shares
                sector_exposure[sector] = sector_exposure.get(sector, 0.0) + position_value
                total_exposure += position_value

        # Convert to percentages
        if total_exposure > 0:
            return {
                sector: (exposure / total_exposure) * 100
                for sector, exposure in sector_exposure.items()
            }
        return {}

    def _count_position_violations(self, simulations: List[TradingSimulation]) -> int:
        """Count simulations that violate position size constraints."""
        violations = 0

        for sim in simulations:
            metadata = sim.simulation_metadata or {}
            constraints = metadata.get("constraints", {})

            if not constraints.get("position_size_ok", True):
                violations += 1

        return violations

    def _count_liquidity_violations(self, simulations: List[TradingSimulation]) -> int:
        """Count simulations that violate liquidity constraints."""
        violations = 0

        for sim in simulations:
            metadata = sim.simulation_metadata or {}
            constraints = metadata.get("constraints", {})

            if not constraints.get("liquidity_ok", True):
                violations += 1

        return violations
