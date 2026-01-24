"""Risk score calculations for trading simulation decisions."""
from dataclasses import dataclass
from typing import Dict, Optional


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    """Clamp a numeric value to a range."""
    return max(low, min(high, value))


def normalize_divergence(divergence_pct: float, max_divergence_pct: float) -> float:
    """Normalize divergence magnitude to 0-1 scale."""
    if max_divergence_pct <= 0:
        return 0.0
    return clamp(abs(divergence_pct) / max_divergence_pct)


def normalize_bps(value_bps: float, max_bps: float) -> float:
    """Normalize basis points magnitude to 0-1 scale."""
    if max_bps <= 0:
        return 0.0
    return clamp(abs(value_bps) / max_bps)


VOLATILITY_RISK_MAP = {
    "low": 0.25,
    "medium": 0.50,
    "high": 0.80,
    "stressed": 0.85,
    "unknown": 0.50,
}


DEFAULT_WEIGHTS = {
    "model_uncertainty": 0.20,
    "divergence_magnitude": 0.20,
    "volatility_regime": 0.15,
    "liquidity_stress": 0.10,
    "regime_instability": 0.10,
    "transaction_cost": 0.10,
    "market_impact": 0.10,
    "correlation_breakdown": 0.05,
}


@dataclass(frozen=True)
class RiskInputs:
    """Inputs required for risk score calculation."""

    model_uncertainty: float
    divergence_pct: float
    volatility_regime: Optional[str] = None
    liquidity_stress: Optional[float] = None
    regime_confidence: Optional[float] = None
    transaction_cost_ratio: Optional[float] = None
    market_impact_bps: Optional[float] = None
    correlation_breakdown: Optional[float] = None


class RiskCalculator:
    """Calculate composite risk scores based on framework components."""

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        max_divergence_pct: float = 10.0,
        max_impact_bps: float = 50.0,
    ):
        self.weights = weights or DEFAULT_WEIGHTS
        self.max_divergence_pct = max_divergence_pct
        self.max_impact_bps = max_impact_bps

    def calculate(self, inputs: RiskInputs) -> Dict:
        """Calculate risk score and component breakdown."""
        volatility_key = (inputs.volatility_regime or "unknown").lower()
        volatility_score = VOLATILITY_RISK_MAP.get(volatility_key, VOLATILITY_RISK_MAP["unknown"])
        regime_confidence = inputs.regime_confidence if inputs.regime_confidence is not None else 0.5

        components = {
            "model_uncertainty": clamp(inputs.model_uncertainty),
            "divergence_magnitude": normalize_divergence(inputs.divergence_pct, self.max_divergence_pct),
            "volatility_regime": clamp(volatility_score),
            "liquidity_stress": clamp(inputs.liquidity_stress if inputs.liquidity_stress is not None else 0.5),
            "regime_instability": clamp(1.0 - clamp(regime_confidence)),
            "transaction_cost": clamp(inputs.transaction_cost_ratio if inputs.transaction_cost_ratio is not None else 0.5),
            "market_impact": normalize_bps(inputs.market_impact_bps or 0.0, self.max_impact_bps),
            "correlation_breakdown": clamp(inputs.correlation_breakdown or 0.0),
        }

        weighted_sum = 0.0
        weight_total = 0.0
        for key, weight in self.weights.items():
            component_value = components.get(key, 0.0)
            weighted_sum += weight * component_value
            weight_total += weight

        risk_score = weighted_sum / weight_total if weight_total > 0 else 0.0
        return {
            "risk_score": float(clamp(risk_score)),
            "components": components,
            "weights": dict(self.weights),
        }
