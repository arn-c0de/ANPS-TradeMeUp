# Repository Structure

This repository follows a simple separation of concerns:

## Top level

- `src/`: application code only
- `scripts/`: operational and developer scripts
- `tests/`: automated tests and data checks
- `docs/`: active documentation and historical reports
- `migrations/`: Alembic environment and SQL migration assets
- `archive/`: retired or diagnostic files that should not be part of the default workflow

## `src/`

- `src/api/`: FastAPI application and routers
- `src/agents/`: domain agents for ingestion, scoring, prediction, and orchestration
- `src/config/`: runtime settings and config loading
- `src/gui/`: Dash GUI application, tabs, callbacks, and assets
- `src/ml/`: model-related feature engineering
- `src/models/`: SQLAlchemy models and database types
- `src/services/`: shared runtime services
- `src/simulations/`: trading simulation and risk logic
- `src/utils/`: shared utilities

## `scripts/`

- `scripts/runtime/`: human-facing startup scripts and runtime entrypoints
- `scripts/setup/`: local environment setup helpers
- `scripts/db/`: database utilities and bootstrap helpers
- `scripts/backfills/`: backfill orchestration scripts
- root `scripts/*.py` files: pipeline jobs and project utilities still intended for active use

## `docs/`

- `docs/setup/`: current setup and quickstart documentation
- `docs/architecture/`: architecture snapshots
- `docs/features/`: feature-focused notes
- `docs/technical/`: implementation and refactor notes
- `docs/reports/`: status reports and historical summaries
- `docs/fixes/`: targeted bug-fix writeups

## `archive/`

- `archive/legacy/sqlite/`: retired SQLite migration and cleanup utilities
- `archive/diagnostics/`: one-off diagnostic scripts kept for reference

## Root policy

The repository root should stay limited to:

- project metadata
- primary build/runtime configuration
- top-level docs that are expected by hosting platforms

New operational scripts should go into `scripts/`, not the root.
