"""
Charts Tab - Live Market Data and Visualizations with Multi-Panel Support
"""

from dash import dcc, html
import dash_bootstrap_components as dbc

from src.gui.charts import MarketDataProvider, create_empty_chart, create_price_indicator_card
from src.gui.charts.live_charts import create_candlestick_chart, create_line_chart, create_multi_line_chart


# Initialize market data provider
market_data = MarketDataProvider()


def create_layout():
    """Create charts tab layout with modern tab-based interface"""
    return dbc.Container([
        # Auto-refresh interval - reduced for better performance
        dcc.Interval(id='chart-update-interval', interval=60000, n_intervals=0, disabled=True),  # 60 seconds, disabled by default
        
        # Store for open chart tabs
        dcc.Store(id='chart-tabs-store', storage_type='local', data={
            'tabs': [
                {'id': 'tab-1', 'symbol': 'AAPL', 'timeframe': '1mo', 'chart_type': 'candlestick', 'show_volume': True, 'show_ma': False},
                {'id': 'tab-2', 'symbol': 'MSFT', 'timeframe': '1mo', 'chart_type': 'candlestick', 'show_volume': True, 'show_ma': False},
                {'id': 'tab-3', 'symbol': 'GOOGL', 'timeframe': '1mo', 'chart_type': 'candlestick', 'show_volume': True, 'show_ma': False},
            ],
            'active_tab': 'tab-1'
        }),
        
        # Store for quad mode selection
        dcc.Store(id='quad-mode-store', storage_type='session', data={
            'enabled': False,
            'selected_tabs': ['tab-1', 'tab-2', 'tab-3', 'tab-1']  # 4 tabs for quad panels
        }),
        
        # Store for fullscreen state
        dcc.Store(id='chart-fullscreen-state', storage_type='session', data={'fullscreen': False}),
        
        # Store for panel sizes (for resizable layouts)
        dcc.Store(id='panel-sizes-store', storage_type='session', data={'sizes': [50, 50]}),  # percentage widths
        
        # ESC key listener for fullscreen
        dcc.Input(id='esc-key-listener', type='text', style={'display': 'none'}),
        
        # Browser-style Tab Bar
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            # Tab buttons container
                            html.Div(id='chart-tab-buttons', className='d-inline-flex flex-wrap align-items-center gap-1'),
                            # Add new tab button
                            dbc.Button([html.I(className="fas fa-plus"), " New"],
                                      id="add-chart-tab-btn",
                                      color="success",
                                      size="sm",
                                      outline=True,
                                      className="ms-2")
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
                                dbc.Button("🔄", id="refresh-all-panels", color="success", size="sm", className="me-2", title="Refresh Charts (Ctrl+R)"),
                                dbc.Button("⛶", id="toggle-fullscreen-btn", color="info", size="sm", outline=True, title="Toggle Fullscreen (ESC to exit)")
                            ], md=2, className="text-end")
                        ], className="align-items-center")
                    ], className="py-2 px-3")
                ], className="mb-2")
            ], width=12)
        ]),
        
        # Chart Display Area with fullscreen support
        html.Div(id='chart-display-area', className='chart-container-normal'),
        
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


def get_stock_chart_components(symbol: str, timeframe: str = '1mo', chart_type: str = 'candlestick', show_volume: bool = True, show_ma: bool = False):
    """Get chart graph component and stats data."""
    try:
        if timeframe == '1d_1m':
            df = market_data.get_intraday_data(symbol, days=1)
        elif timeframe == '5d_5m':
            df = market_data.get_historical_data(symbol, period='5d', interval='5m')
        else:
            df = market_data.get_historical_data(symbol, period=timeframe)

        if df is None or df.empty:
            return dbc.Alert(f"No data available for {symbol}", color="warning"), None

        current_price = df['Close'].iloc[-1]
        first_price = df['Close'].iloc[0]
        price_change = current_price - first_price
        price_change_pct = (price_change / first_price) * 100
        high = df['High'].max()
        low = df['Low'].min()
        volume = df['Volume'].iloc[-1] if 'Volume' in df.columns else 0

        color = "success" if price_change >= 0 else "danger"
        arrow = "🔼" if price_change >= 0 else "🔽"

        stats_data = {
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

        if chart_type == 'candlestick':
            fig = create_candlestick_chart(df, symbol, "", show_volume=show_volume, show_ma=show_ma)
        else:
            fig = create_line_chart(df, symbol)

        chart_graph = dcc.Graph(
            figure=fig,
            style={'height': '100%', 'width': '100%', 'flex': '1 1 auto'},
            config={
                'responsive': True,
                'displayModeBar': True,
                'displaylogo': False,
                'modeBarButtonsToRemove': ['pan2d', 'lasso2d', 'select2d'],
                'toImageButtonOptions': {'format': 'png', 'filename': f'{symbol}_chart'}
            },
            className='flex-grow-1'
        )

        return chart_graph, stats_data

    except Exception as e:
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
    overlay_children.extend([
        html.Div([
            dbc.Input(
                type="text",
                placeholder="Brackets",
                size="sm",
                style={
                    'flex': '1 1 0',
                    'minWidth': '0',
                    'height': '24px',
                    'fontSize': '0.7rem',
                    'backgroundColor': '#111',
                    'color': '#e8e8e8',
                    'border': '1px solid #333'
                }
            ),
            dbc.Input(
                type="text",
                placeholder="Breaks",
                size="sm",
                style={
                    'flex': '1 1 0',
                    'minWidth': '0',
                    'height': '24px',
                    'fontSize': '0.7rem',
                    'backgroundColor': '#111',
                    'color': '#e8e8e8',
                    'border': '1px solid #333'
                }
            )
        ], style={'display': 'flex', 'gap': '6px', 'marginBottom': '6px'}),
        html.Div([
            dbc.Button("Buy", color="success", size="sm", outline=True, style={'flex': '1 1 0', 'height': '24px', 'padding': '0'}),
            dbc.Button("Sell", color="danger", size="sm", outline=True, style={'flex': '1 1 0', 'height': '24px', 'padding': '0'})
        ], style={'display': 'flex', 'gap': '6px'})
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
        'width': '160px',
        'minHeight': '0',
        'color': '#e8e8e8',
        'display': 'flex',
        'flexDirection': 'column',
        'gap': '4px'
    })


def create_chart_panel(panel_id: str, config: dict, show_controls: bool = True):
    """Create a single chart panel with controls and a trading action overlay."""
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
    chart_component, stats_data = get_stock_chart_components(symbol, timeframe, chart_type, show_volume, show_ma)
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


def render_multi_panel_layout(layout: str, panels_config: dict, fullscreen: bool = False):
    """Render the multi-panel layout based on selected mode"""
    
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
                        dbc.Button("⭐ Manage Favorites", id="show-favorites-modal", color="warning", size="sm", className="me-2"),
                        dbc.Button("⬇ Exit Fullscreen", id="toggle-fullscreen-btn", color="danger", size="sm")
                    ], md=6, className="text-end")
                ])
            ], className="py-1 px-2", style={'padding': '3px 8px'})
        ], className="mb-1", style={'marginBottom': '5px'})
    
    # Build layout content
    layout_content = None
    if layout == 'single':
        # Single large panel
        layout_content = dbc.Row([
            dbc.Col([
                html.Div(
                    create_chart_panel('panel-1', panels_config.get('panel-1', {})),
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
                    create_chart_panel('panel-1', panels_config.get('panel-1', {})),
                    style=panel_style
                )
            ], md=6, className=margin_class),
            dbc.Col([
                html.Div(
                    create_chart_panel('panel-2', panels_config.get('panel-2', {})),
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
                        create_chart_panel('panel-1', panels_config.get('panel-1', {})),
                        style=panel_style
                    )
                ], width=12, className=margin_class)
            ], className="gx-1" if fullscreen else "gx-3"),
            dbc.Row([
                dbc.Col([
                    html.Div(
                        create_chart_panel('panel-2', panels_config.get('panel-2', {})),
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
                        create_chart_panel('panel-1', panels_config.get('panel-1', {})),
                        style=panel_style
                    )
                ], md=6, className=margin_class),
                dbc.Col([
                    html.Div(
                        create_chart_panel('panel-2', panels_config.get('panel-2', {})),
                        style=panel_style
                    )
                ], md=6, className=margin_class)
            ], className=gutter_class),
            dbc.Row([
                dbc.Col([
                    html.Div(
                        create_chart_panel('panel-3', panels_config.get('panel-3', {})),
                        style=panel_style
                    )
                ], md=6),
                dbc.Col([
                    html.Div(
                        create_chart_panel('panel-4', panels_config.get('panel-4', {})),
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
