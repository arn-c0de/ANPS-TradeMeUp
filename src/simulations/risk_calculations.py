"""Risk score calculations for trading simulation decisions."""
from dataclasses import dataclass


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
    "model_uncertainty": 0.18,
    "divergence_magnitude": 0.18,
    "volatility_regime": 0.13,
    "liquidity_stress": 0.10,
    "regime_instability": 0.10,
    "transaction_cost": 0.09,
    "market_impact": 0.09,
    "correlation_breakdown": 0.05,
    "position_concentration": 0.05,
    "liquidity_constraint": 0.03,
}


@dataclass(frozen=True)
class RiskInputs:
    """Inputs required for risk score calculation."""

    model_uncertainty: float
    divergence_pct: float
    volatility_regime: str | None = None
    liquidity_stress: float | None = None
    regime_confidence: float | None = None
    transaction_cost_ratio: float | None = None
    market_impact_bps: float | None = None
    correlation_breakdown: float | None = None
    position_size_pct: float | None = None
    daily_volume_usd: float | None = None


class RiskCalculator:
    """Calculate composite risk scores based on framework components."""

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        max_divergence_pct: float = 10.0,
        max_impact_bps: float = 50.0,
    ):
        self.weights = weights or DEFAULT_WEIGHTS
        self.max_divergence_pct = max_divergence_pct
        self.max_impact_bps = max_impact_bps

    def calculate(self, inputs: RiskInputs) -> dict:
        """Calculate risk score and component breakdown."""
        volatility_key = (inputs.volatility_regime or "unknown").lower()
        volatility_score = VOLATILITY_RISK_MAP.get(volatility_key, VOLATILITY_RISK_MAP["unknown"])
        regime_confidence = inputs.regime_confidence if inputs.regime_confidence is not None else 0.5

        # Handle None divergence_pct gracefully (when actual return unavailable)
        divergence_pct = inputs.divergence_pct if inputs.divergence_pct is not None else 0.0

        # Calculate position concentration risk
        position_concentration = self._calculate_position_concentration(inputs.position_size_pct)

        # Calculate liquidity constraint risk
        liquidity_constraint = self._calculate_liquidity_constraint(inputs.daily_volume_usd)

        components = {
            "model_uncertainty": clamp(inputs.model_uncertainty),
            "divergence_magnitude": normalize_divergence(divergence_pct, self.max_divergence_pct),
            "volatility_regime": clamp(volatility_score),
            "liquidity_stress": clamp(inputs.liquidity_stress if inputs.liquidity_stress is not None else 0.5),
            "regime_instability": clamp(1.0 - clamp(regime_confidence)),
            "transaction_cost": clamp(inputs.transaction_cost_ratio if inputs.transaction_cost_ratio is not None else 0.5),
            "market_impact": normalize_bps(inputs.market_impact_bps or 0.0, self.max_impact_bps),
            "correlation_breakdown": clamp(inputs.correlation_breakdown or 0.0),
            "position_concentration": position_concentration,
            "liquidity_constraint": liquidity_constraint,
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

    def _calculate_position_concentration(self, position_size_pct: float | None) -> float:
        """
        Calculate risk from position size concentration.

        Risk increases exponentially as position size approaches max threshold.
        0-5%: Low risk (0.0-0.3)
        5-10%: Medium risk (0.3-0.7)
        10%+: High risk (0.7-1.0)
        """
        if position_size_pct is None or position_size_pct <= 0:
            return 0.0

        # Exponential scaling: risk = (position_pct / 10) ^ 1.5
        # This penalizes large positions more heavily
        risk = min((position_size_pct / 10.0) ** 1.5, 1.0)
        return clamp(risk)

    def _calculate_liquidity_constraint(self, daily_volume_usd: float | None) -> float:
        """
        Calculate risk from liquidity constraints.

        Higher risk for lower liquidity stocks:
        $10M+: Low risk (0.0-0.2)
        $1M-$10M: Medium risk (0.2-0.5)
        $100k-$1M: High risk (0.5-0.8)
        <$100k: Very high risk (0.8-1.0)
        """
        if daily_volume_usd is None or daily_volume_usd <= 0:
            # No volume data = assume moderate risk
            return 0.5

        # Logarithmic scaling for liquidity
        # High volume = low risk, low volume = high risk
        if daily_volume_usd >= 10_000_000:  # $10M+
            return 0.1
        elif daily_volume_usd >= 1_000_000:  # $1M-$10M
            # Scale from 0.2 to 0.5
            normalized = (10_000_000 - daily_volume_usd) / 9_000_000
            return clamp(0.2 + normalized * 0.3)
        elif daily_volume_usd >= 100_000:  # $100k-$1M
            # Scale from 0.5 to 0.8
            normalized = (1_000_000 - daily_volume_usd) / 900_000
            return clamp(0.5 + normalized * 0.3)
        else:  # <$100k
            # Very high risk
            return 0.9
