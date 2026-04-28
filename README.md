# ANPS-TradeMeUp

ANPS-TradeMeUp is a multi-agent news-to-market prediction system. It ingests financial news, extracts entities and events with LLM-supported analysis, scores impact and surprise, and produces market predictions with a Dash GUI and a FastAPI backend.

## Status

- Core application code is organized under `src/`
- Operational scripts are grouped under `scripts/`
- Legacy SQLite migration utilities are archived under `archive/legacy/sqlite/`
- The repository is now prepared for full-container workflows with `postgres`, `api`, `gui`, and `worker` services in `docker-compose.yml`

## Quick Start

### Full Docker stack

```bash
docker compose up --build
```

Nur betroffene Services nach Dateiänderungen neu bauen:

```bash
./scripts/docker/rebuild-on-change.sh
./scripts/docker/rebuild-on-change.sh --watch
```

Das Skript baut bei reinen GUI-Änderungen nur `gui` neu; bei Änderungen in mehreren Bereichen oder gemeinsamen Build-Dateien wird der komplette App-Stack (`api`, `gui`, `worker`) neu gebaut.

Services:

- GUI: `http://localhost:8050`
- API docs: `http://localhost:8000/docs`
- API health: `http://localhost:8000/health`
- PostgreSQL: `localhost:5432`

This default stack starts:

- `postgres`
- `api`
- `gui`

The optional continuous pipeline worker is not started by default.

Start it explicitly:

```bash
docker compose --profile worker up -d worker
```

For older `docker-compose` v1 environments, a compatible command is:

```bash
COMPOSE_PROFILES=worker docker-compose up -d --no-recreate worker
```

### One-shot pipeline in Docker with OpenAI

Set `OPENAI_API_KEY` in `.env.local`, then run:

```bash
docker compose exec -T \
  -e LLM_PROVIDER=openai \
  -e OPENAI_MODEL=gpt-4o-mini \
  api python scripts/run_mvp_pipeline.py
```

If you use a custom OpenAI-compatible proxy, set `OPENAI_BASE_URL` to a full `https://...` URL. If it is empty or invalid, the app now falls back to the official OpenAI endpoint automatically.

### Local development with Dockerized PostgreSQL

```bash
cp .env.example .env.local
docker compose up -d postgres

python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

alembic upgrade head
python scripts/runtime/run_dashboard.py
```

Windows:

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
python scripts\runtime\run_dashboard.py
```

## Common Entrypoints

- Dashboard: `python scripts/runtime/run_dashboard.py`
- API: `uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload`
- Continuous pipeline worker: `python scripts/run_continuous_pipeline.py`
- One-shot MVP pipeline: `python scripts/run_mvp_pipeline.py`
- Database connection check: `python scripts/db/test_db_connection.py`
- Database bootstrap helper: `python scripts/db/init_database.py`

Convenience wrappers remain available under `scripts/runtime/` and `scripts/setup/`.

## Repository Layout

```text
.
├── src/                  # Application code
├── scripts/              # Runtime, setup, db, and utility scripts
├── tests/                # Test suite and validation checks
├── docs/                 # Setup, architecture, features, and reports
├── migrations/           # Alembic environment and SQL migrations
├── archive/              # Legacy and diagnostic assets kept for reference
├── docker-compose.yml    # Full local container stack
├── Dockerfile            # Shared application image
├── pyproject.toml        # Python project metadata and tooling
├── requirements.txt      # Pip-compatible dependency list
├── alembic.ini           # Alembic configuration
└── .env.example          # Environment template
```

Detailed folder notes: [`docs/STRUCTURE.md`](docs/STRUCTURE.md)

## Documentation

- Quickstart: [`docs/setup/QUICKSTART.md`](docs/setup/QUICKSTART.md)
- PostgreSQL setup: [`docs/setup/POSTGRESQL_SETUP.md`](docs/setup/POSTGRESQL_SETUP.md)
- Repository structure: [`docs/STRUCTURE.md`](docs/STRUCTURE.md)
- Architecture snapshot: [`docs/architecture/1.0.3-TradeMeUp_Complete_System_Architecture.md`](docs/architecture/1.0.3-TradeMeUp_Complete_System_Architecture.md)

## Notes

- `src/config/settings.py` loads environment values from `.env.local`
- The Docker stack does not require `.env.local` for the default local boot path
- `OPENAI_MODEL` defaults to `gpt-4o-mini`
- The archived SQLite migration scripts are intentionally no longer part of the default flow
- Historical reports under `docs/reports/` may still describe older paths or workflows
