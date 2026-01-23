"""
TradeMeUp Dashboard - Main Application
Multi-tab dashboard for monitoring news, predictions, and system health
"""

# Suppress pandas deprecation warnings from yfinance library
import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning, module='yfinance')
warnings.filterwarnings('ignore', message='.*Timestamp.utcnow.*')

import dash
from dash import dcc, html, Input, Output, State, ALL, MATCH
import dash_bootstrap_components as dbc
from datetime import datetime
from pathlib import Path
import plotly.graph_objects as go
import pandas as pd
from sqlalchemy import create_engine
import logging

from src.config.settings import settings
from src.gui.components import create_navbar
from src.utils.activity_logger import activity_logger

logger = logging.getLogger(__name__)

# Import tab modules
from src.gui.tabs import dashboard, predictions, news, statistics, charts, system, control, testing
from src.gui.tabs import settings as settings_tab

# Initialize Dash app with Bootstrap dark theme
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.CYBORG],
    suppress_callback_exceptions=True
)

app.title = "TradeMeUp - AI Trading Intelligence"

# Custom dark theme CSS for dropdowns, date pickers and news cards
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            /* Dark theme for Dash dropdowns */
            .Select-control, .Select-menu-outer, .Select-menu {
                background-color: #060606 !important;
                border-color: #444 !important;
            }
            .Select-control:hover {
                border-color: #888 !important;
            }
            .Select-value-label, .Select-placeholder, .Select-input > input {
                color: #fff !important;
            }
            .Select-option {
                background-color: #060606 !important;
                color: #fff !important;
            }
            .Select-option:hover, .Select-option.is-focused {
                background-color: #2a2a2a !important;
            }
            .Select-option.is-selected {
                background-color: #0d6efd !important;
            }
            .Select-multi-value-wrapper {
                color: #fff !important;
            }
            
            /* Dark theme for date pickers */
            .DateInput_input, .DateRangePickerInput {
                background-color: #060606 !important;
                color: #fff !important;
                border-color: #444 !important;
            }
            .DateInput_input::placeholder {
                color: #888 !important;
            }
            .CalendarDay__default {
                background-color: #1a1a1a !important;
                color: #fff !important;
                border-color: #333 !important;
            }
            .CalendarDay__default:hover {
                background-color: #2a2a2a !important;
            }
            .CalendarDay__selected {
                background-color: #0d6efd !important;
                color: #fff !important;
            }
            .DayPicker, .DayPickerNavigation_button {
                background-color: #0a0a0a !important;
            }
            .CalendarMonth_caption {
                color: #fff !important;
            }
            
            /* Dark theme for Bootstrap cards and card bodies */
            .card {
                background-color: #0a0a0a !important;
                border-color: #222 !important;
            }
            .card-body {
                background-color: #0a0a0a !important;
                color: #e0e0e0 !important;
            }
            .card-header {
                background-color: #060606 !important;
                border-bottom-color: #222 !important;
                color: #fff !important;
            }
            
            /* Force dark background on Bootstrap containers, rows, cols */
            .container, .container-fluid, .row, .col, [class*="col-"] {
                background-color: transparent !important;
            }
            
            /* Force dark on all divs */
            div {
                background-color: transparent !important;
            }
            
            /* Override any white/light backgrounds */
            * {
                background-color: inherit !important;
            }
            
            /* But enforce dark on main containers */
            body, html, #react-entry-point, #_dash-app-content {
                background-color: #060606 !important;
                color: #e0e0e0 !important;
            }
            
            /* Dark theme for news cards */
            .news-card-compact .card-body {
                background-color: #0a0a0a !important;
                border: 1px solid #222 !important;
            }
            .news-card-compact:hover .card-body {
                background-color: #1a1a1a !important;
                border-color: #444 !important;
            }
            .news-title {
                color: #e0e0e0 !important;
                font-weight: 500;
            }
            .news-title:hover {
                color: #0d6efd !important;
            }
            
            /* Dark theme for tables */
            .table-dark {
                background-color: #0a0a0a !important;
                color: #e0e0e0 !important;
            }
            .table-dark thead th {
                background-color: #060606 !important;
                border-color: #222 !important;
                color: #fff !important;
            }
            .table-dark tbody tr {
                background-color: #0a0a0a !important;
                border-color: #222 !important;
            }
            .table-dark tbody tr:hover {
                background-color: #1a1a1a !important;
            }
            .table-dark td, .table-dark th {
                border-color: #222 !important;
                color: #e0e0e0 !important;
            }
            .table-dark a {
                color: #6ea8fe !important;
            }
            .table-dark a:hover {
                color: #0d6efd !important;
            }
            
            /* Override striped tables - force dark on ALL rows */
            .table-striped tbody tr, 
            .table-striped tbody tr:nth-of-type(odd),
            .table-striped tbody tr:nth-of-type(even),
            .table-striped.table-dark tbody tr,
            .table-striped.table-dark tbody tr:nth-of-type(odd),
            .table-striped.table-dark tbody tr:nth-of-type(even) {
                background-color: #0a0a0a !important;
            }
            .table-striped tbody tr:hover,
            .table-striped.table-dark tbody tr:hover {
                background-color: #1a1a1a !important;
            }
            
            /* Force all table cells dark - ULTRA AGGRESSIVE */
            table tbody tr td,
            table tbody tr th,
            .table tbody tr td,
            .table tbody tr th,
            .table-dark tbody tr td,
            .table-dark tbody tr th,
            .table.table-striped tbody tr td,
            .table.table-striped tbody tr th,
            .table-dark.table-striped tbody tr td,
            .table-dark.table-striped tbody tr th,
            .table.table-striped.table-dark tbody tr td,
            .table.table-striped.table-dark tbody tr th {
                background-color: #0a0a0a !important;
                color: #e0e0e0 !important;
            }
            
            /* Remove any rgba backgrounds */
            .table-striped > tbody > tr:nth-of-type(2n+1) > *,
            .table-striped tbody tr:nth-of-type(2n+1) td,
            .table-striped tbody tr:nth-of-type(2n+1) th {
                background-color: #0a0a0a !important;
                --bs-table-striped-bg: #0a0a0a !important;
                --bs-table-bg: #0a0a0a !important;
            }
            
            /* Force dark background on all divs inside cards */
            .card-body > div {
                background-color: transparent !important;
            }
            
            /* Dark theme for alerts */
            .alert {
                background-color: #1a1a1a !important;
                border-color: #333 !important;
                color: #e0e0e0 !important;
            }
            .alert-info {
                background-color: #0c3c56 !important;
                border-color: #0a5a7a !important;
            }
            .alert-warning {
                background-color: #665200 !important;
                border-color: #997a00 !important;
            }
            .alert-danger {
                background-color: #661a1a !important;
                border-color: #992626 !important;
            }
            
            /* Dark theme for input fields */
            input[type="text"], textarea {
                background-color: #060606 !important;
                color: #fff !important;
                border-color: #444 !important;
            }
            input[type="text"]::placeholder, textarea::placeholder {
                color: #888 !important;
            }
            input[type="text"]:focus, textarea:focus {
                background-color: #0a0a0a !important;
                border-color: #0d6efd !important;
                color: #fff !important;
            }
            
            /* Ensure all text is light colored */
            body, .container, .container-fluid, div, p, span, small {
                color: #e0e0e0 !important;
            }
            
            /* Dark scrollbar */
            ::-webkit-scrollbar {
                width: 10px;
                height: 10px;
            }
            ::-webkit-scrollbar-track {
                background: #0a0a0a;
            }
            ::-webkit-scrollbar-thumb {
                background: #333;
                border-radius: 5px;
            }
            ::-webkit-scrollbar-thumb:hover {
                background: #555;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# Database connection
engine = create_engine(settings.database_url)

# ============================================================================
# MAIN LAYOUT
# ============================================================================

app.layout = html.Div([
    dcc.Interval(id="interval-component", interval=5*1000, n_intervals=0),  # 5 seconds for live updates
    dcc.Store(id="continuous-pipeline-state", data={"running": False, "pid": None}),
    dcc.Store(id="delete-action-store", data={"action": None, "params": None}),
    create_navbar(),
    dbc.Container([
        dbc.Tabs([
            dbc.Tab(dashboard.create_layout(), label="🏠 Dashboard", tab_id="dashboard", className="text-light"),
            dbc.Tab(predictions.create_layout(), label="🎯 Predictions", tab_id="predictions", className="text-light"),
            dbc.Tab(news.create_layout(), label="📰 News Feed", tab_id="news", className="text-light"),
            dbc.Tab(statistics.create_layout(), label="📊 Statistics", tab_id="statistics", className="text-light"),
            dbc.Tab(charts.create_layout(), label="📈 Live Charts", tab_id="charts", className="text-light"),
            dbc.Tab(control.create_layout(), label="🎮 Agent Control", tab_id="control", className="text-light"),
            dbc.Tab(testing.create_layout(), label="🧪 Testing", tab_id="testing", className="text-light"),
            dbc.Tab(system.create_layout(), label="🔧 System Health", tab_id="system", className="text-light"),
            dbc.Tab(settings_tab.create_layout(), label="⚙️ Settings", tab_id="settings", className="text-light")
        ], id="tabs", active_tab="dashboard", persistence=True, persistence_type="local")
    ], fluid=True)
], className="bg-dark text-light min-vh-100")


# ============================================================================
# CALLBACKS - COMMON
# ============================================================================

@app.callback(
    Output("live-status", "children"),
    Input("interval-component", "n_intervals")
)
def update_live_status(n):
    """Update live status indicator"""
    now = datetime.now().strftime("%H:%M:%S")
    return html.Div([
        html.Span("● ", className="text-success"),
        html.Small(f"Live • Updated {now}")
    ])


# ============================================================================
# CALLBACKS - CONTINUOUS PIPELINE CONTROL
# ============================================================================

@app.callback(
    [Output("continuous-pipeline-state", "data"),
     Output("btn-start-continuous", "disabled"),
     Output("btn-stop-continuous", "disabled")],
    [Input("btn-start-continuous", "n_clicks"),
     Input("btn-stop-continuous", "n_clicks")],
    State("continuous-pipeline-state", "data"),
    prevent_initial_call=True
)
def control_continuous_pipeline(start_clicks, stop_clicks, current_state):
    """Start or stop continuous pipeline"""
    from src.utils.process_utils import start_background_process, stop_process
    
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update
    
    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    
    if button_id == "btn-start-continuous":
        # Start continuous pipeline in separate console window
        import sys
        import os
        import logging
        import subprocess
        from pathlib import Path
        logger = logging.getLogger(__name__)

        # Log Python executable being used
        logger.info(f"Starting continuous pipeline with Python: {sys.executable}")

        # Use wrapper batch script to keep console open on errors
        wrapper_script = Path("scripts/run_continuous_pipeline_wrapper.bat").absolute()

        if not wrapper_script.exists():
            error_msg = f"Wrapper script not found: {wrapper_script}"
            activity_logger.log_activity(error_msg, "ERROR")
            logger.error(error_msg)
            return dash.no_update

        # Start in new console window using start command
        # The wrapper script keeps the window open even if process crashes
        try:
            # Use simple approach: directly call the batch file with start
            # This opens a new console window
            cmd = f'start "TradeMeUp Pipeline" /D "{Path.cwd()}" "{wrapper_script}" --interval 300'

            # Start the process using shell command
            process = subprocess.Popen(
                cmd,
                shell=True,
                cwd=str(Path.cwd())
            )

            success = True
            message = f"Pipeline console opened"
            logger.info(f"Started pipeline with command: {cmd}")
        except Exception as e:
            success = False
            message = f"Failed to start console: {e}"
            logger.error(message, exc_info=True)

        if success and process:
            activity_logger.log_activity(
                f"Continuous Pipeline console opened - Check the new terminal window",
                "SUCCESS"
            )
            logger.info(f"Pipeline console started with PID: {process.pid}")

            return (
                {"running": True, "pid": process.pid},
                True,  # Disable start button
                False  # Enable stop button
            )
        else:
            # Log and show error to user
            activity_logger.log_activity(
                f"Failed to start continuous pipeline: {message}",
                "ERROR"
            )
            # Keep UI state unchanged, user sees log
            return dash.no_update
    
    elif button_id == "btn-stop-continuous":
        # Stop continuous pipeline
        if current_state.get("pid"):
            success, message = stop_process(current_state["pid"])
            
            if success:
                activity_logger.log_activity(
                    f"Continuous Pipeline STOPPED: {message}",
                    "INFO"
                )
            else:
                activity_logger.log_activity(
                    f"Warning stopping pipeline: {message}",
                    "WARNING"
                )
        
        # Always reset state (even if stop failed, process may be gone)
        return (
            {"running": False, "pid": None},
            False,  # Enable start button
            True    # Disable stop button
        )
    
    return dash.no_update


@app.callback(
    Output("continuous-status", "children"),
    Input("interval-component", "n_intervals"),
    State("continuous-pipeline-state", "data")
)
def update_continuous_status(n, state):
    """Update continuous pipeline status display"""
    if state and state.get("running"):
        return html.Div([
            html.Span("🔄 ", className="text-success"),
            html.Small("Auto Mode", className="text-success fw-bold")
        ])
    else:
        return html.Div([
            html.Span("⏸️ ", className="text-muted"),
            html.Small("Manual Mode", className="text-muted")
        ])


# ============================================================================
# CALLBACKS - DASHBOARD TAB
# ============================================================================

@app.callback(
    Output("dashboard-metrics", "children"),
    Input("interval-component", "n_intervals")
)
def update_dashboard_metrics(n):
    """Update dashboard metric cards"""
    return dashboard.get_metrics(engine)


@app.callback(
    Output("recent-news-table", "children"),
    Input("interval-component", "n_intervals")
)
def update_recent_news(n):
    """Update recent news table"""
    return dashboard.get_recent_news(engine, limit=50)


@app.callback(
    Output("market-regime-display", "children"),
    Input("interval-component", "n_intervals")
)
def update_market_regime(n):
    """Update market regime display"""
    return dashboard.get_market_regime(engine)


@app.callback(
    Output("live-agent-activity", "children"),
    Input("interval-component", "n_intervals")
)
def update_live_agent_activity(n):
    """Update live agent activity display"""
    return dashboard.get_live_agent_activity()


@app.callback(
    Output("server-logs-display", "value"),
    Input("interval-component", "n_intervals")
)
def update_server_logs(n):
    """Update server logs display"""
    return dashboard.get_server_logs()


@app.callback(
    Output("performance-chart", "figure"),
    Input("interval-component", "n_intervals")
)
def update_performance_chart(n):
    """Create dummy performance chart (placeholder)"""
    dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
    accuracy = [0.65 + (i % 10) * 0.03 for i in range(30)]
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dates, y=accuracy,
        mode='lines+markers',
        name='Accuracy',
        line=dict(color='#00d9ff', width=3)
    ))
    
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        xaxis_title="Date",
        yaxis_title="Accuracy",
        yaxis=dict(range=[0, 1]),
        margin=dict(l=40, r=40, t=40, b=40)
    )
    
    return fig


# ============================================================================
# CALLBACKS - PREDICTIONS TAB
# ============================================================================

@app.callback(
    Output("pred-entity-filter", "options"),
    Input("interval-component", "n_intervals")
)
def update_entity_filter_options(n):
    """Update entity filter dropdown options"""
    return predictions.get_entity_options(engine)


@app.callback(
    Output("predictions-table", "children"),
    [Input("interval-component", "n_intervals"),
     Input("pred-entity-filter", "value"),
     Input("pred-date-filter", "start_date"),
     Input("pred-date-filter", "end_date"),
     Input("pred-horizon-filter", "value"),
     Input("pred-confidence-filter", "value")]
)
def update_predictions_table(n, entities, start_date, end_date, horizon, min_conf):
    """Update predictions table with filters"""
    date_range = (start_date, end_date) if start_date or end_date else None
    return predictions.get_predictions_table(
        engine,
        entity_filter=entities,
        date_range=date_range,
        min_confidence=min_conf or 0,
        horizon=horizon or '5d'
    )


@app.callback(
    [Output("prediction-modal", "is_open"),
     Output("prediction-detail-cache", "data"),
     Output("current-prediction-id", "data")],
    [Input({"type": "pred-detail-btn", "index": ALL}, "n_clicks"),
     Input("close-prediction-modal", "n_clicks"),
     Input("refresh-prediction-detail", "n_clicks")],
    [State("prediction-modal", "is_open"),
     State({"type": "pred-detail-btn", "index": ALL}, "id"),
     State("prediction-detail-cache", "data"),
     State("current-prediction-id", "data")],
    prevent_initial_call=True
)
def toggle_prediction_modal(detail_clicks, close_click, refresh_click, is_open, button_ids, cached_data, current_pred_id):
    """Open/close prediction detail modal and cache prediction_id"""
    logger.info(f"=== MODAL TOGGLE CALLBACK === details: {detail_clicks}, close: {close_click}, refresh: {refresh_click}")
    
    from dash import callback_context

    if not callback_context.triggered:
        logger.info("No trigger context for modal")
        return dash.no_update, dash.no_update, dash.no_update

    trigger_id = callback_context.triggered[0]["prop_id"]
    logger.info(f"Modal trigger: {trigger_id}")

    # Only process if the trigger value changed (not just a re-render)
    trigger_value = callback_context.triggered[0].get("value")
    if trigger_value is None or trigger_value == 0:
        logger.info(f"Trigger value is None or 0: {trigger_value}")
        return dash.no_update, dash.no_update, dash.no_update

    # Close button clicked
    if "close-prediction-modal" in trigger_id:
        return False, dash.no_update, dash.no_update
    
    # Refresh button clicked - keep modal open, trigger reload with performance
    if "refresh-prediction-detail" in trigger_id and current_pred_id:
        return True, {"prediction_id": current_pred_id, "load_performance": True}, current_pred_id

    # Detail button clicked - parse the prop_id to get the index
    if "pred-detail-btn" in trigger_id and ".n_clicks" in trigger_id:
        # Extract prediction_id from triggered prop_id
        import json
        # prop_id format: '{"index":"uuid","type":"pred-detail-btn"}.n_clicks'
        id_str = trigger_id.split('.')[0]
        id_dict = json.loads(id_str)
        prediction_id = id_dict.get("index")

        if prediction_id:
            # First load without performance for speed
            return True, {"prediction_id": prediction_id, "load_performance": False}, prediction_id

    # No actual button was clicked (just re-render), don't update
    return dash.no_update, dash.no_update, dash.no_update


# Note: Inline performance buttons removed for performance reasons
# Performance data is shown in the modal when clicking Details button


@app.callback(
    [Output("predictions-table", "children", allow_duplicate=True),
     Output("refresh-toast", "is_open"),
     Output("refresh-toast", "children"),
     Output("refresh-toast", "icon")],
    [Input({"type": "pred-refresh-btn", "index": ALL}, "n_clicks")],
    [State({"type": "pred-refresh-btn", "index": ALL}, "id"),
     State("pred-horizon-filter", "value")],
    prevent_initial_call=True
)
def refresh_prediction_performance(refresh_clicks, button_ids, horizon):
    """Load and save performance data for a specific prediction"""
    logger.info(f"=== REFRESH CALLBACK TRIGGERED === clicks: {refresh_clicks}, ids: {button_ids}, horizon: {horizon}")
    
    from dash import callback_context
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from src.services.prediction_performance_service import prediction_performance_service
    from src.models.predictions import Prediction
    from src.models.entities import Entity
    import json
    
    if not callback_context.triggered:
        logger.info("No trigger context")
        return dash.no_update, False, "", "info"
    
    trigger_id = callback_context.triggered[0]["prop_id"]
    trigger_value = callback_context.triggered[0].get("value")
    
    logger.info(f"Trigger ID: {trigger_id}, Value: {trigger_value}")
    
    # Check if button was actually clicked (value should be > 0)
    if trigger_value is None:
        logger.info("Trigger value is None")
        return dash.no_update, False, "", "info"
    
    # Extract prediction_id from the clicked button
    if "pred-refresh-btn" in trigger_id and ".n_clicks" in trigger_id:
        id_str = trigger_id.split('.')[0]
        id_dict = json.loads(id_str)
        prediction_id = id_dict.get("index")
        
        if prediction_id:
            # Create DB session
            db_engine = create_engine(app.server.config.get('DATABASE_URI', 'sqlite:///trademeup.db'))
            Session = sessionmaker(bind=db_engine)
            db_session = Session()
            
            toast_msg = ""
            toast_icon = "info"
            
            try:
                # Load prediction and entity
                pred = db_session.query(Prediction).filter(
                    Prediction.prediction_id == prediction_id
                ).first()
                
                if not pred:
                    logger.error(f"Prediction {prediction_id} not found in database")
                    db_session.close()
                    toast_msg = "❌ Prediction not found"
                    toast_icon = "danger"
                    table = predictions.get_predictions_table(db_engine, entity_filter=None, date_range=None, min_confidence=0, horizon=horizon or '5d')
                    return table, True, toast_msg, toast_icon
                
                entity = db_session.query(Entity).filter(
                    Entity.entity_id == pred.entity_id
                ).first()
                
                if not entity:
                    logger.error(f"Entity {pred.entity_id} not found for prediction {prediction_id}")
                    db_session.close()
                    toast_msg = "❌ Entity not found"
                    toast_icon = "danger"
                    table = predictions.get_predictions_table(db_engine, entity_filter=None, date_range=None, min_confidence=0, horizon=horizon or '5d')
                    return table, True, toast_msg, toast_icon
                
                logger.info(f"Loading performance for {entity.entity_id} ({entity.entity_name}), prediction {prediction_id}")
                
                # Calculate performance
                perf_data = prediction_performance_service.get_prediction_performance(pred, entity)
                
                if perf_data:
                    # Save to database
                    prediction_performance_service.save_prediction_performance(
                        prediction_id, perf_data, db_session
                    )
                    logger.info(f"✅ Saved performance for {prediction_id}: {perf_data.get('total_return_pct')}%")
                    
                    # Success toast
                    toast_msg = f"✅ {entity.entity_name}: {perf_data.get('total_return_pct'):+.2f}%"
                    toast_icon = "success"
                else:
                    logger.warning(f"⚠️ Could not calculate performance for {prediction_id} - ticker: {entity.entity_id}")
                    
                    # Check if it's an invalid ticker
                    invalid_tickers = ['OTHER', 'UNKNOWN', 'N/A', 'NONE', 'TEST', 'HEALTH', 'TAO']
                    if entity.entity_id.upper() in invalid_tickers:
                        toast_msg = f"⚠️ {entity.entity_name}: No market ticker"
                    else:
                        toast_msg = f"⚠️ {entity.entity_name}: Market data unavailable"
                    toast_icon = "warning"
                    
            except Exception as e:
                logger.error(f"Error refreshing prediction performance: {e}", exc_info=True)
                toast_msg = f"❌ Error: {str(e)[:50]}"
                toast_icon = "danger"
            finally:
                db_session.close()
            
            # Refresh the table with proper parameters
            table = predictions.get_predictions_table(
                db_engine,
                entity_filter=None,
                date_range=None,
                min_confidence=0,
                horizon=horizon or '5d'
            )
            
            return table, True, toast_msg, toast_icon
    
    return dash.no_update, False, "", "info"


@app.callback(
    [Output("prediction-modal-title", "children"),
     Output("prediction-modal-body", "children")],
    [Input("prediction-detail-cache", "data")],
    [State("prediction-modal", "is_open")],
    prevent_initial_call=True
)
def update_modal_content(cached_data, is_open):
    """Update modal content from cached prediction_id (survives interval updates)"""
    # Only load if modal is open and we have a prediction_id
    if not is_open or not cached_data or "prediction_id" not in cached_data:
        return dash.no_update, dash.no_update

    # Load fresh data from DB using cached prediction_id
    prediction_id = cached_data["prediction_id"]
    load_performance = cached_data.get("load_performance", False)
    title, body = predictions.get_prediction_details(engine, prediction_id, load_performance=load_performance)
    return title, body


# ============================================================================
# CALLBACKS - NEWS TAB
# ============================================================================

@app.callback(
    Output("news-source-filter", "options"),
    Input("interval-component", "n_intervals")
)
def update_news_source_options(n):
    """Populate source filter dropdown with available sources"""
    from sqlalchemy import distinct
    from src.models.raw_news import RawNews
    from src.models.database import SessionLocal
    
    try:
        with SessionLocal() as db:
            sources = db.query(distinct(RawNews.source)).order_by(RawNews.source).all()
            return [{"label": src[0], "value": src[0]} for src in sources if src[0]]
    except Exception as e:
        return []


@app.callback(
    Output("news-feed", "children"),
    [Input("interval-component", "n_intervals"),
     Input("news-source-filter", "value"),
     Input("news-event-filter", "value"),
     Input("news-sentiment-filter", "value"),
     Input("news-search-input", "value")]
)
def update_news_feed(n, sources, events, sentiment, search):
    """Update news feed with filters"""
    return news.get_news_feed(engine, sources, events, sentiment, search)


# ============================================================================
# CALLBACKS - STATISTICS TAB
# ============================================================================

@app.callback(
    Output("statistics-metrics", "children"),
    Input("interval-component", "n_intervals")
)
def update_statistics_metrics(n):
    """Update statistics metrics"""
    return statistics.get_statistics_metrics(engine)


@app.callback(
    [Output("event-distribution-chart", "figure"),
     Output("quality-distribution-chart", "figure")],
    Input("interval-component", "n_intervals")
)
def update_statistics_charts(n):
    """Update statistics charts"""
    event_fig = statistics.get_event_distribution_chart(engine)
    quality_fig = statistics.get_quality_distribution_chart(engine)
    return event_fig, quality_fig


@app.callback(
    Output("sentiment-distribution-chart", "figure"),
    Input("interval-component", "n_intervals")
)
def update_sentiment_chart(n):
    """Update sentiment distribution chart"""
    return statistics.get_sentiment_distribution_chart(engine)


@app.callback(
    Output("impact-distribution-chart", "figure"),
    Input("interval-component", "n_intervals")
)
def update_impact_chart(n):
    """Update impact distribution chart"""
    return statistics.get_impact_distribution_chart(engine)


@app.callback(
    Output("top-entities-list", "children"),
    Input("interval-component", "n_intervals")
)
def update_top_entities(n):
    """Update top entities list"""
    return statistics.get_top_entities_list(engine)


@app.callback(
    Output("news-volume-chart", "figure"),
    Input("interval-component", "n_intervals")
)
def update_news_volume(n):
    """Update news volume chart"""
    return statistics.get_news_volume_chart(engine)


# NEW: Entity Sentiment Analysis Callbacks
@app.callback(
    Output("entity-sentiment-chart", "figure"),
    [Input("interval-component", "n_intervals"),
     Input("sentiment-timeframe-selector", "value")]
)
def update_entity_sentiment_chart(n, timeframe):
    """Update entity sentiment chart with timeframe filter"""
    return statistics.get_entity_sentiment_chart(engine, timeframe)


@app.callback(
    [Output("top-positive-entities", "children"),
     Output("positive-entities-toggle", "children"),
     Output("positive-entities-toggle", "style"),
     Output("positive-entities-expanded", "data")],
    [Input("interval-component", "n_intervals"),
     Input("positive-entity-search-input", "value"),
     Input("positive-entities-toggle", "n_clicks")],
    [State("positive-entities-expanded", "data")]
)
def update_top_positive_entities(n, search_term, n_clicks, is_expanded):
    """Update top positive entities with optional search filter and expand/collapse"""
    from dash import callback_context
    
    # Toggle expanded state if button was clicked
    if callback_context.triggered and "positive-entities-toggle" in callback_context.triggered[0]["prop_id"]:
        is_expanded = not is_expanded
    
    # Get entities with appropriate limit
    entities = statistics.get_top_positive_entities(engine, search_term or "", show_all=is_expanded)
    
    # Update button text and visibility
    button_text = "Show Less" if is_expanded else "Show More"
    button_style = {"display": "none" if search_term else "inline-block"}
    
    return entities, button_text, button_style, is_expanded


@app.callback(
    [Output("top-negative-entities", "children"),
     Output("negative-entities-toggle", "children"),
     Output("negative-entities-toggle", "style"),
     Output("negative-entities-expanded", "data")],
    [Input("interval-component", "n_intervals"),
     Input("negative-entity-search-input", "value"),
     Input("negative-entities-toggle", "n_clicks")],
    [State("negative-entities-expanded", "data")]
)
def update_top_negative_entities(n, search_term, n_clicks, is_expanded):
    """Update top negative entities with optional search filter and expand/collapse"""
    from dash import callback_context
    
    # Toggle expanded state if button was clicked
    if callback_context.triggered and "negative-entities-toggle" in callback_context.triggered[0]["prop_id"]:
        is_expanded = not is_expanded
    
    # Get entities with appropriate limit
    entities = statistics.get_top_negative_entities(engine, search_term or "", show_all=is_expanded)
    
    # Update button text and visibility
    button_text = "Show Less" if is_expanded else "Show More"
    button_style = {"display": "none" if search_term else "inline-block"}
    
    return entities, button_text, button_style, is_expanded


@app.callback(
    [Output("entity-details-table", "children"),
     Output("entity-table-sort-store", "data")],
    [Input("interval-component", "n_intervals"),
     Input("entity-search-input", "value"),
     Input({"type": "sort-column-btn", "column": dash.dependencies.ALL}, "n_clicks")],
    [State("entity-table-sort-store", "data"),
     State({"type": "sort-column-btn", "column": dash.dependencies.ALL}, "id")],
    prevent_initial_call=False
)
def update_entity_details_table(n, search_term, sort_clicks, sort_state, button_ids):
    """Update entity details table with search and 3-stage sorting (asc → desc → default)"""
    from dash import callback_context
    
    # Default sort state
    if sort_state is None:
        sort_state = {"column": None, "direction": None}
    
    current_column = sort_state.get("column")
    current_direction = sort_state.get("direction")
    
    # Check if a sort button was clicked
    if callback_context.triggered:
        trigger_id = callback_context.triggered[0]["prop_id"]
        
        # Check if trigger is from a sort button
        if "sort-column-btn" in trigger_id and sort_clicks and any(c for c in sort_clicks if c):
            # Find which button was clicked
            for i, clicks in enumerate(sort_clicks):
                if clicks and clicks > 0:
                    clicked_column = button_ids[i]["column"]
                    
                    # 3-stage sorting logic
                    if current_column == clicked_column:
                        # Same column clicked - cycle through states
                        if current_direction == "asc":
                            # asc → desc
                            current_direction = "desc"
                        elif current_direction == "desc":
                            # desc → None (default)
                            current_column = None
                            current_direction = None
                        else:
                            # Should not happen, but reset to asc
                            current_direction = "asc"
                    else:
                        # New column clicked - start with asc
                        current_column = clicked_column
                        current_direction = "asc"
                    
                    break
    
    # Get table with current sort state
    table = statistics.get_entity_details_table(
        engine, 
        search_term or "", 
        current_column, 
        current_direction
    )
    
    # Update sort state
    new_sort_state = {"column": current_column, "direction": current_direction}
    
    return table, new_sort_state


# Entity Details Modal Callbacks
@app.callback(
    [Output("entity-details-modal", "is_open"),
     Output("selected-entity-store", "data")],
    [Input({"type": "entity-detail-btn", "index": dash.dependencies.ALL}, "n_clicks"),
     Input("close-entity-modal", "n_clicks")],
    [State("entity-details-modal", "is_open"),
     State({"type": "entity-detail-btn", "index": dash.dependencies.ALL}, "id")],
    prevent_initial_call=True
)
def toggle_entity_modal(detail_clicks, close_click, is_open, button_ids):
    """Open/close entity details modal"""
    from dash import callback_context
    
    if not callback_context.triggered:
        return dash.no_update, dash.no_update
    
    trigger_id = callback_context.triggered[0]["prop_id"]
    
    # Close button clicked
    if "close-entity-modal" in trigger_id:
        return False, None
    
    # Entity button clicked
    if "entity-detail-btn" in trigger_id:
        # Check if any button was actually clicked (not just re-render)
        if detail_clicks and any(click for click in detail_clicks if click):
            # Find which button was clicked
            for i, click_count in enumerate(detail_clicks):
                if click_count and click_count > 0:
                    entity_name = button_ids[i]["index"]
                    return True, {"entity_name": entity_name}
    
    return dash.no_update, dash.no_update


@app.callback(
    [Output("entity-modal-title", "children"),
     Output("entity-modal-body", "children")],
    Input("selected-entity-store", "data"),
    State("entity-details-modal", "is_open"),
    prevent_initial_call=True
)
def update_entity_modal_content(entity_data, is_open):
    """Load entity details into modal"""
    if not is_open or not entity_data or "entity_name" not in entity_data:
        return dash.no_update, dash.no_update
    
    entity_name = entity_data["entity_name"]
    title, body = statistics.get_entity_full_details(engine, entity_name)
    return title, body


# ============================================================================
# CALLBACKS - CHARTS TAB
# ============================================================================

@app.callback(
    Output("market-indices-display", "children"),
    Input("chart-update-interval", "n_intervals")
)
def update_market_indices(n):
    """Update market indices display"""
    return charts.get_market_indices_cards()


@app.callback(
    [Output("layout-single", "outline"),
     Output("layout-split-h", "outline"),
     Output("layout-split-v", "outline"),
     Output("layout-quad", "outline")],
    Input("chart-panels-config", "data")
)
def highlight_active_layout(config):
    """Highlight the currently active layout button"""
    layout = config.get('layout', 'single')
    return (
        layout != 'single',  # outline=True means not active (inverted logic for outline buttons)
        layout != 'split-horizontal',
        layout != 'split-vertical',
        layout != 'quad'
    )


@app.callback(
    Output("market-overview-collapse", "is_open"),
    Input("toggle-market-overview", "n_clicks"),
    State("market-overview-collapse", "is_open"),
    prevent_initial_call=True
)
def toggle_market_overview(n_clicks, is_open):
    """Toggle market overview section"""
    return not is_open


@app.callback(
    [Output("chart-fullscreen-state", "data"),
     Output("toggle-fullscreen-btn", "children"),
     Output("toggle-fullscreen-btn", "outline"),
     Output("toggle-fullscreen-btn", "color")],
    Input("toggle-fullscreen-btn", "n_clicks"),
    State("chart-fullscreen-state", "data"),
    prevent_initial_call=True
)
def toggle_fullscreen(n_clicks, fullscreen_state):
    """Toggle fullscreen mode for charts"""
    is_fullscreen = fullscreen_state.get('fullscreen', False)
    new_state = not is_fullscreen
    
    if new_state:
        button_text = "⬇ Exit Fullscreen"
        outline = False  # Solid button when in fullscreen
        color = "danger"
    else:
        button_text = "⛶ Fullscreen"
        outline = True  # Outline button in normal mode
        color = "info"
    
    return {'fullscreen': new_state}, button_text, outline, color


@app.callback(
    Output("chart-panels-config", "data"),
    [Input("layout-single", "n_clicks"),
     Input("layout-split-h", "n_clicks"),
     Input("layout-split-v", "n_clicks"),
     Input("layout-quad", "n_clicks"),
     Input("config-apply-btn", "n_clicks"),
     Input({"type": "favorite-btn", "index": dash.dependencies.ALL}, "n_clicks"),
     Input("refresh-all-panels", "n_clicks")],
    [State("chart-panels-config", "data"),
     State("current-config-panel", "children"),
     State("config-symbol-input", "value"),
     State("config-timeframe-selector", "value"),
     State("config-chart-type-selector", "value"),
     State("config-favorite-checkbox", "value")],
    prevent_initial_call=True
)
def update_chart_config(layout_single, layout_h, layout_v, layout_quad, 
                       apply_config, favorite_clicks, refresh_all,
                       current_config, panel_id, symbol, timeframe, chart_type, is_favorite):
    """Update chart panels configuration"""
    from dash import callback_context
    
    if not callback_context.triggered:
        return current_config
    
    trigger_id = callback_context.triggered[0]['prop_id']
    
    # Handle layout changes
    if 'layout-single' in trigger_id:
        current_config['layout'] = 'single'
    elif 'layout-split-h' in trigger_id:
        current_config['layout'] = 'split-horizontal'
    elif 'layout-split-v' in trigger_id:
        current_config['layout'] = 'split-vertical'
    elif 'layout-quad' in trigger_id:
        current_config['layout'] = 'quad'
    
    # Handle panel configuration updates
    elif 'config-apply-btn' in trigger_id and panel_id:
        if panel_id in current_config.get('panels', {}):
            current_config['panels'][panel_id] = {
                'symbol': (symbol or 'AAPL').upper().strip(),
                'timeframe': timeframe or '1mo',
                'chart_type': chart_type or 'candlestick',
                'favorite': bool(is_favorite)
            }
    
    # Handle favorite toggles
    elif 'favorite-btn' in trigger_id:
        import json
        btn_data = json.loads(trigger_id.split('.')[0])
        panel_id = btn_data['index']
        if panel_id in current_config.get('panels', {}):
            current_config['panels'][panel_id]['favorite'] = not current_config['panels'][panel_id].get('favorite', False)
    
    return current_config


@app.callback(
    [Output("multi-panel-chart-area", "children"),
     Output("multi-panel-chart-area", "className")],
    [Input("chart-panels-config", "data"),
     Input("chart-update-interval", "n_intervals"),
     Input("refresh-all-panels", "n_clicks"),
     Input("chart-fullscreen-state", "data")],
    prevent_initial_call='initial_duplicate'
)
def render_chart_panels(config, n_intervals, refresh_clicks, fullscreen_state):
    """Render the multi-panel chart layout with fullscreen support"""
    layout = config.get('layout', 'single')
    panels = config.get('panels', {})
    is_fullscreen = fullscreen_state.get('fullscreen', False)
    
    # Set container class based on fullscreen state
    container_class = 'chart-container-fullscreen' if is_fullscreen else 'chart-container-normal'
    
    chart_layout = charts.render_multi_panel_layout(layout, panels, is_fullscreen)
    return chart_layout, container_class


@app.callback(
    [Output("config-panel-modal", "is_open"),
     Output("current-config-panel", "children"),
     Output("config-symbol-input", "value"),
     Output("config-timeframe-selector", "value"),
     Output("config-chart-type-selector", "value"),
     Output("config-favorite-checkbox", "value")],
    [Input({"type": "config-btn", "index": dash.dependencies.ALL}, "n_clicks"),
     Input("config-cancel-btn", "n_clicks"),
     Input("config-apply-btn", "n_clicks")],
    [State("chart-panels-config", "data"),
     State("config-panel-modal", "is_open")],
    prevent_initial_call=True
)
def toggle_config_modal(config_clicks, cancel_click, apply_click, panels_config, is_open):
    """Toggle configuration modal and populate with panel data"""
    from dash import callback_context
    import json
    
    if not callback_context.triggered:
        raise dash.exceptions.PreventUpdate
    
    trigger_id = callback_context.triggered[0]['prop_id']
    
    # Open modal with panel config - only if button was actually clicked
    if 'config-btn' in trigger_id:
        # Check if this is a real click (not just initialization)
        if config_clicks and any(click for click in config_clicks if click):
            btn_data = json.loads(trigger_id.split('.')[0])
            panel_id = btn_data['index']
            panel_config = panels_config.get('panels', {}).get(panel_id, {})
            
            return (True, panel_id, 
                    panel_config.get('symbol', ''),
                    panel_config.get('timeframe', '1mo'),
                    panel_config.get('chart_type', 'candlestick'),
                    panel_config.get('favorite', False))
        else:
            raise dash.exceptions.PreventUpdate
    
    # Close modal
    elif 'cancel-btn' in trigger_id or 'apply-btn' in trigger_id:
        return False, None, "", "1mo", "candlestick", False
    
    raise dash.exceptions.PreventUpdate


@app.callback(
    [Output("quick-edit-modal", "is_open"),
     Output("current-quick-edit-panel", "children"),
     Output("quick-edit-symbol-input", "value")],
    [Input({"type": "symbol-label", "index": dash.dependencies.ALL}, "n_clicks"),
     Input("quick-edit-cancel-btn", "n_clicks"),
     Input("quick-edit-apply-btn", "n_clicks")],
    [State("chart-panels-config", "data"),
     State("quick-edit-modal", "is_open")],
    prevent_initial_call=True
)
def toggle_quick_edit_modal(label_clicks, cancel_click, apply_click, panels_config, is_open):
    """Toggle quick edit modal when clicking on symbol name"""
    from dash import callback_context
    import json
    
    if not callback_context.triggered:
        raise dash.exceptions.PreventUpdate
    
    trigger_id = callback_context.triggered[0]['prop_id']
    
    # Open modal when symbol label is clicked
    if 'symbol-label' in trigger_id:
        # Check if this is a real click
        if label_clicks and any(click for click in label_clicks if click):
            btn_data = json.loads(trigger_id.split('.')[0])
            panel_id = btn_data['index']
            panel_config = panels_config.get('panels', {}).get(panel_id, {})
            current_symbol = panel_config.get('symbol', '')
            
            return True, panel_id, current_symbol
        else:
            raise dash.exceptions.PreventUpdate
    
    # Close modal
    elif 'cancel-btn' in trigger_id or 'apply-btn' in trigger_id:
        return False, None, ""
    
    raise dash.exceptions.PreventUpdate


@app.callback(
    [Output("symbol-search-results", "children"),
     Output("symbol-search-cache", "data")],
    Input("quick-edit-symbol-input", "value"),
    prevent_initial_call=True
)
def search_symbols_live(query):
    """Search for stock symbols as user types (live search)"""
    if not query or len(query) < 1:
        return html.Div([
            html.Small("💡 Start typing to search symbols by ticker or company name",
                      className="text-muted")
        ]), []

    try:
        from src.gui.charts.market_data import market_data
        results = market_data.search_symbols(query, limit=8)

        if not results:
            return dbc.Alert(
                f"No results found for '{query}'. Try a different search term.",
                color="warning",
                className="mt-2",
                style={"fontSize": "0.9rem"}
            ), []

        # Cache symbols for later retrieval
        symbols_cache = [r.get('symbol', '') for r in results]

        # Display search results as clickable buttons
        result_items = []
        for i, result in enumerate(results):
            symbol = result.get('symbol', 'N/A')
            name = result.get('name', 'Unknown')
            result_type = result.get('type', 'EQUITY')

            result_items.append(
                dbc.ListGroupItem([
                    html.Div([
                        html.Div([
                            html.Strong(symbol, className="text-primary", style={"fontSize": "1.1rem"}),
                            html.Span(f" · {name}", className="text-muted ms-2")
                        ]),
                        html.Small(result_type, className="badge bg-secondary mt-1")
                    ]),
                    dbc.Button("Select",
                              id={"type": "symbol-result-btn", "index": i},
                              size="sm",
                              color="primary",
                              outline=True,
                              className="mt-2",
                              n_clicks=0)
                ], className="mb-1", action=True, style={"cursor": "pointer"})
            )

        return html.Div([
            html.P([
                html.Strong(f"{len(results)} Result{'s' if len(results) != 1 else ''}"),
                html.Small(" (click Select to choose)", className="text-muted ms-2")
            ], className="mb-2 mt-2"),
            dbc.ListGroup(result_items, flush=True)
        ]), symbols_cache

    except Exception as e:
        return dbc.Alert(
            f"Error searching: {str(e)}",
            color="danger",
            className="mt-2"
        ), []


@app.callback(
    Output("quick-edit-symbol-input", "value", allow_duplicate=True),
    Input({"type": "symbol-result-btn", "index": ALL}, "n_clicks"),
    State("symbol-search-cache", "data"),
    prevent_initial_call=True
)
def select_symbol_from_search(clicks, symbols_cache):
    """Update input when user clicks on a search result"""
    from dash import callback_context

    if not callback_context.triggered or not any(clicks) or not symbols_cache:
        return dash.no_update

    # Find which button was clicked
    for i, click_count in enumerate(clicks):
        if click_count and click_count > 0:
            if i < len(symbols_cache):
                return symbols_cache[i]

    return dash.no_update


@app.callback(
    Output("chart-panels-config", "data", allow_duplicate=True),
    Input("quick-edit-apply-btn", "n_clicks"),
    [State("current-quick-edit-panel", "children"),
     State("quick-edit-symbol-input", "value"),
     State("chart-panels-config", "data")],
    prevent_initial_call=True
)
def apply_quick_symbol_edit(n_clicks, panel_id, new_symbol, current_config):
    """Apply symbol change from quick edit modal"""
    if not panel_id or not new_symbol:
        raise dash.exceptions.PreventUpdate
    
    # Update the symbol for the specified panel
    if panel_id in current_config.get('panels', {}):
        current_config['panels'][panel_id]['symbol'] = new_symbol.upper().strip()
    
    return current_config


@app.callback(
    [Output("favorites-modal", "is_open"),
     Output("favorites-list", "children")],
    [Input("show-favorites-modal", "n_clicks"),
     Input("favorites-close-btn", "n_clicks")],
    [State("chart-panels-config", "data"),
     State("favorites-modal", "is_open")],
    prevent_initial_call=True
)
def toggle_favorites_modal(show_click, close_click, panels_config, is_open):
    """Toggle favorites modal and show favorite symbols"""
    from dash import callback_context
    
    if not callback_context.triggered:
        return False, []
    
    trigger_id = callback_context.triggered[0]['prop_id']
    
    if 'show-favorites' in trigger_id:
        # Collect favorite symbols
        favorites = []
        for panel_id, config in panels_config.get('panels', {}).items():
            if config.get('favorite', False):
                favorites.append(
                    dbc.ListGroupItem([
                        html.Div([
                            html.Strong(f"⭐ {config['symbol']}", className="me-3"),
                            html.Span(f"{config['timeframe']} | {config['chart_type']}", className="text-muted")
                        ])
                    ])
                )
        
        if not favorites:
            favorites = [dbc.Alert("No favorite symbols yet. Mark symbols as favorites using the ⭐ button on chart panels.", color="info")]
        
        return True, favorites
    
    elif 'close-btn' in trigger_id:
        return False, []
    
    return is_open, []


# Dynamic callbacks for individual panel actions
@app.callback(
    Output({"type": "chart-content", "index": dash.dependencies.MATCH}, "children"),
    Input({"type": "refresh-btn", "index": dash.dependencies.MATCH}, "n_clicks"),
    [State({"type": "chart-content", "index": dash.dependencies.MATCH}, "id"),
     State("chart-panels-config", "data")],
    prevent_initial_call=True
)
def refresh_individual_panel(n_clicks, component_id, panels_config):
    """Refresh individual chart panel"""
    panel_id = component_id['index']
    panel_config = panels_config.get('panels', {}).get(panel_id, {})
    
    symbol = panel_config.get('symbol', 'AAPL')
    timeframe = panel_config.get('timeframe', '1mo')
    chart_type = panel_config.get('chart_type', 'candlestick')
    
    return charts.get_stock_chart(symbol, timeframe, chart_type)


# ============================================================================
# CALLBACKS - AGENT CONTROL TAB
# ============================================================================

# Enable/disable single agent button based on selection
@app.callback(
    Output("btn-run-single-agent", "disabled"),
    Input("agent-selector", "value")
)
def toggle_single_agent_button(selected_agent):
    """Enable button when agent is selected"""
    return selected_agent is None


# Update pipeline log periodically
@app.callback(
    [Output("pipeline-log", "value", allow_duplicate=True),
     Output("badge-pipeline-status", "children", allow_duplicate=True),
     Output("badge-pipeline-status", "color", allow_duplicate=True)],
    Input("interval-component", "n_intervals"),
    State("store-pipeline-state", "data"),
    prevent_initial_call=True
)
def update_pipeline_log(n, state):
    """Update pipeline log from activity logger"""
    if not state or not state.get("running"):
        return dash.no_update
    
    try:
        # Read latest pipeline output
        output_file = Path("logs") / "pipeline_output.log"
        if output_file.exists():
            with open(output_file, "r", encoding="utf-8", errors="ignore") as f:
                output_lines = f.readlines()
                # Get last 100 lines to show progress
                recent_output = "".join(output_lines[-100:])
                
                # Check if pipeline completed
                if "PIPELINE COMPLETE" in recent_output or "COMPLETED SUCCESSFULLY" in recent_output:
                    return recent_output, "COMPLETED", "success"
                elif "ERROR" in recent_output and "Traceback" in recent_output:
                    return recent_output, "ERROR", "danger"
                else:
                    return recent_output, "RUNNING", "warning"
        
        # Fallback to activity log
        log_file = Path("logs") / "pipeline_activity.log"
        if log_file.exists():
            with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
                recent_logs = "".join(lines[-50:])
                return recent_logs, "RUNNING", "warning"
        
        return dash.no_update
    except Exception:
        return dash.no_update


# Run full pipeline
@app.callback(
    [Output("store-pipeline-state", "data", allow_duplicate=True),
     Output("pipeline-log", "value", allow_duplicate=True),
     Output("badge-pipeline-status", "children", allow_duplicate=True),
     Output("badge-pipeline-status", "color", allow_duplicate=True)],
    Input("btn-run-full-pipeline", "n_clicks"),
    [State("slider-article-limit", "value"),
     State("check-force-refresh", "value"),
     State("check-verbose", "value")],
    prevent_initial_call=True
)
def run_full_pipeline(n_clicks, limit, force, verbose):
    """Run full MVP pipeline"""
    if not n_clicks:
        return dash.no_update
    
    from pathlib import Path
    import subprocess
    from src.utils.process_utils import get_project_root
    
    # Log pipeline start
    activity_logger.log_activity("User initiated Full MVP Pipeline from GUI", "INFO")
    activity_logger.log_pipeline_start("TradeMeUp MVP Pipeline (GUI)")
    
    # Use wrapper batch script to keep console open
    wrapper_script = Path("scripts/run_mvp_pipeline_wrapper.bat").absolute()
    
    if not wrapper_script.exists():
        error_msg = f"Wrapper script not found: {wrapper_script}"
        activity_logger.log_activity(error_msg, "ERROR")
        return {"running": False}, error_msg, "ERROR", "danger"
    
    # Start in new console window using start command
    try:
        cmd = f'start "TradeMeUp MVP Pipeline" /D "{Path.cwd()}" "{wrapper_script}"'
        process = subprocess.Popen(cmd, shell=True, cwd=str(Path.cwd()))
        success = True
        message = f"Pipeline console opened (PID: {process.pid})"
    except Exception as e:
        success = False
        message = f"Failed to start console: {e}"
        activity_logger.log_agent_error("Full Pipeline (GUI)", message)
        return {"running": False}, message, "ERROR", "danger"
    
    # Successfully started
    state = {
        "running": True,
        "process_id": process.pid,
        "start_time": datetime.now().strftime("%H:%M:%S"),
        "type": "full_pipeline"
    }
    
    log = f"[{datetime.now().strftime('%H:%M:%S')}] Full MVP Pipeline console opened\n"
    log += f"Process ID: {process.pid}\n"
    log += f"Articles to process: {limit}\n"
    log += "-" * 60 + "\n"
    log += "Check the new terminal window for live progress!\n"
    
    activity_logger.log_activity(f"Pipeline process started (PID: {process.pid})", "SUCCESS")
    
    return state, log, "RUNNING", "warning"


# Run quick test
@app.callback(
    [Output("store-pipeline-state", "data", allow_duplicate=True),
     Output("pipeline-log", "value", allow_duplicate=True),
     Output("badge-pipeline-status", "children", allow_duplicate=True),
     Output("badge-pipeline-status", "color", allow_duplicate=True)],
    Input("btn-run-quick-test", "n_clicks"),
    prevent_initial_call=True
)
def run_quick_test(n_clicks):
    """Run quick pipeline test"""
    if not n_clicks:
        return dash.no_update
    
    import subprocess
    from pathlib import Path
    
    # Log test start
    activity_logger.log_activity("User initiated Quick Test from GUI", "INFO")
    activity_logger.log_activity("Running quick test with 3 articles...", "INFO")
    
    # Use wrapper batch script to keep console open
    wrapper_script = Path("scripts/run_mvp_pipeline_wrapper.bat").absolute()
    
    if not wrapper_script.exists():
        error_msg = f"Wrapper script not found: {wrapper_script}"
        activity_logger.log_activity(error_msg, "ERROR")
        return {"running": False}, error_msg, "ERROR", "danger"
    
    # Start in new console window using start command with --quick flag
    try:
        cmd = f'start "TradeMeUp Quick Test" /D "{Path.cwd()}" "{wrapper_script}" --quick'
        process = subprocess.Popen(cmd, shell=True, cwd=str(Path.cwd()))
        success = True
        message = f"Quick test console opened (PID: {process.pid})"
    except Exception as e:
        success = False
        message = f"Failed to start console: {e}"
        activity_logger.log_agent_error("Quick Test (GUI)", message)
        return {"running": False}, message, "ERROR", "danger"
    
    # Successfully started
    state = {
        "running": True,
        "process_id": process.pid,
        "start_time": datetime.now().strftime("%H:%M:%S"),
        "type": "quick_test"
    }
    
    log = f"[{datetime.now().strftime('%H:%M:%S')}] Quick Test console opened\n"
    log += f"Process ID: {process.pid}\n"
    log += "Processing 3 articles with all agents...\n"
    log += "-" * 60 + "\n"
    log += "Check the new terminal window for live progress!\n"
    
    activity_logger.log_activity(f"Quick test started (PID: {process.pid})", "SUCCESS")
    
    return state, log, "RUNNING", "warning"


# Run full backfill
@app.callback(
    [Output("store-pipeline-state", "data", allow_duplicate=True),
     Output("pipeline-log", "value", allow_duplicate=True),
     Output("badge-pipeline-status", "children", allow_duplicate=True),
     Output("badge-pipeline-status", "color", allow_duplicate=True)],
    Input("btn-run-full-backfill", "n_clicks"),
    State("slider-backfill-batch", "value"),
    prevent_initial_call=True
)
def run_full_backfill(n_clicks, batch_size):
    """Run full backfill for all missing analyses"""
    if not n_clicks:
        return dash.no_update
    
    import subprocess
    from src.utils.process_utils import get_project_root
    from pathlib import Path
    
    # Log backfill start
    activity_logger.log_activity("User initiated Full Backfill from GUI", "INFO")
    activity_logger.log_activity(f"Backfill batch size: {batch_size}", "INFO")
    
    # Use wrapper batch script to keep console open
    wrapper_script = Path("scripts/run_backfill_wrapper.bat").absolute()
    
    if not wrapper_script.exists():
        error_msg = f"Wrapper script not found: {wrapper_script}"
        activity_logger.log_activity(error_msg, "ERROR")
        return {"running": False}, error_msg, "ERROR", "danger"
    
    # Start in new console window using start command
    try:
        cmd = f'start "TradeMeUp Backfill" /D "{Path.cwd()}" "{wrapper_script}" --batch-size {batch_size}'
        process = subprocess.Popen(cmd, shell=True, cwd=str(Path.cwd()))
        success = True
        message = f"Backfill console opened (PID: {process.pid})"
    except Exception as e:
        success = False
        message = f"Failed to start console: {e}"
        activity_logger.log_agent_error("Backfill (GUI)", message)
        return {"running": False}, message, "ERROR", "danger"
    
    # Successfully started
    state = {
        "running": True,
        "process_id": process.pid,
        "start_time": datetime.now().strftime("%H:%M:%S"),
        "type": "full_backfill"
    }
    
    log = f"[{datetime.now().strftime('%H:%M:%S')}] Full Backfill console opened\n"
    log += f"Process ID: {process.pid}\n"
    log += f"Batch Size: {batch_size} articles\n"
    log += "Processing all missing analyses:\n"
    log += "  - Quality Assessment\n"
    log += "  - Content Understanding\n"
    log += "  - Entity Mapping\n"
    log += "  - Fact Verification\n"
    log += "  - Surprise Scoring\n"
    log += "  - Impact Scoring\n"
    log += "  - Predictions\n"
    log += "-" * 60 + "\n"
    log += "Check the new terminal window for live progress!\n"
    
    activity_logger.log_activity(f"Full backfill started (PID: {process.pid})", "SUCCESS")
    
    return state, log, "RUNNING", "warning"


# Run selective backfill
@app.callback(
    [Output("store-pipeline-state", "data", allow_duplicate=True),
     Output("pipeline-log", "value", allow_duplicate=True),
     Output("badge-pipeline-status", "children", allow_duplicate=True),
     Output("badge-pipeline-status", "color", allow_duplicate=True)],
    Input("btn-run-selective-backfill", "n_clicks"),
    [State("check-backfill-phases", "value"),
     State("slider-backfill-batch", "value")],
    prevent_initial_call=True
)
def run_selective_backfill(n_clicks, selected_phases, batch_size):
    """Run backfill for selected phases only"""
    if not n_clicks or not selected_phases:
        return dash.no_update
    
    import subprocess
    from src.utils.process_utils import get_project_root
    from pathlib import Path
    
    # Log backfill start
    activity_logger.log_activity("User initiated Selective Backfill from GUI", "INFO")
    activity_logger.log_activity(f"Selected phases: {', '.join(selected_phases)}", "INFO")
    activity_logger.log_activity(f"Batch size: {batch_size}", "INFO")
    
    # Use wrapper batch script to keep console open
    wrapper_script = Path("scripts/run_backfill_wrapper.bat").absolute()
    
    if not wrapper_script.exists():
        error_msg = f"Wrapper script not found: {wrapper_script}"
        activity_logger.log_activity(error_msg, "ERROR")
        return {"running": False}, error_msg, "ERROR", "danger"
    
    # Build args with skip flags for unselected phases
    all_phases = ["quality", "content", "entities", "facts", "surprises", "impact", "predictions"]
    args = ["--batch-size", str(batch_size)]
    for phase in all_phases:
        if phase not in selected_phases:
            args.append(f"--skip-{phase}")
    
    # Start in new console window using start command
    try:
        cmd = f'start "TradeMeUp Backfill" /D "{Path.cwd()}" "{wrapper_script}" {" ".join(args)}'
        process = subprocess.Popen(cmd, shell=True, cwd=str(Path.cwd()))
        success = True
        message = f"Backfill console opened (PID: {process.pid})"
    except Exception as e:
        success = False
        message = f"Failed to start console: {e}"
        activity_logger.log_agent_error("Backfill (GUI)", message)
        return {"running": False}, message, "ERROR", "danger"
    
    if not success or not process:
        error_log = f"[{datetime.now().strftime('%H:%M:%S')}] BACKFILL STARTUP ERROR\n"
        error_log += f"Failed to start backfill: {message}\n"
        activity_logger.log_agent_error("Backfill (GUI)", message)
        return {"running": False}, error_log, "ERROR", "danger"
    
    # Successfully started
    state = {
        "running": True,
        "process_id": process.pid,
        "start_time": datetime.now().strftime("%H:%M:%S"),
        "type": "selective_backfill"
    }
    
    # Map phase codes to readable names
    phase_names = {
        "quality": "Quality Assessment",
        "content": "Content Understanding",
        "entities": "Entity Mapping",
        "facts": "Fact Verification",
        "surprises": "Surprise Scoring",
        "impact": "Impact Scoring",
        "predictions": "Predictions"
    }
    
    log = f"[{datetime.now().strftime('%H:%M:%S')}] Starting Selective Backfill...\n"
    log += f"Process ID: {process.pid}\n"
    log += f"Batch Size: {batch_size} articles\n"
    log += "Processing selected phases:\n"
    for phase in selected_phases:
        log += f"  ✓ {phase_names.get(phase, phase)}\n"
    log += "-" * 60 + "\n"
    
    activity_logger.log_activity(f"Selective backfill started (PID: {process.pid})", "SUCCESS")
    
    return state, log, "RUNNING", "warning"


# Update recent executions
@app.callback(
    Output("recent-executions", "children"),
    Input("interval-component", "n_intervals")
)
def update_recent_executions(n):
    """Update recent executions list"""
    return control.get_recent_executions()


# ============================================================================
# CALLBACKS - TESTING TAB
# ============================================================================

# Generate callbacks for each agent test button dynamically
for agent_key in testing.AGENT_TESTS.keys():
    # Individual agent test
    @app.callback(
        [Output(f"result-{agent_key}", "children"),
         Output(f"badge-{agent_key}", "children"),
         Output(f"badge-{agent_key}", "color"),
         Output(f"btn-details-{agent_key}", "disabled"),
         Output("store-test-results", "data", allow_duplicate=True)],
        Input(f"btn-test-{agent_key}", "n_clicks"),
        State("store-test-results", "data"),
        prevent_initial_call=True
    )
    def test_single_agent(n_clicks, test_results, agent_key=agent_key):
        """Test single agent"""
        if not n_clicks:
            return dash.no_update
        
        success, message, details = testing.test_agent(agent_key)
        
        # Update test results
        test_results = test_results or {}
        test_results[agent_key] = {
            "success": success,
            "message": message,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        
        # Format result display
        result_display = testing.format_test_result(success, message, details)
        
        # Update badge
        badge_text = "✅ Pass" if success else "❌ Fail"
        badge_color = "success" if success else "danger"
        
        # Enable details button if there are details
        details_disabled = not bool(details.get("traceback"))
        
        return result_display, badge_text, badge_color, details_disabled, test_results


# Test all agents
@app.callback(
    [Output("store-test-results", "data", allow_duplicate=True),
     Output("test-summary", "children")],
    Input("btn-test-all", "n_clicks"),
    prevent_initial_call=True
)
def test_all_agents(n_clicks):
    """Test all agents sequentially"""
    if not n_clicks:
        return dash.no_update
    
    test_results = {}
    
    for agent_key in testing.AGENT_TESTS.keys():
        success, message, details = testing.test_agent(agent_key)
        test_results[agent_key] = {
            "success": success,
            "message": message,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
    
    summary = testing.get_test_summary(test_results)
    
    return test_results, summary


# Update summary when tests change
@app.callback(
    Output("test-summary", "children", allow_duplicate=True),
    Input("store-test-results", "data"),
    prevent_initial_call=True
)
def update_test_summary(test_results):
    """Update test summary display"""
    return testing.get_test_summary(test_results)


# Reset all tests
@app.callback(
    Output("store-test-results", "data", allow_duplicate=True),
    Input("btn-reset-tests", "n_clicks"),
    prevent_initial_call=True
)
def reset_tests(n_clicks):
    """Reset all test results"""
    if not n_clicks:
        return dash.no_update
    return {}


# Update all agent badges when store changes
for agent_key in testing.AGENT_TESTS.keys():
    @app.callback(
        [Output(f"badge-{agent_key}", "children", allow_duplicate=True),
         Output(f"badge-{agent_key}", "color", allow_duplicate=True),
         Output(f"result-{agent_key}", "children", allow_duplicate=True),
         Output(f"btn-details-{agent_key}", "disabled", allow_duplicate=True)],
        Input("store-test-results", "data"),
        prevent_initial_call=True
    )
    def update_agent_status(test_results, agent_key=agent_key):
        """Update agent status from store"""
        if not test_results or agent_key not in test_results:
            return "", "secondary", "", True
        
        result = test_results[agent_key]
        success = result.get("success", False)
        message = result.get("message", "")
        details = result.get("details", {})
        
        badge_text = "✅ Pass" if success else "❌ Fail"
        badge_color = "success" if success else "danger"
        result_display = testing.format_test_result(success, message, details)
        details_disabled = not bool(details.get("traceback"))
        
        return badge_text, badge_color, result_display, details_disabled


# Show error details modal
for agent_key in testing.AGENT_TESTS.keys():
    @app.callback(
        [Output("error-modal", "is_open", allow_duplicate=True),
         Output("error-detail-content", "children", allow_duplicate=True)],
        Input(f"btn-details-{agent_key}", "n_clicks"),
        State("store-test-results", "data"),
        prevent_initial_call=True
    )
    def show_error_details(n_clicks, test_results, agent_key=agent_key):
        """Show detailed error information"""
        if not n_clicks or not test_results or agent_key not in test_results:
            return False, ""
        
        result = test_results[agent_key]
        details = result.get("details", {})
        
        content = html.Div([
            html.H5(f"Agent {testing.AGENT_TESTS[agent_key]['id']}: {testing.AGENT_TESTS[agent_key]['name']}"),
            html.Hr(),
            html.H6("Error Message:"),
            html.Pre(result.get("message", "No message"), className="bg-dark p-3 text-light"),
            html.H6("Details:", className="mt-3"),
            html.Pre(details.get("error", "No details"), className="bg-dark p-3 text-light"),
            html.H6("Traceback:", className="mt-3") if details.get("traceback") else None,
            html.Pre(details.get("traceback", ""), className="bg-dark p-3 text-light", style={"fontSize": "11px"}) if details.get("traceback") else None
        ])
        
        return True, content


# Close error modal
@app.callback(
    Output("error-modal", "is_open", allow_duplicate=True),
    Input("close-error-modal", "n_clicks"),
    prevent_initial_call=True
)
def close_error_modal(n_clicks):
    """Close error modal"""
    return False


# ============================================================================
# CALLBACKS - SYSTEM TAB
# ============================================================================

@app.callback(
    Output("agent-status", "children"),
    Input("interval-component", "n_intervals")
)
def update_agent_status(n):
    """Update agent status display"""
    return system.get_agent_status()


@app.callback(
    Output("db-statistics", "children"),
    Input("interval-component", "n_intervals")
)
def update_db_statistics(n):
    """Update database statistics"""
    return system.get_db_statistics(engine)


@app.callback(
    Output("pipeline-stats", "children"),
    Input("interval-component", "n_intervals")
)
def update_pipeline_stats(n):
    """Update pipeline statistics"""
    return system.get_pipeline_stats(engine)


# ============================================================================
# CALLBACKS - SETTINGS TAB
# ============================================================================

# LLM Models by Provider
LLM_MODELS = {
    'ollama': [
        {'label': 'Qwen 3 (8B) - Fast', 'value': 'qwen3:8b'},
        {'label': 'Llama 3.1 (8B)', 'value': 'llama3.1:8b'},
        {'label': 'Mistral (7B)', 'value': 'mistral:7b'},
        {'label': 'Gemma 2 (9B)', 'value': 'gemma2:9b'},
        {'label': 'Phi-3 (3.8B) - Lightweight', 'value': 'phi3'},
    ],
    'openai': [
        {'label': 'GPT-4o-mini (Recommended)', 'value': 'gpt-4o-mini'},
        {'label': 'GPT-3.5-turbo', 'value': 'gpt-3.5-turbo'},
        {'label': 'GPT-4o', 'value': 'gpt-4o'},
        {'label': 'GPT-4-turbo', 'value': 'gpt-4-turbo'},
    ],
    'anthropic': [
        {'label': 'Claude 3.5 Sonnet (Best)', 'value': 'claude-3-5-sonnet-20241022'},
        {'label': 'Claude 3 Haiku (Fast)', 'value': 'claude-3-haiku-20240307'},
        {'label': 'Claude 3 Opus (Powerful)', 'value': 'claude-3-opus-20240229'},
    ]
}


@app.callback(
    Output("settings-llm-provider", "value"),
    Input("tabs", "active_tab"),
    prevent_initial_call=False
)
def load_current_llm_provider(active_tab):
    """Load current LLM provider from settings"""
    try:
        from src.config.settings import settings
        return settings.llm_provider
    except:
        return 'ollama'


@app.callback(
    [Output("settings-llm-model", "options"),
     Output("settings-llm-model", "value"),
     Output("llm-provider-settings", "children"),
     Output("llm-cost-info", "children")],
    Input("settings-llm-provider", "value"),
    prevent_initial_call=False
)
def update_llm_model_options(provider):
    """Update available models based on selected provider"""
    if not provider:
        return [], None, html.Div(), ""

    # Try to load current model from settings
    try:
        from src.config.settings import settings
        if provider == 'ollama' and hasattr(settings, 'ollama_model'):
            current_model = settings.ollama_model
        elif provider == 'openai' and hasattr(settings, 'openai_model'):
            current_model = settings.openai_model
        elif provider == 'anthropic' and hasattr(settings, 'anthropic_model'):
            current_model = settings.anthropic_model
        else:
            current_model = None
    except:
        current_model = None

    # Get models for provider
    models = LLM_MODELS.get(provider, [])

    # Use current model if available, otherwise use first model
    if current_model:
        default_model = current_model
    else:
        default_model = models[0]['value'] if models else None

    # Provider-specific settings (no API keys - those are in environment)
    if provider == 'ollama':
        provider_settings = html.Div([
            html.Small("API URL is configured in .env file", className="text-muted")
        ])
        cost_info = html.Div([
            html.Strong("💡 Local Ollama:"),
            html.Ul([
                html.Li("✅ Free (no API costs)"),
                html.Li("⚡ ~30-60s per article"),
                html.Li("💡 ~€4-5 electricity per 700 articles (35h)"),
                html.Li("🖥️ Requires local GPU (8GB+ VRAM recommended)")
            ])
        ])

    elif provider == 'openai':
        provider_settings = html.Div([
            html.Small("API key is configured in .env file (OPENAI_API_KEY)", className="text-muted")
        ])
        cost_info = html.Div([
            html.Strong("💰 OpenAI Costs (GPT-4o-mini):"),
            html.Ul([
                html.Li("📊 ~$0.0005 per article (~€0.0005)"),
                html.Li("💸 700 articles = ~$0.33 (€0.30)"),
                html.Li("⚡ ~5-10s per article"),
                html.Li("🚀 18x faster than local Ollama"),
                html.Li("✅ No hardware required")
            ])
        ])

    elif provider == 'anthropic':
        provider_settings = html.Div([
            html.Small("API key is configured in .env file (ANTHROPIC_API_KEY)", className="text-muted")
        ])
        cost_info = html.Div([
            html.Strong("💰 Anthropic Costs (Claude 3.5 Sonnet):"),
            html.Ul([
                html.Li("📊 ~$0.003 per article"),
                html.Li("💸 700 articles = ~$2.10"),
                html.Li("⚡ ~5-10s per article"),
                html.Li("🧠 Highest quality analysis"),
                html.Li("✅ Best at complex reasoning")
            ])
        ])

    else:
        provider_settings = html.Div()
        cost_info = ""

    return models, default_model, provider_settings, cost_info


@app.callback(
    Output("llm-settings-save-status", "children"),
    Input("btn-save-llm-settings", "n_clicks"),
    [State("settings-llm-provider", "value"),
     State("settings-llm-model", "value")],
    prevent_initial_call=True
)
def save_llm_settings(n_clicks, provider, model):
    """Save LLM settings to .env.local"""
    if not n_clicks:
        return ""

    try:
        import os
        from pathlib import Path

        # Path to .env.local
        env_path = Path(__file__).parent.parent.parent / ".env.local"

        # Read existing .env.local
        if env_path.exists():
            with open(env_path, 'r') as f:
                lines = f.readlines()
        else:
            lines = []

        # Update LLM settings
        new_lines = []
        updated_provider = False
        updated_model = False

        for line in lines:
            if line.startswith('LLM_PROVIDER='):
                new_lines.append(f'LLM_PROVIDER={provider}\n')
                updated_provider = True
            elif provider == 'ollama' and line.startswith('OLLAMA_MODEL='):
                new_lines.append(f'OLLAMA_MODEL={model}\n')
                updated_model = True
            elif provider == 'openai' and line.startswith('OPENAI_MODEL='):
                new_lines.append(f'OPENAI_MODEL={model}\n')
                updated_model = True
            elif provider == 'anthropic' and line.startswith('ANTHROPIC_MODEL='):
                new_lines.append(f'ANTHROPIC_MODEL={model}\n')
                updated_model = True
            else:
                new_lines.append(line)

        # Add if not found
        if not updated_provider:
            new_lines.append(f'LLM_PROVIDER={provider}\n')
        if not updated_model:
            if provider == 'ollama':
                new_lines.append(f'OLLAMA_MODEL={model}\n')
            elif provider == 'openai':
                new_lines.append(f'OPENAI_MODEL={model}\n')
            elif provider == 'anthropic':
                new_lines.append(f'ANTHROPIC_MODEL={model}\n')

        # Write back
        with open(env_path, 'w') as f:
            f.writelines(new_lines)

        return dbc.Alert(
            [
                html.Strong("✅ Settings saved!"),
                html.Br(),
                html.Small(f"Provider: {provider} | Model: {model}"),
                html.Br(),
                html.Small("⚠️ Restart the pipeline for changes to take effect")
            ],
            color="success",
            dismissable=True
        )

    except Exception as e:
        return dbc.Alert(
            f"❌ Error saving settings: {str(e)}",
            color="danger",
            dismissable=True
        )


# Open settings tab
@app.callback(
    Output("tabs", "active_tab"),
    Input("btn-open-settings", "n_clicks"),
    prevent_initial_call=True
)
def open_settings(n_clicks):
    """Open settings tab"""
    if n_clicks:
        return "settings"
    return dash.no_update


# Enable/disable custom date picker
@app.callback(
    Output("settings-news-custom-dates", "disabled"),
    Input("settings-news-timerange", "value")
)
def toggle_custom_dates(timerange):
    """Enable custom dates when 'custom' is selected"""
    return timerange != 'custom'


# Confirmation modal for clear actions
@app.callback(
    [Output("confirm-modal", "is_open"),
     Output("confirm-modal-body", "children"),
     Output("delete-action-store", "data")],
    [Input("btn-clear-news", "n_clicks"),
     Input("btn-clear-predictions", "n_clicks"),
     Input("btn-clear-all", "n_clicks"),
     Input("btn-confirm-cancel", "n_clicks"),
     Input("btn-confirm-delete", "n_clicks")],
    [State("settings-news-timerange", "value"),
     State("settings-news-custom-dates", "start_date"),
     State("settings-news-custom-dates", "end_date"),
     State("settings-pred-timerange", "value"),
     State("delete-action-store", "data"),
     State("confirm-modal", "is_open")],
    prevent_initial_call=True
)
def handle_delete_confirmation(clear_news, clear_pred, clear_all, cancel, confirm,
                               news_range, custom_start, custom_end, pred_range, 
                               action_store, modal_open):
    """Handle delete confirmation dialog"""
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update
    
    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    
    # Open confirmation modal
    if button_id == "btn-clear-news":
        timerange_text = {
            'all': 'ALL NEWS ARTICLES',
            '1d': 'news from last 24 hours',
            '7d': 'news from last 7 days',
            '30d': 'news from last 30 days',
            '90d': 'news from last 90 days',
            'custom': f'news from {custom_start} to {custom_end}'
        }.get(news_range, 'selected news')
        
        return (
            True,
            html.Div([
                html.H5("⚠️ Delete News Articles", className="text-danger mb-3"),
                html.P(f"You are about to delete: {timerange_text}"),
                html.P("This action cannot be undone!", className="fw-bold text-warning")
            ]),
            {"action": "clear_news", "params": {"range": news_range, "start": custom_start, "end": custom_end}}
        )
    
    elif button_id == "btn-clear-predictions":
        timerange_text = {
            'all': 'ALL PREDICTIONS',
            '1d': 'predictions from last 24 hours',
            '7d': 'predictions from last 7 days',
            '30d': 'predictions from last 30 days'
        }.get(pred_range, 'selected predictions')
        
        return (
            True,
            html.Div([
                html.H5("⚠️ Delete Predictions", className="text-danger mb-3"),
                html.P(f"You are about to delete: {timerange_text}"),
                html.P("This action cannot be undone!", className="fw-bold text-warning")
            ]),
            {"action": "clear_predictions", "params": {"range": pred_range}}
        )
    
    elif button_id == "btn-clear-all":
        return (
            True,
            html.Div([
                html.H5("💣 NUCLEAR OPTION", className="text-danger mb-3"),
                html.P("You are about to delete EVERYTHING from the database:", className="fw-bold"),
                html.Ul([
                    html.Li("All news articles (raw and processed)"),
                    html.Li("All predictions"),
                    html.Li("All entities and mappings"),
                    html.Li("All impact scores"),
                    html.Li("All quality assessments")
                ]),
                html.P("THIS ACTION CANNOT BE UNDONE!", className="fw-bold text-danger fs-5")
            ]),
            {"action": "clear_all", "params": {}}
        )
    
    # Cancel - close modal
    elif button_id == "btn-confirm-cancel":
        return False, "", {"action": None, "params": None}
    
    # Confirm - execute delete and close modal
    elif button_id == "btn-confirm-delete":
        return False, "", action_store
    
    return dash.no_update


# Execute delete actions
@app.callback(
    [Output("news-clear-status", "children"),
     Output("pred-clear-status", "children"),
     Output("all-clear-status", "children")],
    Input("btn-confirm-delete", "n_clicks"),
    State("delete-action-store", "data"),
    prevent_initial_call=True
)
def execute_delete_action(n_clicks, action_data):
    """Execute the confirmed delete action"""
    if not n_clicks or not action_data or not action_data.get("action"):
        return dash.no_update
    
    from sqlalchemy.orm import Session
    from datetime import datetime, timedelta
    from src.models.raw_news import RawNews
    from src.models.processed_news import ProcessedNews
    from src.models.predictions import Prediction
    from src.models.entities import Entity, NewsEntityMapping
    from src.models.analysis import ImpactScore
    from src.models.data_quality import DataQualityScore
    
    action = action_data["action"]
    params = action_data.get("params", {})
    
    news_msg = dash.no_update
    pred_msg = dash.no_update
    all_msg = dash.no_update
    
    try:
        with Session(engine) as db:
            if action == "clear_news":
                time_range = params.get("range")
                cutoff_date = None
                
                if time_range == "1d":
                    cutoff_date = datetime.now() - timedelta(days=1)
                elif time_range == "7d":
                    cutoff_date = datetime.now() - timedelta(days=7)
                elif time_range == "30d":
                    cutoff_date = datetime.now() - timedelta(days=30)
                elif time_range == "90d":
                    cutoff_date = datetime.now() - timedelta(days=90)
                elif time_range == "custom":
                    cutoff_date = datetime.fromisoformat(params["start"])
                    end_date = datetime.fromisoformat(params["end"])
                
                if time_range == "all":
                    count_raw = db.query(RawNews).delete()
                    count_processed = db.query(ProcessedNews).delete()
                else:
                    count_raw = db.query(RawNews).filter(RawNews.created_at >= cutoff_date).delete()
                    count_processed = db.query(ProcessedNews).filter(ProcessedNews.created_at >= cutoff_date).delete()
                
                db.commit()
                activity_logger.log_activity(f"Deleted {count_raw + count_processed} news articles", "INFO")
                news_msg = dbc.Alert(
                    f"✅ Successfully deleted {count_raw + count_processed} news articles",
                    color="success",
                    dismissable=True
                )
            
            elif action == "clear_predictions":
                time_range = params.get("range")
                cutoff_date = None
                
                if time_range == "1d":
                    cutoff_date = datetime.now() - timedelta(days=1)
                elif time_range == "7d":
                    cutoff_date = datetime.now() - timedelta(days=7)
                elif time_range == "30d":
                    cutoff_date = datetime.now() - timedelta(days=30)
                
                if time_range == "all":
                    count = db.query(Prediction).delete()
                else:
                    count = db.query(Prediction).filter(Prediction.created_at >= cutoff_date).delete()
                
                db.commit()
                activity_logger.log_activity(f"Deleted {count} predictions", "INFO")
                pred_msg = dbc.Alert(
                    f"✅ Successfully deleted {count} predictions",
                    color="success",
                    dismissable=True
                )
            
            elif action == "clear_all":
                # Delete everything in order
                db.query(Prediction).delete()
                db.query(ImpactScore).delete()
                db.query(NewsEntityMapping).delete()
                db.query(Entity).delete()
                db.query(DataQualityScore).delete()
                db.query(ProcessedNews).delete()
                db.query(RawNews).delete()
                
                db.commit()
                activity_logger.log_activity("DATABASE CLEARED - All data deleted", "WARNING")
                all_msg = dbc.Alert(
                    "💣 Database cleared! All data has been deleted.",
                    color="danger",
                    dismissable=True
                )
        
        return news_msg, pred_msg, all_msg
        
    except Exception as e:
        # Log detailed error
        import traceback
        error_detail = traceback.format_exc()
        activity_logger.log_activity(
            f"Error deleting data ({action}): {str(e)}",
            "ERROR"
        )
        activity_logger.log_activity(f"Traceback: {error_detail}", "ERROR")
        
        # User-friendly error message
        error_msg = dbc.Alert([
            html.H5("❌ Delete Operation Failed", className="alert-heading"),
            html.P(f"Error: {str(e)}"),
            html.Hr(),
            html.P([
                "This may be caused by:",
                html.Ul([
                    html.Li("Database connection issues"),
                    html.Li("Foreign key constraints"),
                    html.Li("Insufficient permissions"),
                    html.Li("Active transactions blocking deletion")
                ]),
                html.Small("Check logs/pipeline_activity.log for details.", className="text-muted")
            ], className="mb-0")
        ], color="danger", dismissable=True)
        
        # Return error in appropriate slot
        if action == "clear_news":
            return error_msg, dash.no_update, dash.no_update
        elif action == "clear_predictions":
            return dash.no_update, error_msg, dash.no_update
        else:
            return dash.no_update, dash.no_update, error_msg


if __name__ == "__main__":
    print("🚀 Starting TradeMeUp Dashboard...")
    print("📊 Dashboard will be available at: http://127.0.0.1:8050")
    app.run(debug=True, host="0.0.0.0", port=8050)
