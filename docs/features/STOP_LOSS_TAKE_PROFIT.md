# Stop Loss & Take Profit Implementation

## Overview

The TradeMeUp system now includes comprehensive stop loss and take profit calculations for all trading simulations. This feature provides realistic exit levels that adapt to market volatility, risk profiles, and stock characteristics.

## Features

### 🎯 Multiple Calculation Methods

1. **ATR-Based (Default)** - Most realistic approach
   - Uses Average True Range to adapt to each stock's volatility
   - 14-day ATR calculation period
   - Multipliers scale with volatility regime (1.5x-4.0x)
   - Automatically adjusts for low/medium/high/stressed markets

2. **Risk-Adjusted**
   - Integrates with risk score (0-1)
   - High risk positions → tighter stops
   - Low risk positions → wider stops
   - Optional confidence adjustment

3. **Percentage-Based**
   - Simple fixed percentage stops
   - Configurable by horizon (1d/5d/20d)
   - Fallback method when ATR unavailable

### 📊 Key Capabilities

- **Trailing Stops**: Dynamic stops that move with profitable price action
- **Penny Stock Handling**: Special adjustments for low-priced stocks
- **Risk/Reward Ratios**: Calculated for every position
- **Visual Display**: Interactive price ladder in prediction popup
- **Table Integration**: Stop loss columns in simulations table

## Configuration

Configuration is in `config/simulation_params.json` under `stop_loss_take_profit`:

```json
{
  "stop_loss_take_profit": {
    "enabled": true,
    "default_method": "atr_based",
    
    "atr_based": {
      "atr_period_days": 14,
      "atr_multiplier_stop_loss": {
        "low": 1.5,
        "medium": 2.0,
        "high": 2.5,
        "stressed": 3.0
      },
      "atr_multiplier_take_profit": {
        "low": 2.5,
        "medium": 3.0,
        "high": 3.5,
        "stressed": 4.0
      }
    }
  }
}
```

## Database Schema

New columns in `trading_simulations` table:

| Column | Type | Description |
|--------|------|-------------|
| `stop_loss_price` | Float | Stop loss price level |
| `stop_loss_pct` | Float | Stop loss distance as % |
| `stop_loss_type` | String | Method used (atr_based, risk_adjusted, etc.) |
| `trailing_stop_price` | Float | Trailing stop price (if enabled) |
| `take_profit_price` | Float | Take profit target price |
| `take_profit_pct` | Float | Take profit distance as % |
| `risk_reward_ratio` | Float | Risk/reward ratio |
| `exit_strategy` | JSON | Full exit strategy metadata |

## Usage

### Automatic Calculation

Stop loss and take profit are calculated automatically when creating simulations:

```python
from src.simulations.trading_simulator import TradingSimulationEngine

engine = TradingSimulationEngine()
stats = engine.create_simulations_from_predictions(limit=50)
```

All new simulations will include exit levels.

### Manual Calculation

Calculate exit levels for a specific scenario:

```python
from src.simulations.exit_strategy import ExitStrategyCalculator
from src.services.market_data import MarketDataProvider
import json

# Load config
with open('config/simulation_params.json') as f:
    config = json.load(f)

calculator = ExitStrategyCalculator(config)
market_provider = MarketDataProvider()

result = calculator.calculate_exit_levels(
    entry_price=150.0,
    direction='up',
    volatility_regime='medium',
    risk_score=0.5,
    confidence=0.7,
    horizon='5d',
    market_data_provider=market_provider,
    ticker='AAPL'
)

print(f"Stop Loss: ${result['stop_loss_price']:.2f} (-{result['stop_loss_pct']:.2f}%)")
print(f"Take Profit: ${result['take_profit_price']:.2f} (+{result['take_profit_pct']:.2f}%)")
print(f"Risk/Reward: 1:{result['risk_reward_ratio']:.2f}")
```

## Migration

### Apply Migration

```bash
# Using the manual migration script
python migrations/apply_stop_loss_migration.py

# Or using Alembic
alembic upgrade head
```

### Rollback (if needed)

```bash
python migrations/apply_stop_loss_migration.py --rollback
```

## Testing

Run the comprehensive test suite:

```bash
# Run all test scenarios
python tests/test_stop_loss_calculations.py --all

# Test with a specific ticker
python tests/test_stop_loss_calculations.py --ticker AAPL
```

Test scenarios include:
- Different volatility regimes (low/medium/high/stressed)
- Different risk scores (0.2 - 0.85)
- Long and short positions
- Penny stocks and ultra-penny stocks
- Different time horizons (1d/5d/20d)

## UI Display

### Prediction Details Popup

The prediction details modal now shows a dedicated "Exit Strategy" section with:

- **Method Badge**: Shows which calculation method was used
- **Risk/Reward Ratio**: Color-coded (green ≥2.0, yellow ≥1.5, red <1.5)
- **Stop Loss Card**: Price and percentage distance
- **Take Profit Card**: Target price and percentage gain
- **Visual Price Ladder**: Interactive display showing:
  - 🎯 Take Profit level
  - 📍 Entry price
  - 🛑 Stop Loss level
  - Current price position in range

### Simulations Table

The simulations table includes three new columns:

1. **Stop Loss**: Shows percentage distance with tooltip showing price
2. **Take Profit**: Shows percentage target with tooltip showing price
3. **R:R**: Risk/reward ratio (color-coded)

## Calculation Examples

### Example 1: Normal Stock (AAPL @ $150)

**Scenario**: Medium volatility, medium risk
- Entry: $150.00
- Stop Loss: $147.00 (-2.0%)
- Take Profit: $154.50 (+3.0%)
- R/R: 1:1.5

### Example 2: High Volatility (TSLA @ $200)

**Scenario**: High volatility, high risk
- Entry: $200.00
- Stop Loss: $195.00 (-2.5%)
- Take Profit: $207.00 (+3.5%)
- R/R: 1:1.4

### Example 3: Penny Stock ($0.50)

**Scenario**: High volatility, adjusted for penny stock
- Entry: $0.50
- Stop Loss: $0.475 (-5.0%)
- Take Profit: $0.537 (+7.5%)
- R/R: 1:1.5

Note: Penny stocks get wider stops due to higher spreads and volatility.

## Best Practices

### 1. ATR Method (Recommended)

✅ **Use when:**
- Stock has sufficient price history (>14 days)
- Stock is liquid and actively traded
- You want volatility-adapted stops

❌ **Avoid when:**
- Stock is newly listed
- Historical data unavailable
- Price < $0.01 (too volatile)

### 2. Risk-Adjusted Method

✅ **Use when:**
- ATR calculation fails
- You want risk-integrated stops
- Position sizing is risk-based

### 3. Percentage Method

✅ **Use when:**
- Simple fixed stops needed
- Fallback for data issues
- Quick estimates

### 4. Trailing Stops

- Activate after reaching profit threshold (default: 1.0%)
- Trail distance: 1.5% by default
- Update dynamically as price moves favorably

## Performance Considerations

### Calculation Speed

- **ATR-based**: ~100-200ms (requires historical data fetch)
- **Risk-adjusted**: ~1-5ms (pure calculation)
- **Percentage**: <1ms (instant)

### Caching

Market data is cached for 10 minutes to reduce API calls:
- First calculation fetches from API
- Subsequent calculations use cache
- Cache automatically refreshes

## Troubleshooting

### Stop Loss Not Calculated

**Problem**: Simulation shows "—" for stop loss

**Possible Causes**:
1. Price data unavailable
2. Price below minimum threshold ($0.00001)
3. Feature disabled in config

**Solution**:
```python
# Check if enabled
config = load_config()
print(config['stop_loss_take_profit']['enabled'])

# Check price threshold
print(config['penny_stock_handling']['min_valid_price_usd'])
```

### Unrealistic Stop Loss Values

**Problem**: Stop loss too tight or too wide

**Solution**: Adjust multipliers in config:
```json
{
  "atr_based": {
    "atr_multiplier_stop_loss": {
      "medium": 2.0  // Increase for wider stops
    }
  }
}
```

### ATR Calculation Fails

**Problem**: Falls back to risk-adjusted method

**Possible Causes**:
1. Insufficient historical data
2. New stock listing
3. API rate limiting

**Solution**: Use risk-adjusted as primary method or increase cache TTL.

## API Reference

### ExitStrategyCalculator

```python
class ExitStrategyCalculator:
    def __init__(self, config: Dict):
        """Initialize with simulation config"""
        
    def calculate_exit_levels(
        self,
        entry_price: float,
        direction: str,  # 'up', 'down', 'flat'
        volatility_regime: str,  # 'low', 'medium', 'high', 'stressed'
        risk_score: float,  # 0.0 - 1.0
        confidence: float,  # 0.0 - 1.0
        horizon: str,  # '1d', '5d', '20d'
        market_data_provider: MarketDataProvider,
        ticker: str
    ) -> Dict:
        """
        Calculate exit levels.
        
        Returns:
            {
                'stop_loss_price': float,
                'stop_loss_pct': float,
                'take_profit_price': float,
                'take_profit_pct': float,
                'risk_reward_ratio': float,
                'trailing_stop_price': float,
                'method': str,
                'exit_strategy_metadata': dict
            }
        """
```

## Future Enhancements

### Planned Features

- [ ] Partial position exits (scale out at profit levels)
- [ ] Dynamic trailing stops based on volatility
- [ ] Time-based stop adjustments
- [ ] Correlation-aware stops for portfolio
- [ ] Machine learning optimized stop levels

### Configuration Extensions

- [ ] Per-stock custom multipliers
- [ ] Sector-specific stop levels
- [ ] Market condition overrides
- [ ] Backtest optimization

## References

- **ATR Calculation**: Wilder, J. W. (1978). New Concepts in Technical Trading Systems
- **Risk Management**: Van Tharp, T. (1998). Trade Your Way to Financial Freedom
- **Position Sizing**: Jones, R. (1999). The Trading Game

---

**Last Updated**: 2026-01-26  
**Version**: 1.0.3  
**Author**: TradeMeUp Development Team
