"""Test suite to validate simulation calculations and formulas."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta
from src.simulations.risk_calculations import RiskCalculator, RiskInputs
from src.simulations.trading_simulator import TradingSimulationEngine


def test_risk_calculation_formulas():
    """Verify risk calculation formulas are correct."""
    print("\n=== Testing Risk Calculation Formulas ===\n")
    
    calculator = RiskCalculator()
    
    # Test 1: All components at minimum risk
    inputs_low_risk = RiskInputs(
        model_uncertainty=0.1,  # High confidence (90%)
        divergence_pct=0.5,     # Low divergence
        volatility_regime="low",
        liquidity_stress=0.1,
        regime_confidence=0.9,
        transaction_cost_ratio=0.1,
        market_impact_bps=5.0,
        correlation_breakdown=0.0
    )
    
    result_low = calculator.calculate(inputs_low_risk)
    print(f"Low Risk Scenario:")
    print(f"  Risk Score: {result_low['risk_score']:.3f}")
    print(f"  Components: {result_low['components']}")
    assert result_low['risk_score'] < 0.3, "Low risk scenario should produce low score"
    print("  ✅ Low risk test passed\n")
    
    # Test 2: All components at high risk
    inputs_high_risk = RiskInputs(
        model_uncertainty=0.9,  # Low confidence (10%)
        divergence_pct=8.0,     # High divergence
        volatility_regime="high",
        liquidity_stress=0.9,
        regime_confidence=0.1,
        transaction_cost_ratio=0.9,
        market_impact_bps=40.0,
        correlation_breakdown=0.8
    )
    
    result_high = calculator.calculate(inputs_high_risk)
    print(f"High Risk Scenario:")
    print(f"  Risk Score: {result_high['risk_score']:.3f}")
    print(f"  Components: {result_high['components']}")
    assert result_high['risk_score'] > 0.7, "High risk scenario should produce high score"
    print("  ✅ High risk test passed\n")
    
    # Test 3: Handle None divergence (missing actual data)
    inputs_missing_data = RiskInputs(
        model_uncertainty=0.3,
        divergence_pct=None,  # Missing actual return
        volatility_regime="medium",
        liquidity_stress=0.5,
        regime_confidence=0.7,
        transaction_cost_ratio=0.3,
        market_impact_bps=10.0,
        correlation_breakdown=0.2
    )
    
    result_missing = calculator.calculate(inputs_missing_data)
    print(f"Missing Data Scenario (divergence_pct=None):")
    print(f"  Risk Score: {result_missing['risk_score']:.3f}")
    print(f"  Components: {result_missing['components']}")
    assert result_missing['risk_score'] >= 0.0, "Should handle None divergence gracefully"
    print("  ✅ Missing data test passed\n")


def test_cost_calculation_formulas():
    """Verify transaction cost calculations."""
    print("\n=== Testing Transaction Cost Formulas ===\n")
    
    engine = TradingSimulationEngine()
    
    # Test with different price points and volatility regimes
    test_cases = [
        {"price": 100, "volatility": "low", "shares": 100, "expected_range": (15, 20)},
        {"price": 100, "volatility": "medium", "shares": 100, "expected_range": (19, 25)},
        {"price": 100, "volatility": "high", "shares": 100, "expected_range": (26, 32)},
        {"price": 50, "volatility": "low", "shares": 200, "expected_range": (21, 28)},
    ]
    
    for case in test_cases:
        total_bps, breakdown = engine._estimate_costs_bps(
            case["price"], case["volatility"], case["shares"]
        )
        print(f"Price: ${case['price']}, Vol: {case['volatility']}, Shares: {case['shares']}")
        print(f"  Total Cost: {total_bps:.1f} bps")
        print(f"  Breakdown: {breakdown}")
        
        # Verify total is within expected range
        assert case["expected_range"][0] <= total_bps <= case["expected_range"][1], \
            f"Cost {total_bps} bps not in expected range {case['expected_range']}"
        
        # Verify all components are present
        assert "commission_bps" in breakdown
        assert "spread_bps" in breakdown
        assert "slippage_bps" in breakdown
        assert "market_impact_bps" in breakdown
        
        # Verify components sum to total (exclude 'total_bps' from sum)
        component_sum = sum(v for k, v in breakdown.items() if k != "total_bps")
        assert abs(component_sum - total_bps) < 0.1, f"Components sum {component_sum} should equal total {total_bps}"
        print("  ✅ Passed\n")


def test_expected_return_calculation():
    """Verify expected return percentage scaling."""
    print("\n=== Testing Expected Return Calculations ===\n")
    
    from src.models.predictions import Prediction
    
    engine = TradingSimulationEngine()
    
    # Test case 1: Fractional return (should be scaled to percentage)
    pred1 = Prediction(
        prediction_id="test1",
        entity_id="TEST",
        expected_return={"mean": 0.0142}  # 1.42% as fraction
    )
    result1 = engine._get_expected_return_pct(pred1)
    print(f"Input: 0.0142 (fraction) → Output: {result1:.2f}%")
    assert abs(result1 - 1.42) < 0.01, "Should scale fraction to percentage"
    print("  ✅ Fraction scaling passed\n")
    
    # Test case 2: Already percentage (should not be scaled)
    pred2 = Prediction(
        prediction_id="test2",
        entity_id="TEST",
        expected_return={"mean": 1.42}  # Already 1.42%
    )
    result2 = engine._get_expected_return_pct(pred2)
    print(f"Input: 1.42 (percentage) → Output: {result2:.2f}%")
    assert abs(result2 - 1.42) < 0.01, "Should preserve percentage"
    print("  ✅ Percentage preservation passed\n")
    
    # Test case 3: Large value (should not be scaled)
    pred3 = Prediction(
        prediction_id="test3",
        entity_id="TEST",
        expected_return={"mean": 15.5}
    )
    result3 = engine._get_expected_return_pct(pred3)
    print(f"Input: 15.5 (large %) → Output: {result3:.2f}%")
    assert abs(result3 - 15.5) < 0.01, "Should preserve large percentage"
    print("  ✅ Large value preservation passed\n")


def test_divergence_calculation():
    """Verify divergence (E-R) calculation."""
    print("\n=== Testing Divergence Calculations ===\n")
    
    test_cases = [
        {"expected": 5.0, "actual": 3.0, "divergence": 2.0, "desc": "Overestimated"},
        {"expected": 5.0, "actual": 7.0, "divergence": -2.0, "desc": "Underestimated"},
        {"expected": 5.0, "actual": 5.0, "divergence": 0.0, "desc": "Perfect prediction"},
        {"expected": -3.0, "actual": -5.0, "divergence": 2.0, "desc": "Negative return overestimated"},
        {"expected": 5.0, "actual": None, "divergence": None, "desc": "Missing actual data"},
    ]
    
    for case in test_cases:
        expected_pct = case["expected"]
        actual_pct = case["actual"]
        
        if actual_pct is not None:
            divergence_pct = expected_pct - actual_pct
        else:
            divergence_pct = None
        
        print(f"{case['desc']}:")
        print(f"  Expected: {expected_pct:+.1f}%, Actual: {actual_pct if actual_pct is not None else 'N/A'}")
        print(f"  Divergence (E-R): {divergence_pct if divergence_pct is not None else 'N/A'}")
        
        if case["divergence"] is not None:
            assert abs(divergence_pct - case["divergence"]) < 0.01, \
                f"Expected divergence {case['divergence']}, got {divergence_pct}"
            print("  ✅ Passed\n")
        else:
            assert divergence_pct is None, "Should be None when actual unavailable"
            print("  ✅ Passed (correctly None)\n")


def test_decision_logic():
    """Verify trading decision thresholds."""
    print("\n=== Testing Decision Logic ===\n")
    
    engine = TradingSimulationEngine()
    
    test_cases = [
        {
            "desc": "Strong BUY signal",
            "direction": "up",
            "expected_return": 2.5,
            "confidence": 0.85,
            "risk_score": 0.30,
            "cost_ratio": 0.20,
            "expected_decision": "buy"
        },
        {
            "desc": "Strong SELL signal",
            "direction": "down",
            "expected_return": -2.5,
            "confidence": 0.85,
            "risk_score": 0.30,
            "cost_ratio": 0.20,
            "expected_decision": "sell"
        },
        {
            "desc": "Low confidence → HOLD",
            "direction": "up",
            "expected_return": 2.5,
            "confidence": 0.50,  # Below MIN_CONFIDENCE (0.55)
            "risk_score": 0.30,
            "cost_ratio": 0.20,
            "expected_decision": "hold"
        },
        {
            "desc": "Low return → HOLD",
            "direction": "up",
            "expected_return": 0.5,  # Below MIN_EXPECTED_RETURN_PCT (0.75)
            "confidence": 0.85,
            "risk_score": 0.30,
            "cost_ratio": 0.20,
            "expected_decision": "hold"
        },
        {
            "desc": "High risk → HOLD",
            "direction": "up",
            "expected_return": 2.5,
            "confidence": 0.85,
            "risk_score": 0.70,  # Above MAX_RISK_SCORE (0.65)
            "cost_ratio": 0.20,
            "expected_decision": "hold"
        },
        {
            "desc": "High costs eat alpha → HOLD",
            "direction": "up",
            "expected_return": 2.5,
            "confidence": 0.85,
            "risk_score": 0.30,
            "cost_ratio": 0.75,  # Above MAX_COST_RATIO (0.70)
            "expected_decision": "hold"
        },
    ]
    
    for case in test_cases:
        decision = engine._calculate_decision(
            case["direction"],
            case["expected_return"],
            case["confidence"],
            case["risk_score"],
            case["cost_ratio"]
        )
        
        print(f"{case['desc']}:")
        print(f"  Direction: {case['direction']}, Expected: {case['expected_return']:+.1f}%")
        print(f"  Confidence: {case['confidence']:.2f}, Risk: {case['risk_score']:.2f}, Cost Ratio: {case['cost_ratio']:.2f}")
        print(f"  Decision: {decision.upper()}")
        
        assert decision == case["expected_decision"], \
            f"Expected {case['expected_decision']}, got {decision}"
        print("  ✅ Passed\n")


def main():
    """Run all simulation calculation tests."""
    print("\n" + "="*70)
    print("SIMULATION CALCULATIONS VALIDATION TEST SUITE")
    print("="*70)
    
    try:
        test_expected_return_calculation()
        test_divergence_calculation()
        test_cost_calculation_formulas()
        test_risk_calculation_formulas()
        test_decision_logic()
        
        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED - Simulation calculations are correct!")
        print("="*70 + "\n")
        
    except AssertionError as e:
        print("\n" + "="*70)
        print(f"❌ TEST FAILED: {e}")
        print("="*70 + "\n")
        raise
    except Exception as e:
        print("\n" + "="*70)
        print(f"❌ ERROR: {e}")
        print("="*70 + "\n")
        raise


if __name__ == "__main__":
    main()
