"""Database connection and session management."""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from src.config.settings import settings

# Create SQLAlchemy engine with larger pool for concurrent GUI callbacks
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=20,  # Increased from 10 to handle concurrent Dash callbacks
    max_overflow=30,  # Increased from 20
    pool_timeout=30,  # Add timeout to prevent indefinite waiting
    pool_recycle=3600,  # Recycle connections after 1 hour
    echo=settings.log_level == "DEBUG"
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function to get database session.
    Yields a database session and closes it after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
