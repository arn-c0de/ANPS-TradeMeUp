"""Chart tab callbacks: price cache + tab bar."""

import concurrent.futures

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, html

# The shared provider singleton, not a per-module instance.
from src.services.market_data import market_data


def register_price_cache_callbacks(app):
    """Background price cache updates and browser-style tab buttons."""

    @app.callback(
        Output("chart-price-cache-store", "data"),
        [Input("chart-price-update-interval", "n_intervals"),
         Input("chart-tabs-store", "data"),
         Input("tabs", "active_tab")],  # Check if Charts tab is active
        prevent_initial_call=False
    )
    def update_price_cache(n_intervals, tabs_data, active_main_tab):
        """Update price cache in background (non-blocking for UI).
        Only updates when Charts tab is active to save resources."""
        if active_main_tab != "charts":
            return dash.no_update

        tabs = tabs_data.get('tabs', [])
        if not tabs:
            return {}

        symbols = list(set(tab['symbol'] for tab in tabs))
        price_cache = {}

        def fetch_price(symbol):
            try:
                return symbol, market_data.get_live_price(symbol)
            except Exception:
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
        """Render the browser-style tab buttons with cached price data."""
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
