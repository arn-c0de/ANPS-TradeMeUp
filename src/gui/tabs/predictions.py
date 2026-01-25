"""
Predictions Tab - View and Filter Predictions
"""

import json
import logging
import uuid
from datetime import datetime, timedelta

import dash
from dash import ALL, Input, Output, State, dcc, html, dash_table
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from src.models.predictions import Prediction, PredictionOutcome
from src.models.trading_simulation import TradingSimulation
from src.models.entities import Entity
from src.models.raw_news import RawNews
from src.models.processed_news import ProcessedNews
from src.models.analysis import ImpactScore, SurpriseScore, FactVerification
from src.models.database import engine as _engine
from src.services.prediction_performance_service import prediction_performance_service
from src.gui.utils.callbacks import safe_callback
from src.gui.utils.task_queue import get_task_queue, add_gui_task

logger = logging.getLogger(__name__)


def create_layout():
    """Create predictions tab layout"""
    return html.Div([
        dbc.Container([
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
                                        placeholder="All entities...",
                                        searchable=True
                                    )
                                ], width=3),
                                dbc.Col([
                                    dbc.Label("Date Range:"),
                                    dcc.DatePickerRange(
                                        id="pred-date-filter",
                                        start_date=(datetime.now() - timedelta(days=7)).date(),
                                        end_date=datetime.now().date(),
                                    )
                                ], width=2),
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
                                ], width=2),
                                dbc.Col([
                                    dbc.Label("🎯 Surprise Score:"),
                                    dcc.Dropdown(
                                        id="pred-surprise-filter",
                                        options=[
                                            {'label': 'All', 'value': 'all'},
                                            {'label': 'High (>0.7)', 'value': 'high'},
                                            {'label': 'Medium (0.4-0.7)', 'value': 'medium'},
                                            {'label': 'Low (<0.4)', 'value': 'low'}
                                        ],
                                        value='all',
                                        clearable=False
                                    )
                                ], width=2),
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
                            html.Div(
                                id="predictions-table",
                                style={"maxHeight": "800px", "overflowY": "auto"}
                            )
                        ])
                    ])
                ], width=12)
            ]),

            # Hidden stores
            dcc.Store(id="prediction-detail-cache", data={}),
            dcc.Store(id="current-prediction-id", data=None),
            dcc.Store(id="refresh-loading-state", data={})
        ], fluid=True),

        # Modal OUTSIDE container for proper z-index and positioning
        dbc.Modal([
            dbc.ModalHeader([
                dbc.ModalTitle(id="prediction-modal-title"),
                dbc.Button("🔄", id="refresh-prediction-detail",
                          size="sm", color="light", outline=True,
                          className="ms-2", title="Refresh live data")
            ], className="d-flex justify-content-between align-items-center"),
            dbc.ModalBody(id="prediction-modal-body", className="prediction-modal-body-scroll"),
            dbc.ModalFooter(
                dbc.Button("Close", id="close-prediction-modal", className="ms-auto", n_clicks=0)
            )
        ], id="prediction-modal", size="xl", is_open=False, backdrop=True, centered=True),

        # Toast notifications OUTSIDE container
        dbc.Toast(
            id="refresh-toast",
            header="Performance Update",
            is_open=False,
            dismissable=True,
            icon="info",
            duration=3000,
            style={
                "position": "fixed",
                "top": 66,
                "right": 10,
                "width": 350,
                "zIndex": 9999,
                "backgroundColor": "#1e1e1e",
                "border": "1px solid #444",
                "boxShadow": "0 4px 8px rgba(0,0,0,0.3)"
            }
        )
    ])


def get_predictions_table(engine, entity_filter=None, date_range=None, min_confidence=0, horizon='5d', surprise_filter='all', refreshing_prediction_id=None):
    """Get predictions table with filters

    Args:
        engine: Database engine
        entity_filter: List of entity IDs to filter by
        date_range: Tuple of (start_date, end_date)
        min_confidence: Minimum confidence threshold (0-1)
        horizon: Prediction horizon (1d, 5d, 20d)
        surprise_filter: Filter by surprise score ('all', 'high', 'medium', 'low')
        refreshing_prediction_id: ID of prediction currently being refreshed (for visual feedback)
    """
    try:
        with Session(engine, expire_on_commit=False) as db:
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
            
            # Filter by surprise score if needed
            if surprise_filter and surprise_filter != 'all':
                filtered_preds = []
                for pred in predictions:
                    # Get related news IDs
                    news_ids = pred.related_news_ids if pred.related_news_ids else []
                    if news_ids:
                        # Check surprise scores for related news
                        surprise_scores = db.query(SurpriseScore).filter(
                            SurpriseScore.news_id.in_(news_ids)
                        ).all()
                        
                        if surprise_scores:
                            # Get average surprise score (use surprise_normalized field)
                            avg_surprise = sum(abs(s.surprise_normalized) for s in surprise_scores if s.surprise_normalized) / len(surprise_scores)
                            
                            # Apply filter
                            if surprise_filter == 'high' and avg_surprise > 0.7:
                                filtered_preds.append(pred)
                            elif surprise_filter == 'medium' and 0.4 <= avg_surprise <= 0.7:
                                filtered_preds.append(pred)
                            elif surprise_filter == 'low' and avg_surprise < 0.4:
                                filtered_preds.append(pred)
                predictions = filtered_preds

            # Try to load simulations (table may not exist yet)
            simulation_lookup = {}
            try:
                if predictions:
                    prediction_ids = [pred.prediction_id for pred in predictions]
                    simulations = db.query(TradingSimulation).filter(
                        TradingSimulation.prediction_id.in_(prediction_ids)
                    ).order_by(desc(TradingSimulation.created_at)).all()

                    for simulation in simulations:
                        pred_key = str(simulation.prediction_id)
                        if pred_key not in simulation_lookup:
                            simulation_lookup[pred_key] = simulation
            except Exception as sim_error:
                # Table may not exist yet - continue without simulations
                logger.debug(f"Could not load simulations (table may not exist): {sim_error}")

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

                # Simulation results (cached lookup)
                simulation = simulation_lookup.get(str(pred.prediction_id))
                if simulation:
                    decision = simulation.decision or "hold"
                    decision_color = {
                        "buy": "success",
                        "sell": "danger",
                        "hold": "secondary"
                    }.get(decision, "secondary")
                    decision_display = html.Td(
                        dbc.Badge(decision.upper(), color=decision_color, className="px-2")
                    )

                    risk_score = simulation.risk_score
                    if risk_score is None:
                        risk_display = html.Td("—", className="text-muted text-center")
                    else:
                        risk_color = "danger" if risk_score > 0.7 else "warning" if risk_score > 0.4 else "success"
                        risk_display = html.Td(
                            f"{risk_score:.2f}",
                            className=f"text-{risk_color} text-center",
                            title="Risk score (0-1)"
                        )
                else:
                    decision_display = html.Td("—", className="text-muted text-center")
                    risk_display = html.Td("—", className="text-muted text-center")

                # Access outcome from eager-loaded relationship (no separate query!)
                outcome = pred.outcome[0] if pred.outcome else None

                if outcome and outcome.actual_return is not None:
                    # Show ONLY saved performance data - NEVER recalculate on refresh
                    # actual_return is already stored as percentage (e.g., -17.03 = -17.03%)
                    return_val = outcome.actual_return
                    
                    logger.info(f"📊 Showing saved performance for {pred.prediction_id}: return_val={return_val}, outcome.actual_return={outcome.actual_return}")
                    
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
                    ], title="Saved performance data - click 🔄 to update")
                    
                    # Show result based on saved direction_correct
                    result_display = html.Td(
                        "✅" if outcome.direction_correct else "❌",
                        className="text-center",
                        title="Saved result - click 🔄 to update"
                    )
                    return_24h_display = html.Td("—", className="text-muted text-center")
                else:
                    # Not yet loaded
                    perf_display = html.Td("—", className="text-muted text-center", 
                                          title="Click 🔄 to load")
                    result_display = html.Td("—", className="text-muted text-center")
                    return_24h_display = html.Td("—", className="text-muted text-center")

                # Apply loading style if this prediction is being refreshed
                row_style = {}  # Remove cursor pointer to allow button clicks on touch devices
                row_class = ""
                is_refreshing = refreshing_prediction_id and str(pred.prediction_id) == str(refreshing_prediction_id)

                if is_refreshing:
                    # Darker background and slightly transparent during refresh
                    # Also disable hover effect with pointer-events: none
                    row_style.update({
                        "backgroundColor": "rgba(0, 0, 0, 0.4)",
                        "opacity": "0.7",
                        "transition": "all 0.3s ease"
                    })
                    row_class = "refreshing-row"  # CSS class to disable hover

                rows.append(html.Tr([
                    html.Td(pred.created_at.strftime("%Y-%m-%d %H:%M") if pred.created_at else "N/A"),
                    html.Td(entity.entity_name if entity else "Unknown", className="text-primary"),
                    html.Td([direction_emoji, " ", direction.upper()]),
                    html.Td(f"{pred.confidence:.2%}" if pred.confidence else "N/A", className=conf_color),
                    decision_display,
                    risk_display,
                    perf_display,  # Live Return
                    result_display,  # Strategy Result
                    return_24h_display,  # 24h Return
                    html.Td(pred.horizon if pred.horizon else "N/A"),
                    html.Td([
                        dbc.Button(
                            "⏳" if is_refreshing else "🔄",
                            id={"type": "pred-refresh-btn", "index": str(pred.prediction_id)},
                            size="sm", color="success", outline=True, className="me-1 touch-button",
                            title="Refreshing..." if is_refreshing else "Load & Save Performance",
                            disabled=is_refreshing,
                            style={
                                "minWidth": "44px", 
                                "minHeight": "44px", 
                                "touchAction": "manipulation",
                                "pointerEvents": "auto",
                                "cursor": "pointer",
                                "zIndex": "10"
                            }
                        ),
                        dbc.Button("Details", 
                                   id={"type": "pred-detail-btn", "index": str(pred.prediction_id)},
                                   size="sm", color="info", outline=True, className="touch-button",
                                   style={
                                       "minWidth": "70px", 
                                       "minHeight": "44px", 
                                       "touchAction": "manipulation",
                                       "pointerEvents": "auto",
                                       "cursor": "pointer",
                                       "zIndex": "10"
                                   })
                    ], style={"whiteSpace": "nowrap", "position": "relative"})
                ], style=row_style, className=row_class if row_class else None))

            # Always disable hover to prevent light background issues
            enable_hover = False

            return dbc.Table([
                html.Thead(html.Tr([
                    html.Th("Timestamp"),
                    html.Th("Entity"),
                    html.Th("Direction"),
                    html.Th("Confidence"),
                html.Th("Decision", title="Simulation decision"),
                html.Th("Risk", title="Composite risk score (0-1)"),
                    html.Th("📊 Performance", title="Click 🔄 to load live data"),
                    html.Th("✓/✗ Result", title="Strategy outcome"),
                    html.Th("📈 24h", title="24h performance"),
                    html.Th("Horizon"),
                    html.Th("Actions")
                ])),
                html.Tbody(rows)
            ], bordered=True, hover=False, striped=True, className="table-dark predictions-table-no-hover")
    except Exception as e:
        return dbc.Alert(
            f"⚠️ Unable to load predictions: {str(e)}",
            color="warning"
        )


def get_entity_options(engine):
    """Get available entities for dropdown filter - includes all entities that have predictions"""
    try:
        with Session(engine) as db:
            # Get all entities that have predictions (regardless of entity_type)
            # This includes companies, ETFs, indices, etc.
            entities = db.query(Entity).join(
                Prediction, Entity.entity_id == Prediction.entity_id
            ).distinct().order_by(Entity.entity_name).all()

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
    from src.gui.tabs.charts.market_data import MarketDataProvider
    
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

            # Load simulation data if available
            simulation = db.query(TradingSimulation).filter(
                TradingSimulation.prediction_id == prediction_id
            ).order_by(desc(TradingSimulation.created_at)).first()

            logger.info(f"🧪 Checking simulation for {prediction_id}")
            logger.info(f"   Found simulation: {simulation is not None}")
            
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
                    dbc.CardHeader(html.Div("📰 News", style={"fontWeight": "bold"}), className="py-1"),
                    dbc.CardBody([
                        html.Div(raw_news.title if raw_news else "Unknown", className="text-primary mb-1", style={"fontWeight": "500"}),
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
                            html.Span(f"Overall {processed.sentiment.get('overall', 0):.2f}",
                                     className="text-success" if processed and processed.sentiment.get('overall', 0) > 0 else "text-danger"),
                            " | ",
                            html.Span(f"Market {processed.sentiment.get('market', 0):.2f}",
                                     className="text-success" if processed and processed.sentiment.get('market', 0) > 0 else "text-danger"),
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

            # Expected returns
            expected = pred.expected_return or {}

            # Key drivers
            drivers = pred.key_drivers or []
            drivers_content = dbc.Card([
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

            # Build modal content - use entity_id (ticker) in button index, show entity_name as text
            ticker_symbol = entity.entity_id if entity else pred.entity_id
            title = html.Div([
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

            # Performance section
            performance_section = None
            if performance:
                total_return = performance['total_return_pct']
                return_color = "success" if total_return > 0 else "danger" if total_return < 0 else "secondary"
                
                performance_section = dbc.Row([
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
                                            html.Span(f"${performance['prediction_price']:.2f}"),
                                            " → ",
                                            html.Strong("Now: "),
                                            html.Span(f"${performance['current_price']:.2f} ", className=f"text-{return_color}"),
                                            html.Span(f"({performance['current_price'] - performance['prediction_price']:+.2f})", className=f"text-{return_color}")
                                        ], className="d-block")
                                    ], width=6),
                                    dbc.Col([
                                        html.Small([
                                            html.Strong("Range: "),
                                            html.Span(f"${performance['low_since_prediction']:.2f} - ${performance['high_since_prediction']:.2f}"),
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
            elif load_performance:
                # Performance was requested but not available
                performance_section = dbc.Alert(
                    html.Small("⚠️ Performance data not available for this entity (may not be a tradable stock)"),
                    color="info", className="mb-2 py-2"
                )
            else:
                # Performance not yet loaded
                performance_section = dbc.Alert([
                    html.Small([
                        "📊 Live performance data not loaded. ",
                        html.Strong("Click the 🔄 Refresh button above to load it.")
                    ])
                ], color="light", className="mb-2 py-2")

            # Simulation section
            simulation_section = None
            if simulation:
                decision = simulation.decision or "hold"
                decision_color = {
                    "buy": "success",
                    "sell": "danger",
                    "hold": "secondary"
                }.get(decision, "secondary")

                risk_score = simulation.risk_score or 0
                risk_color = "danger" if risk_score > 0.7 else "warning" if risk_score > 0.4 else "success"

                expected_return = simulation.expected_return_pct or 0
                expected_color = "success" if expected_return > 0 else "danger" if expected_return < 0 else "secondary"

                actual_return = simulation.actual_return_pct or 0
                actual_color = "success" if actual_return > 0 else "danger" if actual_return < 0 else "secondary"

                divergence = simulation.divergence_pct or 0
                divergence_color = "warning" if abs(divergence) > 2 else "secondary"

                cost_bps = simulation.transaction_cost_bps or 0
                cost_breakdown = simulation.cost_breakdown or {}

                simulation_section = dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader(html.Div("🧪 Trading Simulation", style={"fontWeight": "bold"}), className="py-1"),
                            dbc.CardBody([
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
                                                html.H5(f"{risk_score:.2f}", className=f"text-{risk_color} text-center mb-0"),
                                                html.Small("Risk", className="text-center text-muted d-block")
                                            ], className="py-1 px-2")
                                        ], color="light")
                                    ], width=3),
                                    dbc.Col([
                                        dbc.Card([
                                            dbc.CardBody([
                                                html.H5(f"{expected_return:+.2f}%", className=f"text-{expected_color} text-center mb-0"),
                                                html.Small("Expected", className="text-center text-muted d-block")
                                            ], className="py-1 px-2")
                                        ], color="light")
                                    ], width=3),
                                    dbc.Col([
                                        dbc.Card([
                                            dbc.CardBody([
                                                html.H5(f"{actual_return:+.2f}%", className=f"text-{actual_color} text-center mb-0"),
                                                html.Small("Actual", className="text-center text-muted d-block")
                                            ], className="py-1 px-2")
                                        ], color="light")
                                    ], width=3)
                                ], className="mb-2"),
                                # Second Row: Details
                                dbc.Row([
                                    dbc.Col([
                                        html.Small([
                                            html.Strong("Divergence: "),
                                            html.Span(f"{divergence:+.2f}%", className=f"text-{divergence_color}"),
                                            " | ",
                                            html.Strong("Cost: "),
                                            html.Span(f"{cost_bps:.1f} bps"),
                                            " | ",
                                            html.Strong("Conf: "),
                                            html.Span(f"{simulation.confidence:.1%}" if simulation.confidence else "N/A")
                                        ], className="d-block")
                                    ], width=12)
                                ])
                            ], className="py-2")
                        ], className="mb-2")
                    ], width=12)
                ], className="mb-2")

            body = dbc.Container([
                # Live Performance Section (if available)
                performance_section if performance_section else None,

                # Simulation Section (if available)
                simulation_section if simulation_section else None,

                # Overview
                dbc.Row([
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
                ], className="mb-2"),

                # Direction Probabilities
                dbc.Row([
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
                ], className="mb-2"),

                # News and Drivers
                dbc.Row([
                    dbc.Col([news_content], width=7),
                    dbc.Col([drivers_content], width=5)
                ]),

                # Model Info
                dbc.Row([
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
            ], fluid=True)

            return title, body

    except Exception as e:
        return "Error", dbc.Alert(f"Error loading prediction details: {str(e)}", color="danger")


def register_callbacks(app):
    """Register predictions tab callbacks."""

    @app.callback(
        Output("pred-entity-filter", "options"),
        Input("interval-component", "n_intervals")
    )
    @safe_callback(default_return=[])
    def update_entity_filter_options(n):
        """Update entity filter dropdown options"""
        return get_entity_options(_engine)

    @app.callback(
        Output("predictions-table", "children"),
        [Input("pred-entity-filter", "value"),
         Input("pred-date-filter", "start_date"),
         Input("pred-date-filter", "end_date"),
         Input("pred-horizon-filter", "value"),
         Input("pred-surprise-filter", "value"),
         Input("pred-confidence-filter", "value"),
         Input("refresh-loading-state", "data")]
    )
    def update_predictions_table(entities, start_date, end_date, horizon, surprise_filter, min_conf, loading_state):
        """Update predictions table with filters (removed interval for performance)"""
        date_range = (start_date, end_date) if start_date or end_date else None
        refreshing_id = loading_state.get("prediction_id") if loading_state else None
        return get_predictions_table(
            _engine,
            entity_filter=entities,
            date_range=date_range,
            min_confidence=min_conf or 0,
            horizon=horizon or '5d',
            surprise_filter=surprise_filter or 'all',
            refreshing_prediction_id=refreshing_id
        )

    @app.callback(
        [Output("prediction-modal", "is_open"),
         Output("prediction-detail-cache", "data"),
         Output("current-prediction-id", "data")],
        [Input({"type": "pred-detail-btn", "index": ALL}, "n_clicks"),
         Input({"type": "sim-detail-btn", "index": ALL}, "n_clicks"),
         Input("close-prediction-modal", "n_clicks"),
         Input("refresh-prediction-detail", "n_clicks")],
        [State("prediction-modal", "is_open"),
         State({"type": "pred-detail-btn", "index": ALL}, "id"),
         State({"type": "sim-detail-btn", "index": ALL}, "id"),
         State("prediction-detail-cache", "data"),
         State("current-prediction-id", "data")],
        prevent_initial_call=True
    )
    def toggle_prediction_modal(detail_clicks, sim_detail_clicks, close_click, refresh_click, is_open, button_ids, sim_button_ids, cached_data, current_pred_id):
        """Open/close prediction detail modal and cache prediction_id"""
        from dash import callback_context
        if not callback_context.triggered:
            return dash.no_update, dash.no_update, dash.no_update
        trigger_id = callback_context.triggered[0]["prop_id"]
        trigger_value = callback_context.triggered[0].get("value")
        if trigger_value is None or trigger_value == 0:
            return dash.no_update, dash.no_update, dash.no_update
        if "close-prediction-modal" in trigger_id:
            return False, dash.no_update, dash.no_update
        if "refresh-prediction-detail" in trigger_id and current_pred_id:
            return True, {"prediction_id": current_pred_id, "load_performance": True}, current_pred_id
        if "pred-detail-btn" in trigger_id and ".n_clicks" in trigger_id:
            id_str = trigger_id.split('.')[0]
            id_dict = json.loads(id_str)
            prediction_id = id_dict.get("index")
            if prediction_id:
                return True, {"prediction_id": prediction_id, "load_performance": True}, prediction_id
        if "sim-detail-btn" in trigger_id and ".n_clicks" in trigger_id:
            id_str = trigger_id.split('.')[0]
            id_dict = json.loads(id_str)
            prediction_id = id_dict.get("index")
            if prediction_id:
                return True, {"prediction_id": prediction_id, "load_performance": True}, prediction_id
        return dash.no_update, dash.no_update, dash.no_update

    @app.callback(
        [Output("refresh-loading-state", "data"),
         Output("predictions-table", "children", allow_duplicate=True),
         Output("refresh-toast", "is_open", allow_duplicate=True),
         Output("refresh-toast", "children", allow_duplicate=True),
         Output("refresh-toast", "icon", allow_duplicate=True)],
        [Input({"type": "pred-refresh-btn", "index": ALL}, "n_clicks")],
        [State({"type": "pred-refresh-btn", "index": ALL}, "id"),
         State("pred-horizon-filter", "value"),
         State("pred-entity-filter", "value"),
         State("pred-date-filter", "start_date"),
         State("pred-date-filter", "end_date"),
         State("pred-surprise-filter", "value"),
         State("pred-confidence-filter", "value")],
        prevent_initial_call=True
    )
    def set_refresh_loading_state(refresh_clicks, button_ids, horizon, entities, start_date, end_date, surprise_filter, min_conf):
        """Add refresh task to queue and show loading UI immediately"""
        from dash import callback_context
        if not callback_context.triggered:
            return {}, dash.no_update, False, "", "info"
        trigger_id = callback_context.triggered[0]["prop_id"]
        trigger_value = callback_context.triggered[0].get("value")
        if trigger_value is None:
            return {}, dash.no_update, False, "", "info"
        if "pred-refresh-btn" in trigger_id and ".n_clicks" in trigger_id:
            id_str = trigger_id.split('.')[0]
            id_dict = json.loads(id_str)
            prediction_id = id_dict.get("index")
            if prediction_id:
                def refresh_task():
                    try:
                        with Session(_engine) as db:
                            pred = db.query(Prediction).filter(Prediction.prediction_id == prediction_id).first()
                            if not pred:
                                return {"status": "error", "error": "Prediction not found"}
                            entity = db.query(Entity).filter(Entity.entity_id == pred.entity_id).first()
                            if not entity:
                                return {"status": "error", "error": "Entity not found"}
                            outcome = db.query(PredictionOutcome).filter(
                                PredictionOutcome.prediction_id == prediction_id
                            ).first()
                            if not outcome:
                                outcome = PredictionOutcome(
                                    outcome_id=uuid.uuid4(),
                                    prediction_id=prediction_id,
                                    actual_return=0,
                                    error=0,
                                    direction_correct=False,
                                    within_confidence_interval=True,
                                    sharpe_contribution=0,
                                    evaluation_timestamp=datetime.now(),
                                    created_at=datetime.now()
                                )
                                db.add(outcome)
                                db.flush()
                            performance = _format_saved_performance(pred, entity, outcome, load_live_prices=True)
                            if not performance:
                                return {"status": "error", "error": "Could not calculate performance"}
                            outcome.actual_return = performance.get('total_return_pct', 0)
                            outcome.error = abs(performance.get('total_return_pct', 0))
                            outcome.direction_correct = performance.get('is_correct', False)
                            outcome.evaluation_timestamp = datetime.now()
                            db.commit()
                            return {
                                "status": "success",
                                "total_return_pct": performance.get('total_return_pct', 0),
                                "is_correct": performance.get('is_correct', False)
                            }
                    except Exception as e:
                        logger.error(f"Error in refresh_task for {prediction_id}: {e}", exc_info=True)
                        return {"status": "error", "error": str(e)}

                queue_mgr = get_task_queue()
                queue_stats = queue_mgr.get_queue_stats()
                queue_size = queue_stats.get('queue_sizes', {}).get('refresh_prediction', 0)
                task_id = add_gui_task(task_type="refresh_prediction", function=refresh_task, priority=1)
                toast_msg = f"Refreshing... (queue position: {queue_size + 1})" if queue_size > 0 else "Refreshing performance..."
                return {"prediction_id": prediction_id, "task_id": task_id}, dash.no_update, True, toast_msg, "info"
        return {}, dash.no_update, False, "", "info"

    @app.callback(
        [Output("predictions-table", "children", allow_duplicate=True),
         Output("refresh-toast", "is_open", allow_duplicate=True),
         Output("refresh-toast", "children", allow_duplicate=True),
         Output("refresh-toast", "icon", allow_duplicate=True),
         Output("refresh-loading-state", "data", allow_duplicate=True)],
        [Input("interval-component", "n_intervals")],
        [State("refresh-loading-state", "data"),
         State("pred-horizon-filter", "value"),
         State("pred-entity-filter", "value"),
         State("pred-date-filter", "start_date"),
         State("pred-date-filter", "end_date"),
         State("pred-surprise-filter", "value"),
         State("pred-confidence-filter", "value")],
        prevent_initial_call=True
    )
    def refresh_prediction_performance(n_intervals, loading_state, horizon, entities, start_date, end_date, surprise_filter, min_conf):
        """Check task queue and update UI when tasks complete"""
        from src.gui.utils.task_queue import TaskStatus
        try:
            if not loading_state or "task_id" not in loading_state:
                raise PreventUpdate
            task_id = loading_state.get("task_id")
            prediction_id = loading_state.get("prediction_id")
            if not task_id or not prediction_id:
                raise PreventUpdate
            queue_mgr = get_task_queue()
            status = queue_mgr.get_task_status(task_id)
        except PreventUpdate:
            raise
        except Exception as e:
            logger.error(f"Error in refresh_prediction_performance: {e}", exc_info=True)
            raise PreventUpdate
        if status is None or status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            raise PreventUpdate
        try:
            import time
            time.sleep(0.5)
            date_range = (start_date, end_date) if start_date or end_date else None
            table = get_predictions_table(
                _engine,
                entity_filter=entities,
                date_range=date_range,
                min_confidence=min_conf or 0,
                horizon=horizon or '5d',
                surprise_filter=surprise_filter or 'all',
                refreshing_prediction_id=None
            )
            toast_msg = ""
            toast_icon = "info"
            if status == TaskStatus.COMPLETED:
                result = queue_mgr.get_task_result(task_id)
                if result and isinstance(result, dict):
                    toast_msg = f"Performance updated: {result.get('total_return_pct', 0):+.2f}%"
                    toast_icon = "success"
                else:
                    toast_msg = "Performance updated"
                    toast_icon = "success"
            elif status == TaskStatus.FAILED:
                toast_msg = "Error updating performance"
                toast_icon = "danger"
            elif status == TaskStatus.CANCELLED:
                toast_msg = "Task cancelled"
                toast_icon = "warning"
            return table, True, toast_msg, toast_icon, {}
        except Exception as e:
            logger.error(f"Error updating UI after task completion: {e}", exc_info=True)
            return dash.no_update, True, "Error displaying results", "danger", {}

    @app.callback(
        [Output("prediction-modal-title", "children"),
         Output("prediction-modal-body", "children")],
        [Input("prediction-detail-cache", "data")],
        [State("prediction-modal", "is_open")],
        prevent_initial_call=True
    )
    def update_modal_content(cached_data, is_open):
        """Update modal content from cached prediction_id"""
        if not is_open or not cached_data or "prediction_id" not in cached_data:
            return dash.no_update, dash.no_update
        prediction_id = cached_data["prediction_id"]
        load_performance = cached_data.get("load_performance", False)
        title, body = get_prediction_details(_engine, prediction_id, load_performance=load_performance)
        return title, body