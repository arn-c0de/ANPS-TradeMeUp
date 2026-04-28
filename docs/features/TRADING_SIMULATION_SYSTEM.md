# Trading Simulation System

## Overview

Trading simulations are part of the current PostgreSQL-backed application flow. They operate on predictions and market data and are exposed through the GUI and pipeline code.

## Main code locations

- `src/simulations/trading_simulator.py`
- `src/simulations/risk_calculations.py`
- `src/agents/trading_simulation_agent.py`
- `src/models/trading_simulation.py`

## Setup

```bash
docker compose up -d postgres
alembic upgrade head
```

The `trading_simulations` table is managed by Alembic migrations. Do not use old one-off setup scripts.

## Generate simulations

```bash
python scripts/run_mvp_pipeline.py
python scripts/run_continuous_pipeline.py
python scripts/resimulate_all.py
```

## View in the GUI

```bash
python scripts/runtime/run_dashboard.py
```

Check:

- `Predictions` tab
- `Simulations` tab

## Historical note

Older versions of this document referenced SQLite backups and one-off setup scripts such as `add_simulation_table.py`. Those paths are obsolete after the repository refactor and PostgreSQL migration.
