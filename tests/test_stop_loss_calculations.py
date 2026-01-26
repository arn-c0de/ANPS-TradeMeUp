"""
Test stop loss and take profit calculations.

This script validates the exit strategy calculator with various scenarios:
- Different volatility regimes
- Different risk scores  
- Penny stocks and ultra-penny stocks
- All calculation methods (ATR, risk-adjusted, percentage)
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.simulations.exit_strategy import ExitStrategyCalculator
from src.services.market_data import MarketDataProvider
import json
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config():
    """Load simulation configuration."""
    config_path = project_root / "config" / "simulation_params.json"
    with open(config_path, 'r') as f:
        return json.load(f)


def test_scenario(name: str, **kwargs):
    """Test a specific scenario and print results."""
    logger.info(f"\n{'='*80}")
    logger.info(f"TEST SCENARIO: {name}")
    logger.info(f"{'='*80}")
    
    config = load_config()
    calculator = ExitStrategyCalculator(config)
    market_provider = MarketDataProvider()
    
    # Set defaults
    params = {
        'entry_price': 100.0,
        'direction': 'up',
        'volatility_regime': 'medium',
        'risk_score': 0.5,
        'confidence': 0.7,
        'horizon': '5d',
        'market_data_provider': market_provider,
        'ticker': 'AAPL'
    }
    params.update(kwargs)
    
    logger.info(f"Parameters:")
    for key, value in params.items():
        if key != 'market_data_provider':
            logger.info(f"  {key}: {value}")
    
    result = calculator.calculate_exit_levels(**params)
    
    logger.info(f"\nResults:")
    logger.info(f"  Method: {result.get('method', 'N/A')}")
    logger.info(f"  Stop Loss Price: ${result.get('stop_loss_price', 0):.4f}")
    logger.info(f"  Stop Loss %: {result.get('stop_loss_pct', 0):.2f}%")
    logger.info(f"  Take Profit Price: ${result.get('take_profit_price', 0):.4f}")
    logger.info(f"  Take Profit %: {result.get('take_profit_pct', 0):.2f}%")
    logger.info(f"  Risk/Reward Ratio: 1:{result.get('risk_reward_ratio', 0):.2f}")
    
    if result.get('trailing_stop_price'):
        logger.info(f"  Trailing Stop: ${result.get('trailing_stop_price', 0):.4f}")
    
    # Validate results
    if result.get('stop_loss_price') and result.get('take_profit_price'):
        logger.info(f"✅ Exit levels calculated successfully")
        
        # Check risk/reward ratio
        rr = result.get('risk_reward_ratio', 0)
        if rr >= 1.5:
            logger.info(f"✅ Good risk/reward ratio: 1:{rr:.2f}")
        else:
            logger.warning(f"⚠️  Low risk/reward ratio: 1:{rr:.2f}")
    else:
        logger.error(f"❌ Failed to calculate exit levels")
    
    return result


def run_all_tests():
    """Run comprehensive test suite."""
    logger.info("\n" + "="*80)
    logger.info("STOP LOSS & TAKE PROFIT - COMPREHENSIVE TEST SUITE")
    logger.info("="*80)
    
    # Test 1: Normal stock, medium volatility
    test_scenario(
        "Normal Stock - Medium Volatility",
        entry_price=150.0,
        direction='up',
        volatility_regime='medium',
        risk_score=0.5,
        confidence=0.7
    )
    
    # Test 2: High volatility regime
    test_scenario(
        "Normal Stock - High Volatility",
        entry_price=150.0,
        direction='up',
        volatility_regime='high',
        risk_score=0.6,
        confidence=0.65
    )
    
    # Test 3: Low volatility regime
    test_scenario(
        "Normal Stock - Low Volatility",
        entry_price=150.0,
        direction='up',
        volatility_regime='low',
        risk_score=0.3,
        confidence=0.8
    )
    
    # Test 4: Stressed market
    test_scenario(
        "Stressed Market Conditions",
        entry_price=150.0,
        direction='up',
        volatility_regime='stressed',
        risk_score=0.8,
        confidence=0.5
    )
    
    # Test 5: High risk position
    test_scenario(
        "High Risk Position (Tight Stops)",
        entry_price=100.0,
        direction='up',
        volatility_regime='medium',
        risk_score=0.85,  # Very high risk
        confidence=0.55
    )
    
    # Test 6: Low risk position
    test_scenario(
        "Low Risk Position (Wide Stops)",
        entry_price=100.0,
        direction='up',
        volatility_regime='medium',
        risk_score=0.2,  # Very low risk
        confidence=0.85
    )
    
    # Test 7: Short position
    test_scenario(
        "Short Position (Down Direction)",
        entry_price=100.0,
        direction='down',
        volatility_regime='medium',
        risk_score=0.5,
        confidence=0.7
    )
    
    # Test 8: Penny stock
    test_scenario(
        "Penny Stock ($0.50)",
        entry_price=0.50,
        direction='up',
        volatility_regime='high',
        risk_score=0.6,
        confidence=0.6
    )
    
    # Test 9: Ultra-penny stock
    test_scenario(
        "Ultra-Penny Stock ($0.0005)",
        entry_price=0.0005,
        direction='up',
        volatility_regime='high',
        risk_score=0.7,
        confidence=0.55
    )
    
    # Test 10: Different horizons
    for horizon in ['1d', '5d', '20d']:
        test_scenario(
            f"Horizon Test - {horizon}",
            entry_price=100.0,
            direction='up',
            volatility_regime='medium',
            risk_score=0.5,
            confidence=0.7,
            horizon=horizon
        )
    
    logger.info("\n" + "="*80)
    logger.info("TEST SUITE COMPLETED")
    logger.info("="*80)


def test_real_ticker(ticker: str):
    """Test with a real ticker using live market data."""
    logger.info(f"\n{'='*80}")
    logger.info(f"REAL TICKER TEST: {ticker}")
    logger.info(f"{'='*80}")
    
    config = load_config()
    calculator = ExitStrategyCalculator(config)
    market_provider = MarketDataProvider()
    
    # Get current price
    try:
        price_data = market_provider.get_live_price(ticker)
        if not price_data:
            logger.error(f"Could not get price data for {ticker}")
            return
        
        entry_price = price_data.get('price', 100.0)
        logger.info(f"Current price: ${entry_price:.2f}")
        
        result = calculator.calculate_exit_levels(
            entry_price=entry_price,
            direction='up',
            volatility_regime='medium',
            risk_score=0.5,
            confidence=0.7,
            horizon='5d',
            market_data_provider=market_provider,
            ticker=ticker
        )
        
        logger.info(f"\nATR-based Exit Levels:")
        logger.info(f"  Method: {result.get('method', 'N/A')}")
        logger.info(f"  Stop Loss: ${result.get('stop_loss_price', 0):.2f} (-{result.get('stop_loss_pct', 0):.2f}%)")
        logger.info(f"  Take Profit: ${result.get('take_profit_price', 0):.2f} (+{result.get('take_profit_pct', 0):.2f}%)")
        logger.info(f"  Risk/Reward: 1:{result.get('risk_reward_ratio', 0):.2f}")
        
        if result.get('atr_value'):
            logger.info(f"  ATR: ${result.get('atr_value'):.2f}")
        
        logger.info(f"✅ Real ticker test completed")
        
    except Exception as e:
        logger.error(f"Error testing ticker {ticker}: {e}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test stop loss calculations")
    parser.add_argument(
        "--ticker",
        type=str,
        help="Test with a specific real ticker (e.g., AAPL, MSFT)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all test scenarios"
    )
    
    args = parser.parse_args()
    
    if args.ticker:
        test_real_ticker(args.ticker)
    elif args.all:
        run_all_tests()
    else:
        # Default: run all tests
        run_all_tests()
        
        # Test a few real tickers if available
        logger.info("\n\nTesting with real tickers...")
        for ticker in ['AAPL', 'MSFT', 'TSLA']:
            try:
                test_real_ticker(ticker)
            except Exception as e:
                logger.warning(f"Skipping {ticker}: {e}")
