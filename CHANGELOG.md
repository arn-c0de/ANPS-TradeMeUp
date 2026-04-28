# Changelog

All notable changes to this project will be documented in this file.


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
