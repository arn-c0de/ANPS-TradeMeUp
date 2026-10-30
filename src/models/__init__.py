"""Models package - imports all models to ensure SQLAlchemy can resolve relationships."""

from sqlalchemy.orm import configure_mappers

# Import database base first
from src.models.analysis import ImpactScore, MarketRegime, SurpriseScore
from src.models.chart_overlays import ChartOverlay
from src.models.data_quality import DataQualityScore
from src.models.database import Base, get_db
from src.models.entities import Entity, EntityRelationship, NewsEntityMapping
from src.models.predictions import Prediction, PredictionOutcome
from src.models.processed_news import ProcessedNews

# Import all models to ensure relationships are resolved
from src.models.raw_news import RawNews
from src.models.system_logs import SystemLog
from src.models.trading_simulation import TradingSimulation

__all__ = [
    "Base",
    "get_db",
    "RawNews",
    "Entity",
    "NewsEntityMapping",
    "EntityRelationship",
    "ProcessedNews",
    "DataQualityScore",
    "MarketRegime",
    "SurpriseScore",
    "ImpactScore",
    "Prediction",
    "PredictionOutcome",
    "TradingSimulation",
    "ChartOverlay",
    "SystemLog",
]

# Importing any src.models.* module runs this package first, so every model is
# mapped here. Configure eagerly: backref attributes such as Prediction.outcome
# or RawNews.quality_score only exist on the classes after configuration, and
# 2.0-style select() statements (unlike Session.query) do not trigger it.
configure_mappers()
