"""
Charts Tab - Live Market Data and Visualizations with Multi-Panel Support
"""

from dash import dcc, html
import dash_bootstrap_components as dbc

from src.gui.tabs.charts.market_data import MarketDataProvider
from src.gui.tabs.charts.live_charts import create_empty_chart, create_price_indicator_card
from src.gui.tabs.charts.live_charts import create_candlestick_chart, create_line_chart, create_multi_line_chart
from src.gui.tabs.charts.chart_data_manager import get_chart_data_manager
from typing import Optional, Tuple, Dict
import pandas as pd


# Initialize market data provider
market_data = MarketDataProvider()


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
        
        # Store for chart resize trigger (triggered when charts tab becomes active)
        dcc.Store(id='chart-resize-trigger', storage_type='memory', data={'resize': False}),
        
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


def get_market_indices_cards():
    """Get market indices as Bootstrap cards"""
    try:
        indices = market_data.get_market_indices()
        
        cards = []
        for symbol, data in indices.items():
            card_data = create_price_indicator_card(data)
            
            card = dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6(card_data['name'], className="mb-2"),
                        html.H4(card_data['price'], className=f"text-{card_data['color']} mb-1"),
                        html.Div([
                            html.Span(card_data['change'], className=f"text-{card_data['color']} me-2"),
                            html.Span(f"({card_data['change_percent']})", className=f"text-{card_data['color']}")
                        ])
                    ], className="text-center")
                ], className="h-100")
            ], md=3, sm=6, className="mb-2")
            
            cards.append(card)
        
        return dbc.Row(cards)
    
    except Exception as e:
        return html.Div(f"Error loading market indices: {str(e)}", className="text-danger")


def get_price_indicator(symbol: str):
    """Get price indicator card for a symbol"""
    try:
        quote = market_data.get_live_price(symbol)
        if not quote:
            return html.Div(f"Could not load data for {symbol}", className="text-warning")
        
        card_data = create_price_indicator_card(quote)
        
        return dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        html.H4(card_data['name'], className="mb-0"),
                        html.Small(card_data['symbol'], className="text-muted")
                    ], md=3),
                    dbc.Col([
                        html.H3(card_data['price'], className=f"text-{card_data['color']} mb-0"),
                        html.Div([
                            html.Span(card_data['change'], className=f"text-{card_data['color']} me-2"),
                            html.Span(f"({card_data['change_percent']})", className=f"text-{card_data['color']}")
                        ])
                    ], md=3),
                    dbc.Col([
                        html.Div([
                            html.Strong("High: "), card_data['high']
                        ], className="mb-1"),
                        html.Div([
                            html.Strong("Low: "), card_data['low']
                        ])
                    ], md=3),
                    dbc.Col([
                        html.Div([
                            html.Strong("Volume: "), card_data['volume']
                        ], className="mb-1"),
                        html.Div([
                            html.Strong("Market Cap: "), card_data['market_cap']
                        ])
                    ], md=3)
                ])
            ])
        ], className="mb-3")
    
    except Exception as e:
        return html.Div(f"Error loading price data: {str(e)}", className="text-danger")


def _build_stats_card(stats_data: dict):
    """Build a compact statistics card from stats data."""
    if not stats_data:
        return None

    return dbc.Card([
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.Span([stats_data['arrow'], f" {stats_data['symbol']} "], className="fw-bold me-2", style={"fontSize": "0.9rem"}),
                    html.Span(f"${stats_data['current_price']:.2f}", className=f"text-{stats_data['color']} fw-bold me-2", style={"fontSize": "0.9rem"}),
                    html.Span(
                        f"{stats_data['price_change']:+.2f} ({stats_data['price_change_pct']:+.2f}%)",
                        className=f"text-{stats_data['color']} me-3",
                        style={"fontSize": "0.75rem"}
                    ),
                ], width="auto", className="d-flex align-items-center"),
                dbc.Col([
                    html.Span(["H ", html.Strong(f"${stats_data['high']:.2f}")], className="me-2", style={"fontSize": "0.75rem"}),
                    html.Span(["L ", html.Strong(f"${stats_data['low']:.2f}")], className="me-2", style={"fontSize": "0.75rem"}),
                    html.Span(
                        ["Vol ", html.Strong(
                            f"{stats_data['volume']/1000000:.1f}M" if stats_data['volume'] > 1000000 else f"{stats_data['volume']/1000:.1f}K"
                        )],
                        style={"fontSize": "0.75rem"}
                    )
                ], width="auto", className="d-flex align-items-center")
            ], className="align-items-center justify-content-between")
        ], className="py-1 px-2")
    ], className="mb-1", style={"backgroundColor": "rgba(0,0,0,0.3)"})


def _build_overlay_shapes(overlays: dict):
    """Build plotly shapes for brackets/breaks overlays."""
    shapes = []
    if not overlays:
        return shapes

    def add_items(group: str, dash_style: str):
        items = overlays.get(group, []) or []
        for item in items:
            price = item.get('price')
            if price is None:
                continue
            try:
                price_value = float(price)
            except (TypeError, ValueError):
                continue
            color = item.get('color') or ("#00ff88" if group == "brackets" else "#ff4444")
            visible = item.get('visible', True)
            shapes.append({
                "type": "line",
                "xref": "paper",
                "x0": 0,
                "x1": 1,
                "yref": "y",
                "y0": price_value,
                "y1": price_value,
                "line": {"color": color, "width": 1.6, "dash": dash_style},
                "opacity": 0.9,
                "layer": "above",
                "visible": bool(visible)
            })

    add_items("brackets", "solid")
    add_items("breaks", "dot")
    return shapes


def _fetch_chart_data(symbol: str, timeframe: str, loaded_data: Optional[pd.DataFrame] = None) -> Optional[pd.DataFrame]:
    """
    Fetch chart data, using loaded_data if provided (for infinite scroll).
    
    Args:
        symbol: Stock ticker symbol
        timeframe: Chart timeframe
        loaded_data: Optional pre-loaded DataFrame
        
    Returns:
        DataFrame with OHLCV data or None if error
    """
    if loaded_data is not None and not loaded_data.empty:
        return loaded_data
    
    # Use ChartDataManager for initial load
    data_manager = get_chart_data_manager()
    df = data_manager.get_initial_data(symbol, timeframe)
    
    if df is None or df.empty:
        # Fallback to direct market_data call
        if timeframe == '1d_1m':
            df = market_data.get_intraday_data(symbol, days=1)
        elif timeframe == '5d_5m':
            df = market_data.get_historical_data(symbol, period='5d', interval='5m')
        else:
            df = market_data.get_historical_data(symbol, period=timeframe)
    
    return df


def _calculate_stats(df: pd.DataFrame, symbol: str) -> Optional[Dict]:
    """
    Calculate statistics from DataFrame.
    
    Args:
        df: DataFrame with OHLCV data
        symbol: Stock ticker symbol
        
    Returns:
        Dictionary with stats or None if error
    """
    if df is None or df.empty:
        return None
    
    try:
        current_price = df['Close'].iloc[-1]
        first_price = df['Close'].iloc[0]
        price_change = current_price - first_price
        price_change_pct = (price_change / first_price) * 100
        high = df['High'].max()
        low = df['Low'].min()
        volume = df['Volume'].iloc[-1] if 'Volume' in df.columns else 0

        color = "success" if price_change >= 0 else "danger"
        arrow = "🔼" if price_change >= 0 else "🔽"

        return {
            'symbol': symbol,
            'current_price': current_price,
            'price_change': price_change,
            'price_change_pct': price_change_pct,
            'high': high,
            'low': low,
            'volume': volume,
            'color': color,
            'arrow': arrow
        }
    except Exception as e:
        return None


def _build_chart_figure(
    df: pd.DataFrame,
    symbol: str,
    chart_type: str,
    show_volume: bool,
    show_ma: bool,
    overlays: Optional[dict],
    dragmode: str,
    auto_scroll: bool,
    view_state: Optional[dict]
) -> 'go.Figure':
    """
    Build Plotly figure from DataFrame.
    
    Args:
        df: DataFrame with OHLCV data
        symbol: Stock ticker symbol
        chart_type: Type of chart ('candlestick' or 'line')
        show_volume: Show volume subplot
        show_ma: Show moving averages
        overlays: Overlay shapes dict
        dragmode: Drag mode ('zoom' or 'pan')
        auto_scroll: Auto-scroll to latest data
        view_state: Saved view state dict
        
    Returns:
        Plotly Figure object
    """
    if chart_type == 'candlestick':
        fig = create_candlestick_chart(df, symbol, "", show_volume=show_volume, show_ma=show_ma)
    else:
        fig = create_line_chart(df, symbol)

    overlay_shapes = _build_overlay_shapes(overlays)
    if overlay_shapes:
        fig.update_layout(shapes=overlay_shapes)
    
    # Set dragmode (zoom or pan)
    # Note: 'pan' mode allows easier horizontal scrolling with mouse wheel
    fig.update_layout(dragmode=dragmode)
    
    # Enable horizontal scrolling: ensure x-axis is not fixed
    if show_volume:
        fig.update_xaxes(fixedrange=False, row=1)
        fig.update_xaxes(fixedrange=False, row=2)  # Volume subplot
    else:
        fig.update_xaxes(fixedrange=False)
    
    # Apply saved view state (zoom/pan position) if available
    # Only apply if auto_scroll is False (user wants to keep their view)
    if view_state and not auto_scroll:
        # Apply x-axis range if saved
        if 'xaxis_range' in view_state and view_state['xaxis_range']:
            fig.update_xaxes(range=view_state['xaxis_range'], row=1 if show_volume else None)
        
        # Apply y-axis range if saved (for price chart)
        if 'yaxis_range' in view_state and view_state['yaxis_range']:
            fig.update_yaxes(range=view_state['yaxis_range'], row=1 if show_volume else None)
        
        # Apply y-axis2 range if saved (for volume chart)
        if show_volume and 'yaxis2_range' in view_state and view_state['yaxis2_range']:
            fig.update_yaxes(range=view_state['yaxis2_range'], row=2)
    
    # Auto-scroll: Set x-axis range to show latest candles, with newest candle visible on the right
    elif auto_scroll and len(df) > 0:
        # Show last 50-100 candles (adjust based on data density)
        visible_candles = min(80, len(df))
        start_idx = max(0, len(df) - visible_candles)
        
        # For category type axes, we need to use the index positions
        # Since we're using category type, we'll set the range using index values
        if hasattr(df.index, '__len__'):
            # Convert to list if needed
            indices = list(df.index) if not isinstance(df.index, list) else df.index
            if start_idx < len(indices):
                # Set range to show last N candles
                # For category axes, range is set using the category values
                start_val = indices[start_idx] if start_idx < len(indices) else indices[0]
                end_val = indices[-1] if len(indices) > 0 else None
                
                if end_val is not None:
                    # Update xaxis range - for category type, use the actual index values
                    fig.update_xaxes(range=[start_val, end_val], row=1 if show_volume else None)
    
    return fig


def update_chart_with_prepended_data(
    existing_fig: 'go.Figure',
    new_df: pd.DataFrame,
    old_df: pd.DataFrame,
    old_range: Optional[list],
    show_volume: bool
) -> Tuple['go.Figure', list]:
    """
    Update chart figure with prepended data while maintaining view position.
    
    Args:
        existing_fig: Existing Plotly figure
        new_df: New DataFrame to prepend
        old_df: Old DataFrame
        old_range: Old x-axis range [left_val, right_val]
        show_volume: Whether volume subplot is shown
        
    Returns:
        Tuple of (updated_figure, new_range)
    """
    from plotly.graph_objects import Figure
    
    # Calculate offset (how many new data points were added)
    offset = len(new_df)
    
    # If we have old range, calculate new range
    new_range = old_range
    if old_range and len(old_df) > 0:
        # Find indices of old range values in old DataFrame
        old_indices = list(old_df.index)
        try:
            left_idx = old_indices.index(old_range[0]) if old_range[0] in old_indices else 0
            right_idx = old_indices.index(old_range[1]) if old_range[1] in old_indices else len(old_indices) - 1
            
            # Calculate new indices with offset
            new_left_idx = left_idx + offset
            new_right_idx = right_idx + offset
            
            # Get new DataFrame with prepended data
            combined_df = pd.concat([new_df, old_df])
            combined_df = combined_df[~combined_df.index.duplicated(keep='last')]
            combined_df = combined_df.sort_index()
            
            # Get new range values
            new_indices = list(combined_df.index)
            if new_left_idx < len(new_indices) and new_right_idx < len(new_indices):
                new_range = [new_indices[new_left_idx], new_indices[new_right_idx]]
        except (ValueError, IndexError):
            # Fallback: use original range if calculation fails
            pass
    
    # Update figure with new data (this will be done by recreating traces)
    # For now, return the existing figure - actual update happens in callback
    return existing_fig, new_range or []


def get_stock_chart_components(
    symbol: str,
    timeframe: str = '1mo',
    chart_type: str = 'candlestick',
    show_volume: bool = True,
    show_ma: bool = False,
    overlays: Optional[dict] = None,
    graph_id: Optional[dict] = None,
    dragmode: str = 'zoom',
    auto_scroll: bool = False,
    view_state: Optional[dict] = None,
    loaded_data: Optional[pd.DataFrame] = None
) -> Tuple[dcc.Graph, Optional[Dict]]:
    """
    Get chart graph component and stats data.
    
    Args:
        symbol: Stock ticker symbol
        timeframe: Chart timeframe
        chart_type: Type of chart ('candlestick' or 'line')
        show_volume: Show volume subplot
        show_ma: Show moving averages
        overlays: Overlay shapes dict
        graph_id: Graph component ID
        dragmode: Drag mode ('zoom' or 'pan')
        auto_scroll: Auto-scroll to latest data
        view_state: Saved view state dict
        loaded_data: Optional pre-loaded DataFrame (for infinite scroll)
        
    Returns:
        Tuple of (chart_graph_component, stats_data_dict)
    """
    try:
        # Fetch data
        df = _fetch_chart_data(symbol, timeframe, loaded_data)
        
        if df is None or df.empty:
            return dbc.Alert(f"No data available for {symbol}", color="warning"), None

        # Calculate stats
        stats_data = _calculate_stats(df, symbol)
        if stats_data is None:
            return dbc.Alert(f"Error calculating stats for {symbol}", color="warning"), None

        # Get last update time from cache metadata
        last_update_time = None
        try:
            data_manager = get_chart_data_manager()
            cache_metadata = data_manager.get_cache_metadata(symbol, timeframe)
            if cache_metadata and cache_metadata.get('loaded_at'):
                last_update_time = cache_metadata['loaded_at']
        except Exception as e:
            import logging
            logging.getLogger(__name__).debug(f"Could not get last update time: {e}")

        # Build figure
        fig = _build_chart_figure(
            df, symbol, chart_type, show_volume, show_ma,
            overlays, dragmode, auto_scroll, view_state
        )

        graph_props = dict(
            figure=fig,
            style={'height': '100%', 'width': '100%', 'flex': '1 1 auto'},
            config={
                'responsive': True,
                'displayModeBar': True,
                'displaylogo': False,
                'editable': True,
                'edits': {'shapePosition': True},
                'modeBarButtonsToRemove': ['lasso2d', 'select2d'],  # Keep pan2d enabled
                'toImageButtonOptions': {'format': 'png', 'filename': f'{symbol}_chart'},
                'scrollZoom': True,  # Enable Ctrl+Wheel zoom, Shift+Wheel horizontal pan
                'doubleClick': 'reset',  # Double click to reset zoom
            },
            className='flex-grow-1'
        )
        if graph_id is not None:
            graph_props["id"] = graph_id

        chart_graph = dcc.Graph(**graph_props)
        
        # Wrap in div with data-last-update attribute for JavaScript access
        # JavaScript will check both the graph element and its parent for this attribute
        if last_update_time is not None:
            # Convert datetime to ISO format string
            if hasattr(last_update_time, 'isoformat'):
                last_update_str = last_update_time.isoformat()
            elif isinstance(last_update_time, str):
                last_update_str = last_update_time
            else:
                from datetime import datetime
                last_update_str = datetime.fromtimestamp(last_update_time).isoformat() if isinstance(last_update_time, (int, float)) else str(last_update_time)
            
            # Wrap graph in div with data attribute
            # The Graph component will still have its ID, and JavaScript can access the data attribute from parent
            chart_graph = html.Div(
                chart_graph,
                **{'data-last-update': last_update_str}
            )

        return chart_graph, stats_data

    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error creating chart: {e}", exc_info=True)
        return dbc.Alert(f"Error creating chart: {str(e)}", color="danger"), None


def get_stock_chart_with_stats(
    symbol: str,
    timeframe: str = '1mo',
    chart_type: str = 'candlestick',
    show_volume: bool = True,
    show_ma: bool = False,
    show_stats: bool = True,
    render_stats_card: bool = True
):
    """Get stock chart with optional statistics card."""
    chart_component, stats_data = get_stock_chart_components(
        symbol,
        timeframe,
        chart_type,
        show_volume=show_volume,
        show_ma=show_ma
    )
    if stats_data is None:
        return chart_component

    stats_card = _build_stats_card(stats_data) if show_stats and render_stats_card else None
    children = [stats_card, chart_component] if stats_card else [chart_component]
    return html.Div(children, style={'height': '100%', 'display': 'flex', 'flexDirection': 'column'})





def get_comparison_chart(symbols: list, timeframe: str = '3mo'):
    """Get comparison chart for multiple symbols"""
    try:
        if not symbols or len(symbols) == 0:
            return dcc.Graph(figure=create_empty_chart("Enter symbols to compare"))
        
        data_dict = {}
        for symbol in symbols:
            df = market_data.get_historical_data(symbol.strip().upper(), period=timeframe)
            if df is not None and not df.empty:
                # Normalize to percentage change
                df['Close'] = (df['Close'] / df['Close'].iloc[0] - 1) * 100
                data_dict[symbol.strip().upper()] = df
        
        if not data_dict:
            return dcc.Graph(figure=create_empty_chart("No data available for comparison"))
        
        fig = create_multi_line_chart(data_dict, "Stock Performance Comparison (% Change)")
        fig.update_yaxes(title="% Change from Start")
        
        return dcc.Graph(figure=fig)
    
    except Exception as e:
        return html.Div(f"Error creating comparison: {str(e)}", className="text-danger")


def create_trading_overlay(stats_data: dict = None, show_stats: bool = True, panel_id: str = None):
    """Create trading action overlay for chart panels."""
    if not show_stats:
        return None

    stats_block = None
    if show_stats and stats_data:
        stats_block = html.Div([
            html.Div([
                html.Span([stats_data['arrow'], f" {stats_data['symbol']}"], className="fw-bold"),
                html.Span(f"${stats_data['current_price']:.2f}", className=f"text-{stats_data['color']} fw-bold")
            ], style={
                'display': 'flex',
                'flexWrap': 'wrap',
                'gap': '4px',
                'alignItems': 'baseline',
                'fontSize': '0.72rem',
                'lineHeight': '1.1'
            }),
            html.Div(
                f"{stats_data['price_change']:+.2f} ({stats_data['price_change_pct']:+.2f}%)",
                className=f"text-{stats_data['color']}",
                style={'fontSize': '0.68rem', 'lineHeight': '1.1'}
            )
        ], style={'display': 'flex', 'flexDirection': 'column', 'gap': '2px', 'minWidth': '0', 'flex': '1 1 auto'})

    settings_button = None
    if panel_id:
        settings_button = dbc.Button(
            html.I(className="fas fa-cog"),
            id={"type": "panel-settings-btn", "index": panel_id},
            color="dark",
            size="sm",
            className="p-0",
            outline=True,
            style={
                'width': '24px',
                'height': '22px',
                'lineHeight': '1',
                'display': 'flex',
                'alignItems': 'center',
                'justifyContent': 'center',
                'backgroundColor': '#111',
                'border': '1px solid #333'
            },
            title="Chart Settings"
        )

    overlay_children = []
    overlay_children.append(html.Div(
        [stats_block or html.Div(), settings_button] if settings_button else [stats_block or html.Div()],
        style={
            'display': 'flex',
            'justifyContent': 'space-between',
            'alignItems': 'flex-start',
            'gap': '6px',
            'marginBottom': '6px'
        }
    ))
    manage_button = None
    if panel_id:
        manage_button = dbc.Button(
            [html.I(className="fas fa-layer-group"), " Brackets/Breaks"],
            id={"type": "overlay-manage-btn", "index": panel_id},
            color="info",
            size="sm",
            outline=True,
            className="overlay-manage-btn"
        )
    
    overlay_children.extend([
        html.Div(
            [manage_button] if manage_button else [],
            className="overlay-manage-row"
        ),
        html.Div([
            dbc.Button("Buy", color="success", size="sm", outline=True, className="overlay-action-btn"),
            dbc.Button("Sell", color="danger", size="sm", outline=True, className="overlay-action-btn")
        ], className="overlay-action-row")
    ])

    return html.Div(overlay_children, className="trading-overlay", style={
        'position': 'absolute',
        'top': '10px',
        'left': '10px',
        'zIndex': '1500',
        'backgroundColor': '#000',
        'opacity': '1',
        'border': '1px solid #333',
        'padding': '6px',
        'borderRadius': '5px',
        'width': '175px',
        'minHeight': '0',
        'color': '#e8e8e8',
        'display': 'flex',
        'flexDirection': 'column',
        'gap': '4px'
    })


def create_chart_panel(panel_id: str, config: dict, show_controls: bool = True, overlays: dict = None, view_state: dict = None, loaded_data: Optional[pd.DataFrame] = None):
    """Create a single chart panel with controls and a trading action overlay."""
    # Handle None config
    if not config:
        config = {}
    
    # Extract configuration with sensible defaults
    symbol = config.get('symbol', 'AAPL')
    timeframe = config.get('timeframe', '1mo')
    chart_type = config.get('chart_type', 'candlestick')
    is_favorite = config.get('favorite', False)

    # Extract chart-specific options from the config
    show_volume = config.get('show_volume', True)
    show_ma = config.get('show_ma', False)
    show_stats = config.get('show_stats', True)

    # Panel header with controls
    header_content = [
        dbc.Row([
            dbc.Col([
                html.Span(
                    f"{'⭐ ' if is_favorite else ''}{symbol}",
                    id={"type": "symbol-label", "index": panel_id},
                    className="fw-bold symbol-clickable",
                    style={'cursor': 'pointer', 'textDecoration': 'underline dotted', 'textUnderlineOffset': '3px'}
                )
            ], width=8),
            dbc.Col([
                dbc.ButtonGroup([
                    dbc.Button("⚙️", id={"type": "config-btn", "index": panel_id}, color="link", size="sm", className="text-light p-0"),
                    dbc.Button("🔄", id={"type": "refresh-btn", "index": panel_id}, color="link", size="sm", className="text-light p-0"),
                    dbc.Button("⭐" if not is_favorite else "★", id={"type": "favorite-btn", "index": panel_id}, color="link", size="sm", className="text-warning p-0")
                ], size="sm")
            ], width=4, className="text-end")
        ])
    ] if show_controls else [html.H6(f"{symbol}", className="mb-0")]

    # Get chart content and stats for overlay
    overlay_payload = overlays if show_stats else {}
    
    # Get interaction mode for this panel (default: zoom)
    # This will be set by callbacks in app.py
    interaction_mode = config.get('dragmode', 'zoom')
    auto_scroll_enabled = config.get('auto_scroll', False)
    
    chart_component, stats_data = get_stock_chart_components(
        symbol,
        timeframe,
        chart_type,
        show_volume,
        show_ma,
        overlays=overlay_payload,
        graph_id={"type": "chart-graph", "index": panel_id},
        dragmode=interaction_mode,
        auto_scroll=auto_scroll_enabled,
        view_state=view_state,
        loaded_data=loaded_data  # NEW: Pass loaded data for infinite scroll
    )
    chart_content = chart_component
    trading_overlay = create_trading_overlay(stats_data, show_stats, panel_id=panel_id) if show_stats else None

    return dbc.Card([
        dbc.CardHeader(header_content, className="py-1", style={'padding': '4px 12px', 'minHeight': '32px', 'maxHeight': '32px'}) if show_controls else None,
        dbc.CardBody(
            ([trading_overlay] if trading_overlay else []) + [
                dcc.Loading(
                    id={"type": "loading-panel", "index": panel_id},
                    type="default",
                    children=html.Div(
                        chart_content,
                        id={"type": "chart-content", "index": panel_id},
                        style={
                            'height': '100%',
                            'width': '100%',
                            'overflow': 'hidden',
                            'display': 'flex',
                            'flexDirection': 'column'
                        }
                    )
                )
            ],
        className="p-1",
        style={ # ADDED position: relative HERE
            'position': 'relative',
            'height': 'calc(100% - 32px)',
            'overflow': 'hidden'
        })
    ], className="h-100", style={'height': '100%', 'overflow': 'hidden'})


def render_multi_panel_layout(layout: str, panels_config: dict, fullscreen: bool = False, overlays_data: dict = None, view_state_data: dict = None, loaded_data_store: dict = None):
    """Render the multi-panel layout based on selected mode"""
    
    def get_panel_overlays(panel_id: str):
        return (overlays_data or {}).get('tabs', {}).get(panel_id, {})
    
    def get_panel_view_state(panel_id: str):
        return (view_state_data or {}).get('tabs', {}).get(panel_id) if view_state_data else None
    
    def get_panel_loaded_data(panel_id: str):
        """Get loaded data for a panel from cache."""
        if not loaded_data_store or not loaded_data_store.get('tabs'):
            return None
        
        tab_loaded = loaded_data_store.get('tabs', {}).get(panel_id)
        if not tab_loaded:
            return None
        
        # Get cached data from ChartDataManager
        data_manager = get_chart_data_manager()
        symbol = tab_loaded.get('symbol')
        timeframe = tab_loaded.get('timeframe')
        
        if symbol and timeframe:
            return data_manager.get_cached_data(symbol, timeframe)
        
        return None
    
    # Handle empty panels_config
    if not panels_config:
        panels_config = {}
    
    # Determine panel height based on fullscreen and layout
    if fullscreen:
        if layout == 'quad':
            # Aggressive: Use almost all space - 60px for control bar, 20px for margins/gaps, divide by 2
            panel_height = 'calc((100vh - 80px) / 2)'
        elif layout in ['split-vertical']:
            # Aggressive: Use almost all space - 60px for control bar, 20px for gap, divide by 2
            panel_height = 'calc((100vh - 80px) / 2)'
        else:
            # Single panel: use almost all height
            panel_height = 'calc(100vh - 70px)'
    else:
        if layout == 'quad':
            panel_height = '450px'
        elif layout in ['split-vertical', 'split-horizontal']:
            panel_height = '500px'
        else:
            panel_height = '600px'
    
    panel_style = {
        'height': panel_height, 
        'minHeight': '200px',
        'maxHeight': panel_height,
        'overflow': 'hidden'
    }
    
    # Fullscreen control bar (only shown in fullscreen mode)
    fullscreen_controls = None
    if fullscreen:
        fullscreen_controls = dbc.Card([
            dbc.CardBody([
                dbc.Row([
                    dbc.Col([
                        dbc.Label("📐 Layout Mode:", className="fw-bold me-2"),
                        dbc.ButtonGroup([
                            dbc.Button("Single", id="layout-single", color="primary", size="sm", outline=True),
                            dbc.Button("Split ↔", id="layout-split-h", color="primary", size="sm", outline=True),
                            dbc.Button("Split ↕", id="layout-split-v", color="primary", size="sm", outline=True),
                            dbc.Button("Quad ⊞", id="layout-quad", color="primary", size="sm", outline=True)
                        ], className="me-3")
                    ], md=6),
                    dbc.Col([
                        dbc.Button("🔄 Refresh All", id="refresh-all-panels", color="success", size="sm", className="me-2"),
                        dbc.Button("⭐ Manage Favorites", id="show-favorites-modal", color="warning", size="sm", className="me-2")
                        # Exit button is now in main layout, controlled by visibility callback
                    ], md=6, className="text-end")
                ])
            ], className="py-1 px-2", style={'padding': '3px 8px'})
        ], className="mb-1", style={'marginBottom': '5px'})
    
    # Build layout content
    layout_content = None
    if layout == 'single':
        # Single large panel
        panel_config = panels_config.get('panel-1', {})
        if not panel_config or not panel_config.get('symbol'):
            layout_content = dbc.Alert("No chart configured. Click ⚙️ to configure a chart.", color="info", className="mt-3")
        else:
            layout_content = dbc.Row([
                dbc.Col([
                    html.Div(
                        create_chart_panel('panel-1', panel_config, overlays=get_panel_overlays('panel-1'), view_state=get_panel_view_state('panel-1'), loaded_data=get_panel_loaded_data('panel-1')),
                        style=panel_style
                    )
                ], width=12)
            ])
    
    elif layout == 'split-horizontal':
        # Two panels side by side
        margin_class = "mb-1" if fullscreen else "mb-3"
        gutter_class = "g-1" if fullscreen else "g-3"
        layout_content = dbc.Row([
            dbc.Col([
                html.Div(
                    create_chart_panel('panel-1', panels_config.get('panel-1', {}), overlays=get_panel_overlays('panel-1'), view_state=get_panel_view_state('panel-1'), loaded_data=get_panel_loaded_data('panel-1')),
                    style=panel_style
                )
            ], md=6, className=margin_class),
            dbc.Col([
                html.Div(
                    create_chart_panel('panel-2', panels_config.get('panel-2', {}), overlays=get_panel_overlays('panel-2'), view_state=get_panel_view_state('panel-2'), loaded_data=get_panel_loaded_data('panel-2')),
                    style=panel_style
                )
            ], md=6, className=margin_class)
        ], className=gutter_class)
    
    elif layout == 'split-vertical':
        # Two panels stacked vertically
        margin_class = "mb-1" if fullscreen else "mb-3"
        layout_content = html.Div([
            dbc.Row([
                dbc.Col([
                    html.Div(
                    create_chart_panel('panel-1', panels_config.get('panel-1', {}), overlays=get_panel_overlays('panel-1'), view_state=get_panel_view_state('panel-1'), loaded_data=get_panel_loaded_data('panel-1')),
                        style=panel_style
                    )
                ], width=12, className=margin_class)
            ], className="gx-1" if fullscreen else "gx-3"),
            dbc.Row([
                dbc.Col([
                    html.Div(
                    create_chart_panel('panel-2', panels_config.get('panel-2', {}), overlays=get_panel_overlays('panel-2'), view_state=get_panel_view_state('panel-2'), loaded_data=get_panel_loaded_data('panel-2')),
                        style=panel_style
                    )
                ], width=12)
            ], className="gx-1" if fullscreen else "gx-3")
        ])
    
    elif layout == 'quad':
        # Four panels in a 2x2 grid
        margin_class = "mb-1" if fullscreen else "mb-3"
        gutter_class = "g-1" if fullscreen else "g-3"
        layout_content = html.Div([
            dbc.Row([
                dbc.Col([
                    html.Div(
                    create_chart_panel('panel-1', panels_config.get('panel-1', {}), overlays=get_panel_overlays('panel-1'), view_state=get_panel_view_state('panel-1'), loaded_data=get_panel_loaded_data('panel-1')),
                        style=panel_style
                    )
                ], md=6, className=margin_class),
                dbc.Col([
                    html.Div(
                    create_chart_panel('panel-2', panels_config.get('panel-2', {}), overlays=get_panel_overlays('panel-2'), view_state=get_panel_view_state('panel-2'), loaded_data=get_panel_loaded_data('panel-2')),
                        style=panel_style
                    )
                ], md=6, className=margin_class)
            ], className=gutter_class),
            dbc.Row([
                dbc.Col([
                    html.Div(
                    create_chart_panel('panel-3', panels_config.get('panel-3', {}), overlays=get_panel_overlays('panel-3'), view_state=get_panel_view_state('panel-3'), loaded_data=get_panel_loaded_data('panel-3')),
                        style=panel_style
                    )
                ], md=6),
                dbc.Col([
                    html.Div(
                    create_chart_panel('panel-4', panels_config.get('panel-4', {}), overlays=get_panel_overlays('panel-4'), view_state=get_panel_view_state('panel-4'), loaded_data=get_panel_loaded_data('panel-4')),
                        style=panel_style
                    )
                ], md=6)
            ], className=gutter_class)
        ])
    
    else:
        layout_content = html.Div("Invalid layout mode", className="text-danger")
    
    # Return with or without fullscreen controls
    if fullscreen:
        return html.Div([
            fullscreen_controls,
            layout_content
        ])
    else:
        return layout_content
