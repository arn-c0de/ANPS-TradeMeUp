"""
Prediction Details Popup - Centralized Modal for Prediction Details

This module provides a shared popup/modal component for displaying detailed
prediction information. It can be used by multiple tabs (predictions, simulations, etc.)
"""

import logging
import dash_bootstrap_components as dbc
from dash import html
from sqlalchemy.orm import Session, joinedload, defer
from sqlalchemy import desc, and_
from datetime import datetime, timezone

from src.models.predictions import Prediction, PredictionOutcome
from src.models.trading_simulation import TradingSimulation
from src.models.entities import Entity
from src.models.raw_news import RawNews
from src.models.processed_news import ProcessedNews
from src.models.analysis import ImpactScore
from src.services.prediction_performance_service import prediction_performance_service
from src.utils.json_helpers import ensure_dict as _ensure_dict, ensure_list as _ensure_list

logger = logging.getLogger(__name__)


def _format_price_ui(p):
    """Format prices with higher precision for sub-dollar values."""
    if p is None:
        return "N/A"
    try:
        p = float(p)
    except Exception:
        return str(p)
    return f"${p:.4f}" if abs(p) < 1.0 else f"${p:,.2f}"


def _format_saved_performance(pred, entity, outcome, load_live_prices=False):
    """Format saved PredictionOutcome for display

    Args:
        pred: Prediction object
        entity: Entity object
        outcome: PredictionOutcome object from database
        load_live_prices: Whether to load live prices (slow) or use only saved data (fast)

    Returns:
        dict: Performance data in same format as prediction_performance_service
    """
    from src.services.market_data import MarketDataProvider

    # Get direction from prediction
    probs = _ensure_dict(pred.direction_probabilities, {})
    predicted_direction = max(probs, key=probs.get) if probs else "flat"

    # Initialize variables
    ticker = entity.entity_id if entity else None
    current_price = 0
    prediction_price = 0
    high_since = 0
    low_since = 0
    volatility = 0
    return_24h = 0
    price_24h_ago = 0  # Add tracking for 24h ago price

    logger.info(f"🔍 _format_saved_performance for ticker: {ticker}, load_live_prices: {load_live_prices}")

    # Only load live prices if explicitly requested (slow operation)
    if ticker and load_live_prices:
        try:
            market_data = MarketDataProvider()

            # Calculate days since prediction (use timezone-aware datetime)
            days_since = (datetime.now(timezone.utc) - pred.timestamp).days if pred.timestamp else 0
            logger.info(f"   Days since prediction: {days_since}")

            # Get historical data since prediction
            period_days = max(days_since + 5, 7)
            if period_days <= 7:
                period = "7d"
            elif period_days <= 30:
                period = "1mo"
            elif period_days <= 90:
                period = "3mo"
            else:
                period = "1y"

            logger.info(f"   Fetching historical data: period={period}")
            hist_data = market_data.get_historical_data(ticker, period=period, interval="1d")

            if hist_data is not None and len(hist_data) > 0:
                logger.info(f"   Got {len(hist_data)} days of historical data")

                # Get prediction date
                prediction_date = pred.timestamp.date() if pred.timestamp else datetime.now(timezone.utc).date()
                logger.info(f"   Prediction date: {prediction_date}")

                # Filter data from prediction date onwards
                hist_data_filtered = hist_data[hist_data.index >= prediction_date.strftime('%Y-%m-%d')]

                if len(hist_data_filtered) > 0:
                    logger.info(f"   Found {len(hist_data_filtered)} days since prediction")
                    prediction_price = hist_data_filtered.iloc[0]['Close']

                    # Use the latest available close price (could be from today or yesterday)
                    current_price = hist_data_filtered.iloc[-1]['Close']

                    high_since = hist_data_filtered['High'].max()
                    low_since = hist_data_filtered['Low'].min()

                    if len(hist_data_filtered) > 1:
                        returns = hist_data_filtered['Close'].pct_change().dropna()
                        volatility = returns.std() * 100 if len(returns) > 0 else 0

                    logger.info(f"   Entry: {_format_price_ui(prediction_price)}, Current: {_format_price_ui(current_price)}")
                    logger.info(f"   High: {_format_price_ui(high_since)}, Low: {_format_price_ui(low_since)}, Vol: {volatility:.2f}%")
                else:
                    logger.warning(f"   No data since prediction date, using all available")
                    prediction_price = hist_data.iloc[0]['Close']
                    current_price = hist_data.iloc[-1]['Close']
                    high_since = hist_data['High'].max()
                    low_since = hist_data['Low'].min()
                    if len(hist_data) > 1:
                        returns = hist_data['Close'].pct_change().dropna()
                        volatility = returns.std() * 100 if len(returns) > 0 else 0

                # Calculate 24h return - use the last 2 days of ALL historical data
                if len(hist_data) >= 2:
                    # Get yesterday's close and today's (or latest) close
                    price_24h_ago = hist_data.iloc[-2]['Close']
                    price_today = hist_data.iloc[-1]['Close']
                    return_24h = ((price_today - price_24h_ago) / price_24h_ago) * 100
                    logger.info(f"   24h return: {return_24h:+.2f}% (from ${price_24h_ago:.2f} to ${price_today:.2f})")
                elif len(hist_data) == 1:
                    # Only one day of data available
                    price_24h_ago = hist_data.iloc[0]['Close']
                    return_24h = 0
                    logger.info(f"   24h return: Only 1 day of data available")

                # Try to get real-time current price (more accurate than historical close)
                try:
                    live_price_data = market_data.get_live_price(ticker)
                    if live_price_data:
                        # Support multiple provider key names for compatibility
                        live_current_price = live_price_data.get('price') or live_price_data.get('current_price') or live_price_data.get('currentPrice')
                        if live_current_price and live_current_price > 0:
                            logger.info(f"   Got live price: ${live_current_price:.2f} (vs historical ${current_price:.2f})")
                            current_price = live_current_price

                            # Recalculate 24h return with live current price
                            if price_24h_ago > 0:
                                return_24h = ((current_price - price_24h_ago) / price_24h_ago) * 100
                                logger.info(f"   Updated 24h return with live price: {return_24h:+.2f}%")
                except Exception as live_error:
                    logger.debug(f"   Could not get live price: {live_error}")
            else:
                logger.warning(f"   No historical data available for {ticker}")

        except Exception as e:
            logger.error(f"❌ Error getting price data for {ticker}: {e}")
            logger.exception(e)
    elif ticker and not load_live_prices:
        logger.info(f"   Skipping live price data for fast loading")

    # Calculate days since prediction (use timezone-aware datetime)
    days_since = (datetime.now(timezone.utc) - pred.timestamp).days if pred.timestamp else 0

    # Calculate actual return from live prices if available, otherwise use saved data
    actual_return_pct = 0
    if prediction_price > 0 and current_price > 0:
        actual_return_pct = ((current_price - prediction_price) / prediction_price) * 100
        logger.info(f"   Calculated return: {actual_return_pct:+.2f}%")
    else:
        # Fallback to saved outcome - already stored as percentage
        actual_return_pct = outcome.actual_return or 0
        logger.info(f"   Using saved return: {actual_return_pct:+.2f}%")

    # Recalculate actual direction from current return
    if actual_return_pct > 0.001:
        actual_direction = "up"
    elif actual_return_pct < -0.001:
        actual_direction = "down"
    else:
        actual_direction = "flat"

    # Recalculate if prediction is correct
    is_correct = (predicted_direction == actual_direction)
    strategy_result = "✅ CORRECT" if is_correct else "❌ WRONG"

    return {
        'total_return_pct': actual_return_pct,
        'is_correct': is_correct,
        'strategy_result': strategy_result,
        'return_24h_pct': return_24h,
        'days_since_prediction': days_since,
        'prediction_price': prediction_price,
        'current_price': current_price,
        'price_24h_ago': price_24h_ago,
        'high_since_prediction': high_since,
        'low_since_prediction': low_since,
        'volatility': volatility,
        'predicted_direction': predicted_direction,
        'actual_direction': actual_direction
    }


def _save_performance(db: Session, prediction_id, performance: dict, label: str) -> dict | None:
    """Persist performance data for a prediction.

    Args:
        db: Active database session
        prediction_id: UUID of the prediction
        performance: Performance data dict to save
        label: Short description used in log messages ("updated" or "new")

    Returns:
        A sync trigger dict to notify the UI on success, or None on failure.
    """
    try:
        logger.info(f"💾 Saving {label} performance to database")
        prediction_performance_service.save_prediction_performance(
            prediction_id, performance, db
        )
        db.commit()
        tr = performance.get('total_return_pct')
        logger.info(f"✅ Saved {label} performance: {tr:.2f}%" if tr is not None else f"✅ Saved {label} performance: N/A")
        # Notify UI to refresh predictions table
        return {"prediction_id": prediction_id, "ts": datetime.now(timezone.utc).isoformat()}
    except Exception as save_error:
        logger.warning(f"Could not save {label} performance: {save_error}")
        db.rollback()
        return None


def _resolve_performance(db: Session, pred: Prediction, entity: Entity | None,
                         prediction_id, load_performance: bool) -> tuple[dict | None, dict | None]:
    """Resolve performance data for a prediction.

    Prefers a saved PredictionOutcome (fast). Live prices are only fetched when
    load_performance is True; freshly fetched data is written back to the
    database, in which case a sync trigger is returned so the UI can refresh.

    Returns:
        Tuple of (performance dict or None, sync_trigger dict or None)
    """
    # Note: pred.outcome is a list due to backref, so we take first element if exists
    saved_outcome = pred.outcome[0] if hasattr(pred, 'outcome') and pred.outcome else None

    logger.info(f"🔍 Checking saved performance for {prediction_id}")
    logger.info(f"   Found outcome: {saved_outcome is not None}")
    if saved_outcome:
        logger.info(f"   Actual return: {saved_outcome.actual_return}")
        logger.info(f"   Direction correct: {saved_outcome.direction_correct}")
        logger.info(f"   Timestamp: {saved_outcome.evaluation_timestamp}")

    performance = None
    sync_trigger = None

    if saved_outcome and saved_outcome.actual_return is not None:
        # Use saved performance data; only fetch live prices if explicitly requested
        try:
            logger.info(f"✅ Using saved performance for modal (load_live_prices={load_performance})")
            performance = _format_saved_performance(pred, entity, saved_outcome, load_live_prices=load_performance)
            # If we loaded live prices, save them back to the database
            if load_performance and performance:
                sync_trigger = _save_performance(db, prediction_id, performance, label="updated")
        except Exception as e:
            logger.warning(f"Could not format saved performance: {e}")
    elif load_performance:
        # Load live performance (and save it)
        try:
            logger.info("🔄 Loading live performance (load_performance=True)")
            performance = prediction_performance_service.get_prediction_performance(pred, entity)
            if performance:
                sync_trigger = _save_performance(db, prediction_id, performance, label="new")
        except Exception as e:
            logger.warning(f"Could not load performance: {e}")
    else:
        logger.info("ℹ️ No saved performance and load_performance=False")

    return performance, sync_trigger


def _load_latest_simulation(db: Session, prediction_id) -> TradingSimulation | None:
    """Load the most recent trading simulation for a prediction, if any."""
    simulation = db.query(TradingSimulation).filter(
        TradingSimulation.prediction_id == prediction_id
    ).order_by(desc(TradingSimulation.created_at)).first()

    logger.info(f"🧪 Checking simulation for {prediction_id}")
    logger.info(f"   Found simulation: {simulation is not None}")
    return simulation


def _build_modal_title(pred: Prediction, entity: Entity | None, entity_name: str,
                       direction: str, direction_emoji: str) -> html.Div:
    """Build the modal title with a clickable chart button for the entity."""
    # Use entity_id (ticker) in button index, show entity_name as text
    ticker_symbol = entity.entity_id if entity else pred.entity_id
    return html.Div([
        html.Span(f"{direction_emoji} ", style={"fontSize": "1.5rem"}),
        dbc.Button(
            ["📊 ", entity_name],
            id={"type": "open-chart-btn", "index": ticker_symbol},
            color="link",
            className="p-0 text-decoration-none text-primary",
            style={"fontSize": "1.5rem", "fontWeight": "bold"},
            title=f"Open {entity_name} chart",
            n_clicks=0
        ),
        html.Span(f" - {direction.upper()} Prediction", style={"fontSize": "1.5rem"})
    ], className="d-flex align-items-center")


def _build_news_section(db: Session, pred: Prediction):
    """Build the related news card (or a warning alert if no news is linked)."""
    news_ids = _ensure_list(pred.related_news_ids, [])
    if not news_ids:
        return dbc.Alert("No related news found", color="warning")

    # Extract first news ID from the array
    if isinstance(news_ids, list) and len(news_ids) > 0:
        news_id = news_ids[0]
    else:
        news_id = news_ids

    # OPTIMIZED: Combine 3 separate queries into single JOIN query
    # This reduces 3 database roundtrips to just 1
    news_data = db.query(
        RawNews, ProcessedNews, ImpactScore
    ).outerjoin(
        ProcessedNews,
        RawNews.news_id == ProcessedNews.news_id
    ).outerjoin(
        ImpactScore,
        and_(
            ImpactScore.news_id == RawNews.news_id,
            ImpactScore.entity_id == pred.entity_id
        )
    ).options(defer(ProcessedNews.embedding)).filter(
        RawNews.news_id == news_id
    ).first()

    # Unpack results
    raw_news, processed, impact = news_data if news_data else (None, None, None)

    return dbc.Card([
        dbc.CardHeader(html.Div("📰 News", style={"fontWeight": "bold"}), className="py-1"),
        dbc.CardBody([
            html.A(
                raw_news.title if raw_news else "Unknown",
                href=raw_news.url if raw_news and raw_news.url else "#",
                target="_blank",
                className="text-primary mb-1",
                style={"fontWeight": "500", "textDecoration": "none", "display": "block", "cursor": "pointer"}
            ) if raw_news and raw_news.url else html.Div(
                raw_news.title if raw_news else "Unknown",
                className="text-primary mb-1",
                style={"fontWeight": "500"}
            ),
            html.Small([
                html.Strong("Source: "),
                html.Span(raw_news.source if raw_news else "Unknown"),
                " | ",
                html.Strong("Published: "),
                html.Span(raw_news.published_at.strftime("%Y-%m-%d %H:%M") if raw_news and raw_news.published_at else "Unknown")
            ], className="d-block mb-2"),
            html.Small(raw_news.full_text[:300] + "..." if raw_news and raw_news.full_text and len(raw_news.full_text) > 300
                   else raw_news.full_text if raw_news and raw_news.full_text else "No content available",
                   className="text-muted d-block", style={"maxHeight": "120px", "overflowY": "auto"}),
            html.Hr(className="my-2") if processed else None,
            html.Small([
                html.Strong("Sentiment: "),
                html.Span(f"Overall {_ensure_dict(processed.sentiment, {}).get('overall', 0):.2f}",
                         className="text-success" if processed and _ensure_dict(processed.sentiment, {}).get('overall', 0) > 0 else "text-danger"),
                " | ",
                html.Strong("Confidence: "),
                html.Span(f"{_ensure_dict(processed.sentiment, {}).get('confidence', 0):.2f}",
                         className="text-info"),
                " | ",
                html.Strong("Event: "),
                dbc.Badge(processed.event_type, color="primary", className="py-0 px-1") if processed.event_type else ""
            ], className="d-block") if processed and processed.sentiment else None,
            html.Hr(className="my-2") if impact else None,
            html.Small([
                html.Strong("Impact: "),
                html.Span(f"{impact.impact_score:.3f}", className="text-warning")
            ], className="d-block") if impact else None
        ], className="py-2")
    ], className="mb-2")


def _build_drivers_section(pred: Prediction) -> dbc.Card:
    """Build the key drivers card (top 5 drivers with importance bars)."""
    drivers = _ensure_list(pred.key_drivers, [])
    return dbc.Card([
        dbc.CardHeader(html.Div("🎯 Key Drivers", style={"fontWeight": "bold"}), className="py-1"),
        dbc.CardBody([
            dbc.Table([
                html.Thead(html.Tr([
                    html.Th("Feature"),
                    html.Th("Importance"),
                    html.Th("Weight")
                ])),
                html.Tbody([
                    html.Tr([
                        html.Td(d.get('driver', 'Unknown')),
                        html.Td(
                            dbc.Progress(value=d.get('importance', 0) * 100,
                                       className="mb-0", style={"height": "14px"})
                        ),
                        html.Td(f"{d.get('importance', 0):.1%}")
                    ]) for d in drivers[:5]  # Top 5
                ])
            ], bordered=True, striped=True, size="sm") if drivers else html.Small("No driver data available", className="text-muted")
        ], className="py-2")
    ], className="mb-2")


def _build_performance_section(performance: dict | None, pred: Prediction, load_performance: bool):
    """Build the live performance section (metrics row + entry/current prices).

    Falls back to an info alert when performance data is unavailable or
    has not been loaded yet.
    """
    if not performance:
        if load_performance:
            # Performance was requested but not available
            return dbc.Alert(
                html.Small("⚠️ Performance data not available for this entity (may not be a tradable stock)"),
                color="info", className="mb-2 py-2"
            )
        # Performance not yet loaded
        return dbc.Alert([
            html.Small([
                "📊 Live performance data not loaded. ",
                html.Strong("Click the 🔄 Refresh button above to load it.")
            ])
        ], color="light", className="mb-2 py-2")

    total_return = performance['total_return_pct']
    return_color = "success" if total_return > 0 else "danger" if total_return < 0 else "secondary"

    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.Div("📊 Live Performance", style={"fontWeight": "bold"}), className="py-1"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            dbc.Card([
                                dbc.CardBody([
                                    html.H5(f"{total_return:+.2f}%", className=f"text-{return_color} text-center mb-0"),
                                    html.Small("Return", className="text-center text-muted d-block")
                                ], className="py-1 px-2")
                            ], color=return_color, outline=True)
                        ], width=3),
                        dbc.Col([
                            dbc.Card([
                                dbc.CardBody([
                                    html.H5(performance['strategy_result'].split()[0], className="text-center mb-0"),
                                    html.Small(performance['strategy_result'].split()[1] if len(performance['strategy_result'].split()) > 1 else "", className="text-center d-block")
                                ], className="py-1 px-2")
                            ], color="light")
                        ], width=3),
                        dbc.Col([
                            dbc.Card([
                                dbc.CardBody([
                                    html.H5(f"{performance['return_24h_pct']:+.2f}%",
                                           className=f"text-{'success' if performance['return_24h_pct'] > 0 else 'danger' if performance['return_24h_pct'] < 0 else 'secondary'} text-center mb-0"),
                                    html.Small("24h", className="text-center text-muted d-block")
                                ], className="py-1 px-2")
                            ], color="light")
                        ], width=3),
                        dbc.Col([
                            dbc.Card([
                                dbc.CardBody([
                                    html.H5(f"{performance['days_since_prediction']}d", className="text-center mb-0"),
                                    html.Small("Days", className="text-center text-muted d-block")
                                ], className="py-1 px-2")
                            ], color="light")
                        ], width=3)
                    ], className="mb-2"),
                    dbc.Row([
                        dbc.Col([
                            html.Small([
                                html.Strong("Entry: "),
                                html.Span(_format_price_ui(performance['prediction_price'])),
                                html.Span(f" ({pred.timestamp.strftime('%Y-%m-%d %H:%M')})" if pred.timestamp else "", className="text-muted"),
                                " → ",
                                html.Strong("Now: "),
                                html.Span(_format_price_ui(performance['current_price']), className=f"text-{return_color}"),
                                html.Span(f" ({performance['timestamp'].strftime('%Y-%m-%d %H:%M')})" if performance.get('timestamp') else "", className="text-muted"),
                                html.Span(f"({_format_price_ui(performance['current_price'] - performance['prediction_price'])})", className=f"text-{return_color}")
                            ], className="d-block")
                        ], width=6),
                        dbc.Col([
                            html.Small([
                                html.Strong("Range: "),
                                html.Span(f"{_format_price_ui(performance.get('low_since_prediction'))} - {_format_price_ui(performance.get('high_since_prediction'))}"),
                                " | ",
                                html.Strong("Vol: "),
                                html.Span(f"{performance['volatility']:.1f}%")
                            ], className="d-block")
                        ], width=6)
                    ])
                ], className="py-2")
            ], className="mb-2")
        ], width=12)
    ], className="mb-2")


def _exit_ladder_position_pct(entry_price, current_price, take_profit_price) -> float:
    """Position of current price on the entry → take-profit ladder, in percent.

    0% = entry, 100% = take profit reached. Values are capped at -20% / 120%
    so prices slightly outside the range still render on the visual ladder.
    Returns 50 (midpoint) when the inputs are missing or degenerate.
    """
    if not (entry_price and take_profit_price and current_price):
        return 50
    total_range = abs(take_profit_price - entry_price)
    if total_range <= 0:
        return 50
    if entry_price < take_profit_price:
        # Long position (UP prediction)
        current_pct = ((current_price - entry_price) / total_range) * 100
    else:
        # Short position (DOWN prediction)
        current_pct = ((entry_price - current_price) / total_range) * 100
    # Allow >100% (above TP) and <0% (below entry), capped for display
    return max(-20, min(120, current_pct))


def _build_exit_strategy_section(simulation: TradingSimulation | None, performance: dict | None) -> dbc.Row | None:
    """Build the exit strategy (stop loss & take profit) section.

    Returns None when there is no simulation or no stop loss price.
    """
    if not simulation or simulation.stop_loss_price is None:
        return None

    entry_price = performance.get('prediction_price') if performance else None
    current_price = performance.get('current_price') if performance else None

    # Position in entry → take-profit range (for the visual ladder)
    current_pct = _exit_ladder_position_pct(entry_price, current_price, simulation.take_profit_price)

    # Risk/reward ratio color
    rr_ratio = simulation.risk_reward_ratio or 0
    rr_color = "success" if rr_ratio >= 2.0 else "warning" if rr_ratio >= 1.5 else "danger"

    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.Div("🎯 Exit Strategy - Stop Loss & Take Profit", style={"fontWeight": "bold"}), className="py-1"),
                dbc.CardBody([
                    # Method and Risk/Reward
                    dbc.Row([
                        dbc.Col([
                            dbc.Card([
                                dbc.CardBody([
                                    html.Small("Method", className="text-muted d-block"),
                                    dbc.Badge(
                                        (simulation.stop_loss_type or "unknown").replace("_", " ").title(),
                                        color="info",
                                        className="mt-1"
                                    )
                                ], className="py-1 px-2 text-center")
                            ], color="light")
                        ], width=6),
                        dbc.Col([
                            dbc.Card([
                                dbc.CardBody([
                                    html.Small("Risk:Reward", className="text-muted d-block"),
                                    html.H6(
                                        f"1:{rr_ratio:.2f}" if rr_ratio else "N/A",
                                        className=f"text-{rr_color} mb-0 mt-1"
                                    )
                                ], className="py-1 px-2 text-center")
                            ], color="light")
                        ], width=6)
                    ], className="mb-2"),

                    # Stop Loss and Take Profit Side by Side
                    dbc.Row([
                        # Stop Loss
                        dbc.Col([
                            dbc.Card([
                                dbc.CardBody([
                                    html.Div([
                                        html.Strong("🛑 Stop Loss", className="text-danger d-block mb-2"),
                                        html.Div([
                                            html.Small("Price:", className="text-muted"),
                                            html.Strong(
                                                f" {_format_price_ui(simulation.stop_loss_price)}",
                                                className="text-danger"
                                            )
                                        ], className="mb-1"),
                                        html.Div([
                                            html.Small("Distance:", className="text-muted"),
                                            html.Strong(
                                                f" {simulation.stop_loss_pct:.2f}%",
                                                className="text-danger"
                                            )
                                        ])
                                    ])
                                ], className="py-2")
                            ], outline=True, color="danger")
                        ], width=6),

                        # Take Profit
                        dbc.Col([
                            dbc.Card([
                                dbc.CardBody([
                                    html.Div([
                                        html.Strong("✅ Take Profit", className="text-success d-block mb-2"),
                                        html.Div([
                                            html.Small("Price:", className="text-muted"),
                                            html.Strong(
                                                f" {_format_price_ui(simulation.take_profit_price)}",
                                                className="text-success"
                                            )
                                        ], className="mb-1"),
                                        html.Div([
                                            html.Small("Target:", className="text-muted"),
                                            html.Strong(
                                                f" +{simulation.take_profit_pct:.2f}%",
                                                className="text-success"
                                            )
                                        ])
                                    ])
                                ], className="py-2")
                            ], outline=True, color="success")
                        ], width=6)
                    ], className="mb-3"),

                    # Visual Price Ladder
                    html.Div([
                        html.Small("Price Levels:", className="text-muted d-block mb-2"),
                        html.Div([
                            # Take Profit level
                            html.Div([
                                html.Span("🎯 ", style={"fontSize": "0.9rem"}),
                                html.Small(
                                    f"Take Profit: {_format_price_ui(simulation.take_profit_price)}",
                                    className="text-success"
                                )
                            ], className="mb-1"),
                            # Visual progress bar
                            dbc.Progress([
                                dbc.Progress(
                                    value=current_pct,
                                    color="info",
                                    bar=True,
                                    label=f"Current: {_format_price_ui(current_price)}" if current_price else "—",
                                    style={"fontSize": "0.7rem"}
                                )
                            ], value=100, color="light", className="mb-1", style={"height": "25px"}),
                            # Entry level
                            html.Div([
                                html.Span("📍 ", style={"fontSize": "0.9rem"}),
                                html.Small(
                                    f"Entry: {_format_price_ui(entry_price)}",
                                    className="text-info"
                                )
                            ], className="mb-1"),
                            # Stop Loss level
                            html.Div([
                                html.Span("🛑 ", style={"fontSize": "0.9rem"}),
                                html.Small(
                                    f"Stop Loss: {_format_price_ui(simulation.stop_loss_price)}",
                                    className="text-danger"
                                )
                            ])
                        ], style={
                            "backgroundColor": "#2a2a2a",
                            "padding": "10px",
                            "borderRadius": "5px"
                        })
                    ], className="mb-2"),

                    # Trailing Stop (if applicable)
                    # NOTE: preserved from the original code -- `self` is undefined at
                    # module level, so when trailing_stop_price is not set this raises
                    # NameError, which is caught by get_prediction_details' except.
                    html.Div([
                        html.Hr(className="my-2"),
                        html.Small([
                            html.Strong("🔄 Trailing Stop: "),
                            html.Span(
                                f"{_format_price_ui(simulation.trailing_stop_price)}" if simulation.trailing_stop_price else "Not activated",
                                className="text-warning" if simulation.trailing_stop_price else "text-muted"
                            )
                        ], className="d-block")
                    ]) if simulation.trailing_stop_price or self.config.get("stop_loss_take_profit", {}).get("trailing_stop", {}).get("enabled") else None

                ], className="py-2")
            ], className="mb-2")
        ], width=12)
    ], className="mb-2")


def _build_simulation_section(simulation: TradingSimulation | None, portfolio_capital: float,
                              currency: str, risk_adjustment: float) -> dbc.Row | None:
    """Build the trading simulation analysis section.

    Includes decision/risk/returns summary, cost breakdown, penny stock info,
    risk components and the position/investment recommendation.
    Returns None when no simulation exists.
    """
    if not simulation:
        return None

    decision = simulation.decision or "hold"
    decision_color = {
        "buy": "success",
        "sell": "danger",
        "hold": "secondary"
    }.get(decision, "secondary")

    risk_score = simulation.risk_score or 0
    risk_color = "danger" if risk_score > 0.7 else "warning" if risk_score > 0.4 else "success"

    # Extract penny stock info from metadata
    penny_stock_info = (simulation.simulation_metadata or {}).get("penny_stock_info", {})
    is_penny_stock = penny_stock_info.get("is_penny_stock", False)
    is_ultra_penny = penny_stock_info.get("is_ultra_penny_stock", False)
    cost_method = penny_stock_info.get("cost_method", "standard")
    shares_multiplier = penny_stock_info.get("shares_multiplier", 1.0)

    expected_return = simulation.expected_return_pct or 0
    expected_color = "success" if expected_return > 0 else "danger" if expected_return < 0 else "secondary"

    actual_return = simulation.actual_return_pct or 0
    actual_color = "success" if actual_return > 0 else "danger" if actual_return < 0 else "secondary"

    cost_bps = simulation.transaction_cost_bps or 0
    cost_breakdown = _ensure_dict(simulation.cost_breakdown, {})
    risk_breakdown = _ensure_dict(simulation.risk_breakdown, {})
    sim_metadata = _ensure_dict(simulation.simulation_metadata, {})

    # Extract detailed metrics
    position_info = sim_metadata.get("position_info", {})
    cost_details = sim_metadata.get("cost_details", {})
    constraints = sim_metadata.get("constraints", {})
    market_snapshot = sim_metadata.get("market_snapshot", {})

    # Calculate recommended investment size
    currency_symbol = {"EUR": "€", "USD": "$", "GBP": "£"}.get(currency, currency)
    position_size_pct = position_info.get('position_size_pct', 0)
    base_investment = portfolio_capital * (position_size_pct / 100) if position_size_pct > 0 else 0
    risk_factor = 1.0 - (risk_score * risk_adjustment) if risk_score is not None else 1.0
    recommended_investment = base_investment * risk_factor

    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.Div("🧪 Trading Simulation - Complete Analysis", style={"fontWeight": "bold"}), className="py-1"),
                dbc.CardBody([
                    # Timestamp and Horizon
                    dbc.Row([
                        dbc.Col([
                            html.Small([
                                html.Span("🕒 ", style={"fontSize": "0.9rem"}),
                                html.Strong("Simulation Time: ", className="text-muted"),
                                html.Span(
                                    simulation.created_at.strftime("%Y-%m-%d %H:%M:%S") if simulation.created_at else "—",
                                    className="text-info"
                                )
                            ], className="me-3")
                        ], width="auto"),
                        dbc.Col([
                            html.Small([
                                html.Span("📅 ", style={"fontSize": "0.9rem"}),
                                html.Strong("Horizon: ", className="text-muted"),
                                dbc.Badge(
                                    simulation.horizon if simulation.horizon else "—",
                                    color="secondary",
                                    className="ms-1"
                                )
                            ])
                        ], width="auto")
                    ], className="mb-2"),

                    # Top Row: Decision, Risk Score, Returns
                    dbc.Row([
                        dbc.Col([
                            dbc.Card([
                                dbc.CardBody([
                                    html.H5(dbc.Badge(decision.upper(), color=decision_color, className="px-2"),
                                           className="text-center mb-0"),
                                    html.Small("Decision", className="text-center text-muted d-block")
                                ], className="py-1 px-2")
                            ], color=decision_color, outline=True)
                        ], width=3),
                        dbc.Col([
                            dbc.Card([
                                dbc.CardBody([
                                    html.H5(f"{risk_score:.2f}" if risk_score is not None else "—", className=f"text-{risk_color} text-center mb-0"),
                                    html.Small("Risk Score", className="text-center text-muted d-block")
                                ], className="py-1 px-2")
                            ], color="light")
                        ], width=3),
                        dbc.Col([
                            dbc.Card([
                                dbc.CardBody([
                                    html.H5(f"{expected_return:+.2f}%", className=f"text-{expected_color} text-center mb-0"),
                                    html.Small("Expected Return", className="text-center text-muted d-block")
                                ], className="py-1 px-2")
                            ], color="light")
                        ], width=3),
                        dbc.Col([
                            dbc.Card([
                                dbc.CardBody([
                                    html.H5(f"{actual_return:+.2f}%", className=f"text-{actual_color} text-center mb-0"),
                                    html.Small("Actual Return", className="text-center text-muted d-block")
                                ], className="py-1 px-2")
                            ], color="light")
                        ], width=3)
                    ], className="mb-3"),

                    # Show note when simulation was skipped/invalid
                    dbc.Row([
                        dbc.Col([
                            dbc.Alert(sim_metadata.get('note'), color="warning", className="mb-2")
                        ], width=12)
                    ]) if sim_metadata.get('note') else None,

                    # Cost Breakdown Section
                    dbc.Row([
                        dbc.Col([
                            dbc.Card([
                                dbc.CardHeader([
                                    html.Strong("💰 Cost Breakdown "),
                                    html.Small(f"(Total: {cost_bps:.1f} bps)", className="text-muted")
                                ], className="py-1"),
                                dbc.CardBody([
                                    dbc.Row([
                                        dbc.Col([
                                            html.Small("Commission:", className="text-muted"),
                                            html.Strong(f" {cost_breakdown.get('commission_bps', 0):.2f} bps")
                                        ], width=4),
                                        dbc.Col([
                                            html.Small("Spread:", className="text-muted"),
                                            html.Strong(f" {cost_breakdown.get('spread_bps', 0):.2f} bps")
                                        ], width=4),
                                        dbc.Col([
                                            html.Small("Slippage:", className="text-muted"),
                                            html.Strong(f" {cost_breakdown.get('slippage_bps', 0):.2f} bps")
                                        ], width=4)
                                    ], className="mb-2"),
                                    dbc.Row([
                                        dbc.Col([
                                            html.Small("Market Impact:", className="text-muted"),
                                            html.Strong(f" {cost_breakdown.get('market_impact_bps', 0):.2f} bps")
                                        ], width=4),
                                        dbc.Col([
                                            html.Small("Overnight Financing:", className="text-muted"),
                                            html.Strong(f" {cost_breakdown.get('overnight_cost_bps', 0):.2f} bps")
                                        ], width=4),
                                        dbc.Col([
                                            html.Small("Borrow Cost:", className="text-muted"),
                                            html.Strong(f" {cost_breakdown.get('borrow_cost_bps', 0):.2f} bps")
                                        ], width=4)
                                    ], className="mb-2"),
                                    dbc.Row([
                                        dbc.Col([
                                            html.Small("Regulatory (SEC/FINRA):", className="text-muted"),
                                            html.Strong(f" {cost_breakdown.get('regulatory_bps', 0):.2f} bps")
                                        ], width=4),
                                        dbc.Col([
                                            html.Small("Cost Ratio:", className="text-muted"),
                                            html.Strong(f" {cost_details.get('cost_ratio', 0):.2f}",
                                                       className="text-warning" if cost_details.get('cost_ratio', 0) > 0.5 else "")
                                        ], width=4)
                                    ])
                                ], className="py-2")
                            ], color="dark", className="mb-2")
                        ], width=12)
                    ]),

                    # Penny Stock Info Section (if applicable)
                    dbc.Row([
                        dbc.Col([
                            dbc.Alert([
                                html.Div([
                                    html.Strong(
                                        "⭐ Ultra-Penny Stock Handling: " if is_ultra_penny else "💎 Penny Stock Handling: ",
                                        className="text-info"
                                    ),
                                    html.Span(f"Price ${penny_stock_info.get('price', 0):.6f} - " if is_ultra_penny else f"Price ${penny_stock_info.get('price', 0):.4f} - ", className="text-muted"),
                                    dbc.Badge(
                                        cost_method.replace("_", " ").title(),
                                        color="warning" if is_ultra_penny else "info",
                                        className="ms-2"
                                    ),
                                ]),
                                html.Small([
                                    f"Ultra-cheap stock: Using {shares_multiplier:.0f}x shares ({penny_stock_info.get('shares_used', 0):,} shares) for realistic position sizing. " if is_ultra_penny else "",
                                    "Alternative cost calculation used for low-priced stocks to prevent unrealistic basis point calculations."
                                ], className="d-block mt-2 text-muted")
                            ], color="warning" if is_ultra_penny else "info", className="mb-2")
                        ], width=12)
                    ]) if is_penny_stock else None,

                    # Risk Components Breakdown Section
                    dbc.Row([
                        dbc.Col([
                            dbc.Card([
                                dbc.CardHeader([
                                    html.Strong("⚠️ Risk Components "),
                                    html.Small(f"(Weighted Score: {risk_score:.2f})" if risk_score is not None else "(Weighted Score: N/A)", className=f"text-{risk_color}")
                                ], className="py-1"),
                                dbc.CardBody([
                                    dbc.Row([
                                        dbc.Col([
                                            html.Small("Model Uncertainty:", className="text-muted d-block"),
                                            dbc.Progress(value=risk_breakdown.get('model_uncertainty', 0) * 100,
                                                       color="warning", className="mb-1", style={"height": "12px"}),
                                            html.Small(f"{risk_breakdown.get('model_uncertainty', 0):.3f}", className="text-muted")
                                        ], width=4),
                                        dbc.Col([
                                            html.Small("Divergence:", className="text-muted d-block"),
                                            dbc.Progress(value=risk_breakdown.get('divergence_magnitude', 0) * 100,
                                                       color="warning", className="mb-1", style={"height": "12px"}),
                                            html.Small(f"{risk_breakdown.get('divergence_magnitude', 0):.3f}", className="text-muted")
                                        ], width=4),
                                        dbc.Col([
                                            html.Small("Volatility Regime:", className="text-muted d-block"),
                                            dbc.Progress(value=risk_breakdown.get('volatility_regime', 0) * 100,
                                                       color="danger", className="mb-1", style={"height": "12px"}),
                                            html.Small(f"{risk_breakdown.get('volatility_regime', 0):.3f}", className="text-muted")
                                        ], width=4)
                                    ], className="mb-2"),
                                    dbc.Row([
                                        dbc.Col([
                                            html.Small("Liquidity Stress:", className="text-muted d-block"),
                                            dbc.Progress(value=risk_breakdown.get('liquidity_stress', 0) * 100,
                                                       color="info", className="mb-1", style={"height": "12px"}),
                                            html.Small(f"{risk_breakdown.get('liquidity_stress', 0):.3f}", className="text-muted")
                                        ], width=4),
                                        dbc.Col([
                                            html.Small("Position Concentration:", className="text-muted d-block"),
                                            dbc.Progress(value=risk_breakdown.get('position_concentration', 0) * 100,
                                                       color="warning", className="mb-1", style={"height": "12px"}),
                                            html.Small(f"{risk_breakdown.get('position_concentration', 0):.3f}", className="text-muted")
                                        ], width=4),
                                        dbc.Col([
                                            html.Small("Liquidity Constraint:", className="text-muted d-block"),
                                            dbc.Progress(value=risk_breakdown.get('liquidity_constraint', 0) * 100,
                                                       color="info", className="mb-1", style={"height": "12px"}),
                                            html.Small(f"{risk_breakdown.get('liquidity_constraint', 0):.3f}", className="text-muted")
                                        ], width=4)
                                    ])
                                ], className="py-2")
                            ], color="dark", className="mb-2")
                        ], width=12)
                    ]),

                    # Position & Constraints Section
                    dbc.Row([
                        dbc.Col([
                            dbc.Card([
                                dbc.CardHeader([
                                    html.Strong("📍 Position & Investment Recommendation"),
                                    html.Small(f" (Portfolio: {currency_symbol}{portfolio_capital:,.0f})", className="text-muted ms-2")
                                ], className="py-1"),
                                dbc.CardBody([
                                    dbc.Row([
                                        dbc.Col([
                                            html.Small("Position Size:", className="text-muted"),
                                            html.Strong(f" {position_info.get('position_size_pct', 0):.1f}%",
                                                       className="text-info" if constraints.get('position_size_ok', True) else "text-danger")
                                        ], width=3),
                                        dbc.Col([
                                            html.Small("Position Value:", className="text-muted"),
                                            html.Strong(f" ${position_info.get('position_value_usd', 0):,.0f}")
                                        ], width=3),
                                        dbc.Col([
                                            html.Small("Daily Volume:", className="text-muted"),
                                            html.Strong(f" ${market_snapshot.get('volume_usd', 0):,.0f}",
                                                       className="text-info" if constraints.get('liquidity_ok', True) else "text-danger")
                                        ], width=3),
                                        dbc.Col([
                                            html.Small("Constraints:", className="text-muted"),
                                            html.Strong(" ✅ Pass" if not constraints.get('blocked_by', []) else f" ⚠️ {len(constraints.get('blocked_by', []))} violations",
                                                       className="text-success" if not constraints.get('blocked_by', []) else "text-warning")
                                        ], width=3)
                                    ], className="mb-2"),
                                    # Recommended Investment Row
                                    dbc.Row([
                                        dbc.Col([
                                            dbc.Alert([
                                                html.Div([
                                                    html.H5([
                                                        html.Span("💰 Recommended Investment: ", className="text-muted"),
                                                        html.Strong(f"{currency_symbol}{recommended_investment:,.0f}", className="text-success")
                                                    ], className="mb-2"),
                                                    html.Small([
                                                        f"Base ({position_size_pct:.1f}%): {currency_symbol}{base_investment:,.0f} × Risk Factor ({risk_factor:.3f}) = {currency_symbol}{recommended_investment:,.0f}"
                                                    ], className="text-muted")
                                                ])
                                            ], color="success", className="mb-0")
                                        ], width=12)
                                    ])
                                ], className="py-2")
                            ], color="dark")
                        ], width=12)
                    ])
                ], className="py-2")
            ], className="mb-2")
        ], width=12)
    ], className="mb-2")


def _build_overview_row(pred: Prediction, direction: str, direction_emoji: str, expected: dict) -> dbc.Row:
    """Build the overview row: direction, confidence, expected return, horizon."""
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H5(f"{direction_emoji} {direction.upper()}", className="text-center mb-0"),
                    html.Small("Direction", className="text-center text-muted d-block")
                ], className="py-1 px-2")
            ])
        ], width=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H5(f"{pred.confidence:.1%}", className="text-center mb-0"),
                    html.Small("Confidence", className="text-center text-muted d-block")
                ], className="py-1 px-2")
            ])
        ], width=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H5(f"{expected.get('mean', 0):.2%}", className="text-center mb-0"),
                    html.Small("Expected Return", className="text-center text-muted d-block")
                ], className="py-1 px-2")
            ])
        ], width=3),
        dbc.Col([
            dbc.Card([
                dbc.CardBody([
                    html.H5(pred.horizon, className="text-center mb-0"),
                    html.Small("Horizon", className="text-center text-muted d-block")
                ], className="py-1 px-2")
            ])
        ], width=3)
    ], className="mb-2")


def _build_direction_probabilities_section(probs: dict) -> dbc.Row:
    """Build the direction probabilities section (up/flat/down progress bars)."""
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.Div("📊 Direction Probabilities", style={"fontWeight": "bold"}), className="py-1"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Small("🔼 UP", className="mb-1 d-block"),
                            dbc.Progress(value=probs.get('up', 0) * 100,
                                       color="success", className="mb-2",
                                       style={"height": "18px"},
                                       label=f"{probs.get('up', 0):.1%}")
                        ], width=12),
                        dbc.Col([
                            html.Small("➡️ FLAT", className="mb-1 d-block"),
                            dbc.Progress(value=probs.get('flat', 0) * 100,
                                       color="warning", className="mb-2",
                                       style={"height": "18px"},
                                       label=f"{probs.get('flat', 0):.1%}")
                        ], width=12),
                        dbc.Col([
                            html.Small("🔽 DOWN", className="mb-1 d-block"),
                            dbc.Progress(value=probs.get('down', 0) * 100,
                                       color="danger", className="mb-2",
                                       style={"height": "18px"},
                                       label=f"{probs.get('down', 0):.1%}")
                        ], width=12)
                    ])
                ], className="py-2")
            ])
        ], width=12)
    ], className="mb-2")


def _build_model_info_section(pred: Prediction) -> dbc.Row:
    """Build the model info section (version, creation time, prediction ID)."""
    return dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader(html.Div("🤖 Model Info", style={"fontWeight": "bold"}), className="py-1"),
                dbc.CardBody([
                    html.Small([
                        html.Strong("Version: "),
                        html.Span(pred.model_version or "Unknown"),
                        " | ",
                        html.Strong("Created: "),
                        html.Span(pred.created_at.strftime("%Y-%m-%d %H:%M") if pred.created_at else "Unknown"),
                        html.Br(),
                        html.Strong("ID: "),
                        html.Code(str(pred.prediction_id))
                    ], className="d-block")
                ], className="py-2")
            ])
        ], width=12)
    ], className="mt-2")


def get_prediction_details(engine, prediction_id, load_performance=False, portfolio_capital=100000, currency="USD", risk_adjustment=0.3):
    """Get detailed information about a prediction

    Args:
        engine: Database engine
        prediction_id: UUID of prediction to show details for
        load_performance: Whether to load live performance data (slow)
        portfolio_capital: Total portfolio capital for position sizing
        currency: Currency symbol (USD/EUR/GBP)
        risk_adjustment: Risk adjustment factor (0-1)

    Returns:
        Tuple of (title, body_content, sync_trigger) where sync_trigger is a dict to notify UI refresh or None
    """
    try:
        with Session(engine) as db:
            # OPTIMIZED: Get prediction with eager loading for entity in single query
            # This eliminates N+1 query problem by using JOINs
            pred = db.query(Prediction).options(
                joinedload(Prediction.entity)
            ).filter(
                Prediction.prediction_id == prediction_id
            ).first()

            if not pred:
                # NOTE: preserved from the original code -- this branch returns a
                # 2-tuple (no sync_trigger), unlike the success and error paths.
                return "Error", dbc.Alert("Prediction not found", color="danger")

            # Entity is already loaded via eager loading
            entity = pred.entity
            entity_name = entity.entity_name if entity else pred.entity_id

            # Get predicted direction
            probs = _ensure_dict(pred.direction_probabilities, {})
            direction = max(probs, key=probs.get) if probs else "unknown"
            direction_emoji = {"up": "🔼", "down": "🔽", "flat": "➡️"}.get(direction, "❓")

            simulation = _load_latest_simulation(db, prediction_id)
            performance, sync_trigger = _resolve_performance(db, pred, entity, prediction_id, load_performance)

            expected = _ensure_dict(pred.expected_return, {})

            title = _build_modal_title(pred, entity, entity_name, direction, direction_emoji)
            body = dbc.Container([
                # Live Performance Section
                _build_performance_section(performance, pred, load_performance),

                # Exit Strategy Section (Stop Loss & Take Profit, if available)
                _build_exit_strategy_section(simulation, performance),

                # Simulation Section (if available)
                _build_simulation_section(simulation, portfolio_capital, currency, risk_adjustment),

                # Overview
                _build_overview_row(pred, direction, direction_emoji, expected),

                # Direction Probabilities
                _build_direction_probabilities_section(probs),

                # News and Drivers
                dbc.Row([
                    dbc.Col([_build_news_section(db, pred)], width=7),
                    dbc.Col([_build_drivers_section(pred)], width=5)
                ]),

                # Model Info
                _build_model_info_section(pred)
            ], fluid=True)

            return title, body, sync_trigger

    except Exception as e:
        return "Error", dbc.Alert(f"Error loading prediction details: {str(e)}", color="danger"), None


def create_prediction_modal():
    """Create the prediction details modal component

    Returns:
        dbc.Modal component that can be added to any layout
    """
    return dbc.Modal([
        dbc.ModalHeader([
            dbc.ModalTitle(id="prediction-modal-title"),
            html.Div([
                dbc.Button("🔄", id="refresh-prediction-detail",
                          size="sm", color="light", outline=True,
                          className="me-2", title="Refresh live data"),
                dbc.Button("📄", id="export-prediction-a4-png",
                          size="sm", color="primary", outline=True,
                          title="Export as DIN A4 PNG", n_clicks=0)
            ], className="d-flex")
        ], className="d-flex justify-content-between align-items-center"),
        dbc.ModalBody(id="prediction-modal-body", className="prediction-modal-body-scroll"),
        dbc.ModalFooter(
            dbc.Button("Close", id="close-prediction-modal", className="ms-auto", n_clicks=0)
        )
    ], id="prediction-modal", size="xl", is_open=False, backdrop=True, centered=True)
