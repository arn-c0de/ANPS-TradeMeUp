"""
ANPS-TradeMeUp Dashboard - Main Application
Multi-tab dashboard for monitoring news, predictions, and system health
"""

# Suppress pandas deprecation warnings from yfinance library
import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning, module='yfinance')
warnings.filterwarnings('ignore', message='.*Timestamp.utcnow.*')

import dash
from dash import dcc, html
import dash_bootstrap_components as dbc

from src.config.settings import VERSION
from src.gui.components import create_navbar
from src.gui.callbacks import register_charts_callbacks, register_common_callbacks
from src.gui.helpers.prediction_details_popup import create_prediction_modal
from src.gui.tabs import (
    dashboard,
    predictions,
    news,
    statistics,
    charts,
    simulations,
    system,
    control,
    testing,
    databases,
)
from src.gui.tabs import settings as settings_tab

# Initialize Dash app with Bootstrap dark theme
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.CYBORG],
    suppress_callback_exceptions=True,
    assets_ignore="react_suppress\\.js|chart_splitters\\.js|export_a4\\.js",
    # Improve asset loading reliability
    serve_locally=True,
    compress=False,  # Disable compression to avoid cache issues during dev
)

app.title = f"ANPS-TradeMeUp v{VERSION} - AI Trading Intelligence"

# Custom dark theme CSS for dropdowns, date pickers and news cards
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        <script src="/assets/react_suppress.js"></script>
        {%metas%}
        <title>{%title%}</title>
        <link rel="icon" type="image/png" href="/assets/ANPS-LOGO.png">
        <link rel="shortcut icon" type="image/png" href="/assets/ANPS-LOGO.png">
        <link rel="apple-touch-icon" href="/assets/ANPS-LOGO.png">
        {%css%}
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            <script src="/assets/chart_splitters.js"></script>
            <script src="/assets/export_a4.js"></script>
            {%renderer%}
        </footer>
    </body>
</html>
'''

# ============================================================================
# MAIN LAYOUT
# ============================================================================

app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    dcc.Interval(id="url-tab-startup", interval=400, n_intervals=0, max_intervals=1),  # once after 400ms for hash-ready
    dcc.Interval(id="interval-component", interval=5*1000, n_intervals=0),  # 5 seconds for live updates
    dcc.Store(id="continuous-pipeline-state", data={"running": False, "pid": None}),
    dcc.Store(id="delete-action-store", data={"action": None, "params": None}),
    dcc.Store(id="rss-fetch-status-store", data=None),
    dcc.Store(id="portfolio-capital-store", storage_type="local", data={"capital": 100000, "currency": "USD", "risk_adjustment": 0.3}),
    
    # Shared stores for prediction modal (used by multiple tabs)
    dcc.Store(id="prediction-detail-cache", data={}),
    dcc.Store(id="current-prediction-id", data=None),
    dcc.Store(id="refresh-loading-state", data={}),
    dcc.Store(id="simulation-sync-trigger", data={}),
    
    html.Button(id='refresh-all-panels', style={'display': 'none'}),
    
    # Shared prediction details modal (used by dashboard, predictions, simulations tabs)
    create_prediction_modal(),
    
    create_navbar(),
    dbc.Container([
        dbc.Tabs([
            dbc.Tab(dashboard.create_layout(), label="🏠 Dashboard", tab_id="dashboard", className="text-light"),
            dbc.Tab(news.create_layout(), label="📰 News Feed", tab_id="news", className="text-light"),
            dbc.Tab(predictions.create_layout(), label="🎯 Predictions", tab_id="predictions", className="text-light"),
            dbc.Tab(simulations.create_layout(), label="🧪 Simulations", tab_id="simulations", className="text-light"),
            dbc.Tab(statistics.create_layout(), label="📊 Statistics", tab_id="statistics", className="text-light"),
            dbc.Tab(charts.create_layout(), label="📈 Live Charts", tab_id="charts", className="text-light"),
            dbc.Tab(control.create_layout(), label="🎮 Agent Control", tab_id="control", className="text-light"),
            dbc.Tab(testing.create_layout(), label="🧪 Testing", tab_id="testing", className="text-light"),
            dbc.Tab(system.create_layout(), label="🔧 System Health", tab_id="system", className="text-light"),
            dbc.Tab(databases.create_layout(), label="🗄️ Databases", tab_id="databases", className="text-light"),
            dbc.Tab(settings_tab.create_layout(), label="⚙️ Settings", tab_id="settings", className="text-light")
        ], id="tabs", active_tab="dashboard", persistence=False)
    ], fluid=True)
], className="bg-dark text-light min-vh-100")

register_common_callbacks(app)
register_charts_callbacks(app)
dashboard.register_callbacks(app)
news.register_callbacks(app)
control.register_callbacks(app)
predictions.register_callbacks(app)
simulations.register_callbacks(app)
statistics.register_callbacks(app)
testing.register_callbacks(app)
system.register_callbacks(app)
settings_tab.register_callbacks(app)
databases.register_callbacks(app)

if __name__ == "__main__":
    print(f"🚀 Starting ANPS-TradeMeUp Dashboard v{VERSION}...")
    print("📊 Dashboard will be available at: http://127.0.0.1:8050")
    app.run(debug=True, host="0.0.0.0", port=8050)
