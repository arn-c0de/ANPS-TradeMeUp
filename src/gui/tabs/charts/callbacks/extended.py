"""
Chart tab extended callbacks: price cache, tabs, overlays, infinite scroll, render, panels.
"""

import concurrent.futures
import copy
import json
import logging
import time
import uuid
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
from dash import ALL, MATCH, Input, Output, State, html
from dash.exceptions import PreventUpdate
from sqlalchemy.orm import Session

from src.models.database import engine as _engine
from src.gui.tabs.charts.components import (
    get_stock_chart_components,
    create_trading_overlay,
    render_multi_panel_layout
)
from src.gui.tabs.charts.market_data import MarketDataProvider
from src.gui.tabs.charts.fullscreen_manager import get_fullscreen_state, get_container_classname
from src.gui.tabs.charts.overlay_utils import normalize_overlay_store, save_overlays_to_db, ensure_overlay_tab
from src.gui.tabs.charts.chart_utils import find_index_binary
from src.gui.tabs.charts.chart_data_manager import get_chart_data_manager

# Initialize market data provider
market_data = MarketDataProvider()

logger = logging.getLogger(__name__)


def register_charts_extended(app):
    """Register extended chart callbacks (tabs, overlays, render, panels)."""
    @app.callback(
        Output("chart-price-cache-store", "data"),
        [Input("chart-price-update-interval", "n_intervals"),
         Input("chart-tabs-store", "data")],
        prevent_initial_call=False
    )
    def update_price_cache(n_intervals, tabs_data):
        """Update price cache in background (non-blocking for UI)"""
        import concurrent.futures

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
        overlays = normalize_overlay_store(overlays_data)

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
            with Session(_engine) as db:
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
                    df = market_data.get_historical_data(symbol, period='1d')
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

        overlays = normalize_overlay_store(copy.deepcopy(overlays_data))
        tab_overlays = ensure_overlay_tab(overlays, tab_id)
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

        overlays = normalize_overlay_store(copy.deepcopy(overlays_data))
        tab_overlays = ensure_overlay_tab(overlays, tab_id)
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

        overlays = normalize_overlay_store(copy.deepcopy(overlays_data))
        tab_overlays = ensure_overlay_tab(overlays, tab_id)
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
        overlays = normalize_overlay_store(copy.deepcopy(overlays_data))
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
        [Output("chart-loaded-data-store", "data", allow_duplicate=True),
         Output("chart-scroll-state-store", "data", allow_duplicate=True)],
        Input({"type": "chart-graph", "index": ALL}, "relayoutData"),
        [State("chart-loaded-data-store", "data"),
         State("chart-scroll-state-store", "data"),
         State("chart-tabs-store", "data"),
         State("chart-interaction-modes", "data"),
         State({"type": "chart-graph", "index": ALL}, "id")],
        prevent_initial_call=True
    )
    def handle_infinite_scroll(relayout_data_list, loaded_data_store, scroll_state_store, tabs_data, interaction_modes, graph_ids):
        """
        Handle infinite scroll: detect when user scrolls and load more data symmetrically.

        Features:
        - Tracks visible range and centered candle
        - Symmetric loading: loads historical data (left) and future data (right)
        - Buffer zone: maintains 2x visible range for smooth scrolling
        - Position persistence: saves position to view_state to prevent jumping on refresh
        - Optimized with binary search and improved throttling
        """
        from dash import callback_context
        import json
        import copy
        import time

        if not callback_context.triggered:
            return dash.no_update, dash.no_update

        # Find which graph triggered
        trigger = callback_context.triggered[0]["prop_id"]
        if ".relayoutData" not in trigger:
            return dash.no_update, dash.no_update

        try:
            trigger_id_str = trigger.split(".")[0]
            trigger_id = json.loads(trigger_id_str)
            tab_id = trigger_id.get("index")
        except Exception as e:
            logger.debug(f"[Infinite Scroll] Error parsing trigger ID: {e}")
            return dash.no_update, dash.no_update

        # Get the relayout data for this graph
        trigger_index = None
        for idx, graph_id in enumerate(graph_ids):
            if graph_id.get("index") == tab_id:
                trigger_index = idx
                break

        if trigger_index is None or trigger_index >= len(relayout_data_list):
            return dash.no_update, dash.no_update

        relayout_data = relayout_data_list[trigger_index]
        if not relayout_data:
            return dash.no_update, dash.no_update

        # Only process x-axis range changes (ignore other relayout events like y-axis, shapes, etc.)
        if 'xaxis.range' not in relayout_data and 'xaxis.range[0]' not in relayout_data:
            return dash.no_update, dash.no_update

        # Get chart configuration
        tabs = tabs_data.get('tabs', []) if tabs_data else []
        tab_config = None
        for tab in tabs:
            if tab.get('id') == tab_id:
                tab_config = tab
                break

        if not tab_config:
            return dash.no_update, dash.no_update

        symbol = tab_config.get('symbol')
        timeframe = tab_config.get('timeframe', '1mo')

        if not symbol:
            return dash.no_update, dash.no_update

        # Get interaction mode to check if auto_scroll is enabled
        interaction_modes_dict = interaction_modes if interaction_modes else {'tabs': {}}
        tab_interaction = interaction_modes_dict.get('tabs', {}).get(tab_id, {})
        auto_scroll = tab_interaction.get('auto_scroll', False)

        # Check scroll state to prevent race conditions
        scroll_state = copy.deepcopy(scroll_state_store) if scroll_state_store else {'tabs': {}}
        if 'tabs' not in scroll_state:
            scroll_state['tabs'] = {}

        tab_scroll_state = scroll_state['tabs'].get(tab_id, {})

        # Check if already loading
        if tab_scroll_state.get('loading', False):
            return dash.no_update, dash.no_update

        # Debounce: check last load time (200ms for responsive loading)
        current_time = time.time()
        last_load_time = tab_scroll_state.get('last_load_time', 0)
        if current_time - last_load_time < 0.2:  # 200ms debounce for fast response
            return dash.no_update, dash.no_update

        # Get visible range
        visible_range = None
        if 'xaxis.range' in relayout_data:
            visible_range = relayout_data['xaxis.range']
        elif 'xaxis.range[0]' in relayout_data and 'xaxis.range[1]' in relayout_data:
            visible_range = [relayout_data['xaxis.range[0]'], relayout_data['xaxis.range[1]']]

        if not visible_range or not isinstance(visible_range, list) or len(visible_range) != 2:
            return dash.no_update, dash.no_update

        # Validate range values and convert to proper types
        try:
            left_value = visible_range[0]
            right_value = visible_range[1]
            if left_value is None or right_value is None:
                return dash.no_update, dash.no_update

            logger.debug(f"[Infinite Scroll] Received range: left={left_value} (type={type(left_value).__name__}), right={right_value} (type={type(right_value).__name__})")

            # Convert string timestamps to datetime if needed (Plotly sends ISO strings for date-type x-axis)
            # For category-type x-axis, Plotly sends numeric indices (int/float)
            from pandas import to_datetime
            if isinstance(left_value, str):
                try:
                    left_value = to_datetime(left_value)
                except (ValueError, TypeError):
                    logger.debug(f"[Infinite Scroll] Could not parse left_value: {left_value}")
                    return dash.no_update, dash.no_update
            if isinstance(right_value, str):
                try:
                    right_value = to_datetime(right_value)
                except (ValueError, TypeError):
                    logger.debug(f"[Infinite Scroll] Could not parse right_value: {right_value}")
                    return dash.no_update, dash.no_update
        except (TypeError, ValueError) as e:
            logger.debug(f"[Infinite Scroll] Error validating range values: {e}")
            return dash.no_update, dash.no_update

        # Get loaded data metadata
        loaded_store = copy.deepcopy(loaded_data_store) if loaded_data_store else {'tabs': {}}
        if 'tabs' not in loaded_store:
            loaded_store['tabs'] = {}

        # Get data manager
        data_manager = get_chart_data_manager()

        # Get cached data to check total points
        cached_df = data_manager.get_cached_data(symbol, timeframe)
        if cached_df is None or cached_df.empty:
            # No cached data yet, initialize
            cached_df = data_manager.get_initial_data(symbol, timeframe)
            if cached_df is None or cached_df.empty:
                return dash.no_update, dash.no_update

        total_points = len(cached_df)
        if total_points == 0:
            return dash.no_update, dash.no_update

        # Find left and right indices in visible range
        # With type='category' x-axis, Plotly sends numeric indices (0, 1, 2...) not timestamps
        indices = list(cached_df.index)

        try:
            # Check if values are already numeric indices (from category-type x-axis)
            if isinstance(left_value, (int, float)) and isinstance(right_value, (int, float)):
                # Direct numeric indices - no need for binary search
                left_index = int(round(left_value))
                right_index = int(round(right_value))
                logger.debug(f"[Infinite Scroll] Using numeric indices: left={left_index}, right={right_index}")
            else:
                # Timestamp values - use binary search (legacy behavior)
                left_index = find_index_binary(indices, left_value)
                right_index = find_index_binary(indices, right_value)
                logger.debug(f"[Infinite Scroll] Using binary search for timestamps")

            # Validate indices
            if left_index < 0 or left_index >= total_points:
                left_index = 0
            if right_index < 0 or right_index >= total_points:
                right_index = total_points - 1
            if right_index < left_index:
                right_index = left_index

            # Calculate visible candle count and centered candle
            visible_candle_count = right_index - left_index + 1
            centered_index = left_index + (visible_candle_count // 2)
            centered_candle = indices[centered_index] if centered_index < len(indices) else indices[-1]

            # Serialize centered_candle safely (handle pandas Timestamp, datetime, or string)
            try:
                if hasattr(centered_candle, 'isoformat'):
                    centered_candle_str = centered_candle.isoformat()
                elif hasattr(centered_candle, 'strftime'):
                    centered_candle_str = centered_candle.strftime('%Y-%m-%dT%H:%M:%S')
                else:
                    centered_candle_str = str(centered_candle)
            except Exception:
                centered_candle_str = str(centered_candle)

            # Calculate buffer zone (2x visible range for smooth scrolling)
            buffer_size = max(visible_candle_count * 2, 50)  # Minimum 50 candles buffer

            # Save current visible range and centered candle to scroll_state_store
            scroll_state['tabs'][tab_id] = {
                'loading': tab_scroll_state.get('loading', False),
                'last_load_time': tab_scroll_state.get('last_load_time', 0),
                'last_threshold_check': current_time,
                'xaxis_range': visible_range,  # NEW: Save current visible range
                'centered_candle': centered_candle_str,  # NEW: Save centered candle (safely serialized)
                'visible_candle_count': visible_candle_count,  # NEW: Save visible candle count
                'left_index': left_index,  # NEW: Save indices for position restoration
                'right_index': right_index
            }

            # Check if we need to load more data (symmetric loading: left AND right)
            should_load_left = data_manager.should_load_more_left(left_index, total_points, buffer_size)
            should_load_right = data_manager.should_load_more_right(right_index, total_points, buffer_size)

            logger.info(f"[Infinite Scroll] Threshold check for {symbol} ({timeframe}): left_index={left_index}, right_index={right_index}, total={total_points}, buffer={buffer_size}, should_load_left={should_load_left}, should_load_right={should_load_right}")

            # If no loading needed, just save the state and return
            if not should_load_left and not should_load_right:
                return dash.no_update, scroll_state

            # Set loading flag BEFORE starting async operation
            scroll_state['tabs'][tab_id]['loading'] = True

            combined_df = cached_df.copy()
            data_loaded = False
            index_offset = 0  # Track how many points were prepended (shifts indices right)

            # Load historical data if needed (scrolling left)
            if should_load_left:
                earliest_date = cached_df.index[0]
                new_historical_df = data_manager.load_more_historical(symbol, timeframe, earliest_date)

                if new_historical_df is not None and not new_historical_df.empty:
                    # Prepend new data
                    old_len = len(combined_df)
                    combined_df = data_manager.prepend_data(combined_df, new_historical_df)
                    new_len = len(combined_df)
                    index_offset = new_len - old_len  # How many points were added at the beginning
                    data_loaded = True
                    logger.info(f"[Infinite Scroll] Loaded {len(new_historical_df)} historical points for {symbol} ({timeframe}), index_offset={index_offset}")
                else:
                    logger.debug(f"[Infinite Scroll] No more historical data for {symbol} ({timeframe})")

            # Load future data if needed (scrolling right)
            if should_load_right:
                latest_date = combined_df.index[-1]
                new_future_df = data_manager.load_more_future(symbol, timeframe, latest_date)

                if new_future_df is not None and not new_future_df.empty:
                    # Append new data (no index offset needed - data added at end)
                    combined_df = data_manager.append_data(combined_df, new_future_df)
                    data_loaded = True
                    logger.info(f"[Infinite Scroll] Loaded {len(new_future_df)} future points for {symbol} ({timeframe})")
                else:
                    logger.debug(f"[Infinite Scroll] No more future data for {symbol} ({timeframe})")

            # Only update if we actually loaded data
            if data_loaded:
                # Update cache
                data_manager.update_cached_data(symbol, timeframe, combined_df)

                # Update loaded data store (safely serialize dates)
                earliest_date_str = None
                latest_date_str = None
                if len(combined_df) > 0:
                    try:
                        earliest_date = combined_df.index[0]
                        latest_date = combined_df.index[-1]
                        if hasattr(earliest_date, 'isoformat'):
                            earliest_date_str = earliest_date.isoformat()
                        elif hasattr(earliest_date, 'strftime'):
                            earliest_date_str = earliest_date.strftime('%Y-%m-%dT%H:%M:%S')
                        else:
                            earliest_date_str = str(earliest_date)

                        if hasattr(latest_date, 'isoformat'):
                            latest_date_str = latest_date.isoformat()
                        elif hasattr(latest_date, 'strftime'):
                            latest_date_str = latest_date.strftime('%Y-%m-%dT%H:%M:%S')
                        else:
                            latest_date_str = str(latest_date)
                    except Exception as e:
                        logger.debug(f"[Infinite Scroll] Error serializing dates: {e}")
                        earliest_date_str = str(combined_df.index[0]) if len(combined_df) > 0 else None
                        latest_date_str = str(combined_df.index[-1]) if len(combined_df) > 0 else None

                import time
                loaded_store['tabs'][tab_id] = {
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'earliest_date': earliest_date_str,
                    'latest_date': latest_date_str,
                    'data_points': len(combined_df),
                    'index_offset': index_offset,  # NEW: Store offset for position correction
                    'offset_timestamp': time.time()  # Timestamp when offset was set
                }

                # Note: view_state is saved automatically by save_chart_view_state callback
                # which listens to the same relayoutData events
                load_direction = "left" if should_load_left else "right" if should_load_right else "both"
                logger.info(f"[Infinite Scroll] Loaded data ({load_direction}) for {symbol} ({timeframe}): {len(combined_df)} total points, index_offset={index_offset}")
            else:
                # No data loaded, but still update scroll state
                pass

            # Reset loading flag
            scroll_state['tabs'][tab_id]['loading'] = False
            scroll_state['tabs'][tab_id]['last_load_time'] = current_time

            return loaded_store, scroll_state

        except Exception as e:
            tab_id_str = str(tab_id) if 'tab_id' in locals() else 'unknown'
            logger.error(f"[Infinite Scroll] Error handling scroll for tab {tab_id_str}: {e}", exc_info=True)
            # Ensure scroll_state is initialized before accessing it
            if 'tabs' not in scroll_state:
                scroll_state['tabs'] = {}
            # Only try to reset loading flag if tab_id is valid
            if 'tab_id' in locals() and tab_id is not None:
                if tab_id not in scroll_state['tabs']:
                    scroll_state['tabs'][tab_id] = {}
                scroll_state['tabs'][tab_id]['loading'] = False
            return dash.no_update, scroll_state


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

        overlays = normalize_overlay_store(overlays_data)
        tab_overlays = overlays.get("tabs", {}).get(tab_id, {})
        items = tab_overlays.get(group, []) or []
        overlay_item = next((item for item in items if item.get("id") == item_id), None)
        if not overlay_item:
            return dash.no_update

        price = overlay_item.get("price")
        if price is None:
            tabs_data["active_tab"] = tab_id
            return tabs_data

        from src.gui.tabs.charts.market_data import market_data

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

        # Create new tab with symbol in ID for better debugging
        new_tab_id = f"tab-{symbol}-{uuid.uuid4().hex[:8]}"
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
            with Session(_engine) as db:
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
        Output("chart-display-area", "children"),
        [Input("chart-tabs-store", "data"),
         Input("quad-mode-store", "data"),
         Input("chart-overlays-store", "data"),
         Input("chart-options-checklist", "value"),
         Input("chart-fullscreen-state", "data"),  # Keep for height calculation
         Input("layout-preset-dropdown", "value"),
         Input("refresh-all-panels", "n_clicks"),
         Input("chart-update-interval", "n_intervals"),
         Input("chart-interaction-modes", "data"),
         Input("chart-view-state", "data"),
         Input("chart-loaded-data-store", "data")],  # NEW: Listen to loaded data changes
        prevent_initial_call='initial_duplicate'
    )
    def render_chart_display(tabs_data, quad_data, overlays_data, chart_options, fullscreen_data, layout_preset, refresh_clicks, n_intervals, interaction_modes, view_state_data, loaded_data_store):
        """
        Render chart display area - OPTIMIZED to only render active tab.
        This significantly improves tab switching performance.
        """
        tabs = tabs_data.get('tabs', [])
        active_tab_id = tabs_data.get('active_tab')
        # Ensure quad_data is properly initialized and preserve quad_enabled state
        if quad_data is None:
            quad_data = {'enabled': False, 'selected_tabs': []}
        quad_enabled = quad_data.get('enabled', False)
        is_fullscreen = get_fullscreen_state(fullscreen_data)

        show_volume = 'volume' in (chart_options or [])
        show_ma = 'ma' in (chart_options or [])
        show_overlay = 'stats' in (chart_options or [])

        if not tabs:
            return dbc.Alert("No charts open. Click '+ New' to add a chart.", color="info", className="mt-3")

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

            # Get loaded data from cache (for infinite scroll)
            loaded_data = None
            index_offset = 0  # Offset to adjust range when new data is prepended
            if loaded_data_store and loaded_data_store.get('tabs'):
                tab_loaded = loaded_data_store.get('tabs', {}).get(tab['id'])
                if tab_loaded:
                    # Get cached data from ChartDataManager
                    from src.gui.tabs.charts.chart_data_manager import get_chart_data_manager
                    data_manager = get_chart_data_manager()
                    loaded_data = data_manager.get_cached_data(tab['symbol'], tab['timeframe'])

                    # Get index offset (if new data was prepended, we need to adjust the view)
                    index_offset = tab_loaded.get('index_offset', 0)
                    offset_timestamp = tab_loaded.get('offset_timestamp', 0)

                    # Apply offset to view_state range if needed
                    # Only apply if offset is fresh (set within last 2 seconds) to avoid applying it multiple times
                    import time
                    if index_offset > 0 and view_state and 'xaxis_range' in view_state:
                        time_since_offset = time.time() - offset_timestamp
                        if time_since_offset < 2.0:  # Only apply if fresh (within 2 seconds)
                            old_range = view_state['xaxis_range']
                            try:
                                # For category-type x-axis, range is in index form (numeric)
                                # Shift range right by the number of prepended points
                                new_range = [old_range[0] + index_offset, old_range[1] + index_offset]
                                view_state['xaxis_range'] = new_range
                                logger.info(f"[Infinite Scroll] Adjusted view range by offset {index_offset}: {old_range} -> {new_range}")
                            except (TypeError, ValueError, IndexError) as e:
                                logger.warning(f"[Infinite Scroll] Could not adjust range: {e}")
                        else:
                            logger.debug(f"[Infinite Scroll] Offset too old ({time_since_offset:.2f}s), skipping adjustment")

            chart_component, stats_data = get_stock_chart_components(
                tab['symbol'],
                tab['timeframe'],
                tab['chart_type'],
                show_volume=tab_show_volume,
                show_ma=tab_show_ma,
                overlays=tab_overlays,
                graph_id={"type": "chart-graph", "index": tab['id']},
                dragmode=dragmode,
                auto_scroll=auto_scroll,
                view_state=view_state,
                loaded_data=loaded_data  # NEW: Pass loaded data for infinite scroll
            )

            chart_div = html.Div(
                [chart_component],
                style={'height': '100%', 'display': 'flex', 'flexDirection': 'column'}
            )
            trading_overlay = create_trading_overlay(stats_data, show_overlay, panel_id=tab['id']) if show_overlay else None

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
                return dbc.Alert("No charts available for quad view.", color="info", className="mt-3")

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

            return quad_layout

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
            return dbc.Alert("No active chart.", color="info", className="mt-3")

        # Only render the single active tab (in single mode)
        height = 'calc(100vh - 180px)' if is_fullscreen else 'calc(100vh - 320px)'
        final_style = {'display': 'block', 'height': height, 'minHeight': '600px'}

        panel_content = build_tab_panel(active_tab, "100%", True, clickable=False)
        single_chart_div = html.Div(panel_content, style=final_style)

        return single_chart_div


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


    # ESC handler removed - now handled by clicking exit-fullscreen-btn directly


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
         Input({"type": "favorite-btn", "index": ALL}, "n_clicks"),
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

        # Handle layout changes - only update if explicitly triggered by layout button
        # Don't reset layout when refresh-all-panels or other non-layout triggers fire
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


    # Separate callback for multi-panel className to avoid re-rendering when only fullscreen changes
    @app.callback(
        Output("multi-panel-chart-area", "className"),
        Input("chart-fullscreen-state", "data"),
        prevent_initial_call=False
    )
    def update_multi_panel_classname(fullscreen_state):
        """Update multi-panel chart area className based on fullscreen state"""
        is_fullscreen = get_fullscreen_state(fullscreen_state)
        return get_container_classname(is_fullscreen)


    @app.callback(
        Output("multi-panel-chart-area", "children"),
        [Input("chart-panels-config", "data"),
         Input("chart-update-interval", "n_intervals"),
         Input("refresh-all-panels", "n_clicks"),
         Input("chart-overlays-store", "data"),
         Input("chart-fullscreen-state", "data"),  # Keep for height calculation
         Input("chart-interaction-modes", "data"),
         Input("chart-view-state", "data"),
         Input("chart-loaded-data-store", "data")],  # NEW: Listen to loaded data changes
        prevent_initial_call='initial_duplicate'
    )
    def render_chart_panels(config, n_intervals, refresh_clicks, overlays_data, fullscreen_state, interaction_modes, view_state_data, loaded_data_store):
        """Render the multi-panel chart layout with fullscreen support"""
        # Handle None values
        if not config:
            config = {'layout': 'single', 'panels': {}}
        if not interaction_modes:
            interaction_modes = {'tabs': {}}
        if not view_state_data:
            view_state_data = {'tabs': {}}

        layout = config.get('layout', 'single')
        panels = config.get('panels', {})
        is_fullscreen = get_fullscreen_state(fullscreen_state)

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

        try:
            chart_layout = render_multi_panel_layout(layout, panels, is_fullscreen, overlays_data, view_state_data, loaded_data_store)
            return chart_layout
        except Exception as e:
            logger.error(f"Error rendering chart panels: {e}", exc_info=True)
            return html.Div(f"Error rendering charts: {str(e)}", className="text-danger")


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
        Input({"type": "chart-mode-toggle", "index": ALL}, "n_clicks"),
        [State({"type": "chart-mode-toggle", "index": ALL}, "id"),
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
            with Session(_engine) as db:
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
        [Input({"type": "config-btn", "index": ALL}, "n_clicks"),
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
        [Input({"type": "symbol-label", "index": ALL}, "n_clicks"),
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
            from src.gui.tabs.charts.market_data import market_data
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
        Output({"type": "chart-content", "index": MATCH}, "children"),
        Input({"type": "refresh-btn", "index": MATCH}, "n_clicks"),
        [State({"type": "chart-content", "index": MATCH}, "id"),
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

        # Use get_stock_chart_with_stats instead (get_stock_chart doesn't exist)
        from src.gui.tabs.charts.components import get_stock_chart_with_stats
        return get_stock_chart_with_stats(symbol, timeframe, chart_type)
