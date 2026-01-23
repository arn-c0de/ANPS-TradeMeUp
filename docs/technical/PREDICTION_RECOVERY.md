# Prediction Recovery Guide

## Problem Solved ✅

**Issue**: The pipeline was creating 0 new predictions despite analyzing 2000+ articles.

**Root Causes Found & Fixed**:
1. ✅ **Fact Verification Agent** - Was accessing wrong relationship (`raw_news` → `news`)
2. ✅ **Meta Strategy Agent** - Was accessing non-existent attribute (`predicted_direction`)
3. ✅ **Prediction Agent** - JSON array search in SQLite was unreliable
4. ✅ **Backfill Script** - Was passing wrong parameters to PredictionAgent

## Current Status (2026-01-23 22:44)

- **Total Predictions**: 750
- **Distribution**: 250 per horizon (1d, 5d, 20d)
- **High Impact Scores**: 250
- **Pipeline**: Fixed and operational

## Files Modified

### Core Fixes
1. `src/agents/fact_verification_agent.py` - Fixed relationship access + eager loading
2. `src/agents/meta_strategy_agent.py` - Extract direction from probabilities
3. `src/agents/prediction_agent.py` - Fixed JSON search + added generate_prediction()
4. `scripts/backfill_all_agents.py` - Removed incorrect db parameter

### New Tools
5. `recalculate_recent_predictions.py` - Manual prediction regeneration tool

## Usage

### Restore Predictions (if needed)
```bash
# Generate predictions for all high-impact scores
python scripts/backfill_all_agents.py --batch-size 100 --skip-quality --skip-content --skip-entities --skip-facts --skip-surprises --skip-impact
```

### Recalculate Recent Predictions
```bash
# For last hour (with safety check)
python recalculate_recent_predictions.py --hours 1 --min-impact 0.4

# For last 24 hours without deletion (safe)
python recalculate_recent_predictions.py --hours 24 --no-force

# Custom threshold
python recalculate_recent_predictions.py --hours 6 --min-impact 0.5
```

**⚠️ WARNING**: Using `--force` (default) will delete existing predictions. Use `--no-force` to be safe!

## Verification

Check prediction count:
```bash
python check_predictions.py
```

Or quick SQL check:
```bash
python -c "from sqlalchemy import create_engine, func; from sqlalchemy.orm import Session; from src.models.predictions import Prediction; engine = create_engine('sqlite:///trademeup.db'); db = Session(engine); print(f'Total: {db.query(Prediction).count()}'); [print(f'{h}: {c}') for h,c in db.query(Prediction.horizon, func.count(Prediction.prediction_id)).group_by(Prediction.horizon).all()]"
```

## Expected Behavior (Fixed)

The continuous pipeline should now:
1. ✅ Ingest news (no errors)
2. ✅ Process with LLM (no errors)
3. ✅ Verify facts (no errors) 
4. ✅ Calculate impact scores
5. ✅ Generate predictions automatically
6. ✅ Update meta strategy (no errors)

## Next Steps

1. Restart continuous pipeline: `python scripts/run_continuous_pipeline.py`
2. Monitor logs for errors
3. Check GUI dashboard for new predictions
4. Predictions should increase as new high-impact news arrives

## Rollback (if needed)

If predictions were accidentally deleted:
```bash
# Full backfill (takes ~3 seconds)
python scripts/backfill_all_agents.py --batch-size 100 --skip-quality --skip-content --skip-entities --skip-facts --skip-surprises --skip-impact
```

---

**Last Updated**: 2026-01-23 22:44
**Fixed By**: GitHub Copilot
**Status**: ✅ OPERATIONAL
