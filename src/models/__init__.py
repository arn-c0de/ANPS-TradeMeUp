"""Models package - imports all models to ensure SQLAlchemy can resolve relationships."""

# Import database base first
from src.models.database import Base, get_db

# Import all models to ensure relationships are resolved
from src.models.raw_news import RawNews
from src.models.entities import Entity, NewsEntityMapping, EntityRelationship
from src.models.processed_news import ProcessedNews
from src.models.data_quality import DataQualityScore
from src.models.analysis import MarketRegime, SurpriseScore, ImpactScore
from src.models.predictions import Prediction, PredictionOutcome
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
]
