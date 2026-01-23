"""Application configuration using Pydantic Settings."""
from typing import List, Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path

# Application Version
VERSION = "1.0.2"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent.parent / ".env.local"),
        env_file_encoding="utf-8",
        case_sensitive=False
    )

    # Application
    app_env: str = Field(default="local", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    secret_key: str = Field(default="dev-secret-key", alias="SECRET_KEY")

    # API
    api_v1_prefix: str = Field(default="/api/v1", alias="API_V1_PREFIX")
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8050", "http://localhost:8000"],
        alias="CORS_ORIGINS"
    )

    # Database - supports both SQLite and PostgreSQL
    # Use absolute path for SQLite to avoid multiple databases
    database_url: str = Field(
        default=f"sqlite:///{Path(__file__).parent.parent.parent / 'trademeup.db'}", 
        alias="DATABASE_URL"
    )

    # Redis (optional for local dev)
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")

    # LLM Configuration
    llm_provider: Literal["ollama", "openai", "anthropic"] = Field(
        default="ollama",
        alias="LLM_PROVIDER"
    )

    # Ollama (local)
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama2", alias="OLLAMA_MODEL")

    # OpenAI
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-3.5-turbo", alias="OPENAI_MODEL")

    # Anthropic
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-3-haiku-20240307", alias="ANTHROPIC_MODEL")

    # API Keys for data sources
    news_api_key: str = Field(default="", alias="NEWS_API_KEY")
    alpha_vantage_key: str = Field(default="", alias="ALPHA_VANTAGE_KEY")

    # Model Settings
    model_path: str = Field(default="./models", alias="MODEL_PATH")
    default_temperature: float = Field(default=0.1, alias="DEFAULT_TEMPERATURE")
    max_tokens: int = Field(default=4096, alias="MAX_TOKENS")


# Global settings instance
settings = Settings()
