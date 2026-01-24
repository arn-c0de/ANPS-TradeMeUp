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
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta
from pathlib import Path
import plotly.graph_objects as go
import pandas as pd
from sqlalchemy import create_engine
import logging

from src.config.settings import settings
from src.gui.components import create_navbar
from src.utils.activity_logger import activity_logger
from src.gui.utils.task_queue import get_task_queue, add_gui_task

logger = logging.getLogger(__name__)

# Import tab modules
from src.gui.tabs import dashboard, predictions, news, statistics, charts, simulations, system, control, testing
from src.gui.tabs import settings as settings_tab
from src.gui.charts import MarketDataProvider

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
            
            /* COMPLETELY DISABLE hover effect on predictions table */
            .predictions-table-no-hover tbody tr:hover,
            .predictions-table-no-hover.table-striped tbody tr:hover,
            .predictions-table-no-hover.table-dark tbody tr:hover,
            .predictions-table-no-hover.table-striped.table-dark tbody tr:hover {
                background-color: #0a0a0a !important;
                cursor: default !important;
            }
            
            /* Keep hover for other tables */
            .table-striped tbody tr:hover:not(.predictions-table-no-hover tbody tr),
            .table-striped.table-dark tbody tr:hover:not(.predictions-table-no-hover tbody tr) {
                background-color: #0a0a0a !important;
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
            
            /* Mobile-friendly touch buttons */
            .touch-button {
                -webkit-tap-highlight-color: rgba(102, 126, 234, 0.3) !important;
                tap-highlight-color: rgba(102, 126, 234, 0.3) !important;
                user-select: none !important;
                -webkit-user-select: none !important;
                -moz-user-select: none !important;
                -ms-user-select: none !important;
                cursor: pointer !important;
                position: relative !important;
                z-index: 100 !important;
                touch-action: manipulation !important;
            }
            
            /* Ensure buttons capture all touch events with visual feedback */
            .touch-button:active {
                transform: scale(0.95);
                background-color: rgba(102, 126, 234, 0.3) !important;
                transition: transform 0.1s ease, background-color 0.1s ease;
            }
            
            /* DON'T block pointer events on table rows - needed for Dash updates! */
            /* Just ensure buttons have high z-index to capture clicks first */
            .predictions-table-no-hover tbody tr td button {
                isolation: isolate;
            }
            
            /* Ensure buttons are easily tappable on mobile (48x48px minimum) */
            @media (max-width: 768px) {
                .touch-button {
                    min-width: 48px !important;
                    min-height: 48px !important;
                    padding: 10px 14px !important;
                    font-size: 14px !important;
                }
            }
            
            /* Increase tap target for tablets (50x50px) */
            @media (min-width: 769px) and (max-width: 1024px) {
                .touch-button {
                    min-width: 52px !important;
                    min-height: 52px !important;
                    padding: 12px 16px !important;
                    font-size: 15px !important;
                }
            }
            
            /* Quad panel styling - professional focus indication without scale */
            .quad-panel-hover {
                transition: border-color 0.3s ease, box-shadow 0.3s ease;
            }
            .quad-panel-hover:hover {
                box-shadow: 0 6px 16px rgba(102, 126, 234, 0.5) !important;
                border-color: rgba(102, 126, 234, 0.9) !important;
            }
            
            /* Settings button hover effect */
            .quad-panel-hover:hover .position-absolute {
                opacity: 1 !important;
                transform: scale(1.05);
                backgroundColor: rgba(40,40,40,0.95) !important;
            }
            
            /* Active/focused panel styling */
            .panel-focused {
                border: 3px solid rgba(102, 126, 234, 0.9) !important;
                box-shadow: 0 0 20px rgba(102, 126, 234, 0.6) !important;
            }

            /* Ensure panel settings modal is on top of fullscreen charts */
            .panel-settings-modal {
                z-index: 3003 !important;
            }
            .panel-settings-modal .modal-dialog {
                z-index: 3004 !important;
            }
            .modal-backdrop.show {
                z-index: 3002 !important;
            }
            
            /* Resizable chart splitters */
            .chart-splitter-horizontal {
                height: 8px;
                background: linear-gradient(to bottom, rgba(102, 126, 234, 0.2), rgba(102, 126, 234, 0.4), rgba(102, 126, 234, 0.2));
                cursor: ns-resize;
                position: relative;
                z-index: 100;
                transition: background 0.2s ease;
            }
            .chart-splitter-horizontal:hover {
                background: linear-gradient(to bottom, rgba(102, 126, 234, 0.4), rgba(102, 126, 234, 0.7), rgba(102, 126, 234, 0.4));
            }
            .chart-splitter-horizontal:active {
                background: rgba(102, 126, 234, 0.8);
            }
            
            .chart-splitter-vertical {
                width: 8px;
                background: linear-gradient(to right, rgba(102, 126, 234, 0.2), rgba(102, 126, 234, 0.4), rgba(102, 126, 234, 0.2));
                cursor: ew-resize;
                position: relative;
                z-index: 100;
                transition: background 0.2s ease;
                display: inline-block;
                height: 100%;
            }
            .chart-splitter-vertical:hover {
                background: linear-gradient(to right, rgba(102, 126, 234, 0.4), rgba(102, 126, 234, 0.7), rgba(102, 126, 234, 0.4));
            }
            .chart-splitter-vertical:active {
                background: rgba(102, 126, 234, 0.8);
            }
            
            /* Resizable panel container */
            .resizable-panel {
                position: relative;
                overflow: hidden;
            }
            
            /* Chart container styles */
            .chart-container-normal {
                position: relative;
                width: 100%;
            }
            
            /* Fullscreen chart container - fills entire viewport */
            .chart-container-fullscreen {
                position: fixed !important;
                top: 0 !important;
                left: 0 !important;
                width: 100vw !important;
                height: 100vh !important;
                z-index: 3000 !important;
                background-color: #060606 !important;
                overflow-y: auto !important;
                overflow-x: hidden !important;
                padding: 5px 10px !important;
                box-sizing: border-box !important;
            }
            
            /* Fix chart panel heights in fullscreen mode */
            .chart-container-fullscreen .card {
                margin-bottom: 5px !important;
                overflow: hidden !important;
            }
            
            .chart-container-fullscreen .card-body {
                overflow: hidden !important;
            }
            
            .chart-container-fullscreen .h-100 {
                height: 100% !important;
                max-height: 100% !important;
            }
            
            /* Force Plotly charts to respect container heights */
            .chart-container-fullscreen .js-plotly-plot,
            .chart-container-fullscreen .plotly,
            .chart-container-fullscreen .plotly .main-svg {
                height: 100% !important;
                max-height: 100% !important;
                width: 100% !important;
            }
            
            /* Make dcc.Graph components flex properly */
            .chart-container-fullscreen .dash-graph,
            ._dash-loading-callback {
                height: 100% !important;
                display: flex !important;
                flex-direction: column !important;
            }
            
            /* Force flex on all chart containers */
            .chart-container-fullscreen [id^="chart-content"] > div {
                height: 100% !important;
                display: flex !important;
                flex-direction: column !important;
            }
            
            /* Ensure proper spacing in fullscreen mode */
            .chart-container-fullscreen .mb-3 {
                margin-bottom: 10px !important;
            }
            
            .chart-container-fullscreen .mb-2 {
                margin-bottom: 10px !important;
            }
            
            /* Remove bottom padding from last row */
            .chart-container-fullscreen .row:last-child {
                margin-bottom: 0 !important;
            }
            
            .chart-container-fullscreen .row:last-child .col {
                margin-bottom: 0 !important;
            }
        </style>
        <script>
            // Drag-to-resize functionality for chart splitters
            document.addEventListener('DOMContentLoaded', function() {
                let isDragging = false;
                let currentSplitter = null;
                let startPos = 0;
                let resizeRaf = null;

                function resizePlotlyCharts(scope) {
                    if (!window.Plotly || !Plotly.Plots || !Plotly.Plots.resize) return;
                    const root = scope || document;
                    const graphs = root.querySelectorAll('.js-plotly-plot');
                    graphs.forEach(graph => {
                        if (!graph || graph.offsetParent === null) return;
                        try {
                            Plotly.Plots.resize(graph);
                        } catch (err) {
                            // Ignore resize errors for detached nodes
                        }
                    });
                }

                function schedulePlotlyResize(scope) {
                    if (resizeRaf) return;
                    resizeRaf = window.requestAnimationFrame(() => {
                        resizeRaf = null;
                        resizePlotlyCharts(scope);
                    });
                }
                
                function initSplitters() {
                    // Horizontal splitters
                    const hSplitters = document.querySelectorAll('.chart-splitter-horizontal');
                    hSplitters.forEach(splitter => {
                        splitter.addEventListener('mousedown', function(e) {
                            isDragging = true;
                            currentSplitter = splitter;
                            startPos = e.clientY;
                            document.body.style.cursor = 'ns-resize';
                            e.preventDefault();
                        });
                    });
                    
                    // Vertical splitters
                    const vSplitters = document.querySelectorAll('.chart-splitter-vertical');
                    vSplitters.forEach(splitter => {
                        splitter.addEventListener('mousedown', function(e) {
                            isDragging = true;
                            currentSplitter = splitter;
                            startPos = e.clientX;
                            document.body.style.cursor = 'ew-resize';
                            e.preventDefault();
                        });
                    });
                }
                
                document.addEventListener('mousemove', function(e) {
                    if (!isDragging || !currentSplitter) return;
                    
                    const isHorizontal = currentSplitter.classList.contains('chart-splitter-horizontal');
                    const parent = currentSplitter.parentElement;
                    const prevElement = currentSplitter.previousElementSibling;
                    const nextElement = currentSplitter.nextElementSibling;
                    
                    if (!prevElement || !nextElement) return;
                    
                    if (isHorizontal) {
                        // Vertical drag (horizontal splitter)
                        const delta = e.clientY - startPos;
                        const parentHeight = parent.offsetHeight;
                        const prevHeight = prevElement.offsetHeight;
                        const nextHeight = nextElement.offsetHeight;
                        
                        const newPrevHeight = prevHeight + delta;
                        const newNextHeight = nextHeight - delta;
                        
                        // Minimum height 100px
                        if (newPrevHeight > 100 && newNextHeight > 100) {
                            const prevPercent = (newPrevHeight / parentHeight) * 100;
                            const nextPercent = (newNextHeight / parentHeight) * 100;
                            
                            prevElement.style.height = `calc(${prevPercent}% - 4px)`;
                            nextElement.style.height = `calc(${nextPercent}% - 4px)`;
                            
                            startPos = e.clientY;
                        }
                    } else {
                        // Horizontal drag (vertical splitter)
                        const delta = e.clientX - startPos;
                        const parentWidth = parent.offsetWidth;
                        const prevWidth = prevElement.offsetWidth;
                        const nextWidth = nextElement.offsetWidth;
                        
                        const newPrevWidth = prevWidth + delta;
                        const newNextWidth = nextWidth - delta;
                        
                        // Minimum width 200px
                        if (newPrevWidth > 200 && newNextWidth > 200) {
                            const prevPercent = (newPrevWidth / parentWidth) * 100;
                            const nextPercent = (newNextWidth / parentWidth) * 100;
                            
                            prevElement.style.width = `${prevPercent}%`;
                            nextElement.style.width = `${nextPercent}%`;
                            
                            startPos = e.clientX;
                        }
                    }
                });
                
                document.addEventListener('mouseup', function() {
                    if (isDragging) {
                        isDragging = false;
                        currentSplitter = null;
                        document.body.style.cursor = '';
                    }
                });
                
                // Initialize on load and reinitialize on updates
                initSplitters();
                
                // MutationObserver to reinitialize when chart layout changes
                const observer = new MutationObserver(function(mutations) {
                    initSplitters();
                    schedulePlotlyResize(chartArea);
                });
                
                const chartArea = document.getElementById('chart-display-area');
                if (chartArea) {
                    observer.observe(chartArea, { childList: true, subtree: true });
                    if (window.ResizeObserver) {
                        const resizeObserver = new ResizeObserver(() => schedulePlotlyResize(chartArea));
                        resizeObserver.observe(chartArea);
                    }
                    // Kick a couple of fast resizes for tab activation/layout settle
                    schedulePlotlyResize(chartArea);
                    setTimeout(() => schedulePlotlyResize(chartArea), 50);
                    setTimeout(() => schedulePlotlyResize(chartArea), 250);
                }

                window.addEventListener('resize', function() {
                    schedulePlotlyResize(chartArea);
                });
            });
        </script>
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
    dcc.Store(id="rss-fetch-status-store", data=None),
    
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
            dbc.Tab(settings_tab.create_layout(), label="⚙️ Settings", tab_id="settings", className="text-light")
        ], id="tabs", active_tab="dashboard", persistence=True, persistence_type="local")
    ], fluid=True)
], className="bg-dark text-light min-vh-100")


# ============================================================================
# CLIENTSIDE CALLBACKS
# ============================================================================

# ESC key listener for fullscreen mode - fixed version
app.clientside_callback(
    """
    function(fullscreen_data) {
        // Remove old listener if exists
        if (window.escKeyHandler) {
            document.removeEventListener('keydown', window.escKeyHandler);
        }

        // Only add listener if in fullscreen mode
        if (fullscreen_data && fullscreen_data.fullscreen) {
            window.escKeyHandler = function(event) {
                if (event.key === 'Escape' || event.key === 'Esc') {
                    // Check if any Bootstrap modal is currently open
                    const openModals = document.querySelectorAll('.modal.show');
                    if (openModals.length > 0) {
                        // Don't trigger fullscreen toggle if a modal is open
                        return;
                    }

                    const fullscreenBtn = document.getElementById('toggle-fullscreen-btn');
                    if (fullscreenBtn) {
                        fullscreenBtn.click();
                    }
                }
            };
            document.addEventListener('keydown', window.escKeyHandler);
        }

        return window.dash_clientside.no_update;
    }
    """,
    Output("esc-key-listener", "value"),
    Input("chart-fullscreen-state", "data")
)

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
    Output("rss-fetch-status-store", "data"),
    Input("btn-fetch-rss-only", "n_clicks"),
    prevent_initial_call=True
)
def fetch_rss_only(n_clicks):
    """Open RSS fetch in separate terminal window"""
    if not n_clicks:
        return dash.no_update
    
    import subprocess
    from pathlib import Path
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # Use wrapper batch script to keep console open
        wrapper_script = Path("scripts/run_rss_fetch_wrapper.bat").absolute()
        
        if not wrapper_script.exists():
            error_msg = f"RSS fetch script not found: {wrapper_script}"
            activity_logger.log_activity(error_msg, "ERROR")
            logger.error(error_msg)
            return {"status": "error", "message": str(error_msg)}
        
        # Start in new console window
        cmd = f'start "TradeMeUp RSS Fetch" /D "{Path.cwd()}" "{wrapper_script}"'
        
        # Start the process using shell command
        process = subprocess.Popen(
            cmd,
            shell=True,
            cwd=str(Path.cwd())
        )
        
        logger.info(f"RSS fetch terminal opened with command: {cmd}")
        activity_logger.log_activity(
            "RSS Feed Fetch: Terminal window opened - Check the new window",
            "INFO"
        )
        
        return {"status": "success", "message": "RSS fetch started in new terminal"}
        
    except Exception as e:
        logger.error(f"Error opening RSS fetch terminal: {e}", exc_info=True)
        activity_logger.log_activity(
            f"RSS Fetch Error: {str(e)}",
            "ERROR"
        )
        return {"status": "error", "message": str(e)}


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

    # Extract refreshing prediction ID from loading state
    refreshing_id = loading_state.get("prediction_id") if loading_state else None

    return predictions.get_predictions_table(
        engine,
        entity_filter=entities,
        date_range=date_range,
        min_confidence=min_conf or 0,
        horizon=horizon or '5d',
        surprise_filter=surprise_filter or 'all',
        refreshing_prediction_id=refreshing_id
    )


# ============================================================================
# CALLBACKS - SIMULATIONS TAB
# ============================================================================

@app.callback(
    Output("sim-entity-filter", "options"),
    [Input("interval-component", "n_intervals"),
     Input("sim-date-filter", "start_date"),
     Input("sim-date-filter", "end_date")]
)
def update_simulation_entity_options(n, start_date, end_date):
    """Update simulation entity filter dropdown options"""
    date_range = (start_date, end_date) if start_date or end_date else None
    return simulations.get_entity_options(engine, date_range=date_range)


@app.callback(
    Output("simulation-table", "children"),
    [Input("sim-entity-filter", "value"),
     Input("sim-date-filter", "start_date"),
     Input("sim-date-filter", "end_date"),
     Input("sim-horizon-filter", "value"),
     Input("sim-decision-filter", "value"),
     Input("create-sim-status", "children"),
     Input("sim-delete-status", "data")]  # Refresh table after creating/deleting
)
def update_simulation_table(entities, start_date, end_date, horizon, decision, _, __):
    """Update simulations table with filters."""
    date_range = (start_date, end_date) if start_date or end_date else None
    return simulations.get_simulation_table(
        engine,
        entity_filter=entities,
        date_range=date_range,
        decision_filter=decision or "all",
        horizon_filter=horizon or "all"
    )


@app.callback(
    Output("create-sim-entity-filter", "options"),
    Input("interval-component", "n_intervals")
)
def update_create_simulation_entity_options(n):
    """Update create simulation entity filter dropdown options"""
    return simulations.get_entity_options(engine)


@app.callback(
    Output("create-sim-status", "children"),
    Input("btn-create-simulations", "n_clicks"),
    [State("create-sim-entity-filter", "value"),
     State("create-sim-date-range", "start_date"),
     State("create-sim-date-range", "end_date"),
     State("create-sim-horizon-filter", "value"),
     State("create-sim-limit", "value")],
    prevent_initial_call=True
)
def create_simulations_from_predictions(n_clicks, entities, start_date, end_date, horizon, limit):
    """Create new simulations from predictions based on filters."""
    if not n_clicks:
        return ""

    try:
        from src.simulations.trading_simulator import TradingSimulationEngine
        from datetime import datetime

        engine_sim = TradingSimulationEngine()

        # Prepare date range
        date_range = None
        if start_date and end_date:
            start = datetime.fromisoformat(start_date) if isinstance(start_date, str) else start_date
            end = datetime.fromisoformat(end_date) if isinstance(end_date, str) else end_date
            date_range = (start, end)

        # Create simulations
        stats = engine_sim.create_simulations_from_predictions(
            entity_filter=entities if entities else None,
            horizon_filter=horizon if horizon != "all" else None,
            date_range=date_range,
            limit=limit or 50
        )

        return dbc.Alert(
            f"✓ Created {stats['created']} simulations, updated {stats['updated']}, skipped {stats['skipped']}, errors {stats['errors']}",
            color="success" if stats['errors'] == 0 else "warning",
            dismissable=True,
            duration=5000
        )
    except Exception as e:
        logger.error(f"Error creating simulations: {e}")
        return dbc.Alert(
            f"✗ Error creating simulations: {str(e)}",
            color="danger",
            dismissable=True,
            duration=5000
        )


@app.callback(
    [Output({"type": "delete-sim", "index": ALL}, "disabled"),
     Output("sim-delete-status", "data")],
    Input({"type": "delete-sim", "index": ALL}, "n_clicks"),
    State({"type": "delete-sim", "index": ALL}, "id"),
    prevent_initial_call=True
)
def delete_simulation(n_clicks, button_ids):
    """Delete a simulation."""
    if not n_clicks or not any(n_clicks):
        raise PreventUpdate

    ctx = dash.callback_context
    if not ctx.triggered:
        raise PreventUpdate

    import json
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    try:
        button_id = json.loads(triggered_id)
    except Exception:
        return dash.no_update, dash.no_update

    if not button_ids:
        return dash.no_update, dash.no_update

    target_index = None
    for i, item in enumerate(button_ids):
        if item == button_id:
            target_index = i
            break

    if target_index is None:
        return dash.no_update, dash.no_update

    try:
        from src.simulations.trading_simulator import TradingSimulationEngine

        simulation_id = button_id["index"]
        engine_sim = TradingSimulationEngine()
        success = engine_sim.delete_simulation(simulation_id)

        if success:
            logger.info(f"Deleted simulation {simulation_id}")
            disabled_states = [False] * len(button_ids)
            disabled_states[target_index] = True
            return disabled_states, {"simulation_id": simulation_id, "deleted": True, "ts": datetime.utcnow().isoformat()}
        return [False] * len(button_ids), dash.no_update
    except Exception as e:
        logger.error(f"Error deleting simulation: {e}")
        return [False] * len(button_ids), dash.no_update


@app.callback(
    Output({"type": "refresh-sim", "index": MATCH}, "disabled"),
    Input({"type": "refresh-sim", "index": MATCH}, "n_clicks"),
    State({"type": "refresh-sim", "index": MATCH}, "id"),
    prevent_initial_call=True
)
def refresh_simulation(n_clicks, button_id):
    """Refresh/recalculate a simulation."""
    if not n_clicks:
        return False

    try:
        from src.simulations.trading_simulator import TradingSimulationEngine

        simulation_id = button_id["index"]
        engine_sim = TradingSimulationEngine()
        success = engine_sim.refresh_simulation(simulation_id)

        if success:
            logger.info(f"Refreshed simulation {simulation_id}")
        return False  # Keep button enabled
    except Exception as e:
        logger.error(f"Error refreshing simulation: {e}")
        return False


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
    logger.info(f"=== MODAL TOGGLE CALLBACK === details: {detail_clicks}, sim_details: {sim_detail_clicks}, close: {close_click}, refresh: {refresh_click}")

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

    # Detail button clicked (from predictions tab) - parse the prop_id to get the index
    if "pred-detail-btn" in trigger_id and ".n_clicks" in trigger_id:
        # Extract prediction_id from triggered prop_id
        import json
        # prop_id format: '{"index":"uuid","type":"pred-detail-btn"}.n_clicks'
        id_str = trigger_id.split('.')[0]
        id_dict = json.loads(id_str)
        prediction_id = id_dict.get("index")

        if prediction_id:
            # Load with live performance data for accurate calculations
            return True, {"prediction_id": prediction_id, "load_performance": True}, prediction_id

    # Detail button clicked (from simulations tab) - parse the prop_id to get the index
    if "sim-detail-btn" in trigger_id and ".n_clicks" in trigger_id:
        # Extract prediction_id from triggered prop_id
        import json
        # prop_id format: '{"index":"uuid","type":"sim-detail-btn"}.n_clicks'
        id_str = trigger_id.split('.')[0]
        id_dict = json.loads(id_str)
        prediction_id = id_dict.get("index")

        if prediction_id:
            logger.info(f"Opening prediction modal from simulations tab: {prediction_id}")
            # Load with live performance data for accurate calculations
            return True, {"prediction_id": prediction_id, "load_performance": True}, prediction_id

    # No actual button was clicked (just re-render), don't update
    return dash.no_update, dash.no_update, dash.no_update


# Note: Inline performance buttons removed for performance reasons
# Performance data is shown in the modal when clicking Details button


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
    import json

    if not callback_context.triggered:
        return {}, dash.no_update, False, "", "info"

    trigger_id = callback_context.triggered[0]["prop_id"]
    trigger_value = callback_context.triggered[0].get("value")

    if trigger_value is None:
        return {}, dash.no_update, False, "", "info"

    # Extract prediction_id from the clicked button
    if "pred-refresh-btn" in trigger_id and ".n_clicks" in trigger_id:
        id_str = trigger_id.split('.')[0]
        id_dict = json.loads(id_str)
        prediction_id = id_dict.get("index")

        if prediction_id:
            logger.info(f"🔄 Adding refresh task for prediction: {prediction_id}")

            # Add task to queue
            def refresh_task():
                """Execute the refresh in background - using same logic as Details view"""
                try:
                    from sqlalchemy.orm import Session
                    from src.models.predictions import Prediction, PredictionOutcome
                    from src.models.entities import Entity
                    from src.gui.tabs.predictions import _format_saved_performance
                    import uuid
                    from datetime import datetime
                    
                    with Session(engine) as db:
                        # Get prediction and entity
                        pred = db.query(Prediction).filter(
                            Prediction.prediction_id == prediction_id
                        ).first()
                        
                        if not pred:
                            logger.warning(f"Prediction {prediction_id} not found")
                            return {"status": "error", "error": "Prediction not found"}
                        
                        entity = db.query(Entity).filter(
                            Entity.entity_id == pred.entity_id
                        ).first()
                        
                        if not entity:
                            logger.warning(f"Entity {pred.entity_id} not found")
                            return {"status": "error", "error": "Entity not found"}
                        
                        # Get or create outcome
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
                            db.flush()  # Get the ID but don't commit yet
                        
                        # Calculate performance using SAME logic as Details view
                        performance = _format_saved_performance(pred, entity, outcome, load_live_prices=True)
                        
                        if not performance:
                            return {"status": "error", "error": "Could not calculate performance"}
                        
                        # Update outcome with calculated values
                        outcome.actual_return = performance.get('total_return_pct', 0)
                        outcome.error = abs(performance.get('total_return_pct', 0))
                        outcome.direction_correct = performance.get('is_correct', False)
                        outcome.evaluation_timestamp = datetime.now()
                        
                        db.commit()
                        
                        logger.info(f"✅ Saved performance for {prediction_id}: {outcome.actual_return:.2f}%")
                        
                        return {
                            "status": "success",
                            "total_return_pct": performance.get('total_return_pct', 0),
                            "is_correct": performance.get('is_correct', False)
                        }
                        
                except Exception as e:
                    logger.error(f"Error in refresh_task for {prediction_id}: {e}", exc_info=True)
                    return {"status": "error", "error": str(e)}
            
            # Get queue stats
            queue_mgr = get_task_queue()
            queue_stats = queue_mgr.get_queue_stats()
            queue_size = queue_stats.get('queue_sizes', {}).get('refresh_prediction', 0)
            
            # Add task
            task_id = add_gui_task(
                task_type="refresh_prediction",
                function=refresh_task,
                priority=1
            )

            # Don't regenerate table - keep current data and just show toast
            # The table will be updated when task completes

            # Toast notification about queue
            toast_msg = f"Refreshing... (queue position: {queue_size + 1})" if queue_size > 0 else "🔄 Refreshing performance..."
            toast_icon = "info"

            return {"prediction_id": prediction_id, "task_id": task_id}, dash.no_update, True, toast_msg, toast_icon

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
        # Check if we have an active task
        if not loading_state or "task_id" not in loading_state:
            raise dash.exceptions.PreventUpdate

        task_id = loading_state.get("task_id")
        prediction_id = loading_state.get("prediction_id")

        if not task_id or not prediction_id:
            raise dash.exceptions.PreventUpdate

        # Check task status
        queue_mgr = get_task_queue()
        status = queue_mgr.get_task_status(task_id)
    except dash.exceptions.PreventUpdate:
        # Let PreventUpdate propagate without logging - it's normal Dash control flow
        raise
    except Exception as e:
        logger.error(f"Error in refresh_prediction_performance: {e}", exc_info=True)
        raise dash.exceptions.PreventUpdate
    
    # Task not found or still pending/running
    if status is None or status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
        raise dash.exceptions.PreventUpdate
    
    # Task completed or failed - update UI
    try:
        # Delay to ensure database commit is complete and visible
        import time
        time.sleep(0.5)  # Increased from 0.3 to ensure commit is visible
        
        # Log the result before regenerating table
        if status == TaskStatus.COMPLETED:
            result = queue_mgr.get_task_result(task_id)
            logger.info(f"📊 Task completed, result: {result}")
        
        date_range = (start_date, end_date) if start_date or end_date else None
        table = predictions.get_predictions_table(
            engine,
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
                toast_msg = f"✅ Performance updated: {result.get('total_return_pct', 0):+.2f}%"
                toast_icon = "success"
            else:
                toast_msg = "✅ Performance updated"
                toast_icon = "success"
        elif status == TaskStatus.FAILED:
            toast_msg = "❌ Error updating performance"
            toast_icon = "danger"
        elif status == TaskStatus.CANCELLED:
            toast_msg = "⚠️ Task cancelled"
            toast_icon = "warning"
        
        return table, True, toast_msg, toast_icon, {}
    
    except Exception as e:
        logger.error(f"Error updating UI after task completion: {e}", exc_info=True)
        # Return minimal safe values
        return dash.no_update, True, "❌ Error displaying results", "danger", {}


@app.callback(
    [Output("prediction-modal-title", "children"),
     Output("prediction-modal-body", "children")],
    [Input("prediction-detail-cache", "data")],
    [State("prediction-modal", "is_open")],
    prevent_initial_call=True
)
def update_modal_content(cached_data, is_open):
    """Update modal content from cached prediction_id"""
    logger.info(f"=== UPDATE MODAL CONTENT === is_open: {is_open}, cached_data: {cached_data}")

    # Only load if modal is open and we have a prediction_id
    if not is_open or not cached_data or "prediction_id" not in cached_data:
        logger.info("Skipping modal content update - not open or no data")
        return dash.no_update, dash.no_update

    # Load fresh data from DB using cached prediction_id
    prediction_id = cached_data["prediction_id"]
    load_performance = cached_data.get("load_performance", False)
    logger.info(f"Loading prediction details: {prediction_id}, load_performance: {load_performance}")
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

def _resolve_stats_date_range(start_date, end_date, active_filter):
    if active_filter and active_filter != "all":
        if active_filter.endswith("h"):
            hours = None
            if active_filter.startswith("custom-"):
                try:
                    hours = int(active_filter.split("-", 1)[1].rstrip("h"))
                except ValueError:
                    hours = None
            else:
                try:
                    hours = int(active_filter.rstrip("h"))
                except ValueError:
                    hours = None

            if hours:
                end = datetime.utcnow()
                start = end - timedelta(hours=hours)
                return (start, end)

    if start_date or end_date:
        return (start_date, end_date)
    return None

@app.callback(
    Output("statistics-metrics", "children"),
    [Input("interval-component", "n_intervals"),
     Input("stats-date-range", "start_date"),
     Input("stats-date-range", "end_date"),
     Input("stats-granularity", "value"),
     Input("active-filter-store", "data")]
)
def update_statistics_metrics(n, start_date, end_date, granularity, active_filter):
    """Update statistics metrics with date filters"""
    date_range = _resolve_stats_date_range(start_date, end_date, active_filter)
    return statistics.get_statistics_metrics(engine, date_range=date_range, granularity=granularity)


@app.callback(
    [Output("stats-date-range", "start_date"),
     Output("stats-date-range", "end_date"),
     Output("active-filter-store", "data")],
    [Input("quick-1h", "n_clicks"),
     Input("quick-12h", "n_clicks"),
     Input("quick-24h", "n_clicks"),
     Input("quick-7d", "n_clicks"),
     Input("quick-30d", "n_clicks"),
     Input("quick-90d", "n_clicks"),
     Input("quick-1y", "n_clicks"),
     Input("quick-all", "n_clicks"),
     Input("custom-hours-input", "value"),
     Input("stats-reset-filter", "n_clicks")],
    prevent_initial_call=True
)
def update_stats_date_range(btn_1h, btn_12h, btn_24h, btn_7d, btn_30d, btn_90d, btn_1y, btn_all, custom_hours, btn_reset):
    """Update date range based on quick select buttons or custom hours input"""
    from dash import callback_context
    from datetime import datetime, timedelta

    if not callback_context.triggered:
        raise PreventUpdate

    trigger_id = callback_context.triggered[0]["prop_id"].split(".")[0]

    now = datetime.now().date()
    now_datetime = datetime.now()

    if trigger_id == "quick-1h":
        start = (now_datetime - timedelta(hours=1)).date()
        return start, now, "1h"
    elif trigger_id == "quick-12h":
        start = (now_datetime - timedelta(hours=12)).date()
        return start, now, "12h"
    elif trigger_id == "quick-24h":
        return (now - timedelta(days=1)), now, "24h"
    elif trigger_id == "quick-7d":
        return (now - timedelta(days=7)), now, "7d"
    elif trigger_id == "quick-30d":
        return (now - timedelta(days=30)), now, "30d"
    elif trigger_id == "quick-90d":
        return (now - timedelta(days=90)), now, "90d"
    elif trigger_id == "quick-1y":
        return (now - timedelta(days=365)), now, "1y"
    elif trigger_id == "custom-hours-input" and custom_hours:
        try:
            hours = int(custom_hours)
            if hours > 0 and hours <= 8760:  # Max 1 year in hours
                start = (now_datetime - timedelta(hours=hours)).date()
                return start, now, f"custom-{hours}h"
        except:
            pass
    elif trigger_id == "quick-all" or trigger_id == "stats-reset-filter":
        # For "all time", return None to show everything
        return None, None, "all"

    raise PreventUpdate


@app.callback(
    [Output("quick-1h", "outline"),
     Output("quick-12h", "outline"),
     Output("quick-24h", "outline"),
     Output("quick-7d", "outline"),
     Output("quick-30d", "outline"),
     Output("quick-90d", "outline"),
     Output("quick-1y", "outline"),
     Output("quick-all", "outline")],
    Input("active-filter-store", "data")
)
def update_button_styles(active_filter):
    """Update button styles to highlight the active filter"""
    # All buttons start as outline
    styles = [True, True, True, True, True, True, True, True]

    # Set the active button to not outline (filled)
    if active_filter == "1h":
        styles[0] = False
    elif active_filter == "12h":
        styles[1] = False
    elif active_filter == "24h":
        styles[2] = False
    elif active_filter == "7d":
        styles[3] = False
    elif active_filter == "30d":
        styles[4] = False
    elif active_filter == "90d":
        styles[5] = False
    elif active_filter == "1y":
        styles[6] = False
    elif active_filter == "all":
        styles[7] = False
    # For custom filters, all buttons remain outlined

    return styles


@app.callback(
    [Output("event-distribution-chart", "figure"),
     Output("quality-distribution-chart", "figure")],
    [Input("interval-component", "n_intervals"),
     Input("stats-date-range", "start_date"),
     Input("stats-date-range", "end_date"),
     Input("active-filter-store", "data")]
)
def update_statistics_charts(n, start_date, end_date, active_filter):
    """Update statistics charts with date filtering"""
    date_range = _resolve_stats_date_range(start_date, end_date, active_filter)
    event_fig = statistics.get_event_distribution_chart(engine, date_range=date_range)
    quality_fig = statistics.get_quality_distribution_chart(engine, date_range=date_range)
    return event_fig, quality_fig


@app.callback(
    Output("sentiment-distribution-chart", "figure"),
    [Input("interval-component", "n_intervals"),
     Input("stats-date-range", "start_date"),
     Input("stats-date-range", "end_date"),
     Input("active-filter-store", "data")]
)
def update_sentiment_chart(n, start_date, end_date, active_filter):
    """Update sentiment distribution chart with date filtering"""
    date_range = _resolve_stats_date_range(start_date, end_date, active_filter)
    return statistics.get_sentiment_distribution_chart(engine, date_range=date_range)


@app.callback(
    Output("impact-distribution-chart", "figure"),
    [Input("interval-component", "n_intervals"),
     Input("stats-date-range", "start_date"),
     Input("stats-date-range", "end_date"),
     Input("active-filter-store", "data")]
)
def update_impact_chart(n, start_date, end_date, active_filter):
    """Update impact distribution chart with date filtering"""
    date_range = _resolve_stats_date_range(start_date, end_date, active_filter)
    return statistics.get_impact_distribution_chart(engine, date_range=date_range)


@app.callback(
    Output("top-entities-list", "children"),
    [Input("interval-component", "n_intervals"),
     Input("stats-date-range", "start_date"),
     Input("stats-date-range", "end_date"),
     Input("active-filter-store", "data")]
)
def update_top_entities(n, start_date, end_date, active_filter):
    """Update top entities list with date filtering"""
    date_range = _resolve_stats_date_range(start_date, end_date, active_filter)
    return statistics.get_top_entities_list(engine, date_range=date_range)


@app.callback(
    Output("news-volume-chart", "figure"),
    [Input("interval-component", "n_intervals"),
     Input("stats-date-range", "start_date"),
     Input("stats-date-range", "end_date"),
     Input("active-filter-store", "data")]
)
def update_news_volume(n, start_date, end_date, active_filter):
    """Update news volume chart with date filtering"""
    date_range = _resolve_stats_date_range(start_date, end_date, active_filter)
    return statistics.get_news_volume_chart(engine, date_range=date_range)


# NEW: Entity Sentiment Analysis Callbacks
@app.callback(
    Output("entity-sentiment-chart", "figure"),
    [Input("interval-component", "n_intervals"),
     Input("stats-date-range", "start_date"),
     Input("stats-date-range", "end_date"),
     Input("active-filter-store", "data"),
     Input("sentiment-timeframe-selector", "value")]
)
def update_entity_sentiment_chart(n, start_date, end_date, active_filter, timeframe):
    """Update entity sentiment chart with timeframe filter"""
    date_range = _resolve_stats_date_range(start_date, end_date, active_filter)
    return statistics.get_entity_sentiment_chart(engine, date_range=date_range, timeframe=timeframe)


@app.callback(
    [Output("top-positive-entities", "children"),
     Output("positive-entities-toggle", "children"),
     Output("positive-entities-toggle", "style"),
     Output("positive-entities-expanded", "data")],
    [Input("interval-component", "n_intervals"),
     Input("stats-date-range", "start_date"),
     Input("stats-date-range", "end_date"),
     Input("active-filter-store", "data"),
     Input("positive-entity-search-input", "value"),
     Input("positive-entities-toggle", "n_clicks")],
    [State("positive-entities-expanded", "data")]
)
def update_top_positive_entities(n, start_date, end_date, active_filter, search_term, n_clicks, is_expanded):
    """Update top positive entities with optional search filter and expand/collapse"""
    from dash import callback_context
    
    # Toggle expanded state if button was clicked
    if callback_context.triggered and "positive-entities-toggle" in callback_context.triggered[0]["prop_id"]:
        is_expanded = not is_expanded
    
    # Get entities with appropriate limit
    date_range = _resolve_stats_date_range(start_date, end_date, active_filter)
    entities = statistics.get_top_positive_entities(engine, search_term or "", show_all=is_expanded, date_range=date_range)
    
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
     Input("stats-date-range", "start_date"),
     Input("stats-date-range", "end_date"),
     Input("active-filter-store", "data"),
     Input("negative-entity-search-input", "value"),
     Input("negative-entities-toggle", "n_clicks")],
    [State("negative-entities-expanded", "data")]
)
def update_top_negative_entities(n, start_date, end_date, active_filter, search_term, n_clicks, is_expanded):
    """Update top negative entities with optional search filter and expand/collapse"""
    from dash import callback_context
    
    # Toggle expanded state if button was clicked
    if callback_context.triggered and "negative-entities-toggle" in callback_context.triggered[0]["prop_id"]:
        is_expanded = not is_expanded
    
    # Get entities with appropriate limit
    date_range = _resolve_stats_date_range(start_date, end_date, active_filter)
    entities = statistics.get_top_negative_entities(engine, search_term or "", show_all=is_expanded, date_range=date_range)
    
    # Update button text and visibility
    button_text = "Show Less" if is_expanded else "Show More"
    button_style = {"display": "none" if search_term else "inline-block"}
    
    return entities, button_text, button_style, is_expanded


@app.callback(
    [Output("entity-details-table", "children"),
     Output("entity-table-sort-store", "data")],
    [Input("interval-component", "n_intervals"),
     Input("stats-date-range", "start_date"),
     Input("stats-date-range", "end_date"),
     Input("active-filter-store", "data"),
     Input("entity-search-input", "value"),
     Input({"type": "sort-column-btn", "column": dash.dependencies.ALL}, "n_clicks")],
    [State("entity-table-sort-store", "data"),
     State({"type": "sort-column-btn", "column": dash.dependencies.ALL}, "id")],
    prevent_initial_call=False
)
def update_entity_details_table(n, start_date, end_date, active_filter, search_term, sort_clicks, sort_state, button_ids):
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
    date_range = _resolve_stats_date_range(start_date, end_date, active_filter)
    table = statistics.get_entity_details_table(
        engine, 
        search_term or "", 
        current_column, 
        current_direction,
        date_range=date_range
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


@app.callback(
    Output("index-trends-display", "children"),
    Input("interval-component", "n_intervals")
)
def update_index_trends(n_intervals):
    """Update index trends display"""
    return statistics.get_index_trends(engine)


@app.callback(
    [Output("stock-predictions-modal", "is_open"),
     Output("stock-modal-title", "children"),
     Output("stock-modal-body", "children")],
    [Input({"type": "stock-pred-btn", "index": ALL}, "n_clicks"),
     Input("close-stock-modal", "n_clicks")],
    [State({"type": "stock-pred-btn", "index": ALL}, "id"),
     State("stock-predictions-modal", "is_open")],
    prevent_initial_call=True
)
def toggle_stock_predictions_modal(stock_clicks, close_click, button_ids, is_open):
    """Toggle stock predictions modal"""
    from dash import callback_context
    
    if not callback_context.triggered:
        return dash.no_update, dash.no_update, dash.no_update
    
    trigger_id = callback_context.triggered[0]["prop_id"]
    
    # Close button clicked
    if "close-stock-modal" in trigger_id:
        return False, dash.no_update, dash.no_update
    
    # Stock button clicked
    if "stock-pred-btn" in trigger_id:
        if stock_clicks and any(click for click in stock_clicks if click):
            # Find which button was clicked
            triggered_id = callback_context.triggered[0]["prop_id"].split(".")[0]
            import json
            button_id = json.loads(triggered_id)
            stock_symbol = button_id["index"]
            
            # Load stock predictions
            title, body = statistics.get_stock_predictions_detail(engine, stock_symbol)
            return True, title, body
    
    return dash.no_update, dash.no_update, dash.no_update


@app.callback(
    [Output("prediction-modal", "is_open", allow_duplicate=True),
     Output("prediction-detail-cache", "data", allow_duplicate=True),
     Output("current-prediction-id", "data", allow_duplicate=True),
     Output("entity-details-modal", "is_open", allow_duplicate=True),
     Output("no-prediction-toast", "is_open", allow_duplicate=True)],
    Input({"type": "news-pred-detail-btn", "index": ALL}, "n_clicks"),
    [State({"type": "news-pred-detail-btn", "index": ALL}, "id"),
     State("prediction-modal", "is_open"),
     State("entity-details-modal", "is_open")],
    prevent_initial_call=True
)
def open_news_prediction_detail(n_clicks_list, button_ids, pred_modal_open, entity_modal_open):
    """Open prediction detail modal for clicked news article"""
    from sqlalchemy.orm import Session
    from src.models.predictions import Prediction
    
    # Check if any button was clicked
    if not n_clicks_list or not any(n_clicks_list):
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    # Find which button was clicked
    ctx = dash.callback_context
    if not ctx.triggered:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    # Get the news_id from the triggered button
    triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
    import json
    button_id = json.loads(triggered_id)
    news_id = button_id["index"]  # news_id is a UUID string, not an integer
    
    # Find prediction that has this news_id in related_news_ids
    try:
        with Session(engine) as db:
            # Query predictions where related_news_ids contains the news_id
            # related_news_ids is stored as JSON array
            predictions = db.query(Prediction).all()
            
            matching_prediction = None
            for pred in predictions:
                # Check if related_news_ids exists and contains the news_id
                if hasattr(pred, 'related_news_ids') and pred.related_news_ids:
                    try:
                        # related_news_ids might be a list or JSON string
                        news_ids = pred.related_news_ids if isinstance(pred.related_news_ids, list) else []
                        # Convert both to strings for comparison (handle UUID objects)
                        news_ids_str = [str(nid) for nid in news_ids]
                        if str(news_id) in news_ids_str:
                            matching_prediction = pred
                            break
                    except (TypeError, ValueError) as conv_error:
                        logger.debug(f"Error converting news_ids for prediction {pred.prediction_id}: {conv_error}")
                        continue
            
            if not matching_prediction:
                logger.warning(f"No prediction found for news_id {news_id}")
                # Show toast notification to user
                return dash.no_update, dash.no_update, dash.no_update, dash.no_update, True
            
            prediction_id = str(matching_prediction.prediction_id)
            
            # Close entity modal, open prediction modal with performance data (don't show toast)
            return True, {"prediction_id": prediction_id, "load_performance": True}, prediction_id, False, False
            
    except Exception as e:
        logger.error(f"Error loading prediction for news_id {news_id}: {e}", exc_info=True)
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update


# ============================================================================
# CALLBACKS - CHARTS TAB (Modern Tab-based Interface)
# ============================================================================

def _normalize_overlay_store(overlays_data):
    """Ensure overlay store has the expected shape."""
    if not isinstance(overlays_data, dict):
        return {"tabs": {}}
    tabs = overlays_data.get("tabs")
    if not isinstance(tabs, dict):
        tabs = {}
    return {"tabs": tabs}


def _ensure_overlay_tab(overlays_data, tab_id):
    """Ensure an overlay entry exists for a given tab id."""
    tabs = overlays_data.setdefault("tabs", {})
    tab_entry = tabs.get(tab_id)
    if not isinstance(tab_entry, dict):
        tab_entry = {}
    tab_entry.setdefault("brackets", [])
    tab_entry.setdefault("breaks", [])
    tabs[tab_id] = tab_entry
    return tab_entry


def _flatten_overlay_items(tab_overlays: dict):
    """Return list of (group, item) in stable order for shapes."""
    items = []
    for group in ("brackets", "breaks"):
        for item in (tab_overlays or {}).get(group, []) or []:
            items.append((group, item))
    return items

@app.callback(
    [Output("tabs", "active_tab", allow_duplicate=True),
     Output("chart-tabs-store", "data", allow_duplicate=True),
     Output("prediction-modal", "is_open", allow_duplicate=True)],
    Input({"type": "open-chart-btn", "index": ALL}, "n_clicks"),
    [State({"type": "open-chart-btn", "index": ALL}, "id"),
     State("chart-tabs-store", "data")],
    prevent_initial_call=True
)
def open_ticker_in_charts(n_clicks_list, button_ids, tabs_data):
    """Open ticker symbol in charts tab - add new tab or switch to existing"""
    from dash import callback_context
    import uuid

    if not callback_context.triggered or not any(n_clicks_list):
        return dash.no_update, dash.no_update, dash.no_update

    # Get the clicked button's ticker symbol
    triggered_id = callback_context.triggered[0]["prop_id"].split(".")[0]
    import json
    button_id = json.loads(triggered_id)
    ticker = button_id["index"]

    # Check if tab for this ticker already exists
    existing_tab = None
    for tab in tabs_data.get('tabs', []):
        if tab['symbol'] == ticker:
            existing_tab = tab['id']
            break

    if existing_tab:
        # Switch to existing tab
        tabs_data['active_tab'] = existing_tab
    else:
        # Create new tab
        new_tab_id = f"tab-{uuid.uuid4().hex[:8]}"
        new_tab = {
            'id': new_tab_id,
            'symbol': ticker,
            'timeframe': '1mo',
            'chart_type': 'candlestick'
        }
        tabs_data['tabs'].append(new_tab)
        tabs_data['active_tab'] = new_tab_id

    # Switch to charts tab but KEEP the prediction modal open - don't close it
    return "charts", tabs_data, dash.no_update


# ===== DATABASE FUNCTIONS FOR CHART OVERLAYS =====

def load_overlays_from_db():
    """Load all chart overlays from database."""
    from sqlalchemy.orm import Session
    from src.models.chart_overlays import ChartOverlay

    try:
        with Session(engine) as db:
            overlays_db = db.query(ChartOverlay).all()
            logger.info(f"[DB Load] Found {len(overlays_db)} overlays in database")

            overlays_dict = {"tabs": {}}

            for overlay in overlays_db:
                # Create key from symbol + timeframe
                key = f"{overlay.symbol}_{overlay.timeframe}"
                if key not in overlays_dict["tabs"]:
                    overlays_dict["tabs"][key] = {"brackets": [], "breaks": []}

                overlays_dict["tabs"][key][overlay.group].append(overlay.to_dict())
                logger.info(f"[DB Load]   {overlay.symbol} {overlay.timeframe} {overlay.group}: ${overlay.price} ({overlay.name})")

            logger.info(f"[DB Load] Loaded {len(overlays_dict['tabs'])} overlay groups")
            return overlays_dict
    except Exception as e:
        logger.error(f"[DB Load] Error loading overlays from DB: {e}", exc_info=True)
        return {"tabs": {}}


def save_overlays_to_db(overlays_data, tabs_data):
    """Save chart overlays to database."""
    from sqlalchemy.orm import Session
    from src.models.chart_overlays import ChartOverlay
    import uuid

    try:
        tabs = tabs_data.get('tabs', []) if isinstance(tabs_data, dict) else []
        tab_map = {tab['id']: (tab['symbol'], tab['timeframe']) for tab in tabs if 'id' in tab}

        logger.info(f"[DB Save] Tab map: {tab_map}")
        logger.info(f"[DB Save] Overlays tabs: {list(overlays_data.get('tabs', {}).keys())}")

        with Session(engine) as db:
            # Clear existing overlays
            deleted_count = db.query(ChartOverlay).delete()
            logger.info(f"[DB Save] Deleted {deleted_count} existing overlays")

            # Save all overlays
            overlays = overlays_data.get("tabs", {})
            saved_count = 0
            for tab_id, tab_data in overlays.items():
                # Get symbol and timeframe
                # Support both real tab IDs (from tab_map) and symbol_timeframe format
                if tab_id in tab_map:
                    # Real tab ID from active tabs
                    symbol, timeframe = tab_map[tab_id]
                elif "_" in tab_id:
                    # symbol_timeframe format (e.g., "TSLA_1d_1m")
                    parts = tab_id.split("_", 1)
                    if len(parts) == 2:
                        symbol, timeframe = parts
                    else:
                        logger.warning(f"[DB Save] Cannot parse tab_id {tab_id}, skipping")
                        continue
                else:
                    logger.warning(f"[DB Save] Tab ID {tab_id} not recognized, skipping")
                    continue

                logger.info(f"[DB Save] Processing {symbol} {timeframe} (tab_id: {tab_id})")

                for group in ["brackets", "breaks"]:
                    items = tab_data.get(group, [])
                    logger.info(f"[DB Save]   {group}: {len(items)} items")
                    for item in items:
                        # Try to parse existing UUID, or generate new one if invalid
                        try:
                            overlay_id = uuid.UUID(item.get("id", ""))
                        except (ValueError, AttributeError):
                            overlay_id = uuid.uuid4()

                        overlay = ChartOverlay(
                            overlay_id=overlay_id,
                            symbol=symbol,
                            timeframe=timeframe,
                            group=group,
                            price=float(item["price"]),
                            name=item.get("name", ""),
                            color=item.get("color", "#00ff88" if group == "brackets" else "#ff4444"),
                            visible=item.get("visible", True)
                        )
                        db.add(overlay)
                        saved_count += 1
                        logger.info(f"[DB Save]     Added {group} at ${item['price']} (name: {item.get('name', 'N/A')})")

            db.commit()
            logger.info(f"[DB Save] Successfully saved {saved_count} overlays to database")
    except Exception as e:
        logger.error(f"[DB Save] Error saving overlays to DB: {e}", exc_info=True)


@app.callback(
    Output("chart-overlays-store", "data"),
    Input("chart-tabs-store", "data"),
    State("chart-overlays-store", "data")
)
def sync_chart_overlays(tabs_data, overlays_data):
    """Keep overlay store in sync with existing chart tabs and load from DB on first run."""
    import copy
    from dash import callback_context

    # On first load, try to load overlays from database
    if not overlays_data or not overlays_data.get('tabs'):
        logger.info("Loading overlays from database...")
        overlays = load_overlays_from_db()
        if overlays and overlays.get('tabs'):
            logger.info(f"Loaded {len(overlays['tabs'])} overlay groups from DB")
            # Map DB overlays (symbol_timeframe) to tab IDs
            tabs = tabs_data.get('tabs', []) if isinstance(tabs_data, dict) else []
            mapped_overlays = {"tabs": {}}
            for tab in tabs:
                tab_id = tab.get('id')
                symbol = tab.get('symbol')
                timeframe = tab.get('timeframe')
                db_key = f"{symbol}_{timeframe}"
                if db_key in overlays['tabs']:
                    mapped_overlays['tabs'][tab_id] = overlays['tabs'][db_key]
            overlays = mapped_overlays
        else:
            overlays = {"tabs": {}}
    else:
        overlays = _normalize_overlay_store(copy.deepcopy(overlays_data))

    tabs = tabs_data.get('tabs', []) if isinstance(tabs_data, dict) else []
    tab_ids = {tab.get('id') for tab in tabs if tab.get('id')}

    changed = False
    # Add missing entries
    for tab_id in tab_ids:
        if tab_id not in overlays["tabs"]:
            overlays["tabs"][tab_id] = {"brackets": [], "breaks": []}
            changed = True
        else:
            entry = overlays["tabs"][tab_id]
            if not isinstance(entry, dict):
                overlays["tabs"][tab_id] = {"brackets": [], "breaks": []}
                changed = True
            else:
                if "brackets" not in entry:
                    entry["brackets"] = []
                    changed = True
                if "breaks" not in entry:
                    entry["breaks"] = []
                    changed = True

    # Remove stale entries
    for tab_id in list(overlays["tabs"].keys()):
        if tab_id not in tab_ids:
            overlays["tabs"].pop(tab_id, None)
            changed = True

    return overlays if changed else dash.no_update


@app.callback(
    Output("chart-price-cache-store", "data"),
    [Input("chart-price-update-interval", "n_intervals"),
     Input("chart-tabs-store", "data")],
    prevent_initial_call=False
)
def update_price_cache(n_intervals, tabs_data):
    """Update price cache in background (non-blocking for UI)"""
    import concurrent.futures
    from src.gui.charts.market_data import market_data

    tabs = tabs_data.get('tabs', [])
    if not tabs:
        return {}

    symbols = list(set([tab['symbol'] for tab in tabs]))
    price_cache = {}

    def fetch_price(symbol):
        try:
            quote = market_data.get_live_price(symbol)
            return symbol, quote
        except:
            return symbol, None

    # Parallel price fetching (max 5 concurrent)
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = executor.map(fetch_price, symbols)
        for symbol, quote in results:
            if quote:
                price_cache[symbol] = quote

    return price_cache


@app.callback(
    Output("chart-tab-buttons", "children"),
    [Input("chart-tabs-store", "data"),
     Input("chart-price-cache-store", "data")]
)
def render_chart_tabs(tabs_data, price_cache):
    """Render the browser-style tab buttons with cached price data"""
    tabs = tabs_data.get('tabs', [])
    active_tab = tabs_data.get('active_tab')
    price_cache = price_cache or {}

    tab_buttons = []
    for tab in tabs:
        is_active = tab['id'] == active_tab
        symbol = tab['symbol']
        timeframe = tab.get('timeframe', '1mo')

        # Get cached price data (non-blocking)
        quote = price_cache.get(symbol)
        if quote:
            price = quote.get('price', 0)
            change = quote.get('change', 0)
            change_pct = quote.get('change_percent', 0)

            price_class = "chart-tab-price chart-tab-positive" if change >= 0 else "chart-tab-price chart-tab-negative"
            change_class = "chart-tab-change chart-tab-positive" if change >= 0 else "chart-tab-change chart-tab-negative"

            tab_content = html.Span([
                html.Span(symbol, className="chart-tab-symbol"),
                html.Span(f"${price:.2f}", className=price_class),
                html.Span(f"{change:+.2f} ({change_pct:+.2f}%)", className=change_class)
            ], className="chart-tab-label", title=f"{symbol} | {timeframe}")
        else:
            # Fallback if no cached data yet
            tab_content = html.Span([
                html.Span(symbol, className="chart-tab-symbol"),
                html.Span(f" • {timeframe}", className="chart-tab-timeframe", style={'opacity': '0.7'})
            ], className="chart-tab-label", title=f"{symbol} | {timeframe}")
        
        tab_button = dbc.ButtonGroup([
            dbc.Button(
                tab_content,
                id={"type": "chart-tab-btn", "index": tab['id']},
                color="primary" if is_active else "secondary",
                size="sm",
                outline=not is_active,
                className=f"chart-tab-button{' active' if is_active else ''}"
            ),
            dbc.Button(
                "×",
                id={"type": "chart-tab-close-btn", "index": tab['id']},
                color="danger" if is_active else "secondary",
                size="sm",
                outline=True,
                className="chart-tab-close",
                title="Close tab"
            )
        ], size="sm", className="chart-tab-group")
        
        tab_buttons.append(tab_button)
    
    return tab_buttons


@app.callback(
    [Output("trading-overlay-modal", "is_open"),
     Output("overlay-modal-tab-id", "data")],
    [Input({"type": "overlay-manage-btn", "index": ALL}, "n_clicks"),
     Input("overlay-modal-close-btn", "n_clicks")],
    [State("trading-overlay-modal", "is_open"),
     State({"type": "overlay-manage-btn", "index": ALL}, "id")],
    prevent_initial_call=True
)
def toggle_trading_overlay_modal(manage_clicks, close_click, is_open, manage_ids):
    """Open overlay modal from a chart panel."""
    from dash import callback_context
    import json

    if not callback_context.triggered:
        raise PreventUpdate

    triggered = callback_context.triggered[0]
    trigger = triggered["prop_id"].split(".")[0]
    trigger_value = triggered.get("value")
    if trigger == "overlay-modal-close-btn":
        return False, None

    if "overlay-manage-btn" in trigger:
        if not trigger_value:
            return dash.no_update, dash.no_update
        try:
            trigger_id = json.loads(trigger)
        except json.JSONDecodeError:
            return dash.no_update, dash.no_update
        tab_id = trigger_id.get("index")
        return True, tab_id

    return is_open, dash.no_update


@app.callback(
    [Output("overlay-brackets-container", "children"),
     Output("overlay-breaks-container", "children")],
    [Input("chart-overlays-store", "data"),
     Input("chart-tabs-store", "data"),
     Input("overlay-modal-tab-id", "data")]
)
def render_overlay_lists(overlays_data, tabs_data, active_tab_id):
    """Render grouped bracket/break lists for all charts (active tabs + DB overlays)."""
    from sqlalchemy.orm import Session
    from src.models.chart_overlays import ChartOverlay

    # Get active tabs
    tabs = tabs_data.get("tabs", []) if isinstance(tabs_data, dict) else []
    overlays = _normalize_overlay_store(overlays_data)

    # Build combined list: symbol_timeframe -> data
    all_charts = {}  # {symbol_timeframe: {symbol, timeframe, tab_id, brackets, breaks}}

    # 1. Add all ACTIVE tabs first (from chart-tabs-store)
    for tab in tabs:
        tab_id = tab.get("id")
        symbol = tab.get("symbol", "Unknown")
        timeframe = tab.get("timeframe", "1mo")
        key = f"{symbol}_{timeframe}"

        tab_overlays = overlays.get("tabs", {}).get(tab_id, {})
        all_charts[key] = {
            "symbol": symbol,
            "timeframe": timeframe,
            "tab_id": tab_id,  # Use real tab_id for active tabs
            "brackets": tab_overlays.get("brackets", []) or [],
            "breaks": tab_overlays.get("breaks", []) or []
        }

    # 2. Add DB-only overlays (symbols WITHOUT active tabs)
    try:
        with Session(engine) as db:
            overlays_db = db.query(ChartOverlay).all()
            logger.info(f"[Overlay List] Found {len(overlays_db)} overlays in DB")

            for overlay in overlays_db:
                key = f"{overlay.symbol}_{overlay.timeframe}"

                # ONLY add if this symbol_timeframe is NOT in active tabs (to avoid duplicates)
                if key not in all_charts:
                    # Create new entry for DB-only symbol
                    all_charts[key] = {
                        "symbol": overlay.symbol,
                        "timeframe": overlay.timeframe,
                        "tab_id": key,  # Use symbol_timeframe as tab_id for DB-only
                        "brackets": [],
                        "breaks": []
                    }
                    # Add overlay to the appropriate group
                    all_charts[key][overlay.group].append(overlay.to_dict())
                    logger.info(f"[Overlay List] Added DB-only: {overlay.symbol} {overlay.timeframe} {overlay.group}")
    except Exception as e:
        logger.error(f"Error loading DB overlays for list: {e}", exc_info=True)

    if not all_charts:
        empty = html.Div("No charts available.", className="overlay-empty")
        return empty, empty

    # Determine active accordion item
    active_item = []
    if active_tab_id:
        # Find matching symbol_timeframe for active tab
        for tab in tabs:
            if tab.get("id") == active_tab_id:
                key = f"{tab.get('symbol')}_{tab.get('timeframe')}"
                active_item = [key]
                break

    def build_group(group, default_color, label):
        accordion_items = []

        # Iterate over all charts (active tabs + DB-only)
        for key, chart_data in all_charts.items():
            symbol = chart_data["symbol"]
            timeframe = chart_data["timeframe"]
            tab_id = chart_data["tab_id"]  # Real tab_id or symbol_timeframe
            items = chart_data.get(group, []) or []

            # Get current price for this symbol
            current_price = None
            try:
                df = charts.market_data.get_historical_data(symbol, period='1d')
                if df is not None and not df.empty:
                    current_price = df['Close'].iloc[-1]
            except:
                pass

            rows = []
            if items:
                for item in items:
                    item_id = item.get("id")
                    price_value = item.get("price")
                    name_value = item.get("name", "")
                    color_value = item.get("color") or default_color
                    is_visible = item.get("visible", True)
                    rows.append(
                        dbc.Row([
                            dbc.Col(
                                dbc.Input(
                                    id={"type": "overlay-item-price", "group": group, "tab": tab_id, "index": item_id},
                                    type="number",
                                    step="0.01",
                                    value=price_value,
                                    debounce=True,
                                    placeholder="Price",
                                    className="overlay-price-input"
                                ),
                                width=3
                            ),
                            dbc.Col(
                                dbc.Input(
                                    id={"type": "overlay-item-name", "group": group, "tab": tab_id, "index": item_id},
                                    type="text",
                                    value=name_value,
                                    debounce=True,
                                    placeholder="Label",
                                    className="overlay-name-input"
                                ),
                                width=3
                            ),
                            dbc.Col(
                                dbc.Input(
                                    id={"type": "overlay-item-color", "group": group, "tab": tab_id, "index": item_id},
                                    type="color",
                                    value=color_value,
                                    className="overlay-color-input"
                                ),
                                width="auto"
                            ),
                            dbc.Col(
                                dbc.Checklist(
                                    id={"type": "overlay-item-visible", "group": group, "tab": tab_id, "index": item_id},
                                    options=[{"label": "Visible", "value": "visible"}],
                                    value=["visible"] if is_visible else [],
                                    switch=True,
                                    className="overlay-visible-toggle"
                                ),
                                width="auto"
                            ),
                            dbc.Col(
                                dbc.Button(
                                    "↗",
                                    id={"type": "overlay-jump-btn", "group": group, "tab": tab_id, "index": item_id},
                                    color="secondary",
                                    size="sm",
                                    outline=True,
                                    className="overlay-jump-btn",
                                    title="Open chart"
                                ),
                                width="auto"
                            ),
                            dbc.Col(
                                dbc.Button(
                                    "✕",
                                    id={"type": "overlay-item-delete", "group": group, "tab": tab_id, "index": item_id},
                                    color="secondary",
                                    size="sm",
                                    outline=True,
                                    className="overlay-delete-btn"
                                ),
                                width="auto"
                            )
                        ], className="overlay-item-row g-2 align-items-center")
                    )
            else:
                rows.append(html.Div("No entries yet.", className="overlay-empty"))

            rows.append(html.Hr(className="overlay-divider"))
            rows.append(html.Div(f"Add {label}", className="overlay-section-title mb-2"))
            rows.append(
                dbc.Row([
                    dbc.Col(
                        dbc.Input(
                            id={"type": "overlay-add-price", "group": group, "tab": tab_id},
                            type="number",
                            step="0.01",
                            placeholder="Price",
                            debounce=True,
                            className="overlay-price-input"
                        ),
                        width=3
                    ),
                    dbc.Col(
                        dbc.Input(
                            id={"type": "overlay-add-name", "group": group, "tab": tab_id},
                            type="text",
                            placeholder="Label (optional)",
                            debounce=True,
                            className="overlay-name-input"
                        ),
                        width=3
                    ),
                    dbc.Col(
                        dbc.Input(
                            id={"type": "overlay-add-color", "group": group, "tab": tab_id},
                            type="color",
                            value=default_color,
                            className="overlay-color-input"
                        ),
                        width="auto"
                    ),
                    dbc.Col(
                        dbc.Checklist(
                            id={"type": "overlay-add-visible", "group": group, "tab": tab_id},
                            options=[{"label": "Visible", "value": "visible"}],
                            value=["visible"],
                            switch=True,
                            className="overlay-visible-toggle"
                        ),
                        width="auto"
                    ),
                    dbc.Col(
                        dbc.Button(
                            "Add",
                            id={"type": "overlay-add-btn", "group": group, "tab": tab_id},
                            color="primary",
                            size="sm"
                        ),
                        width="auto"
                    )
                ], className="g-2 align-items-center")
            )

            # Build title with current price if available
            price_str = f" ${current_price:.2f}" if current_price else ""
            title_text = f"{symbol}{price_str} • {timeframe} ({len(items)})"

            accordion_items.append(
                dbc.AccordionItem(
                    rows,
                    title=title_text,
                    item_id=key  # Use symbol_timeframe as accordion item_id
                )
            )

        return dbc.Accordion(
            accordion_items,
            active_item=active_item,
            always_open=True,
            className="overlay-accordion"
        )

    brackets_view = build_group("brackets", "#00ff88", "Bracket")
    breaks_view = build_group("breaks", "#ff4444", "Break")
    return brackets_view, breaks_view


@app.callback(
    Output("chart-overlays-store", "data", allow_duplicate=True),
    Input({"type": "overlay-add-btn", "group": ALL, "tab": ALL}, "n_clicks"),
    [State({"type": "overlay-add-btn", "group": ALL, "tab": ALL}, "id"),
     State({"type": "overlay-add-price", "group": ALL, "tab": ALL}, "id"),
     State({"type": "overlay-add-price", "group": ALL, "tab": ALL}, "value"),
     State({"type": "overlay-add-name", "group": ALL, "tab": ALL}, "id"),
     State({"type": "overlay-add-name", "group": ALL, "tab": ALL}, "value"),
     State({"type": "overlay-add-color", "group": ALL, "tab": ALL}, "id"),
     State({"type": "overlay-add-color", "group": ALL, "tab": ALL}, "value"),
     State({"type": "overlay-add-visible", "group": ALL, "tab": ALL}, "id"),
     State({"type": "overlay-add-visible", "group": ALL, "tab": ALL}, "value"),
     State("chart-overlays-store", "data"),
     State("chart-tabs-store", "data")],
    prevent_initial_call=True
)
def add_overlay_item(n_clicks, add_btn_ids,
                     price_ids, price_values,
                     name_ids, name_values,
                     color_ids, color_values,
                     visible_ids, visible_values,
                     overlays_data, tabs_data):
    """Add a new bracket/break overlay line for a specific chart."""
    from dash import callback_context
    import json
    import uuid
    import copy

    if not callback_context.triggered:
        return dash.no_update

    trigger = callback_context.triggered[0]["prop_id"].split(".")[0]
    try:
        trigger_id = json.loads(trigger)
    except json.JSONDecodeError:
        return dash.no_update

    tab_id = trigger_id.get("tab")
    group = trigger_id.get("group")
    if not tab_id or group not in ("brackets", "breaks"):
        return dash.no_update

    def value_for(ids, values):
        for comp_id, value in zip(ids, values):
            if comp_id.get("tab") == tab_id and comp_id.get("group") == group:
                return value
        return None

    price = value_for(price_ids, price_values)
    name = value_for(name_ids, name_values)
    color = value_for(color_ids, color_values)
    visible = value_for(visible_ids, visible_values)

    if price is None:
        return dash.no_update

    overlays = _normalize_overlay_store(copy.deepcopy(overlays_data))
    tab_overlays = _ensure_overlay_tab(overlays, tab_id)
    item_prefix = "br" if group == "brackets" else "bk"
    default_color = "#00ff88" if group == "brackets" else "#ff4444"

    tab_overlays[group].append({
        "id": f"{item_prefix}-{uuid.uuid4().hex[:8]}",
        "price": float(price),
        "name": name or "",
        "color": color or default_color,
        "visible": "visible" in (visible or [])
    })

    # Save to database
    save_overlays_to_db(overlays, tabs_data)

    return overlays


@app.callback(
    Output("chart-overlays-store", "data", allow_duplicate=True),
    [Input({"type": "overlay-item-price", "group": "brackets", "tab": ALL, "index": ALL}, "value"),
     Input({"type": "overlay-item-name", "group": "brackets", "tab": ALL, "index": ALL}, "value"),
     Input({"type": "overlay-item-color", "group": "brackets", "tab": ALL, "index": ALL}, "value"),
     Input({"type": "overlay-item-visible", "group": "brackets", "tab": ALL, "index": ALL}, "value"),
     Input({"type": "overlay-item-delete", "group": "brackets", "tab": ALL, "index": ALL}, "n_clicks")],
    [State({"type": "overlay-item-price", "group": "brackets", "tab": ALL, "index": ALL}, "id"),
     State({"type": "overlay-item-name", "group": "brackets", "tab": ALL, "index": ALL}, "id"),
     State({"type": "overlay-item-color", "group": "brackets", "tab": ALL, "index": ALL}, "id"),
     State({"type": "overlay-item-visible", "group": "brackets", "tab": ALL, "index": ALL}, "id"),
     State({"type": "overlay-item-delete", "group": "brackets", "tab": ALL, "index": ALL}, "id"),
     State("chart-overlays-store", "data"),
     State("chart-tabs-store", "data")],
    prevent_initial_call=True
)
def update_bracket_items(price_values, name_values, color_values, visible_values, delete_clicks,
                         price_ids, name_ids, color_ids, visible_ids, delete_ids, overlays_data, tabs_data):
    """Update bracket items when fields change."""
    from dash import callback_context
    import json
    import copy

    if not callback_context.triggered:
        return dash.no_update

    trigger = callback_context.triggered[0]["prop_id"].split(".")[0]
    try:
        trigger_id = json.loads(trigger)
    except json.JSONDecodeError:
        return dash.no_update

    item_id = trigger_id.get("index")
    tab_id = trigger_id.get("tab")
    action_type = trigger_id.get("type")

    if not tab_id:
        return dash.no_update

    overlays = _normalize_overlay_store(copy.deepcopy(overlays_data))
    tab_overlays = _ensure_overlay_tab(overlays, tab_id)
    items = tab_overlays.get("brackets", [])

    if action_type == "overlay-item-delete":
        tab_overlays["brackets"] = [item for item in items if item.get("id") != item_id]
        save_overlays_to_db(overlays, tabs_data)
        return overlays

    def value_by_id(ids, values):
        for comp_id, value in zip(ids, values):
            if comp_id.get("index") == item_id and comp_id.get("tab") == tab_id:
                return value
        return None

    for item in items:
        if item.get("id") != item_id:
            continue
        if action_type == "overlay-item-price":
            new_value = value_by_id(price_ids, price_values)
            if new_value is not None:
                try:
                    item["price"] = float(new_value)
                except (TypeError, ValueError):
                    pass
        elif action_type == "overlay-item-name":
            new_value = value_by_id(name_ids, name_values)
            if new_value is not None:
                item["name"] = new_value or ""
        elif action_type == "overlay-item-color":
            new_value = value_by_id(color_ids, color_values)
            if new_value:
                item["color"] = new_value
        elif action_type == "overlay-item-visible":
            new_value = value_by_id(visible_ids, visible_values)
            item["visible"] = "visible" in (new_value or [])
        break

    # Save to database
    save_overlays_to_db(overlays, tabs_data)

    return overlays


@app.callback(
    Output("chart-overlays-store", "data", allow_duplicate=True),
    [Input({"type": "overlay-item-price", "group": "breaks", "tab": ALL, "index": ALL}, "value"),
     Input({"type": "overlay-item-name", "group": "breaks", "tab": ALL, "index": ALL}, "value"),
     Input({"type": "overlay-item-color", "group": "breaks", "tab": ALL, "index": ALL}, "value"),
     Input({"type": "overlay-item-visible", "group": "breaks", "tab": ALL, "index": ALL}, "value"),
     Input({"type": "overlay-item-delete", "group": "breaks", "tab": ALL, "index": ALL}, "n_clicks")],
    [State({"type": "overlay-item-price", "group": "breaks", "tab": ALL, "index": ALL}, "id"),
     State({"type": "overlay-item-name", "group": "breaks", "tab": ALL, "index": ALL}, "id"),
     State({"type": "overlay-item-color", "group": "breaks", "tab": ALL, "index": ALL}, "id"),
     State({"type": "overlay-item-visible", "group": "breaks", "tab": ALL, "index": ALL}, "id"),
     State({"type": "overlay-item-delete", "group": "breaks", "tab": ALL, "index": ALL}, "id"),
     State("chart-overlays-store", "data"),
     State("chart-tabs-store", "data")],
    prevent_initial_call=True
)
def update_break_items(price_values, name_values, color_values, visible_values, delete_clicks,
                       price_ids, name_ids, color_ids, visible_ids, delete_ids, overlays_data, tabs_data):
    """Update break items when fields change."""
    from dash import callback_context
    import json
    import copy

    if not callback_context.triggered:
        return dash.no_update

    trigger = callback_context.triggered[0]["prop_id"].split(".")[0]
    try:
        trigger_id = json.loads(trigger)
    except json.JSONDecodeError:
        return dash.no_update

    item_id = trigger_id.get("index")
    tab_id = trigger_id.get("tab")
    action_type = trigger_id.get("type")

    if not tab_id:
        return dash.no_update

    overlays = _normalize_overlay_store(copy.deepcopy(overlays_data))
    tab_overlays = _ensure_overlay_tab(overlays, tab_id)
    items = tab_overlays.get("breaks", [])

    if action_type == "overlay-item-delete":
        tab_overlays["breaks"] = [item for item in items if item.get("id") != item_id]
        save_overlays_to_db(overlays, tabs_data)
        return overlays

    def value_by_id(ids, values):
        for comp_id, value in zip(ids, values):
            if comp_id.get("index") == item_id and comp_id.get("tab") == tab_id:
                return value
        return None

    for item in items:
        if item.get("id") != item_id:
            continue
        if action_type == "overlay-item-price":
            new_value = value_by_id(price_ids, price_values)
            if new_value is not None:
                try:
                    item["price"] = float(new_value)
                except (TypeError, ValueError):
                    pass
        elif action_type == "overlay-item-name":
            new_value = value_by_id(name_ids, name_values)
            if new_value is not None:
                item["name"] = new_value or ""
        elif action_type == "overlay-item-color":
            new_value = value_by_id(color_ids, color_values)
            if new_value:
                item["color"] = new_value
        elif action_type == "overlay-item-visible":
            new_value = value_by_id(visible_ids, visible_values)
            item["visible"] = "visible" in (new_value or [])
        break

    # Save to database
    save_overlays_to_db(overlays, tabs_data)

    return overlays


@app.callback(
    Output("chart-overlays-store", "data", allow_duplicate=True),
    Input({"type": "chart-graph", "index": ALL}, "relayoutData"),
    [State("chart-overlays-store", "data"),
     State("chart-tabs-store", "data"),
     State({"type": "chart-graph", "index": ALL}, "id")],
    prevent_initial_call=True
)
def update_overlays_from_chart_drag(relayout_data_list, overlays_data, tabs_data, graph_ids):
    """Update overlay prices when user drags shapes in the chart."""
    from dash import callback_context
    import json
    import copy

    if not callback_context.triggered:
        return dash.no_update

    # Find which graph triggered
    trigger = callback_context.triggered[0]["prop_id"]
    if ".relayoutData" not in trigger:
        return dash.no_update

    try:
        trigger_id_str = trigger.split(".")[0]
        trigger_id = json.loads(trigger_id_str)
        tab_id = trigger_id.get("index")
    except:
        return dash.no_update

    # Get the relayout data for this graph
    trigger_index = None
    for idx, graph_id in enumerate(graph_ids):
        if graph_id.get("index") == tab_id:
            trigger_index = idx
            break

    if trigger_index is None or trigger_index >= len(relayout_data_list):
        return dash.no_update

    relayout_data = relayout_data_list[trigger_index]
    if not relayout_data:
        return dash.no_update

    # Check if shapes were modified
    shape_updates = {}
    for key, value in relayout_data.items():
        if key.startswith("shapes[") and (key.endswith(".y0") or key.endswith(".y1")):
            # Extract shape index
            import re
            match = re.match(r"shapes\[(\d+)\]\.(y\d)", key)
            if match:
                shape_idx = int(match.group(1))
                y_coord = match.group(2)
                if shape_idx not in shape_updates:
                    shape_updates[shape_idx] = {}
                shape_updates[shape_idx][y_coord] = value

    if not shape_updates:
        return dash.no_update

    # Update overlays
    overlays = _normalize_overlay_store(copy.deepcopy(overlays_data))
    tab_overlays = overlays.get("tabs", {}).get(tab_id, {})

    # Count all items to map shape index to overlay
    all_items = []
    for group in ["brackets", "breaks"]:
        items = tab_overlays.get(group, [])
        for item in items:
            all_items.append((group, item))

    # Update prices based on shape movements
    changed = False
    for shape_idx, coords in shape_updates.items():
        if shape_idx < len(all_items):
            group, item = all_items[shape_idx]
            # Use y0 for horizontal lines
            new_price = coords.get("y0") or coords.get("y1")
            if new_price and abs(float(item["price"]) - new_price) > 0.01:
                item["price"] = round(new_price, 2)
                changed = True
                logger.info(f"[Shape Drag] Updated {group} {item.get('name', 'N/A')} to ${new_price:.2f}")

    if changed:
        # Save to database
        save_overlays_to_db(overlays, tabs_data)
        return overlays
    return dash.no_update


@app.callback(
    Output("chart-view-state", "data", allow_duplicate=True),
    Input({"type": "chart-graph", "index": ALL}, "relayoutData"),
    [State("chart-view-state", "data"),
     State("chart-tabs-store", "data"),
     State({"type": "chart-graph", "index": ALL}, "id")],
    prevent_initial_call=True
)
def save_chart_view_state(relayout_data_list, view_state_data, tabs_data, graph_ids):
    """Save chart zoom/pan state to localStorage for persistence"""
    from dash import callback_context
    import json
    import copy
    
    if not callback_context.triggered:
        return dash.no_update
    
    # Find which graph triggered
    trigger = callback_context.triggered[0]["prop_id"]
    if ".relayoutData" not in trigger:
        return dash.no_update
    
    try:
        trigger_id_str = trigger.split(".")[0]
        trigger_id = json.loads(trigger_id_str)
        tab_id = trigger_id.get("index")
    except:
        return dash.no_update
    
    # Get the relayout data for this graph
    trigger_index = None
    for idx, graph_id in enumerate(graph_ids):
        if graph_id.get("index") == tab_id:
            trigger_index = idx
            break
    
    if trigger_index is None or trigger_index >= len(relayout_data_list):
        return dash.no_update
    
    relayout_data = relayout_data_list[trigger_index]
    if not relayout_data:
        return dash.no_update
    
    # Extract zoom/pan information (ignore shape-related changes)
    view_state = {}
    zoom_pan_keys = ['xaxis.range', 'yaxis.range', 'xaxis2.range', 'yaxis2.range', 
                     'xaxis.autorange', 'yaxis.autorange', 'xaxis2.autorange', 'yaxis2.autorange']
    
    for key in zoom_pan_keys:
        if key in relayout_data:
            view_state[key] = relayout_data[key]
    
    # Only save if we have actual zoom/pan data (not just shape movements)
    if not view_state:
        return dash.no_update
    
    # Update view state store
    state = copy.deepcopy(view_state_data) if view_state_data else {'tabs': {}}
    if 'tabs' not in state:
        state['tabs'] = {}
    
    # Convert Plotly format to our format
    saved_state = {}
    if 'xaxis.range' in view_state:
        saved_state['xaxis_range'] = view_state['xaxis.range']
    if 'yaxis.range' in view_state:
        saved_state['yaxis_range'] = view_state['yaxis.range']
    if 'yaxis2.range' in view_state:
        saved_state['yaxis2_range'] = view_state['yaxis2.range']
    
    state['tabs'][tab_id] = saved_state
    
    logger.debug(f"[Chart View] Saved view state for chart {tab_id}")
    return state


@app.callback(
    Output("chart-tabs-store", "data", allow_duplicate=True),
    Input({"type": "overlay-jump-btn", "group": ALL, "tab": ALL, "index": ALL}, "n_clicks"),
    [State({"type": "overlay-jump-btn", "group": ALL, "tab": ALL, "index": ALL}, "id"),
     State("chart-tabs-store", "data"),
     State("chart-overlays-store", "data")],
    prevent_initial_call=True
)
def jump_to_overlay_chart(n_clicks, button_ids, tabs_data, overlays_data):
    """Jump to chart tab from overlay list and adjust timeframe if needed."""
    from dash import callback_context
    import json
    import copy

    if not callback_context.triggered or not any(n_clicks or []):
        return dash.no_update

    trigger = callback_context.triggered[0]["prop_id"].split(".")[0]
    try:
        trigger_id = json.loads(trigger)
    except json.JSONDecodeError:
        return dash.no_update

    tab_id = trigger_id.get("tab")
    group = trigger_id.get("group")
    item_id = trigger_id.get("index")

    if not tab_id or group not in ("brackets", "breaks") or not item_id:
        return dash.no_update

    if not isinstance(tabs_data, dict):
        return dash.no_update

    tabs = tabs_data.get("tabs", [])
    target_tab = next((tab for tab in tabs if tab.get("id") == tab_id), None)
    if not target_tab:
        return dash.no_update

    overlays = _normalize_overlay_store(overlays_data)
    tab_overlays = overlays.get("tabs", {}).get(tab_id, {})
    items = tab_overlays.get(group, []) or []
    overlay_item = next((item for item in items if item.get("id") == item_id), None)
    if not overlay_item:
        return dash.no_update

    price = overlay_item.get("price")
    if price is None:
        tabs_data["active_tab"] = tab_id
        return tabs_data

    from src.gui.charts.market_data import market_data

    def fetch_df(symbol, timeframe):
        if timeframe == "1d_1m":
            return market_data.get_intraday_data(symbol, days=1)
        if timeframe == "5d_5m":
            return market_data.get_historical_data(symbol, period="5d", interval="5m")
        return market_data.get_historical_data(symbol, period=timeframe)

    def price_in_range(symbol, timeframe, price_value):
        df = fetch_df(symbol, timeframe)
        if df is None or df.empty:
            return False
        if "Low" in df.columns and "High" in df.columns:
            low = df["Low"].min()
            high = df["High"].max()
        else:
            low = df["Close"].min()
            high = df["Close"].max()
        try:
            return float(low) <= float(price_value) <= float(high)
        except (TypeError, ValueError):
            return False

    timeframes = ["1d_1m", "5d_5m", "1mo", "3mo", "6mo", "1y", "2y", "5y"]
    current_tf = target_tab.get("timeframe", "1mo")
    if current_tf not in timeframes:
        current_tf = "1mo"

    symbol = target_tab.get("symbol")
    new_tf = current_tf
    try:
        if not price_in_range(symbol, current_tf, price):
            start_idx = timeframes.index(current_tf)
            for tf in timeframes[start_idx + 1:]:
                if price_in_range(symbol, tf, price):
                    new_tf = tf
                    break
            else:
                new_tf = timeframes[-1]
    except Exception:
        new_tf = current_tf

    tabs_data = copy.deepcopy(tabs_data)
    tabs_data["active_tab"] = tab_id
    for tab in tabs_data.get("tabs", []):
        if tab.get("id") == tab_id:
            tab["timeframe"] = new_tf
            break

    return tabs_data


@app.callback(
    Output("chart-tabs-store", "data", allow_duplicate=True),
    Input({"type": "chart-tab-btn", "index": ALL}, "n_clicks"),
    State("chart-tabs-store", "data"),
    prevent_initial_call=True
)
def switch_chart_tab(n_clicks_list, tabs_data):
    """Switch to clicked tab"""
    from dash import callback_context
    import copy
    
    if not callback_context.triggered or not any(n_clicks_list):
        return dash.no_update
    
    # Get the clicked tab ID
    triggered_id = callback_context.triggered[0]["prop_id"].split(".")[0]
    import json
    button_id = json.loads(triggered_id)
    tab_id = button_id["index"]
    
    # Verify that the tab exists before switching
    tabs = tabs_data.get('tabs', [])
    tab_exists = any(tab.get('id') == tab_id for tab in tabs)
    
    if not tab_exists:
        return dash.no_update
    
    # Return a copy to avoid reference issues
    updated_data = copy.deepcopy(tabs_data)
    updated_data['active_tab'] = tab_id
    return updated_data


@app.callback(
    Output("chart-tabs-store", "data", allow_duplicate=True),
    Input({"type": "chart-tab-close-btn", "index": ALL}, "n_clicks"),
    State("chart-tabs-store", "data"),
    prevent_initial_call=True
)
def close_chart_tab(n_clicks_list, tabs_data):
    """Close clicked tab"""
    from dash import callback_context
    import copy
    
    if not callback_context.triggered or not any(n_clicks_list):
        return dash.no_update
    
    # Get the clicked tab ID
    triggered_id = callback_context.triggered[0]["prop_id"].split(".")[0]
    import json
    button_id = json.loads(triggered_id)
    tab_id_to_close = button_id["index"]
    
    # Don't close if it's the last tab (keep at least one)
    if len(tabs_data.get('tabs', [])) <= 1:
        return dash.no_update
    
    # Return a copy to avoid reference issues
    updated_data = copy.deepcopy(tabs_data)
    
    # Remove the tab
    updated_data['tabs'] = [t for t in updated_data['tabs'] if t['id'] != tab_id_to_close]
    
    # If we closed the active tab, switch to the first remaining tab
    if updated_data['active_tab'] == tab_id_to_close:
        if updated_data['tabs']:
            updated_data['active_tab'] = updated_data['tabs'][0]['id']
        else:
            updated_data['active_tab'] = None
    
    return updated_data


@app.callback(
    [Output("new-tab-modal", "is_open"),
     Output("new-tab-symbol-input", "value"),
     Output("new-tab-timeframe-selector", "value"),
     Output("new-tab-chart-type-selector", "value")],
    [Input("add-chart-tab-btn", "n_clicks"),
     Input("new-tab-cancel-btn", "n_clicks"),
     Input("new-tab-add-btn", "n_clicks")],
    State("new-tab-modal", "is_open"),
    prevent_initial_call=True
)
def toggle_new_tab_modal(add_click, cancel_click, add_btn_click, is_open):
    """Toggle new tab modal"""
    from dash import callback_context
    
    if not callback_context.triggered:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    trigger_id = callback_context.triggered[0]['prop_id'].split('.')[0]
    
    if trigger_id == "add-chart-tab-btn":
        return True, None, '1mo', 'candlestick'
    else:
        return False, None, '1mo', 'candlestick'


@app.callback(
    Output("chart-tabs-store", "data", allow_duplicate=True),
    Input("new-tab-add-btn", "n_clicks"),
    [State("new-tab-symbol-input", "value"),
     State("new-tab-timeframe-selector", "value"),
     State("new-tab-chart-type-selector", "value"),
     State("chart-tabs-store", "data")],
    prevent_initial_call=True
)
def add_new_chart_tab(n_clicks, symbol, timeframe, chart_type, tabs_data):
    """Add new chart tab"""
    import uuid
    
    if not n_clicks or not symbol:
        return dash.no_update
    
    # Create new tab
    new_tab_id = f"tab-{uuid.uuid4().hex[:8]}"
    new_tab = {
        'id': new_tab_id,
        'symbol': symbol,
        'timeframe': timeframe,
        'chart_type': chart_type
    }
    
    tabs_data['tabs'].append(new_tab)
    tabs_data['active_tab'] = new_tab_id
    
    return tabs_data


@app.callback(
    Output("new-tab-symbol-input", "options"),
    Input("new-tab-symbol-input", "search_value"),
    prevent_initial_call=True
)
def search_new_tab_symbols(search_value):
    """Search for symbols in new tab modal"""
    # Don't clear options when search_value is empty - this prevents resetting the selected value
    if not search_value or len(search_value) < 1:
        return dash.no_update
    
    from sqlalchemy.orm import Session
    from src.models.entities import Entity
    
    try:
        with Session(engine) as db:
            search_term = f"%{search_value.upper()}%"
            entities = db.query(Entity).filter(
                (Entity.entity_id.ilike(search_term)) | 
                (Entity.entity_name.ilike(search_term))
            ).limit(20).all()
            
            options = []
            for entity in entities:
                label = f"{entity.entity_id} - {entity.entity_name}"
                options.append({"label": label, "value": entity.entity_id})
            
            return options
    except Exception as e:
        logger.error(f"Error searching symbols: {e}")
        return []


@app.callback(
    [Output("chart-display-area", "children"),
     Output("chart-display-area", "className")],
    [Input("chart-tabs-store", "data"),
     Input("quad-mode-store", "data"),
     Input("chart-overlays-store", "data"),
     Input("chart-options-checklist", "value"),
     Input("chart-fullscreen-state", "data"),
     Input("layout-preset-dropdown", "value"),
     Input("refresh-all-panels", "n_clicks"),
     Input("chart-update-interval", "n_intervals"),
     Input("chart-interaction-modes", "data"),
     Input("chart-view-state", "data")],
    prevent_initial_call='initial_duplicate'
)
def render_chart_display(tabs_data, quad_data, overlays_data, chart_options, fullscreen_data, layout_preset, refresh_clicks, n_intervals, interaction_modes, view_state_data):
    """
    Render chart display area - OPTIMIZED to only render active tab.
    This significantly improves tab switching performance.
    """
    tabs = tabs_data.get('tabs', [])
    active_tab_id = tabs_data.get('active_tab')
    quad_enabled = (quad_data or {}).get('enabled', False)
    is_fullscreen = fullscreen_data.get('fullscreen', False)

    show_volume = 'volume' in (chart_options or [])
    show_ma = 'ma' in (chart_options or [])
    show_overlay = 'stats' in (chart_options or [])

    container_class = 'chart-container-fullscreen' if is_fullscreen else 'chart-container-normal'

    if not tabs:
        return dbc.Alert("No charts open. Click '+ New' to add a chart.", color="info", className="mt-3"), container_class

    def build_tab_panel(tab, panel_height, is_active, clickable=True):
        tab_show_volume = tab.get('show_volume', show_volume)
        tab_show_ma = tab.get('show_ma', show_ma)
        tab_overlays = (overlays_data or {}).get('tabs', {}).get(tab['id'], {}) if show_overlay else {}
        
        # Get interaction mode for this tab (default: zoom, auto_scroll for 1min/5min charts)
        tab_modes = (interaction_modes or {}).get('tabs', {}).get(tab['id'], {})
        dragmode = tab_modes.get('dragmode', 'zoom')
        auto_scroll = tab_modes.get('auto_scroll', tab.get('timeframe') in ['1d_1m', '5d_5m'])
        
        # Get saved view state (zoom/pan position) for this tab
        view_state = None
        if view_state_data and view_state_data.get('tabs'):
            view_state = view_state_data.get('tabs', {}).get(tab['id'])

        chart_component, stats_data = charts.get_stock_chart_components(
            tab['symbol'],
            tab['timeframe'],
            tab['chart_type'],
            show_volume=tab_show_volume,
            show_ma=tab_show_ma,
            overlays=tab_overlays,
            graph_id={"type": "chart-graph", "index": tab['id']},
            dragmode=dragmode,
            auto_scroll=auto_scroll,
            view_state=view_state
        )

        chart_div = html.Div(
            [chart_component],
            style={'height': '100%', 'display': 'flex', 'flexDirection': 'column'}
        )
        trading_overlay = charts.create_trading_overlay(stats_data, show_overlay, panel_id=tab['id']) if show_overlay else None

        panel_content = html.Div(
            ([trading_overlay] if trading_overlay else []) + [chart_div],
            style={'position': 'relative', 'height': '100%'}
        )

        panel_style = {
            'height': panel_height,
            'overflow': 'hidden'
        }
        panel_class = None

        if clickable:
            panel_style.update({
                'minHeight': '260px',
                'border': '2px solid rgba(255,255,255,0.1)',
                'borderRadius': '6px',
                'cursor': 'pointer'
            })
            panel_class = "quad-panel-hover"
            if is_active:
                panel_class = f"{panel_class} panel-focused"

            return html.Div(
                panel_content,
                id={"type": "quad-panel", "index": tab['id']},
                className=panel_class,
                style=panel_style
            )

        return html.Div(panel_content, style=panel_style)

    if quad_enabled:
        selected_tabs = (quad_data or {}).get('selected_tabs', []) or []
        tabs_by_id = {tab['id']: tab for tab in tabs}
        max_panels = min(4, len(tabs))
        if max_panels == 0:
            return dbc.Alert("No charts available for quad view.", color="info", className="mt-3"), container_class

        quad_tabs = []
        seen_tabs = set()

        def add_tab(tab):
            if not tab:
                return
            tab_id = tab.get('id')
            if tab_id and tab_id not in seen_tabs:
                quad_tabs.append(tab)
                seen_tabs.add(tab_id)

        for tab_id in selected_tabs:
            add_tab(tabs_by_id.get(tab_id))
            if len(quad_tabs) >= max_panels:
                break

        if len(quad_tabs) < max_panels:
            for tab in tabs:
                add_tab(tab)
                if len(quad_tabs) >= max_panels:
                    break

        panel_height = 'calc(50vh - 80px)' if is_fullscreen else '500px'
        row_class = "g-1" if is_fullscreen else "g-2"
        margin_class = "mb-1" if is_fullscreen else "mb-3"

        left_width, right_width = (6, 6)
        if layout_preset == 'left-focus':
            left_width, right_width = (8, 4)
        elif layout_preset == 'right-focus':
            left_width, right_width = (4, 8)

        panel_wrappers = [
            build_tab_panel(tab, panel_height, tab['id'] == active_tab_id)
            for tab in quad_tabs
        ]

        if max_panels == 1:
            quad_layout = html.Div([
                dbc.Row([dbc.Col(panel_wrappers[0], md=12)], className=row_class)
            ])
        elif max_panels == 2:
            quad_layout = html.Div([
                dbc.Row([
                    dbc.Col(panel_wrappers[0], md=left_width, className=margin_class),
                    dbc.Col(panel_wrappers[1], md=right_width, className=margin_class)
                ], className=row_class)
            ])
        elif max_panels == 3:
            quad_layout = html.Div([
                dbc.Row([
                    dbc.Col(panel_wrappers[0], md=left_width, className=margin_class),
                    dbc.Col(panel_wrappers[1], md=right_width, className=margin_class)
                ], className=row_class),
                dbc.Row([
                    dbc.Col(panel_wrappers[2], md=12)
                ], className=row_class)
            ])
        else:
            quad_layout = html.Div([
                dbc.Row([
                    dbc.Col(panel_wrappers[0], md=left_width, className=margin_class),
                    dbc.Col(panel_wrappers[1], md=right_width, className=margin_class)
                ], className=row_class),
                dbc.Row([
                    dbc.Col(panel_wrappers[2], md=left_width, className=margin_class),
                    dbc.Col(panel_wrappers[3], md=right_width, className=margin_class)
                ], className=row_class)
            ])

        return quad_layout, container_class

    # PERFORMANCE OPTIMIZATION: Only render the active tab
    # This avoids expensive API calls and chart rendering for hidden tabs
    active_tab = None
    
    # Find the active tab - make sure we use the exact active_tab_id from the store
    if active_tab_id:
        for tab in tabs:
            if tab['id'] == active_tab_id:
                active_tab = tab
                break

    # In single mode, if active tab not found, fallback to first tab for rendering
    # But don't update the store here - let a separate callback handle that
    # IMPORTANT: Only fallback if active_tab_id is None or empty, not if it's just not found
    # This prevents resetting the tab when it's being switched
    if not active_tab:
        if tabs and (not active_tab_id or active_tab_id == ''):
            # Only fallback if active_tab_id is actually None/empty, not just not found
            active_tab = tabs[0]
        elif tabs:
            # If active_tab_id exists but tab not found, try to find it again (might be timing issue)
            # But don't fallback immediately - this could be a race condition
            active_tab = None
        else:
            active_tab = None

    if not active_tab:
        return dbc.Alert("No active chart.", color="info", className="mt-3"), container_class

    # Only render the single active tab (in single mode)
    height = 'calc(100vh - 180px)' if is_fullscreen else 'calc(100vh - 320px)'
    final_style = {'display': 'block', 'height': height, 'minHeight': '600px'}

    panel_content = build_tab_panel(active_tab, "100%", True, clickable=False)
    single_chart_div = html.Div(panel_content, style=final_style)

    return single_chart_div, container_class


@app.callback(
    Output("quad-mode-store", "data"),
    [Input("layout-single", "n_clicks"),
     Input("layout-quad", "n_clicks")],
    State("quad-mode-store", "data"),
    prevent_initial_call=True
)
def toggle_quad_mode(single_click, quad_click, quad_data):
    """Toggle between single and quad mode"""
    from dash import callback_context
    
    if not callback_context.triggered:
        return dash.no_update
    
    trigger_id = callback_context.triggered[0]['prop_id'].split('.')[0]
    
    if trigger_id == "layout-single":
        quad_data['enabled'] = False
    elif trigger_id == "layout-quad":
        quad_data['enabled'] = True
    
    return quad_data


@app.callback(
    [Output("chart-fullscreen-state", "data"),
     Output("toggle-fullscreen-btn", "children"),
     Output("toggle-fullscreen-btn", "color")],
    Input("toggle-fullscreen-btn", "n_clicks"),
    State("chart-fullscreen-state", "data"),
    prevent_initial_call=True
)
def toggle_chart_fullscreen(n_clicks, fullscreen_data):
    """Toggle fullscreen mode for charts"""
    if not n_clicks:
        return dash.no_update, dash.no_update, dash.no_update
    
    is_fullscreen = fullscreen_data.get('fullscreen', False)
    fullscreen_data['fullscreen'] = not is_fullscreen
    
    if fullscreen_data['fullscreen']:
        return fullscreen_data, "⬇ Exit", "danger"
    else:
        return fullscreen_data, "⛶", "info"


@app.callback(
    [Output("layout-single", "outline"),
     Output("layout-quad", "outline")],
    Input("quad-mode-store", "data")
)
def highlight_active_layout_mode(quad_data):
    """Highlight the currently active layout button"""
    quad_enabled = quad_data.get('enabled', False)
    return (quad_enabled, not quad_enabled)


@app.callback(
    [Output("panel-settings-modal", "is_open"),
     Output("panel-settings-tab-id", "data"),
     Output("panel-settings-timeframe", "value"),
     Output("panel-settings-chart-type", "value"),
     Output("panel-settings-options", "value")],
    [Input({"type": "panel-settings-btn", "index": dash.ALL}, "n_clicks"),
     Input("panel-settings-cancel-btn", "n_clicks"),
     Input("panel-settings-apply-btn", "n_clicks")],
    [State("chart-tabs-store", "data"),
     State("panel-settings-tab-id", "data")],
    prevent_initial_call=True
)
def toggle_panel_settings_modal(settings_clicks, cancel_clicks, apply_clicks, tabs_data, current_tab_id):
    """Open/close panel settings modal and load current settings"""
    from dash import callback_context
    
    if not callback_context.triggered:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
    
    trigger = callback_context.triggered[0]['prop_id']
    
    # Close modal
    if 'cancel' in trigger or 'apply' in trigger:
        return False, None, dash.no_update, dash.no_update, dash.no_update
    
    # Open modal - load settings for clicked panel (only if settings button was actually clicked)
    if 'panel-settings-btn' in trigger and any(settings_clicks):
        import json
        trigger_dict = json.loads(trigger.split('.')[0])
        tab_id = trigger_dict['index']
        
        # Find the tab
        tabs = tabs_data.get('tabs', [])
        tab = next((t for t in tabs if t['id'] == tab_id), None)
        
        if tab:
            # Load current settings
            timeframe = tab.get('timeframe', '1mo')
            chart_type = tab.get('chart_type', 'candlestick')
            
            options = []
            if tab.get('show_volume', True):
                options.append('volume')
            if tab.get('show_ma', False):
                options.append('ma')
            # Stats is always shown for now
            options.append('stats')
            
            return True, tab_id, timeframe, chart_type, options
    
    return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update


@app.callback(
    Output("chart-tabs-store", "data", allow_duplicate=True),
    Input("panel-settings-apply-btn", "n_clicks"),
    [State("panel-settings-tab-id", "data"),
     State("panel-settings-timeframe", "value"),
     State("panel-settings-chart-type", "value"),
     State("panel-settings-options", "value"),
     State("chart-tabs-store", "data")],
    prevent_initial_call=True
)
def apply_panel_settings(n_clicks, tab_id, timeframe, chart_type, options, tabs_data):
    """Apply settings to the selected panel/tab"""
    if not n_clicks or not tab_id:
        return dash.no_update
    
    tabs = tabs_data.get('tabs', [])
    
    # Find and update the tab
    for tab in tabs:
        if tab['id'] == tab_id:
            tab['timeframe'] = timeframe
            tab['chart_type'] = chart_type
            tab['show_volume'] = 'volume' in (options or [])
            tab['show_ma'] = 'ma' in (options or [])
            break
    
    tabs_data['tabs'] = tabs
    return tabs_data


@app.callback(
    Output("chart-fullscreen-state", "data", allow_duplicate=True),
    Input("esc-key-listener", "value"),
    State("chart-fullscreen-state", "data"),
    prevent_initial_call=True
)
def close_fullscreen_on_esc(key_value, fullscreen_data):
    """Close fullscreen mode when ESC key is pressed"""
    # ESC key detection via clientside callback would be better, but this works as fallback
    if fullscreen_data.get('fullscreen', False):
        fullscreen_data['fullscreen'] = False
        return fullscreen_data
    return dash.no_update


@app.callback(
    Output("chart-tabs-store", "data", allow_duplicate=True),
    Input({"type": "quad-panel", "index": dash.ALL}, "n_clicks"),
    State("chart-tabs-store", "data"),
    prevent_initial_call=True
)
def focus_tab_on_quad_panel_click(n_clicks_list, tabs_data):
    """Focus the corresponding tab when a quad panel is clicked (but not settings button)"""
    from dash import callback_context
    
    if not callback_context.triggered or not any(n_clicks_list):
        return dash.no_update
    
    # Get the clicked panel's tab ID
    trigger = callback_context.triggered[0]['prop_id']
    
    # Don't focus if a settings button was clicked - check if trigger is exactly quad-panel
    if 'quad-panel' in trigger and 'panel-settings-btn' not in trigger:
        import json
        # Extract tab_id from the trigger string
        try:
            trigger_dict = json.loads(trigger.split('.')[0])
            clicked_tab_id = trigger_dict['index']
            
            # Update active tab
            tabs_data['active_tab'] = clicked_tab_id
            return tabs_data
        except:
            return dash.no_update
    
    return dash.no_update


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
    Output("chart-panels-config", "data"),
    [Input("layout-single", "n_clicks"),
     Input("layout-split-h", "n_clicks"),
     Input("layout-split-v", "n_clicks"),
     Input("layout-quad", "n_clicks"),
     Input("config-apply-btn", "n_clicks"),
     Input({"type": "favorite-btn", "index": dash.dependencies.ALL}, "n_clicks"),
     Input("refresh-all-panels", "n_clicks")],
    [State("chart-panels-config", "data"),
     State("current-config-panel", "data"),
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
     Input("chart-overlays-store", "data"),
     Input("chart-fullscreen-state", "data"),
     Input("chart-interaction-modes", "data"),
     Input("chart-view-state", "data")],
    prevent_initial_call='initial_duplicate'
)
def render_chart_panels(config, n_intervals, refresh_clicks, overlays_data, fullscreen_state, interaction_modes, view_state_data):
    """Render the multi-panel chart layout with fullscreen support"""
    # Handle None values
    if not config:
        config = {'layout': 'single', 'panels': {}}
    if not fullscreen_state:
        fullscreen_state = {'fullscreen': False}
    if not interaction_modes:
        interaction_modes = {'tabs': {}}
    if not view_state_data:
        view_state_data = {'tabs': {}}
    
    layout = config.get('layout', 'single')
    panels = config.get('panels', {})
    is_fullscreen = fullscreen_state.get('fullscreen', False)
    
    # Merge interaction modes into panel configs (create copy to avoid modifying original)
    import copy
    panels = copy.deepcopy(panels)
    modes_dict = (interaction_modes or {}).get('tabs', {})
    for panel_id, panel_config in panels.items():
        if panel_id in modes_dict:
            panel_config['dragmode'] = modes_dict[panel_id].get('dragmode', 'zoom')
            panel_config['auto_scroll'] = modes_dict[panel_id].get('auto_scroll', False)
        else:
            # Default: zoom mode, auto_scroll for intraday charts
            panel_config['dragmode'] = 'zoom'
            panel_config['auto_scroll'] = panel_config.get('timeframe', '1mo') in ['1d_1m', '5d_5m']
    
    # Set container class based on fullscreen state
    container_class = 'chart-container-fullscreen' if is_fullscreen else 'chart-container-normal'
    
    try:
        chart_layout = charts.render_multi_panel_layout(layout, panels, is_fullscreen, overlays_data, view_state_data)
        return chart_layout, container_class
    except Exception as e:
        logger.error(f"Error rendering chart panels: {e}", exc_info=True)
        return html.Div(f"Error rendering charts: {str(e)}", className="text-danger"), container_class


@app.callback(
    [Output("chart-update-interval", "disabled"),
     Output("chart-update-interval", "interval")],
    Input("chart-panels-config", "data"),
    prevent_initial_call=False
)
def update_chart_refresh_interval(config):
    """
    Automatically enable/disable chart refresh interval based on active timeframes.
    - 1-minute charts (1d_1m): Refresh every 60 seconds
    - 5-minute charts (5d_5m): Refresh every 5 minutes (300 seconds)
    - Longer timeframes: Disabled (manual refresh only)
    """
    if not config or not config.get('panels'):
        return True, 60000  # Disabled by default
    
    panels = config.get('panels', {})
    timeframes = []
    
    # Collect all active timeframes from panels
    for panel_id, panel_config in panels.items():
        timeframe = panel_config.get('timeframe', '1mo')
        timeframes.append(timeframe)
    
    if not timeframes:
        return True, 60000  # Disabled if no panels
    
    # Determine refresh interval based on shortest timeframe
    # Priority: 1-minute > 5-minute > disabled
    if any(tf == '1d_1m' for tf in timeframes):
        # 1-minute charts: refresh every 60 seconds
        return False, 60000
    elif any(tf == '5d_5m' for tf in timeframes):
        # 5-minute charts: refresh every 5 minutes
        return False, 300000
    else:
        # Longer timeframes: disable auto-refresh
        return True, 60000


@app.callback(
    Output("chart-interaction-modes", "data", allow_duplicate=True),
    Input({"type": "chart-mode-toggle", "index": dash.dependencies.ALL}, "n_clicks"),
    [State({"type": "chart-mode-toggle", "index": dash.dependencies.ALL}, "id"),
     State("chart-interaction-modes", "data"),
     State("chart-tabs-store", "data"),
     State("chart-panels-config", "data")],
    prevent_initial_call=True
)
def toggle_chart_interaction_mode(n_clicks_list, button_ids, modes_data, tabs_data, panels_config):
    """Toggle between zoom and pan mode for charts"""
    from dash import callback_context
    import copy
    
    if not callback_context.triggered or not any(n_clicks_list):
        return dash.no_update
    
    # Get the clicked button's panel/tab ID
    trigger_id = callback_context.triggered[0]["prop_id"].split(".")[0]
    import json
    button_id = json.loads(trigger_id)
    panel_id = button_id.get("index")
    
    if not panel_id:
        return dash.no_update
    
    # Initialize modes data if needed
    modes = copy.deepcopy(modes_data) if modes_data else {'tabs': {}}
    if 'tabs' not in modes:
        modes['tabs'] = {}
    
    # Get current mode for this panel (default: zoom)
    current_mode = modes['tabs'].get(panel_id, {}).get('dragmode', 'zoom')
    
    # Toggle between zoom and pan
    new_mode = 'pan' if current_mode == 'zoom' else 'zoom'
    
    # Update mode
    if panel_id not in modes['tabs']:
        modes['tabs'][panel_id] = {}
    
    modes['tabs'][panel_id]['dragmode'] = new_mode
    
    # Keep auto_scroll setting if it exists, otherwise set based on timeframe
    if 'auto_scroll' not in modes['tabs'][panel_id]:
        # Check timeframe from tabs or panels
        timeframe = None
        if tabs_data and tabs_data.get('tabs'):
            for tab in tabs_data.get('tabs', []):
                if tab.get('id') == panel_id:
                    timeframe = tab.get('timeframe', '1mo')
                    break
        
        if not timeframe and panels_config and panels_config.get('panels'):
            panel_config = panels_config.get('panels', {}).get(panel_id, {})
            timeframe = panel_config.get('timeframe', '1mo')
        
        modes['tabs'][panel_id]['auto_scroll'] = timeframe in ['1d_1m', '5d_5m'] if timeframe else False
    
    logger.info(f"[Chart Mode] Panel {panel_id}: Switched to {new_mode} mode")
    return modes


@app.callback(
    Output("config-symbol-input", "options"),
    Input("config-symbol-input", "search_value"),
    prevent_initial_call=True
)
def search_config_symbols(search_value):
    """Search for symbols and company names in Entity database"""
    if not search_value or len(search_value) < 1:
        return []
    
    from sqlalchemy.orm import Session
    from src.models.entities import Entity
    
    try:
        with Session(engine) as db:
            # Search by entity_id (ticker) or entity_name (company name)
            search_term = f"%{search_value.upper()}%"
            entities = db.query(Entity).filter(
                (Entity.entity_id.ilike(search_term)) | 
                (Entity.entity_name.ilike(search_term))
            ).limit(20).all()
            
            # Format as dropdown options: "AAPL - Apple Inc."
            options = []
            for entity in entities:
                label = f"{entity.entity_id} - {entity.entity_name}"
                options.append({"label": label, "value": entity.entity_id})
            
            return options
    except Exception as e:
        logger.error(f"Error searching symbols: {e}")
        return []


@app.callback(
    [Output("config-panel-modal", "is_open"),
     Output("current-config-panel", "data"),
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
    Output("tabs", "active_tab", allow_duplicate=True),
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
