"""
Prediction Performance Service
Tracks and validates predictions against actual market data
"""
import logging
import warnings
from datetime import UTC, datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

# Suppress yfinance warnings
warnings.filterwarnings('ignore', category=FutureWarning, module='yfinance')
warnings.filterwarnings('ignore', category=DeprecationWarning, module='yfinance')
warnings.filterwarnings('ignore', message='.*Timestamp.utcnow.*')
try:
    from pandas.errors import Pandas4Warning
    warnings.filterwarnings('ignore', category=Pandas4Warning)
except ImportError:
    pass

import uuid

from src.models.entities import Entity
from src.models.predictions import Prediction, PredictionOutcome
from src.utils.json_helpers import ensure_dict

logger = logging.getLogger(__name__)


def _convert_to_python_type(value):
    """Convert NumPy/pandas types to Python native types for database compatibility.
    
    PostgreSQL doesn't automatically handle NumPy types, so we need to convert them.
    """
    if value is None:
        return None

    # Handle NumPy scalars (has .item() method)
    if hasattr(value, 'item'):
        return value.item()

    # Handle pandas Timestamp
    if hasattr(value, 'to_pydatetime'):
        return value.to_pydatetime()

    # Already a Python native type
    if isinstance(value, (int, float, bool, str)):
        return value

    # Try to convert to float for numeric values
    try:
        return float(value)
    except (ValueError, TypeError):
        return value


class PredictionPerformanceService:
    """Service to track prediction performance against actual market data"""

    def __init__(self):
        # Use the shared market_data instance to centralize rate limiting
        from src.services.market_data import market_data as _global_market_data
        self.market_data = _global_market_data

    def get_prediction_performance(
        self,
        prediction: Prediction,
        entity: Entity
    ) -> dict | None:
        """
        Calculate prediction performance vs actual market data

        Args:
            prediction: Prediction object
            entity: Entity object

        Returns:
            Dict with performance metrics or None
        """
        try:
            # Get ticker/symbol from entity
            ticker = entity.entity_id
            if not ticker:
                logger.debug("No ticker found for entity")
                return None

            # Skip invalid/placeholder tickers
            invalid_tickers = ['OTHER', 'UNKNOWN', 'N/A', 'NONE', 'TEST', 'HEALTH', 'TAO']
            # Also skip crypto tickers that start with $
            if ticker.startswith('$'):
                logger.debug(f"Skipping crypto ticker: {ticker}")
                return None
            if ticker.upper() in invalid_tickers or len(ticker) > 10:
                logger.debug(f"Skipping invalid ticker: {ticker}")
                return None

            # Get current price
            logger.debug(f"Fetching live price for {ticker}")
            current_data = self.market_data.get_live_price(ticker)
            if not current_data or not current_data.get('price'):
                logger.warning(f"❌ No live price data available for {ticker} - Check if ticker exists/is listed")
                return None

            current_price = current_data['price']
            logger.debug(f"Current price for {ticker}: ${current_price}")

            # Get historical data to find price at prediction time
            # Fetch data from prediction date to now
            if not prediction.created_at:
                logger.warning("No created_at timestamp for prediction")
                return None

            # Use timezone-aware datetime for PostgreSQL compatibility
            now = datetime.now(UTC)
            created_at = prediction.created_at if prediction.created_at.tzinfo else prediction.created_at.replace(tzinfo=UTC)
            days_since_prediction = (now - created_at).days
            period = f"{max(days_since_prediction + 5, 7)}d"  # Add buffer days

            logger.debug(f"Fetching {period} historical data for {ticker}")
            # Get historical data
            hist_data = self.market_data.get_historical_data(
                ticker,
                period=period,
                interval="1d"
            )

            if hist_data is None or hist_data.empty:
                logger.warning(f"❌ No historical data available for {ticker} (period={period}) - Check ticker validity or market data source")
                return None

            logger.debug(f"Got {len(hist_data)} historical data points for {ticker}")

            # Find price at or near prediction time
            prediction_date = prediction.created_at.replace(tzinfo=None)

            # Get closest available date (market might be closed on prediction date)
            hist_data.index = hist_data.index.tz_localize(None)  # Remove timezone
            closest_idx = hist_data.index.get_indexer([prediction_date], method='nearest')[0]

            if closest_idx < 0 or closest_idx >= len(hist_data):
                logger.warning(f"❌ Could not find historical price near prediction date {prediction_date} for {ticker} - Insufficient historical data")
                return None

            prediction_price = hist_data.iloc[closest_idx]['Close']
            prediction_actual_date = hist_data.index[closest_idx]

            # Calculate returns
            total_return = ((current_price - prediction_price) / prediction_price) * 100

            # Get 24h performance
            if len(hist_data) >= 2:
                yesterday_price = hist_data.iloc[-2]['Close']
                return_24h = ((current_price - yesterday_price) / yesterday_price) * 100
            else:
                return_24h = 0.0

            # Determine if prediction was correct
            predicted_direction = self._get_predicted_direction(prediction)
            actual_direction = self._get_actual_direction(total_return)

            is_correct = predicted_direction == actual_direction

            # Would buy/sell have worked?
            if predicted_direction == 'up':
                strategy_result = "✅ BUY worked" if total_return > 0 else "❌ BUY failed"
            elif predicted_direction == 'down':
                strategy_result = "✅ SELL/SHORT worked" if total_return < 0 else "❌ SELL/SHORT failed"
            else:  # flat
                strategy_result = "⚪ FLAT predicted" if abs(total_return) < 1 else "❌ FLAT wrong"

            return {
                'ticker': ticker,
                'current_price': current_price,
                'prediction_price': prediction_price,
                'prediction_date': prediction_actual_date,
                'total_return_pct': total_return,
                'return_24h_pct': return_24h,
                'predicted_direction': predicted_direction,
                'actual_direction': actual_direction,
                'is_correct': is_correct,
                'strategy_result': strategy_result,
                'days_since_prediction': days_since_prediction,
                'timestamp': datetime.now(UTC),
                # Additional data
                'high_since_prediction': hist_data.iloc[closest_idx:]['High'].max() if len(hist_data) > closest_idx else current_price,
                'low_since_prediction': hist_data.iloc[closest_idx:]['Low'].min() if len(hist_data) > closest_idx else current_price,
                'volatility': hist_data.iloc[closest_idx:]['Close'].pct_change().std() * 100 if len(hist_data) > closest_idx else 0,
            }

        except Exception as e:
            logger.error(f"Error calculating prediction performance for {ticker}: {type(e).__name__}: {e}")
            logger.debug("Full traceback:", exc_info=True)
            return None

    def _get_predicted_direction(self, prediction: Prediction) -> str:
        """Get the predicted direction from prediction probabilities"""
        probs = ensure_dict(prediction.direction_probabilities, {})
        if not probs:
            return 'unknown'

        return max(probs, key=probs.get)

    def _get_actual_direction(self, return_pct: float, threshold: float = 1.0) -> str:
        """
        Determine actual direction based on return percentage
        
        Args:
            return_pct: Return percentage
            threshold: Threshold for flat direction (default 1%)
        """
        if return_pct > threshold:
            return 'up'
        elif return_pct < -threshold:
            return 'down'
        else:
            return 'flat'

    def get_batch_performance(
        self,
        predictions: list[Prediction],
        db_session: Session
    ) -> dict[str, dict]:
        """
        Get performance for multiple predictions
        
        Args:
            predictions: List of Prediction objects
            db_session: Database session to query entities
            
        Returns:
            Dict mapping prediction_id to performance data
        """
        results = {}

        for pred in predictions:
            # Get entity
            entity = db_session.query(Entity).filter(
                Entity.entity_id == pred.entity_id
            ).first()

            if not entity:
                continue

            perf = self.get_prediction_performance(pred, entity)
            if perf:
                results[str(pred.prediction_id)] = perf

        return results

    def get_prediction_accuracy_stats(
        self,
        predictions: list[Prediction],
        db_session: Session
    ) -> dict:
        """
        Calculate overall accuracy statistics for a set of predictions
        
        Args:
            predictions: List of predictions
            db_session: Database session
            
        Returns:
            Dict with accuracy metrics
        """
        results = self.get_batch_performance(predictions, db_session)

        if not results:
            return {
                'total': 0,
                'correct': 0,
                'accuracy': 0,
                'avg_return': 0,
                'win_rate': 0
            }

        correct = sum(1 for r in results.values() if r['is_correct'])
        positive_returns = sum(1 for r in results.values() if r['total_return_pct'] > 0)
        avg_return = sum(r['total_return_pct'] for r in results.values()) / len(results)

        return {
            'total': len(results),
            'correct': correct,
            'accuracy': (correct / len(results)) * 100 if results else 0,
            'avg_return': avg_return,
            'win_rate': (positive_returns / len(results)) * 100 if results else 0,
            'by_direction': self._stats_by_direction(results)
        }

    def _stats_by_direction(self, results: dict) -> dict:
        """Calculate stats broken down by predicted direction"""
        by_dir = {'up': [], 'down': [], 'flat': []}

        for perf in results.values():
            direction = perf['predicted_direction']
            if direction in by_dir:
                by_dir[direction].append(perf)

        stats = {}
        for direction, perfs in by_dir.items():
            if perfs:
                correct = sum(1 for p in perfs if p['is_correct'])
                stats[direction] = {
                    'count': len(perfs),
                    'correct': correct,
                    'accuracy': (correct / len(perfs)) * 100,
                    'avg_return': sum(p['total_return_pct'] for p in perfs) / len(perfs)
                }
            else:
                stats[direction] = {
                    'count': 0,
                    'correct': 0,
                    'accuracy': 0,
                    'avg_return': 0
                }

        return stats

    def save_prediction_performance(
        self,
        prediction_id: str,
        performance_data: dict,
        db_session: Session
    ) -> bool:
        """
        Save prediction performance to PredictionOutcome table
        
        Args:
            prediction_id: Prediction UUID
            performance_data: Performance metrics from get_prediction_performance
            db_session: Database session
            
        Returns:
            True if saved successfully
        """
        try:
            # Convert all values from NumPy/pandas types to Python native types
            actual_return_value = _convert_to_python_type(performance_data.get('total_return_pct', 0))
            is_correct_value = bool(performance_data.get('is_correct', False))

            # Ensure we have a valid float
            if actual_return_value is None:
                actual_return_value = 0.0
            else:
                actual_return_value = float(actual_return_value)

            logger.info(f"💾 Saving to DB: prediction_id={prediction_id}, actual_return={actual_return_value}, is_correct={is_correct_value}")

            # Check if outcome already exists
            existing = db_session.query(PredictionOutcome).filter(
                PredictionOutcome.prediction_id == prediction_id
            ).first()

            if existing:
                # Update existing - use proper SQLAlchemy update
                from sqlalchemy import update
                logger.info(f"📝 Updating existing outcome (current value: {existing.actual_return})")
                db_session.execute(
                    update(PredictionOutcome)
                    .where(PredictionOutcome.prediction_id == prediction_id)
                    .values(
                        actual_return=actual_return_value,
                        error=abs(actual_return_value),
                        direction_correct=is_correct_value,
                        within_confidence_interval=True,
                        sharpe_contribution=0.0,
                        evaluation_timestamp=_convert_to_python_type(performance_data.get('timestamp', datetime.now(UTC)))
                    )
                )
                logger.info(f"✅ Updated existing outcome for prediction {prediction_id} with value {actual_return_value}")
            else:
                # Create new
                logger.info("📝 Creating new outcome")
                outcome = PredictionOutcome(
                    outcome_id=uuid.uuid4(),
                    prediction_id=prediction_id,
                    actual_return=actual_return_value,
                    error=abs(actual_return_value),
                    direction_correct=is_correct_value,
                    within_confidence_interval=True,  # TODO: implement proper check
                    sharpe_contribution=0,  # TODO: calculate
                    evaluation_timestamp=_convert_to_python_type(performance_data.get('timestamp', datetime.now(UTC))),
                    created_at=datetime.now(UTC)
                )
                db_session.add(outcome)
                logger.info(f"✅ Created new outcome for prediction {prediction_id} with value {actual_return_value}")

            db_session.commit()
            logger.info(f"💾 Committed changes to database for prediction {prediction_id}")
            return True

        except Exception as e:
            logger.error(f"Error saving prediction performance: {e}", exc_info=True)
            db_session.rollback()
            return False

    def calculate_and_save_performance(self, engine, prediction_id: str) -> dict:
        """
        Combined method to calculate and save prediction performance
        
        Args:
            engine: SQLAlchemy engine
            prediction_id: Prediction UUID
            
        Returns:
            Dict with performance metrics
        """
        from sqlalchemy.orm import Session

        with Session(engine) as db:
            try:
                # Get prediction and entity
                prediction = db.query(Prediction).filter(
                    Prediction.prediction_id == prediction_id
                ).first()

                if not prediction:
                    logger.warning(f"Prediction {prediction_id} not found")
                    return {"status": "error", "error": "Prediction not found"}

                entity = db.query(Entity).filter(
                    Entity.entity_id == prediction.entity_id
                ).first()

                if not entity:
                    logger.warning(f"Entity {prediction.entity_id} not found")
                    return {"status": "error", "error": "Entity not found"}

                # Calculate performance
                performance = self.get_prediction_performance(prediction, entity)

                logger.info(f"📊 Performance calculated for {prediction_id}: {performance}")

                if not performance:
                    logger.warning(f"No performance data calculated for {prediction_id}")
                    return {"status": "no_data", "error": "No market data available"}

                logger.info(f"💾 Saving performance: total_return_pct={performance.get('total_return_pct')}, is_correct={performance.get('is_correct')}")

                # Save performance (this will commit internally)
                success = self.save_prediction_performance(prediction_id, performance, db)

                logger.info(f"✅ Save operation result for {prediction_id}: success={success}")

                if success:
                    return {
                        "status": "success",
                        "total_return_pct": performance.get('total_return_pct', 0),
                        "is_correct": performance.get('is_correct', False)
                    }
                else:
                    return {"status": "error", "error": "Failed to save performance"}

            except Exception as e:
                logger.error(f"Error calculating and saving performance: {e}", exc_info=True)
                db.rollback()
                return {"status": "error", "error": str(e)}


# Global instance
prediction_performance_service = PredictionPerformanceService()
