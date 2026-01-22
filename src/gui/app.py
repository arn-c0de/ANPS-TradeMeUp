"""
TradeMeUp Dashboard - Main Application
Multi-tab dashboard for monitoring news, predictions, and system health
"""

import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
from datetime import datetime
import plotly.graph_objects as go
import pandas as pd
from sqlalchemy import create_engine

from src.config.settings import settings
from src.gui.components import create_navbar

# Import tab modules
from src.gui.tabs import dashboard, predictions, news, statistics, charts, system, control, testing

# Initialize Dash app with Bootstrap dark theme
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.CYBORG],
    suppress_callback_exceptions=True
)

app.title = "TradeMeUp - AI Trading Intelligence"

# Database connection
engine = create_engine(settings.database_url)

# ============================================================================
# MAIN LAYOUT
# ============================================================================

app.layout = html.Div([
    dcc.Interval(id="interval-component", interval=30*1000, n_intervals=0),  # 30 seconds
    create_navbar(),
    dbc.Container([
        dbc.Tabs([
            dbc.Tab(dashboard.create_layout(), label="🏠 Dashboard", tab_id="dashboard"),
            dbc.Tab(predictions.create_layout(), label="🎯 Predictions", tab_id="predictions"),
            dbc.Tab(news.create_layout(), label="📰 News Feed", tab_id="news"),
            dbc.Tab(statistics.create_layout(), label="📊 Statistics", tab_id="statistics"),
            dbc.Tab(charts.create_layout(), label="📈 Live Charts", tab_id="charts"),
            dbc.Tab(control.create_layout(), label="🎮 Agent Control", tab_id="control"),
            dbc.Tab(testing.create_layout(), label="🧪 Testing", tab_id="testing"),
            dbc.Tab(system.create_layout(), label="🔧 System Health", tab_id="system")
        ], id="tabs", active_tab="dashboard")
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


@app.callback(
    Output("news-volume-chart", "figure"),
    Input("interval-component", "n_intervals")
)
def update_news_volume_chart(n):
    """Update news volume chart (placeholder)"""
    return charts.get_placeholder_chart()


# ============================================================================
# CALLBACKS - CHARTS TAB
# ============================================================================

@app.callback(
    Output("price-chart", "figure"),
    Input("interval-component", "n_intervals")
)
def update_price_chart(n):
    """Update price chart (placeholder)"""
    return charts.get_placeholder_chart()


@app.callback(
    Output("sentiment-heatmap", "figure"),
    Input("interval-component", "n_intervals")
)
def update_sentiment_heatmap(n):
    """Update sentiment heatmap (placeholder)"""
    return charts.get_placeholder_chart()


@app.callback(
    Output("impact-distribution", "figure"),
    Input("interval-component", "n_intervals")
)
def update_impact_distribution(n):
    """Update impact distribution (placeholder)"""
    return charts.get_placeholder_chart()


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
        PROJECT_ROOT = Path(__file__).parent.parent.parent
        python_exe = os.path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe")
        script = os.path.join(PROJECT_ROOT, "scripts", "run_mvp_pipeline.py")
        
        # Start process in background
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
            "type": "full_pipeline"
        }
        
        log = f"[{datetime.now().strftime('%H:%M:%S')}] Starting Full MVP Pipeline...\n"
        log += f"Process ID: {process.pid}\n"
        log += f"Articles to process: {limit}\n"
        log += "-" * 60 + "\n"
        
        return state, log, "Running", "warning"
        
    except Exception as e:
        error_log = f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: {str(e)}\n"
        return {"running": False}, error_log, "Error", "danger"


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
        
        return state, log, "Running", "success"
        
    except Exception as e:
        error_log = f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: {str(e)}\n"
        return {"running": False}, error_log, "Error", "danger"


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


if __name__ == "__main__":
    print("🚀 Starting TradeMeUp Dashboard...")
    print("📊 Dashboard will be available at: http://127.0.0.1:8050")
    app.run(debug=True, host="0.0.0.0", port=8050)
