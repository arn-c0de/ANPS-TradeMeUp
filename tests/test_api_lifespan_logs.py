import asyncio
import logging

from fastapi import FastAPI

from src.api.main import lifespan
from src.config.settings import settings


def test_lifespan_logs_do_not_contain_db_url(monkeypatch, caplog):
    monkeypatch.setattr(settings, "database_url", "postgresql://user:pass@db.example.com:5432/db")
    app = FastAPI()
    caplog.set_level(logging.INFO)

    async def run_lifespan():
        async with lifespan(app):
            # lifespan yields immediately; nothing else to do
            pass

    asyncio.run(run_lifespan())

    assert "user:pass" not in caplog.text
    # Ensure a Database entry is logged but not credentials
    assert "Database:" in caplog.text
