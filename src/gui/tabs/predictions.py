"""
Predictions Tab - View and Filter Predictions
"""

from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta
from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload
import json
import logging

from src.models.predictions import Prediction, PredictionOutcome
from src.models.entities import Entity
from src.models.raw_news import RawNews
from src.models.processed_news import ProcessedNews
from src.models.analysis import ImpactScore, SurpriseScore, FactVerification
from src.services.prediction_performance_service import prediction_performance_service

logger = logging.getLogger(__name__)


def create_layout():
    """Create predictions tab layout"""
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("Filter Predictions", className="mb-3"),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Entity/Ticker:"),
                                dcc.Dropdown(
                                    id="pred-entity-filter",
                                    multi=True,
                                    placeholder="All entities..."
                                )
                            ], width=3),
                            dbc.Col([
                                dbc.Label("Date Range:"),
                                dcc.DatePickerRange(
                                    id="pred-date-filter",
                                    start_date=(datetime.now() - timedelta(days=7)).date(),
                                    end_date=datetime.now().date(),
                                )
                            ], width=3),
                            dbc.Col([
                                dbc.Label("Horizon:"),
                                dcc.Dropdown(
                                    id="pred-horizon-filter",
                                    options=[
                                        {'label': '1 Day (Short-term)', 'value': '1d'},
                                        {'label': '5 Days (Swing)', 'value': '5d'},
                                        {'label': '20 Days (Position)', 'value': '20d'}
                                    ],
                                    value='5d',
                                    clearable=False
                                )
                            ], width=3),
                            dbc.Col([
                                dbc.Label("Min Confidence:"),
                                dcc.Slider(
                                    id="pred-confidence-filter",
                                    min=0, max=100, step=10, value=0,
                                    marks={i: f"{i}%" for i in range(0, 101, 20)}
                                )
                            ], width=3)
                        ])
                    ])
                ])
            ], width=12)
        ], className="mb-3"),
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("🎯 Active Predictions")),
                    dbc.CardBody([
                        html.P("Click on a prediction to see details", className="text-muted mb-3"),
                        dcc.Loading(
                            id="predictions-loading",
                            type="circle",
                            children=html.Div(
                                id="predictions-table",
                                style={"maxHeight": "800px", "overflowY": "auto"}
                            )
                        )
                    ])
                ])
            ], width=12)
        ]),

        # Modal for prediction details
        dbc.Modal([
            dbc.ModalHeader([
                dbc.ModalTitle(id="prediction-modal-title"),
                dbc.Button("🔄", id="refresh-prediction-detail", 
                          size="sm", color="light", outline=True,
                          className="ms-2", title="Refresh live data")
            ], className="d-flex justify-content-between align-items-center"),
            dbc.ModalBody(id="prediction-modal-body"),
            dbc.ModalFooter(
                dbc.Button("Close", id="close-prediction-modal", className="ms-auto", n_clicks=0)
            )
        ], id="prediction-modal", size="xl", is_open=False),

        # Toast notifications
        dbc.Toast(
            id="refresh-toast",
            header="Performance Update",
            is_open=False,
            dismissable=True,
            icon="info",
            duration=3000,
            style={"position": "fixed", "top": 66, "right": 10, "width": 350, "zIndex": 9999}
        ),

        # Hidden stores
        dcc.Store(id="prediction-detail-cache", data={}),
        dcc.Store(id="current-prediction-id", data=None),
        dcc.Store(id="refresh-loading-state", data={})
    ], fluid=True)


def get_predictions_table(engine, entity_filter=None, date_range=None, min_confidence=0, horizon='5d'):
    """Get predictions table with filters

    Args:
        engine: Database engine
        entity_filter: List of entity IDs to filter by
        date_range: Tuple of (start_date, end_date)
        min_confidence: Minimum confidence threshold (0-1)
        horizon: Prediction horizon (1d, 5d, 20d)
    """
    try:
        with Session(engine) as db:
            # Use eager loading to fetch entity and outcome in single query (fixes N+1 problem)
            query = db.query(Prediction).options(
                joinedload(Prediction.entity),
                joinedload(Prediction.outcome)
            ).join(
                Entity, Prediction.entity_id == Entity.entity_id
            ).order_by(desc(Prediction.created_at))

            # Filter by selected horizon
            query = query.filter(Prediction.horizon == horizon)

            # Apply filters
            if entity_filter:
                query = query.filter(Prediction.entity_id.in_(entity_filter))

            if date_range and len(date_range) == 2:
                start, end = date_range
                if start:
                    # Convert string to date if needed
                    if isinstance(start, str):
                        start = datetime.fromisoformat(start).date()
                    # Start of day
                    query = query.filter(Prediction.created_at >= datetime.combine(start, datetime.min.time()))
                if end:
                    # Convert string to date if needed
                    if isinstance(end, str):
                        end = datetime.fromisoformat(end).date()
                    # End of day (23:59:59)
                    query = query.filter(Prediction.created_at <= datetime.combine(end, datetime.max.time()))

            if min_confidence > 0:
                query = query.filter(Prediction.confidence >= min_confidence / 100)

            predictions = query.limit(200).all()

            if not predictions:
                return dbc.Alert("No predictions match the current filters.", color="info")

            rows = []
            for pred in predictions:
                # Access entity from eager-loaded relationship (no separate query!)
                entity = pred.entity

                # Get direction from probabilities
                probs = pred.direction_probabilities or {}
                direction = max(probs, key=probs.get) if probs else "unknown"
                direction_emoji = {"up": "🔼", "down": "🔽", "flat": "➡️"}.get(direction, "❓")

                # Get confidence color
                conf_color = "text-success" if pred.confidence and pred.confidence > 0.7 else "text-warning"

                # Access outcome from eager-loaded relationship (no separate query!)
                outcome = pred.outcome[0] if pred.outcome else None

                if outcome and outcome.actual_return is not None:
                    # Show saved performance data with last update time
                    return_val = outcome.actual_return
                    
                    # Format last update time
                    if outcome.evaluation_timestamp:
                        from datetime import datetime as dt
                        time_ago = dt.now() - outcome.evaluation_timestamp
                        if time_ago.days > 0:
                            time_str = f"{time_ago.days}d ago"
                        elif time_ago.seconds > 3600:
                            time_str = f"{time_ago.seconds // 3600}h ago"
                        else:
                            time_str = f"{time_ago.seconds // 60}m ago"
                        update_info = html.Small(f"({time_str})", className="text-muted", style={"fontSize": "0.7rem"})
                    else:
                        update_info = ""
                    
                    perf_display = html.Td([
                        html.Div(
                            f"{return_val:+.2f}%",
                            className="text-success" if return_val > 0 else "text-danger" if return_val < 0 else "text-muted"
                        ),
                        update_info
                    ])
                    result_display = html.Td(
                        "✅" if outcome.direction_correct else "❌",
                        className="text-center"
                    )
                    return_24h_display = html.Td("—", className="text-muted text-center")
                else:
                    # Not yet loaded
                    perf_display = html.Td("—", className="text-muted text-center", 
                                          title="Click 🔄 to load")
                    result_display = html.Td("—", className="text-muted text-center")
                    return_24h_display = html.Td("—", className="text-muted text-center")

                rows.append(html.Tr([
                    html.Td(pred.created_at.strftime("%Y-%m-%d %H:%M") if pred.created_at else "N/A"),
                    html.Td(entity.entity_name if entity else "Unknown", className="text-primary"),
                    html.Td([direction_emoji, " ", direction.upper()]),
                    html.Td(f"{pred.confidence:.2%}" if pred.confidence else "N/A", className=conf_color),
                    perf_display,  # Live Return
                    result_display,  # Strategy Result
                    return_24h_display,  # 24h Return
                    html.Td(pred.horizon if pred.horizon else "N/A"),
                    html.Td([
                        dbc.Button(
                            "🔄",
                            id={"type": "pred-refresh-btn", "index": str(pred.prediction_id)},
                            size="sm", color="success", outline=True, className="me-1",
                            title="Load & Save Performance"
                        ),
                        dbc.Button("Details", id={"type": "pred-detail-btn", "index": str(pred.prediction_id)},
                                   size="sm", color="info", outline=True)
                    ])
                ], style={"cursor": "pointer"}))

            return dbc.Table([
                html.Thead(html.Tr([
                    html.Th("Timestamp"),
                    html.Th("Entity"),
                    html.Th("Direction"),
                    html.Th("Confidence"),
                    html.Th("📊 Performance", title="Click 🔄 to load live data"),
                    html.Th("✓/✗ Result", title="Strategy outcome"),
                    html.Th("📈 24h", title="24h performance"),
                    html.Th("Horizon"),
                    html.Th("Actions")
                ])),
                html.Tbody(rows)
            ], bordered=True, hover=True, striped=True, className="table-dark")
    except Exception as e:
        return dbc.Alert(
            f"⚠️ Unable to load predictions: {str(e)}",
            color="warning"
        )


def get_entity_options(engine):
    """Get available entities for dropdown filter"""
    try:
        with Session(engine) as db:
            entities = db.query(Entity).filter(
                Entity.entity_type == 'company'
            ).order_by(Entity.entity_name).all()

            return [
                {'label': f"{e.entity_name} ({e.entity_id})", 'value': e.entity_id}
                for e in entities
            ]
    except Exception:
        return []


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
    from src.gui.charts.market_data import MarketDataProvider
    
    # Get direction from prediction
    probs = pred.direction_probabilities or {}
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
            
            # Calculate days since prediction
            days_since = (datetime.now() - pred.timestamp.replace(tzinfo=None)).days if pred.timestamp else 0
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
                prediction_date = pred.timestamp.date() if pred.timestamp else datetime.now().date()
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
                    
                    logger.info(f"   Entry: ${prediction_price:.2f}, Current: ${current_price:.2f}")
                    logger.info(f"   High: ${high_since:.2f}, Low: ${low_since:.2f}, Vol: {volatility:.2f}%")
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
                    if live_price_data and 'current_price' in live_price_data:
                        live_current_price = live_price_data['current_price']
                        if live_current_price > 0:
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
    
    # Calculate days since prediction
    days_since = (datetime.now() - pred.timestamp.replace(tzinfo=None)).days if pred.timestamp else 0
    
    # Calculate actual return from live prices if available, otherwise use saved data
    actual_return_pct = 0
    if prediction_price > 0 and current_price > 0:
        actual_return_pct = ((current_price - prediction_price) / prediction_price) * 100
        logger.info(f"   Calculated return: {actual_return_pct:+.2f}%")
    else:
        # Fallback to saved outcome
        actual_return_pct = (outcome.actual_return or 0) * 100
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


def get_prediction_details(engine, prediction_id, load_performance=False):
    """Get detailed information about a prediction

    Args:
        engine: Database engine
        prediction_id: UUID of prediction to show details for
        load_performance: Whether to load live performance data (slow)

    Returns:
        Tuple of (title, body_content)
    """
    try:
        with Session(engine) as db:
            # Get prediction
            pred = db.query(Prediction).filter(
                Prediction.prediction_id == prediction_id
            ).first()

            if not pred:
                return "Error", dbc.Alert("Prediction not found", color="danger")

            # Get entity
            entity = db.query(Entity).filter(Entity.entity_id == pred.entity_id).first()
            entity_name = entity.entity_name if entity else pred.entity_id

            # Get direction
            probs = pred.direction_probabilities or {}
            direction = max(probs, key=probs.get) if probs else "unknown"
            direction_emoji = {"up": "🔼", "down": "🔽", "flat": "➡️"}.get(direction, "❓")

            # Check for saved performance first
            performance = None
            saved_outcome = db.query(PredictionOutcome).filter(
                PredictionOutcome.prediction_id == prediction_id
            ).first()
            
            logger.info(f"🔍 Checking saved performance for {prediction_id}")
            logger.info(f"   Found outcome: {saved_outcome is not None}")
            if saved_outcome:
                logger.info(f"   Actual return: {saved_outcome.actual_return}")
                logger.info(f"   Direction correct: {saved_outcome.direction_correct}")
                logger.info(f"   Timestamp: {saved_outcome.evaluation_timestamp}")
            
            if saved_outcome and saved_outcome.actual_return is not None:
                # Use saved performance data
                try:
                    # Convert saved outcome to performance format
                    # Only load live prices if explicitly requested (load_performance=True)
                    logger.info(f"✅ Using saved performance for modal (load_live_prices={load_performance})")
                    performance = _format_saved_performance(pred, entity, saved_outcome, load_live_prices=load_performance)
                    
                    # If we loaded live prices, save them back to the database
                    if load_performance and performance:
                        try:
                            logger.info(f"💾 Saving updated performance to database")
                            prediction_performance_service.save_prediction_performance(
                                prediction_id, performance, db
                            )
                            db.commit()
                            logger.info(f"✅ Saved updated performance: {performance.get('total_return_pct'):.2f}%")
                        except Exception as save_error:
                            logger.warning(f"Could not save updated performance: {save_error}")
                            db.rollback()
                except Exception as e:
                    logger.warning(f"Could not format saved performance: {e}")
            elif load_performance:
                # Load live performance (and save it)
                try:
                    logger.info(f"🔄 Loading live performance (load_performance=True)")
                    performance = prediction_performance_service.get_prediction_performance(pred, entity)
                    
                    # Save to database
                    if performance:
                        try:
                            logger.info(f"💾 Saving new performance to database")
                            prediction_performance_service.save_prediction_performance(
                                prediction_id, performance, db
                            )
                            db.commit()
                            logger.info(f"✅ Saved new performance: {performance.get('total_return_pct'):.2f}%")
                        except Exception as save_error:
                            logger.warning(f"Could not save performance: {save_error}")
                            db.rollback()
                except Exception as e:
                    logger.warning(f"Could not load performance: {e}")
            else:
                logger.info(f"ℹ️ No saved performance and load_performance=False")

            # Get related news
            news_ids = pred.related_news_ids or []
            if not news_ids:
                news_content = dbc.Alert("No related news found", color="warning")
            else:
                news_id = news_ids[0] if isinstance(news_ids, list) else news_ids

                raw_news = db.query(RawNews).filter(RawNews.news_id == news_id).first()
                processed = db.query(ProcessedNews).filter(ProcessedNews.news_id == news_id).first()
                impact = db.query(ImpactScore).filter(
                    ImpactScore.news_id == news_id,
                    ImpactScore.entity_id == pred.entity_id
                ).first()

                news_content = dbc.Card([
                    dbc.CardHeader(html.H6("📰 Related News")),
                    dbc.CardBody([
                        html.H6(raw_news.title if raw_news else "Unknown", className="text-primary"),
                        html.P([
                            html.Strong("Source: "),
                            raw_news.source if raw_news else "Unknown",
                            html.Br(),
                            html.Strong("Published: "),
                            raw_news.published_at.strftime("%Y-%m-%d %H:%M") if raw_news and raw_news.published_at else "Unknown",
                            html.Br(),
                            html.Strong("URL: "),
                            html.A(raw_news.url, href=raw_news.url, target="_blank") if raw_news and raw_news.url else "N/A"
                        ], className="mb-2"),
                        html.Hr(),
                        html.H6("Content Summary"),
                        html.P(raw_news.full_text[:500] + "..." if raw_news and raw_news.full_text and len(raw_news.full_text) > 500
                               else raw_news.full_text if raw_news and raw_news.full_text else "No content available",
                               className="text-muted", style={"maxHeight": "200px", "overflowY": "auto"}),
                        html.Hr() if processed else None,
                        html.H6("Sentiment Analysis") if processed else None,
                        dbc.Row([
                            dbc.Col([
                                html.Strong("Overall: "),
                                html.Span(f"{processed.sentiment.get('overall', 0):.2f}",
                                         className="text-success" if processed and processed.sentiment.get('overall', 0) > 0 else "text-danger")
                            ], width=4) if processed and processed.sentiment else None,
                            dbc.Col([
                                html.Strong("Market: "),
                                html.Span(f"{processed.sentiment.get('market', 0):.2f}",
                                         className="text-success" if processed and processed.sentiment.get('market', 0) > 0 else "text-danger")
                            ], width=4) if processed and processed.sentiment else None,
                            dbc.Col([
                                html.Strong("Company: "),
                                html.Span(f"{processed.sentiment.get('company', 0):.2f}",
                                         className="text-success" if processed and processed.sentiment.get('company', 0) > 0 else "text-danger")
                            ], width=4) if processed and processed.sentiment else None
                        ]) if processed else None,
                        html.Hr() if processed and processed.event_type else None,
                        html.P([
                            html.Strong("Event Type: "),
                            dbc.Badge(processed.event_type, color="primary")
                        ]) if processed and processed.event_type else None,
                        html.Hr() if impact else None,
                        html.P([
                            html.Strong("Impact Score: "),
                            html.Span(f"{impact.impact_score:.3f}", className="text-warning" if impact else "")
                        ]) if impact else None
                    ])
                ], className="mb-3")

            # Expected returns
            expected = pred.expected_return or {}

            # Key drivers
            drivers = pred.key_drivers or []
            drivers_content = dbc.Card([
                dbc.CardHeader(html.H6("🎯 Key Drivers")),
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
                                               className="mb-0", style={"height": "20px"})
                                ),
                                html.Td(f"{d.get('importance', 0):.1%}")
                            ]) for d in drivers[:5]  # Top 5
                        ])
                    ], bordered=True, striped=True) if drivers else html.P("No driver data available", className="text-muted")
                ])
            ], className="mb-3")

            # Build modal content
            title = f"{direction_emoji} {entity_name} - {direction.upper()} Prediction"

            # Performance section
            performance_section = None
            if performance:
                total_return = performance['total_return_pct']
                return_color = "success" if total_return > 0 else "danger" if total_return < 0 else "secondary"
                
                performance_section = dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader(html.H6("📊 Live Performance vs Chart", className="mb-0")),
                            dbc.CardBody([
                                dbc.Row([
                                    dbc.Col([
                                        dbc.Card([
                                            dbc.CardBody([
                                                html.H3(f"{total_return:+.2f}%", className=f"text-{return_color} text-center mb-1"),
                                                html.P("Return Since Prediction", className="text-center text-muted mb-0", style={"fontSize": "0.85em"})
                                            ])
                                        ], color=return_color, outline=True)
                                    ], width=3),
                                    dbc.Col([
                                        dbc.Card([
                                            dbc.CardBody([
                                                html.H3(performance['strategy_result'].split()[0], className="text-center mb-1"),
                                                html.P(performance['strategy_result'], className="text-center mb-0", style={"fontSize": "0.85em"})
                                            ])
                                        ], color="light")
                                    ], width=3),
                                    dbc.Col([
                                        dbc.Card([
                                            dbc.CardBody([
                                                html.H3(f"{performance['return_24h_pct']:+.2f}%", 
                                                       className=f"text-{'success' if performance['return_24h_pct'] > 0 else 'danger' if performance['return_24h_pct'] < 0 else 'secondary'} text-center mb-1"),
                                                html.P("Last 24h Return", className="text-center text-muted mb-0", style={"fontSize": "0.85em"})
                                            ])
                                        ], color="light")
                                    ], width=3),
                                    dbc.Col([
                                        dbc.Card([
                                            dbc.CardBody([
                                                html.H3(f"{performance['days_since_prediction']}d", className="text-center mb-1"),
                                                html.P("Days Active", className="text-center text-muted mb-0", style={"fontSize": "0.85em"})
                                            ])
                                        ], color="light")
                                    ], width=3)
                                ]),
                                html.Hr(),
                                dbc.Row([
                                    dbc.Col([
                                        html.P([
                                            html.Strong("Entry Price: "),
                                            f"${performance['prediction_price']:.2f}",
                                            html.Br(),
                                            html.Strong("Current Price: "),
                                            f"${performance['current_price']:.2f}",
                                            html.Br(),
                                            html.Strong("Price Change: "),
                                            html.Span(f"${performance['current_price'] - performance['prediction_price']:+.2f}",
                                                     className=f"text-{return_color}")
                                        ])
                                    ], width=4),
                                    dbc.Col([
                                        html.P([
                                            html.Strong("24h Ago Price: "),
                                            f"${performance.get('price_24h_ago', 0):.2f}",
                                            html.Br(),
                                            html.Strong("High Since Entry: "),
                                            f"${performance['high_since_prediction']:.2f}",
                                            html.Br(),
                                            html.Strong("Low Since Entry: "),
                                            f"${performance['low_since_prediction']:.2f}"
                                        ])
                                    ], width=4),
                                    dbc.Col([
                                        html.P([
                                            html.Strong("Volatility: "),
                                            f"{performance['volatility']:.2f}%",
                                            html.Br(),
                                            html.Strong("Predicted: "),
                                            f"{performance['predicted_direction'].upper()}",
                                            html.Br(),
                                            html.Strong("Actual: "),
                                            f"{performance['actual_direction'].upper()}",
                                            html.Br(),
                                            html.Strong("Accuracy: "),
                                            html.Span("✅ Correct" if performance['is_correct'] else "❌ Wrong",
                                                     className=f"text-{'success' if performance['is_correct'] else 'danger'}")
                                        ])
                                    ], width=4)
                                ])
                            ])
                        ], className="mb-3")
                    ], width=12)
                ], className="mb-3")
            elif load_performance:
                # Performance was requested but not available
                performance_section = dbc.Alert(
                    "⚠️ Performance data not available for this entity (may not be a tradable stock)",
                    color="info", className="mb-3"
                )
            else:
                # Performance not yet loaded
                performance_section = dbc.Alert([
                    "📊 Live performance data not loaded. ",
                    html.Strong("Click the 🔄 Refresh button above to load it.")
                ], color="light", className="mb-3")

            body = dbc.Container([
                # Live Performance Section (if available)
                performance_section if performance_section else None,
                
                # Overview
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.H4(f"{direction_emoji} {direction.upper()}", className="text-center"),
                                html.P("Direction", className="text-center text-muted")
                            ])
                        ])
                    ], width=3),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.H4(f"{pred.confidence:.1%}", className="text-center"),
                                html.P("Confidence", className="text-center text-muted")
                            ])
                        ])
                    ], width=3),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.H4(f"{expected.get('mean', 0):.2%}", className="text-center"),
                                html.P("Expected Return", className="text-center text-muted")
                            ])
                        ])
                    ], width=3),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.H4(pred.horizon, className="text-center"),
                                html.P("Horizon", className="text-center text-muted")
                            ])
                        ])
                    ], width=3)
                ], className="mb-3"),

                # Direction Probabilities
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader(html.H6("📊 Direction Probabilities")),
                            dbc.CardBody([
                                dbc.Row([
                                    dbc.Col([
                                        html.P("🔼 UP", className="mb-1"),
                                        dbc.Progress(value=probs.get('up', 0) * 100,
                                                   color="success", className="mb-2",
                                                   style={"height": "25px"},
                                                   label=f"{probs.get('up', 0):.1%}")
                                    ], width=12),
                                    dbc.Col([
                                        html.P("➡️ FLAT", className="mb-1"),
                                        dbc.Progress(value=probs.get('flat', 0) * 100,
                                                   color="warning", className="mb-2",
                                                   style={"height": "25px"},
                                                   label=f"{probs.get('flat', 0):.1%}")
                                    ], width=12),
                                    dbc.Col([
                                        html.P("🔽 DOWN", className="mb-1"),
                                        dbc.Progress(value=probs.get('down', 0) * 100,
                                                   color="danger", className="mb-2",
                                                   style={"height": "25px"},
                                                   label=f"{probs.get('down', 0):.1%}")
                                    ], width=12)
                                ])
                            ])
                        ])
                    ], width=12)
                ], className="mb-3"),

                # News and Drivers
                dbc.Row([
                    dbc.Col([news_content], width=7),
                    dbc.Col([drivers_content], width=5)
                ]),

                # Model Info
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader(html.H6("🤖 Model Information")),
                            dbc.CardBody([
                                html.P([
                                    html.Strong("Model Version: "),
                                    pred.model_version or "Unknown"
                                ]),
                                html.P([
                                    html.Strong("Created: "),
                                    pred.created_at.strftime("%Y-%m-%d %H:%M:%S") if pred.created_at else "Unknown"
                                ]),
                                html.P([
                                    html.Strong("Prediction ID: "),
                                    html.Code(str(pred.prediction_id))
                                ])
                            ])
                        ])
                    ], width=12)
                ], className="mt-3")
            ], fluid=True)

            return title, body

    except Exception as e:
        return "Error", dbc.Alert(f"Error loading prediction details: {str(e)}", color="danger")