"""Alembic environment configuration."""
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Import all models to ensure they're registered
from src.models.database import Base
from src.models.raw_news import RawNews
from src.models.data_quality import DataQualityScore
from src.models.processed_news import ProcessedNews
from src.models.entities import Entity, NewsEntityMapping, EntityRelationship
from src.models.analysis import ImpactScore, SurpriseScore, MarketRegime, SignalDecayModel
from src.models.predictions import Prediction, PredictionOutcome, BacktestResult, MarketData

# Import settings
from src.config.settings import settings
from src.models.database import normalize_database_url

# this is the Alembic Config object
config = context.config

# Override sqlalchemy.url with our settings
config.set_main_option('sqlalchemy.url', normalize_database_url(settings.database_url))

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
