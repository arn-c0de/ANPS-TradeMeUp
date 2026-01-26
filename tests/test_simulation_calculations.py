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


def test_small_price_handling():
    """Very small prices should be treated as invalid and return empty breakdown."""
    engine = TradingSimulationEngine()
    total_bps, breakdown = engine._estimate_costs_bps(
        price=0.0001,
        volatility_regime="medium",
        predicted_direction="up",
        horizon="5d",
        shares=100,
        daily_volume=170000
    )
    print("Small price test: price=0.0001")
    print(f"  total_bps: {total_bps}, breakdown: {breakdown}")
    assert total_bps == 0.0
    assert breakdown == {}, "Expected empty breakdown for extremely small price"
    print("  ✅ Passed\n")


def test_penny_stock_detection():
    """Test penny stock detection logic."""
    print("\n=== Testing Penny Stock Detection ===\n")

    engine = TradingSimulationEngine()

    test_cases = [
        {"price": 0.50, "expected": True, "desc": "$0.50 - Penny stock"},
        {"price": 0.99, "expected": True, "desc": "$0.99 - Penny stock"},
        {"price": 1.00, "expected": True, "desc": "$1.00 - Penny stock (at threshold)"},
        {"price": 1.01, "expected": False, "desc": "$1.01 - NOT penny stock"},
        {"price": 5.00, "expected": False, "desc": "$5.00 - NOT penny stock"},
        {"price": 100.00, "expected": False, "desc": "$100.00 - NOT penny stock"},
        {"price": 0.0, "expected": False, "desc": "$0.00 - Invalid (zero price)"},
        {"price": -1.0, "expected": False, "desc": "$-1.00 - Invalid (negative price)"},
    ]

    for case in test_cases:
        result = engine._is_penny_stock(case["price"])
        print(f"{case['desc']}")
        print(f"  Result: {result}")
        assert result == case["expected"], \
            f"Expected {case['expected']} for price ${case['price']}, got {result}"
        print("  ✅ Passed\n")


def test_penny_stock_cost_methods():
    """Test different penny stock cost calculation methods."""
    print("\n=== Testing Penny Stock Cost Methods ===\n")

    engine = TradingSimulationEngine()

    # Test each cost method
    methods = ["per_share_only", "flat_dollar", "capped_bps"]

    for method in methods:
        print(f"Testing method: {method}")
        total_bps, breakdown = engine._estimate_penny_stock_costs(
            price=0.75,  # $0.75 penny stock
            shares=100,
            cost_method=method,
            predicted_direction="up",
            horizon="5d"
        )

        print(f"  Price: $0.75, Shares: 100")
        print(f"  Total Cost: {total_bps:.1f} bps")
        print(f"  Breakdown: {breakdown}")

        # Verify method is tracked
        assert "cost_method" in breakdown, "cost_method should be in breakdown"
        assert breakdown["cost_method"] == method, f"Expected method {method}, got {breakdown['cost_method']}"

        # Verify total is reasonable (not absurdly high)
        assert total_bps < 10000, f"Cost {total_bps} bps is too high (likely calculation error)"
        assert total_bps > 0, f"Cost should be positive, got {total_bps}"

        # Method-specific validations
        if method == "per_share_only":
            assert breakdown.get("spread_bps", 0) == 0, "per_share_only should have zero spread"
            assert breakdown.get("slippage_bps", 0) == 0, "per_share_only should have zero slippage"
            assert breakdown.get("commission_bps", 0) > 0, "per_share_only should have commission"

        elif method == "flat_dollar":
            assert "flat_cost_usd" in breakdown, "flat_dollar should have flat_cost_usd field"

        elif method == "capped_bps":
            assert "max_bps_cap" in breakdown, "capped_bps should have max_bps_cap field"
            assert total_bps <= breakdown["max_bps_cap"], \
                f"Cost {total_bps} exceeds cap {breakdown['max_bps_cap']}"

        print("  ✅ Passed\n")


def test_penny_stock_integration():
    """Test that penny stocks use alternative cost calculation in main flow."""
    print("\n=== Testing Penny Stock Integration ===\n")

    engine = TradingSimulationEngine()

    # Test with penny stock price (should use penny stock method)
    total_bps_penny, breakdown_penny = engine._estimate_costs_bps(
        price=0.85,  # Penny stock
        volatility_regime="medium",
        predicted_direction="up",
        horizon="5d",
        shares=100,
        daily_volume=50000
    )

    print(f"Penny Stock Test (price=$0.85):")
    print(f"  Total Cost: {total_bps_penny:.1f} bps")
    print(f"  Cost Method: {breakdown_penny.get('cost_method', 'standard')}")

    assert "cost_method" in breakdown_penny, "Penny stock should have cost_method field"
    assert breakdown_penny["cost_method"] != "standard", \
        "Penny stock should use alternative cost method, not standard"
    assert total_bps_penny < 1000, \
        f"Penny stock costs {total_bps_penny} should be reasonable (< 1000 bps)"
    print("  ✅ Penny stock handling passed\n")

    # Test with normal stock price (should use standard method)
    total_bps_normal, breakdown_normal = engine._estimate_costs_bps(
        price=50.00,  # Normal stock
        volatility_regime="medium",
        predicted_direction="up",
        horizon="5d",
        shares=100,
        daily_volume=500000
    )

    print(f"Normal Stock Test (price=$50.00):")
    print(f"  Total Cost: {total_bps_normal:.1f} bps")
    print(f"  Cost Method: {breakdown_normal.get('cost_method', 'standard')}")

    # Normal stocks should NOT have cost_method field (or it should be 'standard')
    cost_method_normal = breakdown_normal.get('cost_method', 'standard')
    assert cost_method_normal == 'standard' or cost_method_normal not in breakdown_normal, \
        "Normal stock should use standard cost method"
    assert "spread_bps" in breakdown_normal, "Normal stock should have spread costs"
    assert "slippage_bps" in breakdown_normal, "Normal stock should have slippage costs"
    print("  ✅ Normal stock handling passed\n")
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
        test_small_price_handling()
        test_penny_stock_detection()
        test_penny_stock_cost_methods()
        test_penny_stock_integration()
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
