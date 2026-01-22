"""
Charts Tab - Live Market Data and Visualizations
"""

from dash import dcc, html
import dash_bootstrap_components as dbc
from src.gui.charts import MarketDataProvider, create_candlestick_chart, create_empty_chart, create_price_indicator_card


# Initialize market data provider
market_data = MarketDataProvider()


def create_layout():
    """Create charts tab layout with live market data"""
    return dbc.Container([
        # Auto-refresh interval
        dcc.Interval(id='chart-update-interval', interval=30000, n_intervals=0),  # 30 seconds
        
        # Market Overview Header
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("📊 Live Market Overview", className="mb-0")),
                    dbc.CardBody([
                        html.Div(id='market-indices-display')
                    ])
                ], className="mb-3")
            ], width=12)
        ]),
        
        # Stock Selection and Controls
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Stock Symbol:", className="fw-bold"),
                                dbc.Input(
                                    id="chart-symbol-input",
                                    placeholder="Enter symbol (e.g., AAPL, TSLA, NVDA)",
                                    value="AAPL",
                                    type="text",
                                    className="mb-2"
                                )
                            ], md=4),
                            dbc.Col([
                                dbc.Label("Timeframe:", className="fw-bold"),
                                dcc.Dropdown(
                                    id="chart-timeframe-selector",
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
                                    className="mb-2"
                                )
                            ], md=4),
                            dbc.Col([
                                dbc.Label("Chart Type:", className="fw-bold"),
                                dcc.Dropdown(
                                    id="chart-type-selector",
                                    options=[
                                        {'label': '📊 Candlestick', 'value': 'candlestick'},
                                        {'label': '📈 Line Chart', 'value': 'line'}
                                    ],
                                    value='candlestick',
                                    clearable=False,
                                    className="mb-2"
                                )
                            ], md=4)
                        ]),
                        dbc.Button(
                            "🔄 Update Chart",
                            id="update-chart-btn",
                            color="primary",
                            className="w-100"
                        )
                    ])
                ], className="mb-3")
            ], width=12)
        ]),
        
        # Price Indicator Card
        dbc.Row([
            dbc.Col([
                html.Div(id='price-indicator-card')
            ], width=12)
        ], className="mb-3"),
        
        # Main Chart
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("📈 Live Price Chart", className="mb-0")),
                    dbc.CardBody([
                        dcc.Loading(
                            id="loading-main-chart",
                            type="default",
                            children=html.Div(id="main-price-chart")
                        )
                    ])
                ])
            ], width=12)
        ], className="mb-3"),
        
        # Comparison Section
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("📊 Compare Stocks", className="mb-0")),
                    dbc.CardBody([
                        dbc.Label("Add symbols to compare (comma-separated):", className="fw-bold"),
                        dbc.Input(
                            id="compare-symbols-input",
                            placeholder="e.g., AAPL,MSFT,GOOGL",
                            type="text",
                            className="mb-2"
                        ),
                        dbc.Button(
                            "📊 Compare",
                            id="compare-btn",
                            color="info",
                            className="w-100 mb-3"
                        ),
                        dcc.Loading(
                            id="loading-comparison-chart",
                            type="default",
                            children=html.Div(id="comparison-chart")
                        )
                    ])
                ])
            ], width=12)
        ])
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
            return dcc.Graph(figure=create_empty_chart(f"No data available for {symbol}"))
        
        # Create appropriate chart
        if chart_type == 'candlestick':
            from src.gui.charts.live_charts import create_candlestick_chart
            fig = create_candlestick_chart(df, symbol, title)
        else:
            from src.gui.charts.live_charts import create_line_chart
            fig = create_line_chart(df, symbol)
            fig.update_layout(title=title)
        
        return dcc.Graph(figure=fig)
    
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
