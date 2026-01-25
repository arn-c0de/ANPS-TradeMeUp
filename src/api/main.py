"""Main FastAPI application."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config.settings import settings, VERSION
from src.utils.redact import redact_url
from src.api.routers import predictions, news, entities

# Configure logging
logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting ANPS-TradeMeUp API...")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Database: {redact_url(settings.database_url)}")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    yield
    logger.info("Shutting down ANPS-TradeMeUp API...")


# Create FastAPI application
app = FastAPI(
    title="ANPS-TradeMeUp API",
    description="ANPS (AI News Prediction System) - Multi-Agent News-Based Market Prediction System",
    version=VERSION,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "environment": settings.app_env,
        "version": VERSION,
        "llm_provider": settings.llm_provider
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "ANPS-TradeMeUp API",
        "version": VERSION,
        "docs": "/docs",
        "health": "/health"
    }


# Include routers
app.include_router(predictions.router, prefix=settings.api_v1_prefix)
app.include_router(news.router, prefix=settings.api_v1_prefix)
app.include_router(entities.router, prefix=settings.api_v1_prefix)
