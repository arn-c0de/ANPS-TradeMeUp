# Copilot / AI Agent Instructions for ANPS-TradeMeUp

Purpose: help an AI code agent quickly become productive in this repo by documenting the "big picture", key workflows, patterns, and where to find examples.

1) High level architecture
- Modular multi-agent pipeline: ingest → understand → analyse → predict → monitor. See agents in `src/agents/*` (e.g. `ingestion_agent.py`, `content_understanding_agent.py`, `prediction_agent.py`).
- Backend & API: FastAPI entry at `src/api/main.py`.
- GUI: Dash app at `src/gui/app.py` with tabbed components in `src/gui/tabs/` (Agent Control, Dashboard, Live Charts).
- Storage & infra: Postgres/Timescale, Redis, MinIO (defined in `docker-compose.yml`), DB migrations in `migrations/` (use `alembic upgrade head`).

2) How to run / developer workflows (examples)
- Quick GUI (Windows): `start_gui.bat` → open http://localhost:8050 ✅
- Start infra: `docker-compose up -d` (postgres/redis/minio)
- Run pipeline (continuous): `python scripts/run_continuous_pipeline.py` or one-shot: `python scripts/run_mvp_pipeline.py`
- Run DB migrations: `alembic upgrade head` or use provided `init_database.py` helper
- Tests: `pytest tests/unit` and `pytest tests/integration`
- Environment: copy `.env.example` → `.env` (settings are loaded from `.env.local` by `src/config/settings.py`)

3) Key integrations & env vars
- LLMs: unified interface in `src/services/llm_service.py`. Supported providers: `ollama` (local), `openai`, `anthropic`.
  - Important env vars: `LLM_PROVIDER`, `OLLAMA_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `ANTHROPIC_API_KEY`.
  - Note: `llm_service.generate_json()` tries to extract/repair JSON from LLM outputs — prefer prompts that ask for strict JSON.
- Market data: `ALPHA_VANTAGE_KEY` (configured via `src/config/settings.py`).
- DB & caches: `DATABASE_URL`, `REDIS_URL`.

4) Code & testing patterns to follow
- Agents are class-based, accept a SQLAlchemy `Session` in constructor, expose operations like `process_batch()`, `fetch_all_rss_feeds()`, or `get_statistics()` — use existing agents as templates (e.g., `IngestionAgent`).
- Use `models` for DB objects (`src/models/*`) and perform commit/rollback on exceptions.
- Use the global LLM instance or instantiate `LLMService(provider="openai")` for provider-specific behavior. Example: `from src.services.llm_service import llm_service; llm_service.generate_json(prompt)`.
- Tests mirror the project structure (unit vs integration). Tests commonly initialize agents with a DB fixture and call `get_statistics()` for a smoke test; add focused unit tests for new logic.

5) Common pitfalls & helpful tips
- Ollama: if `LLM_PROVIDER=ollama` ensure `ollama serve` is running at `OLLAMA_BASE_URL`.
- OpenAI: proxy and custom base URL supported (see `llm_service` for proxy checks); invalid proxy ports are detected and disabled.
- Timescale/Postgres: `docker-compose.yml` spins up `timescaledb`; prefer using the compose stack for integration testing.
- Keep `VERSION` in `src/config/settings.py` in sync with docs/README when releasing.

6) Practical first tasks for AI contributors
- Add a focused unit test for new agent functionality under `tests/unit` mirroring existing test style.
- Small bug: replicate pattern in `IngestionAgent._save_article()` for graceful rollback on DB errors.

If any of these sections are unclear or you want more detail (examples of prompts, exact test fixtures to use, or a short checklist for PRs), tell me which areas to expand and I'll iterate. ✅
