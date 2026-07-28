"""Agent 7.5: Scenario Generation Agent - Generate market scenarios and stress tests."""
import logging
from datetime import UTC, datetime, timezone
from typing import Dict, List

from sqlalchemy.orm import Session

from src.models.analysis import MarketRegime

logger = logging.getLogger(__name__)


class ScenarioGenerationAgent:
    """
    Agent 7.5: Scenario Generation Agent

    Responsibilities:
    - Generate plausible market scenarios
    - Stress test predictions under different conditions
    - Create "what-if" analyses
    - Simulate regime changes
    """

    # Predefined scenarios
    SCENARIOS = {
        'market_crash': {
            'name': 'Market Crash (-20%)',
            'vix_multiplier': 3.0,
            'market_return': -0.20,
            'volatility_regime': 'high',
            'risk_appetite': 'fear'
        },
        'correction': {
            'name': 'Correction (-10%)',
            'vix_multiplier': 2.0,
            'market_return': -0.10,
            'volatility_regime': 'medium',
            'risk_appetite': 'cautious'
        },
        'bull_market': {
            'name': 'Strong Bull Market (+15%)',
            'vix_multiplier': 0.6,
            'market_return': 0.15,
            'volatility_regime': 'low',
            'risk_appetite': 'greedy'
        },
        'volatility_spike': {
            'name': 'Volatility Spike (VIX +50%)',
            'vix_multiplier': 1.5,
            'market_return': 0.0,
            'volatility_regime': 'high',
            'risk_appetite': 'neutral'
        },
        'sector_rotation': {
            'name': 'Sector Rotation',
            'vix_multiplier': 1.2,
            'market_return': 0.02,
            'volatility_regime': 'medium',
            'risk_appetite': 'neutral'
        }
    }

    def __init__(self, db: Session):
        """Initialize scenario generation agent."""
        self.db = db

    def generate_scenario(self, scenario_type: str) -> dict:
        """
        Generate a specific market scenario.

        Args:
            scenario_type: Type of scenario to generate

        Returns:
            Scenario parameters
        """
        if scenario_type not in self.SCENARIOS:
            raise ValueError(f"Unknown scenario type: {scenario_type}")

        scenario = self.SCENARIOS[scenario_type].copy()
        scenario['generated_at'] = datetime.now(UTC).isoformat()
        scenario['scenario_id'] = f"{scenario_type}_{datetime.now(UTC).timestamp()}"

        logger.info(f"Generated scenario: {scenario['name']}")

        return scenario

    def stress_test_prediction(
        self,
        base_prediction: float,
        scenario_type: str,
        entity_type: str = 'company'
    ) -> dict:
        """
        Stress test a prediction under a scenario.

        Args:
            base_prediction: Base case return prediction
            scenario_type: Scenario to apply
            entity_type: Type of entity (company, sector)

        Returns:
            Adjusted prediction with stress test results
        """
        scenario = self.generate_scenario(scenario_type)

        # Adjust prediction based on scenario
        market_beta = 1.0  # Assume market beta of 1.0
        market_impact = scenario['market_return'] * market_beta

        # Add scenario-specific adjustments
        vol_impact = (scenario['vix_multiplier'] - 1.0) * 0.1  # Volatility impact

        stressed_prediction = base_prediction + market_impact + vol_impact

        return {
            'scenario_name': scenario['name'],
            'scenario_type': scenario_type,
            'base_prediction': base_prediction,
            'stressed_prediction': stressed_prediction,
            'impact': stressed_prediction - base_prediction,
            'scenario_params': scenario
        }

    def run_monte_carlo_scenarios(
        self,
        base_prediction: float,
        n_simulations: int = 1000
    ) -> dict:
        """
        Run Monte Carlo simulations for prediction uncertainty.

        Args:
            base_prediction: Base prediction
            n_simulations: Number of simulations

        Returns:
            Simulation results
        """
        import numpy as np

        # Generate random market scenarios
        simulations = []

        for _ in range(n_simulations):
            # Random market return (normal distribution)
            market_return = np.random.normal(0.0, 0.02)  # 2% daily vol

            # Random volatility multiplier
            vol_mult = np.random.lognormal(0, 0.3)

            simulated_return = base_prediction + market_return * vol_mult

            simulations.append(simulated_return)

        simulations = np.array(simulations)

        return {
            'base_prediction': base_prediction,
            'mean_simulation': float(np.mean(simulations)),
            'median_simulation': float(np.median(simulations)),
            'std_simulation': float(np.std(simulations)),
            'percentile_5': float(np.percentile(simulations, 5)),
            'percentile_25': float(np.percentile(simulations, 25)),
            'percentile_75': float(np.percentile(simulations, 75)),
            'percentile_95': float(np.percentile(simulations, 95)),
            'n_simulations': n_simulations
        }

    def generate_regime_scenarios(self) -> list[dict]:
        """
        Generate scenarios for different market regimes.

        Returns:
            List of regime scenarios
        """
        regime_scenarios = []

        for scenario_type, params in self.SCENARIOS.items():
            regime = {
                'volatility': params['volatility_regime'],
                'trend': 'bull' if params['market_return'] > 0.05 else 'bear' if params['market_return'] < -0.05 else 'sideways',
                'risk_appetite': params['risk_appetite']
            }

            regime_scenarios.append({
                'scenario_name': params['name'],
                'scenario_type': scenario_type,
                'regime': regime,
                'probability': 0.2  # Equal probability for simplicity
            })

        return regime_scenarios

    def process_batch(self, limit: int = 5) -> dict:
        """
        Generate scenarios for analysis.

        Args:
            limit: Number of scenarios to generate

        Returns:
            Statistics
        """
        logger.info("Generating market scenarios")

        stats = {
            'scenarios_generated': 0,
            'scenarios': []
        }

        for scenario_type in list(self.SCENARIOS.keys())[:limit]:
            try:
                scenario = self.generate_scenario(scenario_type)
                stats['scenarios'].append(scenario)
                stats['scenarios_generated'] += 1

            except Exception as e:
                logger.error(f"Error generating scenario {scenario_type}: {e}")

        logger.info(f"Scenario generation complete. Stats: {stats}")
        return stats

    def get_statistics(self) -> dict:
        """Get scenario generation statistics."""
        return {
            'available_scenarios': len(self.SCENARIOS),
            'scenario_types': list(self.SCENARIOS.keys())
        }
