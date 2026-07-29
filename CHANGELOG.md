# Changelog

All notable changes to this project will be documented in this file.


## [1.0.5] - 2026-07-29

### Fixed (prediction pipeline and LLM cost)
- The three horizons produced byte-identical predictions: `horizon` was passed
  into the generator but never reached the features or the model, so 1d, 5d and
  20d differed only by their label. Expected return now scales with sqrt(time),
  the prediction interval widens with the horizon, and confidence decays for
  longer horizons
- Heuristic predictions were recorded as `model_version="xgboost_v1.0"` with
  `model_contributions={'xgboost': 1.0}` even though no trained model exists on
  disk, so performance monitoring and A/B testing were comparing a heuristic
  they believed was a model. They are now labelled `heuristic_v1`
- The model's class order was assumed to be `[down, flat, up]`; `classes_` is
  read instead, with a warning when it is unusable
- `expected_return` now states `is_percentage: False` explicitly, instead of
  leaving every consumer to infer the format from the magnitude
- `p25`/`p75`/`p95` were fixed offsets carrying no distributional information
  and were identical across horizons. They are derived from a scaled volatility
  now, and `p05` was added so the interval is symmetric
- Three pipeline phases called `get_statistics()` instead of `process_batch()`,
  so they reported on work they never did: no scenario was ever generated, no
  ensemble prediction was ever created, and `calibrated_confidence` was never
  written back onto any prediction
- Embeddings silently fell back from OpenAI (1536-dim) to a local model
  (768-dim) into the same column. The producing model is now recorded in
  `llm_metadata.embedding_model` and the fallback warns explicitly

### Performance (prediction pipeline and LLM cost)
- Prediction batch selection ran a query per candidate per horizon, each
  loading every prediction the entity ever had, and then repeated the whole
  check inside the batch loop - roughly 320 round trips per batch, now two
- JSON responses are requested through OpenAI's `response_format` and Ollama's
  `format: "json"`, so a malformed reply no longer wastes an entire call
- `generate_json` no longer appends a JSON-only instruction that the prompt
  templates already carry
- Prompt content is budgeted in tokens and cut on a sentence boundary rather
  than sliced at a hard-coded character count

### Fixed (agents, ML and API)
- Four agents read `prediction.predicted_direction` / `.predicted_return` /
  `.model_id` as if they were columns. They are not, so model performance
  monitoring, A/B testing, confidence calibration, and the ensemble strategy
  all raised `AttributeError` on their first row. The two derived values are
  now properties on the model; `model_id` call sites use `model_version`
- `Prediction.model_id` was also used inside SQLAlchemy query filters, where
  it compared a Python object instead of emitting SQL
- A "flat" prediction was scored correct only within 0.01%, not 1%, because
  `actual_return` is stored as a percentage - flat was effectively never right
- `actual_return` of NULL was compared against zero without a guard
- Accuracy divided by all fetched predictions, counting those without a usable
  outcome as wrong
- Impact score could exceed its documented 0-1 range: `regime_sensitivity`
  reaches 2.73 but was divided by 2.0, and `sector_sensitivity` was fed in
  unnormalized. Components are now scaled by their true maxima and the result
  is clamped
- Training datasets label rows with random noise (documented TODO); this is now
  logged as a warning and marked with an `is_synthetic_target` column instead of
  passing silently
- Latest market regime was selected by `created_at` in two places and by the
  indexed `timestamp` column in four others, so consumers could disagree about
  the current regime
- `_get_source_authority` crashed on a null source and could match its own
  'default' sentinel

### Performance
- `calibrate_confidence` re-scanned 90 days of history for every prediction in
  a batch; the calibration is now computed once per batch
- Removed N+1 queries in the calibration, A/B testing, and performance-monitor
  agents, and in the news and predictions API list endpoints
- `/predictions/statistics/summary` loaded every prediction row into memory to
  read one JSONB field

### Fixed
- Prediction performance calculation localized the timezone of a shared cached
  DataFrame in place, so every repeat calculation for the same ticker failed and
  silently reported "no market data"
- `MarketDataProvider` was instantiated five more times across the GUI, giving
  each copy its own rate limiter and cache and defeating the throttling meant to
  prevent yfinance "Too Many Requests"
- Live quotes were served from cache for up to an hour; the 60-second freshness
  window was defined but never applied
- Cache age was measured with `timedelta.seconds`, which discards whole days
- Historical data was cached forever via `lru_cache` and handed out by reference
- A `null` price field from yfinance propagated as `None` into numeric comparisons
- Prediction outcomes stored `|actual return|` in the `error` column instead of
  `|predicted - actual|`
- Batch performance updates wrote naive local timestamps into a timezone-aware
  column
- Remaining-time display showed e.g. "23h left" for already-expired horizons
- Simulations reset for an invalid price kept their stale stop loss / take profit
- Trailing stop ignored the configured activation threshold and could sit inside
  the stop loss, making the stop loss unreachable
- Task queue accepted a `priority` argument it never applied, and never enforced
  `max_concurrent_tasks`; queue dict was mutated during iteration
- Local embedding model was reloaded from disk on every single embedding call
- `min_valid_price_usd` had three different fallback values across the codebase

### Changed
- Shared `market_data`, `prediction_math`, `penny_stocks`, and `time_format`
  helpers replace logic that was duplicated across modules
- Redis cache connects lazily instead of blocking every import
- Simulation statistics use one grouped query instead of four table scans

## [1.0.4] - 2026-04-28

### Added
- **Databases tab**: new dashboard tab for full PostgreSQL database management
  - Live stats overview for all 17 tables including DB size
  - Paginated browsers for News, Predictions, and Simulations with per-row delete
  - Cascading news delete (removes processed data, entity mappings, impact/surprise scores, and optionally all linked predictions and simulations)
  - Export database to `.tmu` file (JSON format) with selectable tables and time window (all / last 24h / 7d / 30d / 90d / custom range)
  - Import from `.tmu` file with file preview, embedded history display, time filter, and merge or replace mode
  - Local import/export history log (`data/db_history.json`) embedded in every export so the full chain of custody travels with the file

### Fixed
- Duplicate `refresh-toast` component ID between Predictions and Simulations tabs causing dashboard startup crash

## [1.0.3] - 2026-01-26

### Added
- Published private development version
