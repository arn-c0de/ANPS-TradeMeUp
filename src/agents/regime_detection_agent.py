"""Agent 5: Market Regime Detection Agent."""
import logging
import uuid
import warnings
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

warnings.filterwarnings('ignore', category=FutureWarning, module='yfinance')
import numpy as np
import yfinance as yf

from src.models.analysis import MarketRegime
from src.utils.json_helpers import clean_numpy_types

logger = logging.getLogger(__name__)


class RegimeDetectionAgent:
    """
    Agent 5: Market Regime Detection Agent

    Responsibilities:
    - Detect current market regime
    - Track volatility, trend, risk appetite, liquidity
    - Store regime state in database
    """

    # Volatility thresholds (VIX levels)
    VOLATILITY_THRESHOLDS = {
        'low': 15,
        'medium': 25,
        'high': float('inf')
    }

    # Trend thresholds (price vs moving average)
    TREND_THRESHOLDS = {
        'strong_bull': 1.10,  # 10% above MA200
        'bull': 1.02,  # 2% above MA200
        'neutral': 0.98,  # Within 2% of MA200
        'bear': 0.90,  # More than 10% below MA200
    }

    def __init__(self, db: Session):
        """
        Initialize regime detection agent.

        Args:
            db: Database session
        """
        self.db = db

    def _get_default_indicators(self) -> dict:
        """
        Return default market indicators when data fetch fails
        
        Returns:
            Dictionary with default market indicators
        """
        return {
            'vix': 20.0,
            'spy_price': 450.0,
            'spy_ma50': 450.0,
            'spy_ma200': 450.0,
            'realized_volatility': 15.0,
            'breadth': 0.0,
            'lookback_days': 0
        }

    def _fetch_market_data(self, lookback_days: int = 252) -> dict:
        """
        Fetch market data for regime detection.

        Args:
            lookback_days: Days of history to fetch

        Returns:
            Dictionary with market indicators
        """
        try:
            # Fetch S&P 500 data
            spy = yf.Ticker('SPY')
            spy_hist = spy.history(period=f'{lookback_days}d')

            if spy_hist is None or spy_hist.empty:
                logger.warning("Failed to fetch SPY data - returning default indicators")
                return self._get_default_indicators()

            # Fetch VIX data
            vix = yf.Ticker('^VIX')
            vix_hist = vix.history(period='30d')

            current_vix = vix_hist['Close'].iloc[-1] if (vix_hist is not None and not vix_hist.empty) else 20.0
            current_spy = spy_hist['Close'].iloc[-1]

            # Calculate moving averages
            ma50 = spy_hist['Close'].rolling(window=50).mean().iloc[-1] if len(spy_hist) >= 50 else current_spy
            ma200 = spy_hist['Close'].rolling(window=200).mean().iloc[-1] if len(spy_hist) >= 200 else current_spy

            # Calculate volatility
            returns = spy_hist['Close'].pct_change().dropna()
            realized_vol = returns.std() * np.sqrt(252) if len(returns) > 0 else 0.15  # Annualized

            # Market breadth (simplified - would need advance/decline data)
            recent_returns = spy_hist['Close'].pct_change(20).iloc[-1] if len(spy_hist) > 20 else 0
            breadth_proxy = 1.0 if recent_returns > 0 else -1.0

            return {
                'vix': current_vix,
                'spy_price': current_spy,
                'spy_ma50': ma50,
                'spy_ma200': ma200,
                'realized_volatility': realized_vol * 100,  # As percentage
                'breadth': breadth_proxy,
                'lookback_days': lookback_days
            }

        except Exception as e:
            logger.error(f"Error fetching market data: {e}")
            return self._get_default_indicators()
            return {}

    def _classify_volatility(self, vix: float) -> str:
        """
        Classify volatility regime based on VIX.

        Args:
            vix: VIX level

        Returns:
            Volatility classification
        """
        if vix < self.VOLATILITY_THRESHOLDS['low']:
            return 'low'
        elif vix < self.VOLATILITY_THRESHOLDS['medium']:
            return 'medium'
        else:
            return 'high'

    def _classify_trend(self, price: float, ma200: float) -> str:
        """
        Classify trend regime based on price vs MA200.

        Args:
            price: Current price
            ma200: 200-day moving average

        Returns:
            Trend classification
        """
        ratio = price / ma200

        if ratio >= self.TREND_THRESHOLDS['strong_bull']:
            return 'strong_bull'
        elif ratio >= self.TREND_THRESHOLDS['bull']:
            return 'bull'
        elif ratio >= self.TREND_THRESHOLDS['neutral']:
            return 'sideways'
        elif ratio >= self.TREND_THRESHOLDS['bear']:
            return 'bear'
        else:
            return 'strong_bear'

    def _classify_risk_appetite(self, vix: float, breadth: float) -> str:
        """
        Classify risk appetite.

        Args:
            vix: VIX level
            breadth: Market breadth indicator

        Returns:
            Risk appetite classification
        """
        # Risk-off if high VIX or negative breadth
        if vix > 30 or breadth < -0.5:
            return 'risk_off'
        elif vix < 15 and breadth > 0.5:
            return 'risk_on'
        else:
            return 'neutral'

    def _classify_liquidity(self, volatility: float) -> str:
        """
        Classify liquidity regime.

        Args:
            volatility: Realized volatility

        Returns:
            Liquidity classification
        """
        # Simplified: High vol = stressed liquidity
        if volatility > 30:
            return 'stressed'
        elif volatility < 15:
            return 'abundant'
        else:
            return 'normal'

    def detect_regime(self) -> dict:
        """
        Detect current market regime.

        Returns:
            Dictionary with regime classification
        """
        # Fetch market data
        market_data = self._fetch_market_data()

        if not market_data:
            # Fallback to neutral regime if data unavailable
            logger.warning("No market data available, using neutral regime")
            return {
                'regime': {
                    'volatility': 'medium',
                    'trend': 'sideways',
                    'risk_appetite': 'neutral',
                    'liquidity': 'normal'
                },
                'regime_metadata': {
                    'data_available': False
                }
            }

        # Classify regime components
        volatility_regime = self._classify_volatility(market_data['vix'])
        trend_regime = self._classify_trend(
            market_data['spy_price'],
            market_data['spy_ma200']
        )
        risk_regime = self._classify_risk_appetite(
            market_data['vix'],
            market_data['breadth']
        )
        liquidity_regime = self._classify_liquidity(
            market_data['realized_volatility']
        )

        # Build regime description
        regime = {
            'volatility': volatility_regime,
            'trend': trend_regime,
            'risk_appetite': risk_regime,
            'liquidity': liquidity_regime
        }

        # Calculate regime confidence
        # Higher confidence if extreme values
        confidence = 0.7  # Base confidence

        if market_data['vix'] > 35 or market_data['vix'] < 12:
            confidence += 0.1  # Extreme VIX

        if abs(market_data['spy_price'] / market_data['spy_ma200'] - 1.0) > 0.15:
            confidence += 0.1  # Strong trend

        confidence = min(1.0, confidence)

        # Estimate transition probability (simplified)
        transition_prob = 0.15 if volatility_regime == 'high' else 0.05

        return {
            'regime': regime,
            'regime_probabilities': {
                'current_regime_confidence': confidence,
                'transition_probability_7d': transition_prob
            },
            'regime_metadata': {
                'vix_level': market_data['vix'],
                'spy_price': market_data['spy_price'],
                'spy_ma50': market_data['spy_ma50'],
                'spy_ma200': market_data['spy_ma200'],
                'realized_volatility': market_data['realized_volatility'],
                'market_breadth': market_data['breadth'],
                'data_available': True
            }
        }

    def update_regime(self) -> MarketRegime:
        """
        Detect and store current regime.

        Returns:
            MarketRegime object
        """
        try:
            # Detect regime
            result = self.detect_regime()

            # Create regime record (convert numpy types for PostgreSQL compatibility)
            regime = MarketRegime(
                regime_id=uuid.uuid4(),
                timestamp=datetime.now(UTC),
                regime=clean_numpy_types(result['regime']),
                regime_probabilities=clean_numpy_types(result['regime_probabilities']),
                regime_metadata=clean_numpy_types(result['regime_metadata']),
                created_at=datetime.now(UTC)
            )

            # Save to database
            self.db.add(regime)
            self.db.commit()
            self.db.refresh(regime)

            logger.info(
                f"Updated market regime: "
                f"volatility={regime.regime['volatility']}, "
                f"trend={regime.regime['trend']}, "
                f"risk={regime.regime['risk_appetite']}"
            )

            return regime

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating regime: {e}")
            raise

    def get_current_regime(self) -> MarketRegime | None:
        """Get most recent regime from database."""
        return self.db.query(MarketRegime).order_by(
            MarketRegime.timestamp.desc()
        ).first()

    def process_batch(self, limit: int = 1) -> dict:
        """Process market regime detection."""
        try:
            result = self.detect_regime()
            return {
                'success': True,
                'regime_detected': result['regime'] if result else None,
                'regimes_updated': 1 if result else 0
            }
        except Exception as e:
            logger.error(f"Error in process_batch: {e}")
            return {
                'success': False,
                'error': str(e),
                'regimes_updated': 0
            }

    def get_statistics(self) -> dict:
        """Get regime statistics."""
        from sqlalchemy import func

        total_regimes = self.db.query(MarketRegime).count()

        # Most recent regime
        current = self.get_current_regime()

        # Regime distribution (last 30 days)
        thirty_days_ago = datetime.now(UTC) - timedelta(days=30)
        recent_regimes = self.db.query(MarketRegime).filter(
            MarketRegime.timestamp >= thirty_days_ago
        ).all()

        # Count regime types
        vol_counts = {}
        trend_counts = {}

        for reg in recent_regimes:
            vol = reg.regime.get('volatility')
            trend = reg.regime.get('trend')

            vol_counts[vol] = vol_counts.get(vol, 0) + 1
            trend_counts[trend] = trend_counts.get(trend, 0) + 1

        return {
            'total_regimes_tracked': total_regimes,
            'current_regime': current.regime if current else None,
            'current_metadata': current.regime_metadata if current else None,
            'last_30d_volatility': vol_counts,
            'last_30d_trend': trend_counts
        }
