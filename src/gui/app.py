"""
TradeMeUp Dashboard - Main Application
Multi-tab dashboard for monitoring news, predictions, and system health
"""

# Suppress pandas deprecation warnings from yfinance library
import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning, module='yfinance')
warnings.filterwarnings('ignore', message='.*Timestamp.utcnow.*')

import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
from datetime import datetime
from pathlib import Path
import plotly.graph_objects as go
import pandas as pd
from sqlalchemy import create_engine

from src.config.settings import settings
from src.gui.components import create_navbar
from src.utils.activity_logger import activity_logger

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
    import subprocess
    import os
    from pathlib import Path
    
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update
    
    button_id = ctx.triggered[0]["prop_id"].split(".")[0]
    
    if button_id == "btn-start-continuous":
        # Start continuous pipeline
        try:
            PROJECT_ROOT = Path(__file__).parent.parent.parent
            python_exe = os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")
            script = os.path.join(PROJECT_ROOT, "scripts", "run_continuous_pipeline.py")
            
            # Start process in background
            process = subprocess.Popen(
                [python_exe, "-u", script, "--interval", "300"],  # Check every 5 minutes
                cwd=PROJECT_ROOT,
                creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0
            )
            
            activity_logger.log_activity(f"Continuous Pipeline STARTED (PID: {process.pid})", "SUCCESS")
            
            return (
                {"running": True, "pid": process.pid},
                True,  # Disable start button
                False  # Enable stop button
            )
        except Exception as e:
            activity_logger.log_activity(f"Failed to start continuous pipeline: {str(e)}", "ERROR")
            return dash.no_update
    
    elif button_id == "btn-stop-continuous":
        # Stop continuous pipeline
        try:
            if current_state.get("pid"):
                import psutil
                try:
                    process = psutil.Process(current_state["pid"])
                    process.terminate()
                    activity_logger.log_activity(f"Continuous Pipeline STOPPED (PID: {current_state['pid']})", "INFO")
                except psutil.NoSuchProcess:
                    activity_logger.log_activity("Continuous Pipeline process not found", "WARNING")
            
            return (
                {"running": False, "pid": None},
                False,  # Enable start button
                True    # Disable stop button
            )
        except Exception as e:
            activity_logger.log_activity(f"Failed to stop continuous pipeline: {str(e)}", "ERROR")
            return dash.no_update
    
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
    return dashboard.get_recent_news(engine)


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
    Output("predictions-table", "children"),
    Input("interval-component", "n_intervals")
)
def update_predictions_table(n):
    """Update predictions table"""
    return predictions.get_predictions_table(engine)


# ============================================================================
# CALLBACKS - NEWS TAB
# ============================================================================

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
    Output("price-indicator-card", "children"),
    [Input("update-chart-btn", "n_clicks"),
     Input("chart-update-interval", "n_intervals")],
    State("chart-symbol-input", "value"),
    prevent_initial_call='initial_duplicate'
)
def update_price_indicator(n_clicks, n_intervals, symbol):
    """Update price indicator card"""
    if not symbol:
        symbol = "AAPL"
    return charts.get_price_indicator(symbol.upper().strip())


@app.callback(
    Output("main-price-chart", "children"),
    [Input("update-chart-btn", "n_clicks"),
     Input("chart-update-interval", "n_intervals")],
    [State("chart-symbol-input", "value"),
     State("chart-timeframe-selector", "value"),
     State("chart-type-selector", "value")],
    prevent_initial_call='initial_duplicate'
)
def update_main_chart(n_clicks, n_intervals, symbol, timeframe, chart_type):
    """Update main price chart"""
    if not symbol:
        symbol = "AAPL"
    if not timeframe:
        timeframe = "1mo"
    if not chart_type:
        chart_type = "candlestick"
    
    return charts.get_stock_chart(symbol.upper().strip(), timeframe, chart_type)


@app.callback(
    Output("comparison-chart", "children"),
    Input("compare-btn", "n_clicks"),
    [State("compare-symbols-input", "value"),
     State("chart-timeframe-selector", "value")],
    prevent_initial_call=True
)
def update_comparison_chart(n_clicks, symbols_input, timeframe):
    """Update comparison chart"""
    if not symbols_input:
        from src.gui.charts import create_empty_chart
        from dash import dcc
        return dcc.Graph(figure=create_empty_chart("Enter symbols to compare"))
    
    symbols = [s.strip() for s in symbols_input.split(',') if s.strip()]
    if not timeframe:
        timeframe = "3mo"
    
    return charts.get_comparison_chart(symbols, timeframe)


@app.callback(
    Output("news-volume-chart", "figure"),
    Input("interval-component", "n_intervals")
)
def update_news_volume_chart(n):
    """Update news volume chart (placeholder)"""
    fig = go.Figure()
    fig.add_annotation(
        text="News volume chart - coming soon",
        xref="paper", yref="paper",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=16, color="#666")
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(10,10,10,1)',
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=400
    )
    return fig


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
    
    import subprocess
    from pathlib import Path
    import os
    
    try:
        # Log pipeline start
        activity_logger.log_activity("User initiated Full MVP Pipeline from GUI", "INFO")
        activity_logger.log_pipeline_start("TradeMeUp MVP Pipeline (GUI)")
        
        PROJECT_ROOT = Path(__file__).parent.parent.parent
        python_exe = os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")
        script = os.path.join(PROJECT_ROOT, "scripts", "run_mvp_pipeline.py")
        
        # Create log file for pipeline output
        log_file = PROJECT_ROOT / "logs" / "pipeline_output.log"
        
        # Start process in background with output redirected to file
        with open(log_file, "w") as f:
            process = subprocess.Popen(
                [python_exe, "-u", script],  # -u for unbuffered output
                stdout=f,
                stderr=subprocess.STDOUT,
                cwd=PROJECT_ROOT
            )
        
        state = {
            "running": True,
            "process_id": process.pid,
            "start_time": datetime.now().strftime("%H:%M:%S"),
            "type": "full_pipeline"
        }
        
        log = f"[{datetime.now().strftime('%H:%M:%S')}] Starting Full MVP Pipeline...\n"
        log += f"Process ID: {process.pid}\n"
        log += f"Articles to process: {limit}\n"
        log += "-" * 60 + "\n"
        log += "Pipeline is running... Logs will update every 5 seconds\n"
        
        activity_logger.log_activity(f"Pipeline process started (PID: {process.pid})", "SUCCESS")
        
        return state, log, "RUNNING", "warning"
        
    except Exception as e:
        error_log = f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: {str(e)}\n"
        activity_logger.log_agent_error("Pipeline (GUI)", str(e))
        return {"running": False}, error_log, "ERROR", "danger"


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
    import os
    
    try:
        # Log test start
        activity_logger.log_activity("User initiated Quick Test from GUI", "INFO")
        activity_logger.log_activity("Running quick test with 3 articles...", "INFO")
        
        PROJECT_ROOT = Path(__file__).parent.parent.parent
        python_exe = os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")
        script = os.path.join(PROJECT_ROOT, "test_quick.py")
        
        # Check if script exists
        if not os.path.exists(script):
            script = os.path.join(PROJECT_ROOT, "scripts", "run_mvp_pipeline.py")
        
        process = subprocess.Popen(
            [python_exe, script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=PROJECT_ROOT
        )
        
        state = {
            "running": True,
            "process_id": process.pid,
            "start_time": datetime.now().strftime("%H:%M:%S"),
            "type": "quick_test"
        }
        
        log = f"[{datetime.now().strftime('%H:%M:%S')}] Starting Quick Test Pipeline...\n"
        log += f"Process ID: {process.pid}\n"
        log += "Processing 3 articles with all agents...\n"
        log += "-" * 60 + "\n"
        
        activity_logger.log_activity(f"Quick test started (PID: {process.pid})", "SUCCESS")
        
        return state, log, "RUNNING", "warning"
        
    except Exception as e:
        error_log = f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: {str(e)}\n"
        activity_logger.log_agent_error("Quick Test (GUI)", str(e))
        return {"running": False}, error_log, "ERROR", "danger"


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
        activity_logger.log_activity(f"Error deleting data: {str(e)}", "ERROR")
        error_msg = dbc.Alert(
            f"❌ Error: {str(e)}",
            color="danger",
            dismissable=True
        )
        
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
