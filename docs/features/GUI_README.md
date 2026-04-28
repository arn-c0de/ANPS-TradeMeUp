# GUI README

## Current entrypoint

Start the dashboard with one of these commands:

```bash
python scripts/runtime/run_dashboard.py
```

```bash
python scripts\runtime\run_dashboard.py
```

Convenience wrappers:

- `scripts/runtime/start_gui.sh`
- `scripts/runtime/start_gui.bat`

The dashboard listens on `http://localhost:8050`.

## Structure

The GUI lives under `src/gui/`:

```text
src/gui/
├── app.py
├── components.py
├── callbacks/
├── helpers/
├── tabs/
│   ├── dashboard.py
│   ├── predictions.py
│   ├── news.py
│   ├── simulations.py
│   ├── statistics/
│   ├── charts/
│   ├── control.py
│   ├── system.py
│   └── settings.py
└── utils/
```

## Runtime dependencies

- Database: PostgreSQL via `DATABASE_URL`
- App config: `src/config/settings.py`
- Market data: `src/services/market_data.py`
- Activity logs: `logs/`

## Typical development flow

```bash
docker compose up -d postgres
alembic upgrade head
python scripts/runtime/run_dashboard.py
```

## Notes

- Older screenshots or reports may still show pre-refactor file paths.
- The canonical quickstart now lives in `docs/setup/QUICKSTART.md`.
