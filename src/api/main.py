"""Main FastAPI application."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config.settings import settings
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
    logger.info("Starting TradeMeUp API...")
    logger.info(f"Environment: {settings.app_env}")
    logger.info(f"Database: {settings.database_url}")
    logger.info(f"LLM Provider: {settings.llm_provider}")
    yield
    logger.info("Shutting down TradeMeUp API...")


# Create FastAPI application
app = FastAPI(
    title="TradeMeUp API",
    description="AI Multi-Agent News-Based Market Prediction System",
    version="0.1.0",
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
        "version": "0.1.0",
        "llm_provider": settings.llm_provider
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "TradeMeUp API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health"
    }


# Include routers
app.include_router(predictions.router, prefix=settings.api_v1_prefix)
app.include_router(news.router, prefix=settings.api_v1_prefix)
app.include_router(entities.router, prefix=settings.api_v1_prefix)
