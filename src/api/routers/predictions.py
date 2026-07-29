"""API endpoints for predictions."""
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from src.models.database import get_db
from src.models.entities import Entity
from src.models.predictions import Prediction
from src.utils.json_helpers import ensure_dict

router = APIRouter(prefix="/predictions", tags=["predictions"])


class PredictionResponse(BaseModel):
    """Response model for predictions."""
    prediction_id: str
    entity_id: str
    entity_name: str | None = None
    timestamp: datetime
    horizon: str
    direction_probabilities: dict
    expected_return: dict
    confidence: float
    model_version: str

    model_config = ConfigDict(from_attributes=True)


@router.get("/", response_model=list[PredictionResponse])
def list_predictions(
    entity_id: str | None = Query(None, description="Filter by entity"),
    min_confidence: float = Query(0.0, ge=0.0, le=1.0, description="Minimum confidence"),
    horizon: str | None = Query(None, description="Filter by horizon (1d, 5d, 20d)"),
    start_date: datetime | None = Query(None, description="Start date"),
    end_date: datetime | None = Query(None, description="End date"),
    limit: int = Query(50, le=200, description="Maximum results"),
    db: Session = Depends(get_db)
):
    """
    List predictions with optional filters.

    - **entity_id**: Filter by specific entity/ticker
    - **min_confidence**: Minimum confidence threshold
    - **horizon**: Prediction horizon (1d, 5d, 20d)
    - **start_date**: Start date for filtering
    - **end_date**: End date for filtering
    - **limit**: Maximum number of results
    """
    query = db.query(Prediction)

    # Apply filters
    if entity_id:
        query = query.filter(Prediction.entity_id == entity_id)

    if min_confidence > 0:
        query = query.filter(Prediction.confidence >= min_confidence)

    if horizon:
        query = query.filter(Prediction.horizon == horizon)

    if start_date:
        query = query.filter(Prediction.timestamp >= start_date)

    if end_date:
        query = query.filter(Prediction.timestamp <= end_date)

    # Order by timestamp desc and limit
    predictions = query.order_by(Prediction.timestamp.desc()).limit(limit).all()

    # Resolve entity names in one query. Looking each one up inside the loop
    # issued up to `limit` extra round trips per request.
    entity_ids = {pred.entity_id for pred in predictions}
    entity_names = dict(
        db.query(Entity.entity_id, Entity.entity_name)
        .filter(Entity.entity_id.in_(entity_ids))
        .all()
    ) if entity_ids else {}

    return [
        PredictionResponse(
            prediction_id=str(pred.prediction_id),
            entity_id=pred.entity_id,
            entity_name=entity_names.get(pred.entity_id),
            timestamp=pred.timestamp,
            horizon=pred.horizon,
            # ensure_dict: JSONB columns can come back as strings on rows
            # carried over from the SQLite era, which would fail validation.
            direction_probabilities=ensure_dict(pred.direction_probabilities, {}),
            expected_return=ensure_dict(pred.expected_return, {}),
            confidence=pred.confidence,
            model_version=pred.model_version
        )
        for pred in predictions
    ]


@router.get("/{prediction_id}", response_model=PredictionResponse)
def get_prediction(
    prediction_id: str,
    db: Session = Depends(get_db)
):
    """Get detailed information for a specific prediction."""
    prediction = db.query(Prediction).filter(
        Prediction.prediction_id == prediction_id
    ).first()

    if not prediction:
        raise HTTPException(status_code=404, detail="Prediction not found")

    entity = db.query(Entity).filter(Entity.entity_id == prediction.entity_id).first()

    return PredictionResponse(
        prediction_id=str(prediction.prediction_id),
        entity_id=prediction.entity_id,
        entity_name=entity.entity_name if entity else None,
        timestamp=prediction.timestamp,
        horizon=prediction.horizon,
        direction_probabilities=ensure_dict(prediction.direction_probabilities, {}),
        expected_return=ensure_dict(prediction.expected_return, {}),
        confidence=prediction.confidence,
        model_version=prediction.model_version
    )


@router.get("/statistics/summary")
def get_statistics(db: Session = Depends(get_db)):
    """Get overall prediction statistics."""
    from sqlalchemy import func

    total = db.query(Prediction).count()

    # Count bullish/bearish. Only the probabilities column is loaded: fetching
    # whole Prediction objects pulled every row of the table (with its JSONB
    # payloads) into memory just to read one field.
    probability_rows = db.query(Prediction.direction_probabilities).all()

    bullish = bearish = 0
    for (raw_probabilities,) in probability_rows:
        probabilities = ensure_dict(raw_probabilities, {})
        if probabilities.get('up', 0) > 0.5:
            bullish += 1
        elif probabilities.get('down', 0) > 0.5:
            bearish += 1

    # Average confidence
    avg_confidence = db.query(func.avg(Prediction.confidence)).scalar()

    # Recent predictions (last 24h)
    yesterday = datetime.now(UTC) - timedelta(days=1)
    recent = db.query(Prediction).filter(Prediction.timestamp >= yesterday).count()

    return {
        "total_predictions": total,
        "bullish_predictions": bullish,
        "bearish_predictions": bearish,
        "neutral_predictions": total - bullish - bearish,
        "average_confidence": float(avg_confidence) if avg_confidence else 0.0,
        "predictions_last_24h": recent
    }
