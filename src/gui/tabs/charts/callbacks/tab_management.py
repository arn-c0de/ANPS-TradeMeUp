"""Chart tab callbacks: tab management (open/close/switch, new-tab modal, overlay jump)."""

import copy
import json
import uuid

import dash
from dash import ALL, Input, Output, State, callback_context

from src.gui.tabs.charts.overlay_utils import (
    normalize_overlay_store,
)

# The shared provider singleton, not a per-module instance.
from src.services.market_data import market_data

from ._shared import _search_entity_symbols


def register_tab_management_callbacks(app):
    """Tab switching/closing, the new-tab modal, and jumping to charts from overlay lists."""

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
        """Switch to clicked tab."""
        if not callback_context.triggered or not any(n_clicks_list):
            return dash.no_update

        # Get the clicked tab ID
        triggered_id = callback_context.triggered[0]["prop_id"].split(".")[0]
        button_id = json.loads(triggered_id)
        tab_id = button_id["index"]

        # Verify that the tab exists before switching
        tabs = tabs_data.get('tabs', [])
        if not any(tab.get('id') == tab_id for tab in tabs):
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
        """Close clicked tab."""
        if not callback_context.triggered or not any(n_clicks_list):
            return dash.no_update

        # Get the clicked tab ID
        triggered_id = callback_context.triggered[0]["prop_id"].split(".")[0]
        button_id = json.loads(triggered_id)
        tab_id_to_close = button_id["index"]

        # Don't close if it's the last tab (keep at least one)
        if len(tabs_data.get('tabs', [])) <= 1:
            return dash.no_update

        # Return a copy to avoid reference issues
        updated_data = copy.deepcopy(tabs_data)
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
        """Toggle new tab modal."""
        if not callback_context.triggered:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update

        trigger_id = callback_context.triggered[0]['prop_id'].split('.')[0]

        if trigger_id == "add-chart-tab-btn":
            return True, None, '1mo', 'candlestick'
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
        """Add new chart tab."""
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
        """Search for symbols in new tab modal."""
        # Don't clear options when search_value is empty - this prevents resetting the selected value
        if not search_value or len(search_value) < 1:
            return dash.no_update
        return _search_entity_symbols(search_value)
