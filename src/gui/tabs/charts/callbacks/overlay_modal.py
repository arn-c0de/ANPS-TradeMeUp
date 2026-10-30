"""Chart tab callbacks: overlay modal (brackets / breaks)."""

import copy
import json
import logging
import re
import uuid

import dash
import dash_bootstrap_components as dbc
from dash import ALL, Input, Output, State, callback_context, html
from dash.exceptions import PreventUpdate
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.gui.tabs.charts.overlay_utils import (
    ensure_overlay_tab,
    normalize_overlay_store,
    save_overlays_to_db,
)
from src.models.database import engine as _engine

# The shared provider singleton, not a per-module instance.
from src.services.market_data import market_data

from ._shared import _get_triggered_relayout

logger = logging.getLogger(__name__)


def _overlay_item_row(group: str, tab_id: str, item: dict, default_color: str) -> dbc.Row:
    """Build one editable row (price, label, color, visibility, jump, delete) for an overlay item."""
    item_id = item.get("id")
    return dbc.Row([
        dbc.Col(
            dbc.Input(
                id={"type": "overlay-item-price", "group": group, "tab": tab_id, "index": item_id},
                type="number",
                step="0.01",
                value=item.get("price"),
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
                value=item.get("name", ""),
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
                value=item.get("color") or default_color,
                className="overlay-color-input"
            ),
            width="auto"
        ),
        dbc.Col(
            dbc.Checklist(
                id={"type": "overlay-item-visible", "group": group, "tab": tab_id, "index": item_id},
                options=[{"label": "Visible", "value": "visible"}],
                value=["visible"] if item.get("visible", True) else [],
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


def _overlay_add_row(group: str, tab_id: str, default_color: str) -> dbc.Row:
    """Build the 'add new overlay item' input row for a chart."""
    return dbc.Row([
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


def _build_overlay_group_accordion(all_charts: dict, active_item: list, group: str,
                                   default_color: str, label: str) -> dbc.Accordion:
    """Build the accordion listing all charts' overlay items for one group (brackets or breaks)."""
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
        except Exception:
            pass

        rows = []
        if items:
            for item in items:
                rows.append(_overlay_item_row(group, tab_id, item, default_color))
        else:
            rows.append(html.Div("No entries yet.", className="overlay-empty"))

        rows.append(html.Hr(className="overlay-divider"))
        rows.append(html.Div(f"Add {label}", className="overlay-section-title mb-2"))
        rows.append(_overlay_add_row(group, tab_id, default_color))

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


def _apply_overlay_item_update(group, price_values, name_values, color_values, visible_values,
                               price_ids, name_ids, color_ids, visible_ids, overlays_data, tabs_data):
    """Shared logic for editing/deleting bracket and break overlay items.

    Returns the updated overlay store or dash.no_update.
    """
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
    items = tab_overlays.get(group, [])

    if action_type == "overlay-item-delete":
        tab_overlays[group] = [item for item in items if item.get("id") != item_id]
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

    save_overlays_to_db(overlays, tabs_data)
    return overlays


def register_overlay_modal_callbacks(app):
    """Trading overlay modal: open/close, list rendering, add/edit/delete items, shape dragging."""

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
                overlays_db = db.scalars(select(ChartOverlay)).all()
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

        brackets_view = _build_overlay_group_accordion(all_charts, active_item, "brackets", "#00ff88", "Bracket")
        breaks_view = _build_overlay_group_accordion(all_charts, active_item, "breaks", "#ff4444", "Break")
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
        return _apply_overlay_item_update(
            "brackets", price_values, name_values, color_values, visible_values,
            price_ids, name_ids, color_ids, visible_ids, overlays_data, tabs_data
        )

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
        return _apply_overlay_item_update(
            "breaks", price_values, name_values, color_values, visible_values,
            price_ids, name_ids, color_ids, visible_ids, overlays_data, tabs_data
        )

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
        tab_id, relayout_data = _get_triggered_relayout(relayout_data_list, graph_ids)
        if not relayout_data:
            return dash.no_update

        # Check if shapes were modified
        shape_updates = {}
        for key, value in relayout_data.items():
            if key.startswith("shapes[") and (key.endswith(".y0") or key.endswith(".y1")):
                # Extract shape index
                match = re.match(r"shapes\[(\d+)\]\.(y\d)", key)
                if match:
                    shape_idx = int(match.group(1))
                    y_coord = match.group(2)
                    shape_updates.setdefault(shape_idx, {})[y_coord] = value

        if not shape_updates:
            return dash.no_update

        # Update overlays
        overlays = normalize_overlay_store(copy.deepcopy(overlays_data))
        tab_overlays = overlays.get("tabs", {}).get(tab_id, {})

        # Collect all items to map shape index to overlay
        all_items = []
        for group in ["brackets", "breaks"]:
            for item in tab_overlays.get(group, []):
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
            save_overlays_to_db(overlays, tabs_data)
            return overlays
        return dash.no_update
