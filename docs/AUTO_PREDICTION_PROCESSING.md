# Automatic Prediction Processing

## Overview

The TradeMeUp system now automatically processes new predictions by calculating performance and creating trading simulations. This ensures that all predictions have complete data for analysis and display in the dashboard.

## Features

### 1. Automatic Processing in Pipeline

When the MVP pipeline runs (`scripts/run_mvp_pipeline.py`), it automatically processes all predictions created in the last 60 minutes:

- **Performance Calculation**: Fetches live market data and calculates actual returns
- **Simulation Creation**: Generates trading simulations with risk assessment and position sizing

This happens automatically after Agent 6 (Prediction Generation) completes.

### 2. Backfill Script

For retroactive processing of historical predictions, use the backfill script:

```bash
python scripts/backfill_prediction_performance.py
```

This script:
- Finds all predictions without performance data (PredictionOutcome)
- Calculates and saves performance for each prediction
- Creates trading simulations for predictions without simulations
- Provides detailed statistics and logging

**Example Output:**
```
🔍 Finding predictions without performance data...
📊 Found 45 predictions without performance data
📈 [1/45] Calculating performance for AAPL (5d)...
✅ Saved performance: +2.34% (✓)
🧪 [1/45] Creating simulation for AAPL (5d)...
✅ Created simulation: BUY (Return: +2.34%, Risk: 0.42)
...
📊 Performance backfill complete: 40 success, 0 errors, 5 skipped
🧪 Simulation backfill complete: 38 created, 0 errors, 7 skipped
```

### 3. Auto Prediction Processor Service

The `AutoPredictionProcessor` service (`src/services/auto_prediction_processor.py`) can be used programmatically:

```python
from src.services.auto_prediction_processor import auto_processor
from src.models.database import SessionLocal

db = SessionLocal()

# Process predictions from last hour
stats = auto_processor.process_new_predictions(db, lookback_minutes=60)

# Process specific predictions
stats = auto_processor.process_specific_predictions(db, prediction_ids=['...'])

db.close()
```

## Dashboard Integration

### Top Performers List

The dashboard now shows top performers with:
- **Live Performance**: Displays actual returns (e.g., +6.81% (33m ago))
- **Clickable Names**: Opens detailed prediction popup
- **Auto-Update**: Refreshes every 5 seconds
- **Smart Display**: Shows 3 entries, rest scrollable

Performance data is automatically calculated when:
1. New predictions are created (via pipeline)
2. Backfill script is run
3. Manual refresh button is clicked (🔄 in predictions tab)

## Data Flow

```
New Prediction Created
        ↓
Auto Prediction Processor
        ↓
    ┌───────────────────────┐
    │                       │
    ↓                       ↓
Performance Calculation   Simulation Creation
    ↓                       ↓
PredictionOutcome      TradingSimulation
    ↓                       ↓
    └─────────┬─────────────┘
              ↓
        Dashboard Display
```

## Configuration

### Pipeline Auto-Processing

In `scripts/run_mvp_pipeline.py`:
```python
# Adjust lookback window (default: 60 minutes)
auto_stats = auto_processor.process_new_predictions(db, lookback_minutes=60)
```

### Top Performers Display

In `src/gui/tabs/dashboard.py`:
- **Display Limit**: 10 predictions max
- **Visible Items**: 3 entries (rest scrollable)
- **Scroll Height**: 180px

## Benefits

1. **Always Up-to-Date**: New predictions are automatically processed
2. **Historical Completeness**: Backfill script ensures all old predictions have data
3. **Better UX**: Dashboard shows live performance without manual intervention
4. **Performance Tracking**: All predictions have outcome data for analysis

## Troubleshooting

### No Performance Data Showing

If predictions don't show performance data:

1. **Run Backfill Script**: `python scripts/backfill_prediction_performance.py`
2. **Check Entity**: Prediction must have a valid, tradable entity (stock symbol)
3. **Market Data**: Ensure market data provider (yfinance) is accessible

### Simulations Not Created

Simulations may not be created if:
- Risk score exceeds threshold (>0.65)
- Expected return too low (<0.75%)
- Position size constraints violated
- Entity not tradable

Check logs for specific reasons.

## Logging

All auto-processing operations are logged:
- **INFO**: Successful processing
- **WARNING**: Skipped predictions (with reason)
- **ERROR**: Processing failures

Logs are visible in:
- Console output
- `logs/pipeline_activity.log`
- Dashboard "Live Agent Activity" section

## Future Enhancements

Potential improvements:
- [ ] Real-time processing (triggered on prediction creation event)
- [ ] Batch processing optimization
- [ ] Performance calculation caching
- [ ] Custom processing schedules
- [ ] Email notifications for high-value predictions
