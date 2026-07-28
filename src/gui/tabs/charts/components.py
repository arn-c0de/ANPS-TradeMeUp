"""
Charts Tab - Component Creation Functions
"""

from typing import Dict, Optional, Tuple

import dash_bootstrap_components as dbc
import pandas as pd
from dash import dcc, html

from src.gui.tabs.charts.chart_data_manager import get_chart_data_manager
from src.gui.tabs.charts.live_charts import (
    create_empty_chart,
    create_multi_line_chart,
    create_price_indicator_card,
)
from src.services.market_data import MarketDataProvider

from .data import _calculate_stats, _fetch_chart_data
from .utils import _build_chart_figure, _build_stats_card

# Initialize market data provider
market_data = MarketDataProvider()


def get_stock_chart_components(
    symbol: str,
    timeframe: str = '1mo',
    chart_type: str = 'candlestick',
    show_volume: bool = True,
    show_ma: bool = False,
    overlays: dict | None = None,
    graph_id: dict | None = None,
    dragmode: str = 'zoom',
    auto_scroll: bool = False,
    view_state: dict | None = None,
    loaded_data: pd.DataFrame | None = None
) -> tuple[dcc.Graph, dict | None]:
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


def create_overlay_list(panel_id: str, symbol: str, overlays_data: dict = None, timeframe: str = None):
    """Create compact scrollable list of brackets/breaks for a panel."""
    if not panel_id or not symbol:
        # Always return visible container, even if empty
        return html.Div(
            html.Div(
                "No overlays",
                style={
                    'padding': '2px 4px',
                    'fontSize': '0.65rem',
                    'color': '#888',
                    'fontStyle': 'italic'
                }
            ),
            id={"type": "overlay-list", "index": panel_id},
            className="overlay-list",
            style={
                'maxHeight': '60px',
                'overflowY': 'auto',
                'overflowX': 'hidden',
                'flex': '1 1 auto',
                'minWidth': '80px',  # Minimum width so it's visible
                'minHeight': '20px',  # Minimum height so empty state is visible
                'backgroundColor': '#111',
                'border': '1px solid #333',
                'borderRadius': '3px',
                'padding': '2px 0',
                'display': 'flex'  # Always visible
            }
        )

    # Get overlays for this symbol/timeframe - overlays are stored by tab_id = "symbol_timeframe"
    if not overlays_data:
        overlays_data = {'tabs': {}}

    # Construct tab_id from symbol and timeframe
    if timeframe:
        tab_id = f"{symbol}_{timeframe}"
    else:
        # Try to find any overlay for this symbol (fallback)
        tab_id = None
        for key in overlays_data.get('tabs', {}).keys():
            if key.startswith(f"{symbol}_"):
                tab_id = key
                break

    if not tab_id:
        # No overlays found for this symbol/timeframe
        panel_overlays = {'brackets': [], 'breaks': []}
    else:
        panel_overlays = overlays_data.get('tabs', {}).get(tab_id, {})

    brackets = panel_overlays.get('brackets', []) or []
    breaks = panel_overlays.get('breaks', []) or []

    # Combine and sort by price
    all_items = []
    for item in brackets:
        if item.get('visible', True):
            all_items.append({
                'type': 'Bracket',
                'name': item.get('name', ''),
                'price': item.get('price'),
                'color': item.get('color', '#00ff88'),
                'id': item.get('id', '')
            })
    for item in breaks:
        if item.get('visible', True):
            all_items.append({
                'type': 'Break',
                'name': item.get('name', ''),
                'price': item.get('price'),
                'color': item.get('color', '#ff4444'),
                'id': item.get('id', '')
            })

    # Sort by price (descending)
    all_items.sort(key=lambda x: float(x['price']) if x['price'] is not None else 0, reverse=True)

    # Create list items (max 4 visible, scrollable if more)
    list_items = []
    for item in all_items:
        price_str = f"${float(item['price']):.2f}" if item['price'] is not None else "N/A"
        name_str = item['name'] if item['name'] else item['type']

        list_items.append(
            html.Button(
                [
                    html.Span(name_str, style={'fontSize': '0.65rem', 'color': item['color'], 'fontWeight': 'bold'}),
                    html.Span(price_str, style={'fontSize': '0.65rem', 'color': '#e8e8e8', 'marginLeft': '4px'})
                ],
                id={"type": "overlay-list-item", "index": panel_id, "overlay_id": item['id']},
                className="overlay-list-item",
                style={
                    'padding': '2px 4px',
                    'cursor': 'pointer',
                    'borderBottom': '1px solid #333',
                    'display': 'flex',
                    'justifyContent': 'space-between',
                    'alignItems': 'center',
                    'fontSize': '0.65rem',
                    'lineHeight': '1.2',
                    'width': '100%',
                    'backgroundColor': 'transparent',
                    'border': 'none',
                    'borderTop': 'none',
                    'borderLeft': 'none',
                    'borderRight': 'none',
                    'textAlign': 'left',
                    'color': '#e8e8e8'
                },
                title=f"Click to center line at {price_str}"
            )
        )

    if not list_items:
        list_items.append(
            html.Div(
                "No overlays",
                style={
                    'padding': '2px 4px',
                    'fontSize': '0.65rem',
                    'color': '#888',
                    'fontStyle': 'italic'
                }
            )
        )

    return html.Div(
        list_items,
        id={"type": "overlay-list", "index": panel_id},
        className="overlay-list",
        style={
            'maxHeight': '60px',  # ~4 items at 15px each
            'overflowY': 'auto',
            'overflowX': 'hidden',
            'flex': '1 1 auto',  # Take remaining space
            'minWidth': '80px',  # Minimum width so it's visible
            'minHeight': '20px',  # Minimum height so empty state is visible
            'backgroundColor': '#111',
            'border': '1px solid #333',
            'borderRadius': '3px',
            'padding': '2px 0',
            'display': 'flex',  # Always visible
            'flexDirection': 'column'  # Stack items vertically
        }
    )


def create_trading_overlay(stats_data: dict = None, show_stats: bool = True, panel_id: str = None, symbol: str = None, overlays_data: dict = None, timeframe: str = None):
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

    # Button and list row
    manage_button = None
    overlay_list = None
    if panel_id:
        manage_button = dbc.Button(
            [html.I(className="fas fa-layer-group"), " B/B"],
            id={"type": "overlay-manage-btn", "index": panel_id},
            color="info",
            size="sm",
            outline=True,
            className="overlay-manage-btn",
            style={
                'width': '8.33%',  # Half of 16.67% (quarter of original 33%)
                'minWidth': '25px',  # Minimum readable size
                'fontSize': '0.55rem',  # Even smaller font
                'padding': '1px 2px'  # Even tighter padding
            }
        )

        # Always create overlay list when panel_id exists (create_overlay_list handles None overlays_data)
        if symbol:
            overlay_list = create_overlay_list(panel_id, symbol, overlays_data, timeframe)
        else:
            # Create empty list container if no symbol yet
            overlay_list = create_overlay_list(panel_id, '', overlays_data, timeframe)

    overlay_children.extend([
        html.Div(
            [
                manage_button if manage_button else html.Div(),
                overlay_list if overlay_list else html.Div(id={"type": "overlay-list", "index": panel_id}, style={'display': 'flex', 'flex': '1 1 auto', 'minHeight': '20px'})
            ],
            className="overlay-manage-row",
            style={
                'display': 'flex',
                'gap': '4px',
                'alignItems': 'flex-start',
                'width': '100%'
            }
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


def create_chart_panel(panel_id: str, config: dict, show_controls: bool = True, overlays: dict = None, view_state: dict = None, loaded_data: pd.DataFrame | None = None, overlays_data: dict = None):
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
    # Use passed overlays_data directly (or None if not provided)
    # overlays_data should have structure: {'tabs': {'symbol_timeframe': {'brackets': [], 'breaks': []}}}
    trading_overlay = create_trading_overlay(stats_data, show_stats, panel_id=panel_id, symbol=symbol, overlays_data=overlays_data, timeframe=timeframe) if show_stats else None

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
        """Get overlays for a panel by looking up symbol_timeframe from panels_config."""
        if not overlays_data or not panels_config:
            return {}

        panel_config = panels_config.get('panels', {}).get(panel_id, {})
        symbol = panel_config.get('symbol')
        timeframe = panel_config.get('timeframe')

        if symbol and timeframe:
            tab_id = f"{symbol}_{timeframe}"
            return (overlays_data or {}).get('tabs', {}).get(tab_id, {})
        return {}

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
                        dbc.Button("🔄 Refresh All", id="refresh-all-panels-btn", color="success", size="sm", className="me-2"),
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
                        create_chart_panel('panel-1', panel_config, overlays=get_panel_overlays('panel-1'), view_state=get_panel_view_state('panel-1'), loaded_data=get_panel_loaded_data('panel-1'), overlays_data=overlays_data),
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
                    create_chart_panel('panel-1', panels_config.get('panel-1', {}), overlays=get_panel_overlays('panel-1'), view_state=get_panel_view_state('panel-1'), loaded_data=get_panel_loaded_data('panel-1'), overlays_data=overlays_data),
                    style=panel_style
                )
            ], md=6, className=margin_class),
            dbc.Col([
                html.Div(
                    create_chart_panel('panel-2', panels_config.get('panel-2', {}), overlays=get_panel_overlays('panel-2'), view_state=get_panel_view_state('panel-2'), loaded_data=get_panel_loaded_data('panel-2'), overlays_data=overlays_data),
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
                    create_chart_panel('panel-1', panels_config.get('panel-1', {}), overlays=get_panel_overlays('panel-1'), view_state=get_panel_view_state('panel-1'), loaded_data=get_panel_loaded_data('panel-1'), overlays_data=overlays_data),
                        style=panel_style
                    )
                ], width=12, className=margin_class)
            ], className="gx-1" if fullscreen else "gx-3"),
            dbc.Row([
                dbc.Col([
                    html.Div(
                    create_chart_panel('panel-2', panels_config.get('panel-2', {}), overlays=get_panel_overlays('panel-2'), view_state=get_panel_view_state('panel-2'), loaded_data=get_panel_loaded_data('panel-2'), overlays_data=overlays_data),
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
                    create_chart_panel('panel-1', panels_config.get('panel-1', {}), overlays=get_panel_overlays('panel-1'), view_state=get_panel_view_state('panel-1'), loaded_data=get_panel_loaded_data('panel-1'), overlays_data=overlays_data),
                        style=panel_style
                    )
                ], md=6, className=margin_class),
                dbc.Col([
                    html.Div(
                    create_chart_panel('panel-2', panels_config.get('panel-2', {}), overlays=get_panel_overlays('panel-2'), view_state=get_panel_view_state('panel-2'), loaded_data=get_panel_loaded_data('panel-2'), overlays_data=overlays_data),
                        style=panel_style
                    )
                ], md=6, className=margin_class)
            ], className=gutter_class),
            dbc.Row([
                dbc.Col([
                    html.Div(
                    create_chart_panel('panel-3', panels_config.get('panel-3', {}), overlays=get_panel_overlays('panel-3'), view_state=get_panel_view_state('panel-3'), loaded_data=get_panel_loaded_data('panel-3'), overlays_data=overlays_data),
                        style=panel_style
                    )
                ], md=6),
                dbc.Col([
                    html.Div(
                    create_chart_panel('panel-4', panels_config.get('panel-4', {}), overlays=get_panel_overlays('panel-4'), view_state=get_panel_view_state('panel-4'), loaded_data=get_panel_loaded_data('panel-4'), overlays_data=overlays_data),
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
