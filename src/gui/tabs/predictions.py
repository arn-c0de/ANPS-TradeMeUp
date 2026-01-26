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
from src.gui.helpers.prediction_details_popup import (
    get_prediction_details,
    create_prediction_modal,
    _format_saved_performance
)

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


def _find_first_valid_trigger(triggered):
    """Helper to find the first non-empty trigger and extract action + prediction_id

    Returns:
        tuple(action, prediction_id) where action in {'close', 'refresh', 'detail'} or (None, None)
    """
    if not triggered:
        return None, None
    for trigger in triggered:
        prop_id = trigger.get("prop_id", "")
        value = trigger.get("value")
        # Skip falsy clicks (None or 0)
        if value is None or value == 0:
            continue
        if "close-prediction-modal" in prop_id:
            return "close", None
        if "refresh-prediction-detail" in prop_id:
            return "refresh", None
        if ("pred-detail-btn" in prop_id or "sim-detail-btn" in prop_id) and ".n_clicks" in prop_id:
            try:
                id_str = prop_id.split('.')[0]
                id_dict = json.loads(id_str)
                return "detail", id_dict.get("index")
            except Exception as e:
                logger.warning(f"Failed to parse detail button id from trigger: {prop_id}, error: {e}")
                return None, None
    return None, None


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
            dcc.Store(id="refresh-loading-state", data={}),
            dcc.Store(id="simulation-sync-trigger", data={})  # Triggered when simulations update
        ], fluid=True),

        # Modal OUTSIDE container for proper z-index and positioning
        create_prediction_modal(),

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
         Input("refresh-loading-state", "data"),
         Input("simulation-sync-trigger", "data")]  # Triggered when simulations update
    )
    def update_predictions_table(entities, start_date, end_date, horizon, surprise_filter, min_conf, loading_state, sim_sync):
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

    def _find_first_valid_trigger(triggered):
        """Helper to find the first non-empty trigger and extract action + prediction_id

        Returns:
            tuple(action, prediction_id) where action in {'close', 'refresh', 'detail'} or (None, None)
        """
        if not triggered:
            return None, None
        for trigger in triggered:
            prop_id = trigger.get("prop_id", "")
            value = trigger.get("value")
            # Skip falsy clicks (None or 0)
            if value is None or value == 0:
                continue
            if "close-prediction-modal" in prop_id:
                return "close", None
            if "refresh-prediction-detail" in prop_id:
                return "refresh", None
            if ("pred-detail-btn" in prop_id or "sim-detail-btn" in prop_id) and ".n_clicks" in prop_id:
                try:
                    id_str = prop_id.split('.')[0]
                    id_dict = json.loads(id_str)
                    return "detail", id_dict.get("index")
                except Exception as e:
                    logger.warning(f"Failed to parse detail button id from trigger: {prop_id}, error: {e}")
                    return None, None
        return None, None

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

        # Log raw triggers for diagnostics
        try:
            logger.debug(f"toggle_prediction_modal raw triggered: {callback_context.triggered}")
        except Exception:
            logger.exception("Failed to access callback_context.triggered for logging")

        try:
            action, prediction_id = _find_first_valid_trigger(callback_context.triggered)

            logger.debug(f"toggle_prediction_modal parsed action={action}, prediction_id={prediction_id}")

            if not action:
                return dash.no_update, dash.no_update, dash.no_update
            if action == "close":
                return False, dash.no_update, dash.no_update
            if action == "refresh" and current_pred_id:
                return True, {"prediction_id": current_pred_id, "load_performance": True}, current_pred_id
            if action == "detail" and prediction_id:
                logger.info(f"Opening prediction modal for id: {prediction_id}")
                return True, {"prediction_id": prediction_id, "load_performance": True}, prediction_id
            return dash.no_update, dash.no_update, dash.no_update
        except Exception as e:
            logger.exception(f"Unexpected error in toggle_prediction_modal: {e}")
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
        [State("prediction-modal", "is_open"),
         State("portfolio-capital-input", "value"),
         State("portfolio-currency-dropdown", "value"),
         State("portfolio-risk-adjustment", "value")],
        prevent_initial_call=True
    )
    def update_modal_content(cached_data, is_open, portfolio_capital, currency, risk_adjustment):
        """Update modal content from cached prediction_id with portfolio context"""
        if not is_open or not cached_data or "prediction_id" not in cached_data:
            return dash.no_update, dash.no_update
        prediction_id = cached_data["prediction_id"]
        load_performance = cached_data.get("load_performance", False)

        # Use default values if portfolio settings not configured
        portfolio_capital = portfolio_capital or 100000
        currency = currency or "USD"
        risk_adjustment = risk_adjustment if risk_adjustment is not None else 0.3

        # If loading live performance, update all predictions for this entity
        if load_performance:
            try:
                with Session(_engine) as db:
                    # Get the prediction to find entity_id
                    from src.models.predictions import Prediction
                    pred = db.query(Prediction).filter(
                        Prediction.prediction_id == prediction_id
                    ).first()
                    
                    if pred and pred.entity_id:
                        logger.info(f"📊 Batch-updating all predictions for {pred.entity_id}")
                        
                        from src.services.auto_prediction_processor import auto_processor
                        update_stats = auto_processor.update_all_predictions_for_entity(
                            db,
                            pred.entity_id
                        )
                        
                        logger.info(f"✅ Batch update complete: {update_stats['updated']}/{update_stats['total_found']} predictions updated")
            except Exception as e:
                logger.error(f"Error in batch update: {e}")
                # Continue anyway to show modal

        title, body = get_prediction_details(
            _engine,
            prediction_id,
            load_performance=load_performance,
            portfolio_capital=portfolio_capital,
            currency=currency,
            risk_adjustment=risk_adjustment
        )
        return title, body