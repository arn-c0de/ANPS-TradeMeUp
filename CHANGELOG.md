# Changelog

All notable changes to this project will be documented in this file.


## [1.0.5] - 2026-07-29

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
