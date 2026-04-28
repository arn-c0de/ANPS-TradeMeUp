# Quickstart

## Prerequisites

- Python 3.11+
- Docker with Compose
- A configured `.env.local`
- One LLM provider:
  - Ollama
  - OpenAI
  - Anthropic

## Fastest path: full Docker stack

```bash
docker compose up --build
```

Open:

- GUI: `http://localhost:8050`
- API docs: `http://localhost:8000/docs`

Default services:

- `postgres`
- `api`
- `gui`

## Optional worker

Modern Compose:

```bash
docker compose --profile worker up -d worker
```

Older `docker-compose` v1:

```bash
COMPOSE_PROFILES=worker docker-compose up -d --no-recreate worker
```

## One-shot pipeline with OpenAI in Docker

Set `OPENAI_API_KEY` in `.env.local`, then run:

```bash
docker compose exec -T \
  -e LLM_PROVIDER=openai \
  -e OPENAI_MODEL=gpt-4o-mini \
  api python scripts/run_mvp_pipeline.py
```

`OPENAI_BASE_URL` is optional. If it is blank or invalid, the app falls back to the official OpenAI API URL automatically.

## Local app with Dockerized PostgreSQL

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

## Useful commands

```bash
python scripts/run_continuous_pipeline.py
python scripts/run_mvp_pipeline.py
python scripts/run_ingestion.py
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
python scripts/db/test_db_connection.py
```

## Notes

- The Docker path uses an internal container database URL and runs Alembic plus schema bootstrap automatically.
- `.env.local` is optional for the default Docker boot path; it is mainly needed for local non-container development or custom API keys/settings.
- `OPENAI_MODEL` defaults to `gpt-4o-mini`.

## Database management

```bash
docker compose up -d postgres
docker compose logs -f postgres
docker compose stop postgres
docker compose down
```

## Legacy SQLite migration

SQLite migration helpers are archived and are no longer part of the normal setup flow.

If you still need them, see:

- `archive/legacy/sqlite/migrate_sqlite_to_postgres.py`
- `archive/legacy/sqlite/remigrate_boolean_tables.py`

Use them only for recovery or historical data migration work.
