"""
Charts Tab - Layout Definition
"""

from dash import dcc, html
import dash_bootstrap_components as dbc


def create_layout():
    """Create charts tab layout with modern tab-based interface"""
    return dbc.Container([
        # Auto-refresh interval for price updates
        dcc.Interval(id='chart-price-update-interval', interval=30000, n_intervals=0),  # 30 seconds
        dcc.Interval(id='chart-update-interval', interval=60000, n_intervals=0, disabled=True),  # 60 seconds, disabled by default

        # Store for cached price data (non-blocking)
        dcc.Store(id='chart-price-cache-store', storage_type='memory', data={}),

        # Store for open chart tabs
        dcc.Store(id='chart-tabs-store', storage_type='local', data={
            'tabs': [
                {'id': 'tab-1', 'symbol': 'AAPL', 'timeframe': '1mo', 'chart_type': 'candlestick', 'show_volume': True, 'show_ma': False},
                {'id': 'tab-2', 'symbol': 'MSFT', 'timeframe': '1mo', 'chart_type': 'candlestick', 'show_volume': True, 'show_ma': False},
                {'id': 'tab-3', 'symbol': 'GOOGL', 'timeframe': '1mo', 'chart_type': 'candlestick', 'show_volume': True, 'show_ma': False},
            ],
            'active_tab': 'tab-1'
        }),

        # Store for bracket/break overlays per chart (DB-backed, memory storage only)
        dcc.Store(id='chart-overlays-store', storage_type='memory', data={
            'tabs': {}
        }),
        
        # Store for chart interaction modes (zoom/pan) per chart
        dcc.Store(id='chart-interaction-modes', storage_type='memory', data={
            'tabs': {}  # {tab_id: {'dragmode': 'zoom'|'pan', 'auto_scroll': True|False}}
        }),
        
        # Store for chart zoom/pan state (persisted in browser localStorage)
        dcc.Store(id='chart-view-state', storage_type='local', data={
            'tabs': {}  # {tab_id: {'xaxis_range': [min, max], 'yaxis_range': [min, max], ...}}
        }),
        
        # Store for loaded chart data metadata (for infinite scroll)
        dcc.Store(id='chart-loaded-data-store', storage_type='memory', data={
            'tabs': {}  # {tab_id: {'symbol': str, 'timeframe': str, 'earliest_date': str, 'latest_date': str, 'data_points': int}}
        }),
        
        # Store for scroll state (prevents race conditions)
        dcc.Store(id='chart-scroll-state-store', storage_type='memory', data={
            'tabs': {}  # {tab_id: {'loading': bool, 'last_load_time': float, 'last_threshold_check': float}}
        }),
        
        # Hidden inputs for scroll triggers (one per chart, created dynamically in JS)
        # These will be created by JavaScript and referenced in callbacks
        
        # Store for panel-based chart configuration (for multi-panel layouts)
        dcc.Store(id='chart-panels-config', storage_type='session', data={
            'layout': 'single',
            'panels': {}
        }),
        
        # Store for quad mode selection
        dcc.Store(id='quad-mode-store', storage_type='session', data={
            'enabled': False,
            'selected_tabs': ['tab-1', 'tab-2', 'tab-3', 'tab-1']  # 4 tabs for quad panels
        }),
        
        # Store for fullscreen state
        dcc.Store(id='chart-fullscreen-state', storage_type='memory', data={'fullscreen': False}),
        
        # Store for panel sizes (for resizable layouts)
        dcc.Store(id='panel-sizes-store', storage_type='session', data={'sizes': [50, 50]}),  # percentage widths

        # Track which chart opened the overlay modal
        dcc.Store(id='overlay-modal-tab-id', storage_type='session', data=None),
        
        # ESC key listener for fullscreen
        dcc.Input(id='esc-key-listener', type='text', style={'display': 'none'}),
        
        # Hidden button for ESC key triggering (clicked programmatically)
        html.Button(id='esc-trigger-btn', style={'display': 'none'}),
        
        # Browser-style Tab Bar
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            # Tab buttons container
                            html.Div(id='chart-tab-buttons', className='chart-tab-bar'),
                            # Add new tab button
                            dbc.Button([html.I(className="fas fa-plus"), " New"],
                                      id="add-chart-tab-btn",
                                      color="success",
                                      size="sm",
                                      outline=True,
                                      className="ms-2 chart-tab-add-btn")
                        ], className='d-flex align-items-center')
                    ], className="py-2")
                ], className="mb-2")
            ], width=12)
        ]),
        
        # Layout Control Bar with Chart Options
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("📐 View:", className="fw-bold me-2 d-inline"),
                                dbc.ButtonGroup([
                                    dbc.Button("Single", id="layout-single", color="primary", size="sm", outline=False),
                                    dbc.Button("Split ↔", id="layout-split-h", color="primary", size="sm", outline=True),
                                    dbc.Button("Split ↕", id="layout-split-v", color="primary", size="sm", outline=True),
                                    dbc.Button("Quad", id="layout-quad", color="primary", size="sm", outline=True)
                                ], size="sm", className="me-3 d-inline"),
                                dbc.Label("� Layout:", className="fw-bold me-2 ms-3 d-inline"),
                                dcc.Dropdown(
                                    id="layout-preset-dropdown",
                                    options=[
                                        {'label': 'Equal (50/50)', 'value': 'equal'},
                                        {'label': 'Left Focus (70/30)', 'value': 'left-focus'},
                                        {'label': 'Right Focus (30/70)', 'value': 'right-focus'},
                                        {'label': 'Grid (Auto)', 'value': 'grid'}
                                    ],
                                    value='equal',
                                    clearable=False,
                                    style={'width': '150px', 'display': 'inline-block'},
                                    className="d-inline me-3"
                                ),
                                dbc.Label("📊 Options:", className="fw-bold me-2 d-inline"),
                                dbc.Checklist(
                                    id="chart-options-checklist",
                                    options=[
                                        {"label": " Volume", "value": "volume"},
                                        {"label": " MA", "value": "ma"},
                                        {"label": " Trading Overlay", "value": "stats"}
                                    ],
                                    value=["volume", "stats"],
                                    inline=True,
                                    switch=True,
                                    className="d-inline"
                                )
                            ], md=10),
                            dbc.Col([
                                dbc.Button("🔄", id="refresh-all-panels-btn", color="success", size="sm", className="me-2", title="Refresh Charts (Ctrl+R)"),
                                dbc.Button("⛶", id="toggle-fullscreen-btn", color="info", size="sm", outline=True, title="Toggle Fullscreen (ESC to exit)"),
                                # Exit fullscreen button (hidden by default, shown in fullscreen mode via callback)
                                dbc.Button("⬇ Exit Fullscreen", id="exit-fullscreen-btn", color="danger", size="sm", style={'display': 'none'})
                            ], md=2, className="text-end")
                        ], className="align-items-center")
                    ], className="py-2 px-3")
                ], className="mb-2")
            ], width=12)
        ]),
        
        # Chart Display Area with fullscreen support
        html.Div(id='chart-display-area', className='chart-container-normal'),
        
        # Multi-panel chart area (for panel-based layouts)
        html.Div(id='multi-panel-chart-area', className='chart-container-normal', style={'display': 'none'}),
        
        # Add New Tab Modal
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("➕ Add New Chart")),
            dbc.ModalBody([
                dbc.Label("Stock Symbol:", className="fw-bold"),
                dcc.Dropdown(
                    id="new-tab-symbol-input",
                    placeholder="Type to search symbol or company name...",
                    options=[],
                    searchable=True,
                    clearable=True,
                    className="mb-3"
                ),
                
                dbc.Label("Timeframe:", className="fw-bold"),
                dcc.Dropdown(
                    id="new-tab-timeframe-selector",
                    options=[
                        {'label': '1 Day (1min)', 'value': '1d_1m'},
                        {'label': '5 Days (5min)', 'value': '5d_5m'},
                        {'label': '1 Month', 'value': '1mo'},
                        {'label': '3 Months', 'value': '3mo'},
                        {'label': '6 Months', 'value': '6mo'},
                        {'label': '1 Year', 'value': '1y'},
                        {'label': '2 Years', 'value': '2y'},
                        {'label': '5 Years', 'value': '5y'}
                    ],
                    value='1mo',
                    clearable=False,
                    className="mb-3"
                ),
                
                dbc.Label("Chart Type:", className="fw-bold"),
                dcc.Dropdown(
                    id="new-tab-chart-type-selector",
                    options=[
                        {'label': '📊 Candlestick', 'value': 'candlestick'},
                        {'label': '📈 Line Chart', 'value': 'line'}
                    ],
                    value='candlestick',
                    clearable=False,
                    className="mb-3"
                )
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancel", id="new-tab-cancel-btn", color="secondary", className="me-2"),
                dbc.Button("Add Chart", id="new-tab-add-btn", color="primary")
            ])
        ], id="new-tab-modal", size="md", is_open=False),
        
        # Panel Settings Modal (for individual chart settings)
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("⚙️ Panel Settings")),
            dbc.ModalBody([
                dcc.Store(id="panel-settings-tab-id", data=None),
                
                dbc.Label("Timeframe:", className="fw-bold"),
                dcc.Dropdown(
                    id="panel-settings-timeframe",
                    options=[
                        {'label': '1 Day (1min)', 'value': '1d_1m'},
                        {'label': '5 Days (5min)', 'value': '5d_5m'},
                        {'label': '1 Month', 'value': '1mo'},
                        {'label': '3 Months', 'value': '3mo'},
                        {'label': '6 Months', 'value': '6mo'},
                        {'label': '1 Year', 'value': '1y'},
                        {'label': '2 Years', 'value': '2y'},
                        {'label': '5 Years', 'value': '5y'}
                    ],
                    clearable=False,
                    className="mb-3"
                ),
                
                dbc.Label("Chart Type:", className="fw-bold"),
                dcc.Dropdown(
                    id="panel-settings-chart-type",
                    options=[
                        {'label': '📊Candlestick', 'value': 'candlestick'},
                        {'label': '📈 Line Chart', 'value': 'line'}
                    ],
                    clearable=False,
                    className="mb-3"
                ),
                
                dbc.Label("Options:", className="fw-bold"),
                dbc.Checklist(
                    id="panel-settings-options",
                    options=[
                        {"label": " Show Volume", "value": "volume"},
                        {"label": " Show Moving Averages", "value": "ma"},
                        {"label": " Show Trading Overlay", "value": "stats"}
                    ],
                    value=["volume", "stats"],
                    inline=False,
                    switch=True
                )
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancel", id="panel-settings-cancel-btn", color="secondary", className="me-2"),
                dbc.Button("Apply", id="panel-settings-apply-btn", color="primary")
            ])
        ], id="panel-settings-modal", size="md", is_open=False, className="panel-settings-modal"),
        
        # Config Panel Modal (for panel-based chart configuration)
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("⚙️ Chart Configuration")),
            dbc.ModalBody([
                dcc.Store(id="current-config-panel", data=None),
                
                dbc.Label("Stock Symbol:", className="fw-bold"),
                dcc.Dropdown(
                    id="config-symbol-input",
                    placeholder="Type to search symbol or company name...",
                    options=[],
                    searchable=True,
                    clearable=True,
                    className="mb-3"
                ),
                
                dbc.Label("Timeframe:", className="fw-bold"),
                dcc.Dropdown(
                    id="config-timeframe-selector",
                    options=[
                        {'label': '1 Day (1min)', 'value': '1d_1m'},
                        {'label': '5 Days (5min)', 'value': '5d_5m'},
                        {'label': '1 Month', 'value': '1mo'},
                        {'label': '3 Months', 'value': '3mo'},
                        {'label': '6 Months', 'value': '6mo'},
                        {'label': '1 Year', 'value': '1y'},
                        {'label': '2 Years', 'value': '2y'},
                        {'label': '5 Years', 'value': '5y'}
                    ],
                    value='1mo',
                    clearable=False,
                    className="mb-3"
                ),
                
                dbc.Label("Chart Type:", className="fw-bold"),
                dcc.Dropdown(
                    id="config-chart-type-selector",
                    options=[
                        {'label': '📊 Candlestick', 'value': 'candlestick'},
                        {'label': '📈 Line Chart', 'value': 'line'}
                    ],
                    value='candlestick',
                    clearable=False,
                    className="mb-3"
                ),
                
                dbc.Checklist(
                    id="config-favorite-checkbox",
                    options=[{"label": " Mark as Favorite", "value": "favorite"}],
                    value=[],
                    switch=True
                )
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancel", id="config-cancel-btn", color="secondary", className="me-2"),
                dbc.Button("Apply", id="config-apply-btn", color="primary")
            ])
        ], id="config-panel-modal", size="md", is_open=False),
        
        # Trading Overlay Modal (Brackets / Breaks)
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("📌 Trading Overlays")),
            dbc.ModalBody([
                dbc.Tabs([
                    dbc.Tab(label="Brackets", tab_id="brackets", children=[
                        html.Div(id="overlay-brackets-container", className="overlay-group-container")
                    ]),
                    dbc.Tab(label="Breaks", tab_id="breaks", children=[
                        html.Div(id="overlay-breaks-container", className="overlay-group-container")
                    ])
                ], id="overlay-type-tabs", active_tab="brackets", className="overlay-tabs")
            ]),
            dbc.ModalFooter([
                dbc.Button("Close", id="overlay-modal-close-btn", color="secondary")
            ])
        ], id="trading-overlay-modal", size="lg", is_open=False, className="overlay-modal"),
        
        # Quad Mode Selection Modal
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("⊞ Select Charts for Quad View")),
            dbc.ModalBody([
                html.P("Select 4 charts to display in quad view:", className="mb-3"),
                html.Div(id="quad-mode-selectors")
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancel", id="quad-cancel-btn", color="secondary", className="me-2"),
                dbc.Button("Apply", id="quad-apply-btn", color="primary")
            ])
        ], id="quad-mode-modal", size="md", is_open=False)

    ], fluid=True)
