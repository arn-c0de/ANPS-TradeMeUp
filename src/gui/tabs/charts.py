"""
Charts Tab - Live Market Data and Visualizations with Multi-Panel Support
"""

from dash import dcc, html
import dash_bootstrap_components as dbc
from src.gui.charts import MarketDataProvider, create_candlestick_chart, create_empty_chart, create_price_indicator_card


# Initialize market data provider
market_data = MarketDataProvider()


def create_layout():
    """Create charts tab layout with multi-panel support"""
    return dbc.Container([
        # Auto-refresh interval
        dcc.Interval(id='chart-update-interval', interval=30000, n_intervals=0),  # 30 seconds
        
        # Store for chart panels configuration (persisted in browser)
        dcc.Store(id='chart-panels-config', storage_type='local', data={
            'layout': 'single',  # single, split-vertical, split-horizontal, quad
            'panels': {
                'panel-1': {'symbol': 'AAPL', 'timeframe': '1mo', 'chart_type': 'candlestick', 'favorite': False},
                'panel-2': {'symbol': 'MSFT', 'timeframe': '1mo', 'chart_type': 'candlestick', 'favorite': False},
                'panel-3': {'symbol': 'GOOGL', 'timeframe': '1mo', 'chart_type': 'candlestick', 'favorite': False},
                'panel-4': {'symbol': 'TSLA', 'timeframe': '1mo', 'chart_type': 'candlestick', 'favorite': False}
            }
        }),
        
        # Store for fullscreen state
        dcc.Store(id='chart-fullscreen-state', storage_type='session', data={'fullscreen': False}),
        
        # Market Overview Header (collapsible)
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        dbc.Row([
                            dbc.Col(html.H5("📊 Live Market Overview", className="mb-0"), width=10),
                            dbc.Col([
                                dbc.Button("▼", id="toggle-market-overview", color="link", size="sm", className="text-light")
                            ], width=2, className="text-end")
                        ])
                    ]),
                    dbc.Collapse([
                        dbc.CardBody([
                            html.Div(id='market-indices-display')
                        ])
                    ], id="market-overview-collapse", is_open=False)
                ], className="mb-3")
            ], width=12)
        ]),
        
        # Layout Control Bar
        dbc.Row([
            dbc.Col([
                dbc.Card([
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
                                dbc.Button("⛶ Fullscreen", id="toggle-fullscreen-btn", color="info", size="sm", outline=True)
                            ], md=6, className="text-end")
                        ])
                    ])
                ], className="mb-3")
            ], width=12)
        ]),
        
        # Multi-Panel Chart Area with fullscreen support
        html.Div(id='multi-panel-chart-area', className='chart-container-normal'),
        
        # Panel Configuration Modal
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("⚙️ Configure Chart Panel")),
            dbc.ModalBody([
                dbc.Label("Panel:", className="fw-bold"),
                dcc.Dropdown(id="config-panel-selector", className="mb-3"),
                
                dbc.Label("Stock Symbol:", className="fw-bold"),
                dbc.Input(
                    id="config-symbol-input",
                    placeholder="e.g., AAPL, TSLA, NVDA",
                    type="text",
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
                    clearable=False,
                    className="mb-3"
                ),
                
                dbc.Checkbox(
                    id="config-favorite-checkbox",
                    label="⭐ Mark as Favorite",
                    className="mb-3"
                )
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancel", id="config-cancel-btn", color="secondary", className="me-2"),
                dbc.Button("Apply", id="config-apply-btn", color="primary")
            ])
        ], id="config-panel-modal", size="lg", is_open=False),
        
        # Favorites Modal
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("⭐ Favorite Symbols")),
            dbc.ModalBody([
                html.Div(id="favorites-list")
            ]),
            dbc.ModalFooter([
                dbc.Button("Close", id="favorites-close-btn", color="primary")
            ])
        ], id="favorites-modal", size="lg", is_open=False),
        
        # Quick Symbol Edit Modal
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("🔍 Change Symbol")),
            dbc.ModalBody([
                dbc.Label("Enter new stock symbol:", className="fw-bold mb-2"),
                dbc.Input(
                    id="quick-edit-symbol-input",
                    placeholder="e.g., AAPL, TSLA, MSFT",
                    type="text",
                    className="mb-3",
                    debounce=True
                ),
                html.Div(id="symbol-search-results", className="mt-2"),
                dbc.Alert(
                    "💡 Tip: Start typing to search for symbols. Press Enter or click Apply to update.",
                    color="info",
                    className="mt-3"
                )
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancel", id="quick-edit-cancel-btn", color="secondary", className="me-2"),
                dbc.Button("Apply", id="quick-edit-apply-btn", color="primary")
            ])
        ], id="quick-edit-modal", size="md", is_open=False),
        
        # Hidden divs to store state
        html.Div(id="current-config-panel", style={'display': 'none'}),
        html.Div(id="current-quick-edit-panel", style={'display': 'none'}),
        dcc.Store(id="symbol-search-cache", data=[])

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


def get_stock_chart(symbol: str, timeframe: str = '1mo', chart_type: str = 'candlestick'):
    """Get stock chart based on parameters"""
    try:
        # Parse timeframe
        if timeframe == '1d_1m':
            df = market_data.get_intraday_data(symbol, days=1)
            title = f"{symbol} - 1 Day (1 Minute Intervals)"
        elif timeframe == '5d_5m':
            df = market_data.get_historical_data(symbol, period='5d', interval='5m')
            title = f"{symbol} - 5 Days (5 Minute Intervals)"
        else:
            df = market_data.get_historical_data(symbol, period=timeframe)
            title = f"{symbol} - {timeframe.upper()}"
        
        if df is None or df.empty:
            return dcc.Graph(
                figure=create_empty_chart(f"No data available for {symbol}"),
                style={'height': '100%'},
                config={'responsive': True}
            )
        
        # Create appropriate chart
        if chart_type == 'candlestick':
            from src.gui.charts.live_charts import create_candlestick_chart
            fig = create_candlestick_chart(df, symbol, title)
        else:
            from src.gui.charts.live_charts import create_line_chart
            fig = create_line_chart(df, symbol)
            fig.update_layout(title=title)
        
        return dcc.Graph(
            figure=fig,
            style={'height': '100%'},
            config={'responsive': True, 'displayModeBar': True, 'displaylogo': False}
        )
    
    except Exception as e:
        return html.Div(f"Error creating chart: {str(e)}", className="text-danger")


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
        
        from src.gui.charts.live_charts import create_multi_line_chart
        fig = create_multi_line_chart(data_dict, "Stock Performance Comparison (% Change)")
        fig.update_yaxes(title="% Change from Start")
        
        return dcc.Graph(figure=fig)
    
    except Exception as e:
        return html.Div(f"Error creating comparison: {str(e)}", className="text-danger")


def create_chart_panel(panel_id: str, config: dict, show_controls: bool = True):
    """Create a single chart panel with controls"""
    symbol = config.get('symbol', 'AAPL')
    timeframe = config.get('timeframe', '1mo')
    chart_type = config.get('chart_type', 'candlestick')
    is_favorite = config.get('favorite', False)
    
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
    
    # Get chart
    chart_content = get_stock_chart(symbol, timeframe, chart_type)
    
    return dbc.Card([
        dbc.CardHeader(header_content, className="py-2") if show_controls else None,
        dbc.CardBody([
            dcc.Loading(
                id={"type": "loading-panel", "index": panel_id},
                type="default",
                children=html.Div(
                    chart_content, 
                    id={"type": "chart-content", "index": panel_id},
                    style={'height': '100%', 'display': 'flex', 'flexDirection': 'column'}
                )
            )
        ], className="p-2", style={'height': 'calc(100% - 45px)'})
    ], className="h-100", style={'height': '100%'})


def render_multi_panel_layout(layout: str, panels_config: dict, fullscreen: bool = False):
    """Render the multi-panel layout based on selected mode"""
    
    # Determine panel height based on fullscreen and layout
    if fullscreen:
        if layout == 'quad':
            panel_height = 'calc((100vh - 280px) / 2)'
        elif layout in ['split-vertical']:
            panel_height = 'calc((100vh - 280px) / 2)'
        else:
            panel_height = 'calc(100vh - 280px)'
    else:
        if layout == 'quad':
            panel_height = '450px'
        elif layout in ['split-vertical', 'split-horizontal']:
            panel_height = '500px'
        else:
            panel_height = '600px'
    
    panel_style = {'height': panel_height}
    
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
            ], className="py-2")
        ], className="mb-3")
    
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
        layout_content = dbc.Row([
            dbc.Col([
                html.Div(
                    create_chart_panel('panel-1', panels_config.get('panel-1', {})),
                    style=panel_style
                )
            ], md=6, className="mb-3"),
            dbc.Col([
                html.Div(
                    create_chart_panel('panel-2', panels_config.get('panel-2', {})),
                    style=panel_style
                )
            ], md=6, className="mb-3")
        ])
    
    elif layout == 'split-vertical':
        # Two panels stacked vertically
        layout_content = html.Div([
            dbc.Row([
                dbc.Col([
                    html.Div(
                        create_chart_panel('panel-1', panels_config.get('panel-1', {})),
                        style=panel_style
                    )
                ], width=12, className="mb-3")
            ]),
            dbc.Row([
                dbc.Col([
                    html.Div(
                        create_chart_panel('panel-2', panels_config.get('panel-2', {})),
                        style=panel_style
                    )
                ], width=12, className="mb-3")
            ])
        ])
    
    elif layout == 'quad':
        # Four panels in a 2x2 grid
        layout_content = html.Div([
            dbc.Row([
                dbc.Col([
                    html.Div(
                        create_chart_panel('panel-1', panels_config.get('panel-1', {})),
                        style=panel_style
                    )
                ], md=6, className="mb-3"),
                dbc.Col([
                    html.Div(
                        create_chart_panel('panel-2', panels_config.get('panel-2', {})),
                        style=panel_style
                    )
                ], md=6, className="mb-3")
            ]),
            dbc.Row([
                dbc.Col([
                    html.Div(
                        create_chart_panel('panel-3', panels_config.get('panel-3', {})),
                        style=panel_style
                    )
                ], md=6, className="mb-3"),
                dbc.Col([
                    html.Div(
                        create_chart_panel('panel-4', panels_config.get('panel-4', {})),
                        style=panel_style
                    )
                ], md=6, className="mb-3")
            ])
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
