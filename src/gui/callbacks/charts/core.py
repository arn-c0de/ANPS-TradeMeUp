"""
Chart tab core callbacks: ESC, fullscreen, quad mode, open-ticker, migrate IDs, sync overlays.
"""

import copy
import json
import logging
import uuid

import dash
from dash import ALL, Input, Output, State

from src.gui.charts.fullscreen_manager import (
    create_fullscreen_state,
    get_container_classname,
    get_exit_button_style,
    get_fullscreen_state,
    get_toggle_button_config,
    toggle_fullscreen_state,
)
from src.gui.charts.overlay_utils import load_overlays_from_db, normalize_overlay_store

logger = logging.getLogger(__name__)

_CLIENTSCRIPT_ESC = """
function(fullscreen_data) {
    if (window.escKeyHandler) {
        document.removeEventListener('keydown', window.escKeyHandler);
        window.escKeyHandler = null;
    }
    if (fullscreen_data && fullscreen_data.fullscreen) {
        window.escKeyHandler = function(event) {
            if (event.key === 'Escape' || event.key === 'Esc') {
                if (document.querySelectorAll('.modal.show').length > 0) return;
                event.preventDefault();
                event.stopPropagation();
                var exitBtn = document.getElementById('exit-fullscreen-btn');
                if (exitBtn) exitBtn.click();
                else {
                    var escInput = document.getElementById('esc-key-listener');
                    if (escInput) {
                        escInput.value = Date.now().toString();
                        escInput.dispatchEvent(new Event('input', { bubbles: true }));
                        escInput.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }
            }
        };
        document.addEventListener('keydown', window.escKeyHandler, true);
    }
    return window.dash_clientside.no_update;
}
"""


def register_charts_core(app):
    """Register core chart callbacks (ESC, fullscreen, quad, open-ticker, migrate, sync)."""
    app.clientside_callback(
        _CLIENTSCRIPT_ESC,
        Output("esc-key-listener", "value", allow_duplicate=True),
        Input("chart-fullscreen-state", "data"),
        prevent_initial_call="initial_duplicate",
    )

    @app.callback(
        Output("chart-display-area", "className"),
        Input("chart-fullscreen-state", "data"),
        prevent_initial_call=False,
    )
    def update_chart_display_classname(fullscreen_data):
        return get_container_classname(get_fullscreen_state(fullscreen_data))

    @app.callback(
        Output("quad-mode-store", "data"),
        [Input("layout-single", "n_clicks"), Input("layout-quad", "n_clicks")],
        State("quad-mode-store", "data"),
        prevent_initial_call=True,
    )
    def toggle_quad_mode(single_click, quad_click, quad_data):
        from dash import callback_context

        if not callback_context.triggered:
            return dash.no_update
        if quad_data is None:
            quad_data = {"enabled": False, "selected_tabs": []}
        trigger_id = callback_context.triggered[0]["prop_id"].split(".")[0]
        if trigger_id == "layout-single" and single_click and single_click > 0:
            quad_data["enabled"] = False
        elif trigger_id == "layout-quad" and quad_click and quad_click > 0:
            quad_data["enabled"] = True
        else:
            return dash.no_update
        return quad_data

    @app.callback(
        Output("chart-fullscreen-state", "data"),
        [
            Input("toggle-fullscreen-btn", "n_clicks"),
            Input("exit-fullscreen-btn", "n_clicks"),
            Input("esc-key-listener", "value"),
        ],
        State("chart-fullscreen-state", "data"),
        prevent_initial_call=True,
    )
    def set_fullscreen_state(toggle_clicks, exit_clicks, esc_value, current_state):
        from dash import callback_context

        if not callback_context.triggered:
            return dash.no_update
        trigger = callback_context.triggered[0]["prop_id"]
        if "toggle-fullscreen-btn" in trigger and toggle_clicks:
            return toggle_fullscreen_state(current_state)
        if ("exit-fullscreen-btn" in trigger and exit_clicks) or ("esc-key-listener" in trigger and esc_value):
            if get_fullscreen_state(current_state):
                return create_fullscreen_state(False)
        return dash.no_update

    @app.callback(
        [
            Output("toggle-fullscreen-btn", "children"),
            Output("toggle-fullscreen-btn", "color"),
            Output("exit-fullscreen-btn", "style"),
        ],
        Input("chart-fullscreen-state", "data"),
        prevent_initial_call="initial_duplicate",
    )
    def update_fullscreen_ui(fullscreen_data):
        is_fs = get_fullscreen_state(fullscreen_data)
        btn_text, btn_color = get_toggle_button_config(is_fs)
        return btn_text, btn_color, get_exit_button_style(is_fs)

    @app.callback(
        [Output("layout-single", "outline"), Output("layout-quad", "outline")],
        Input("quad-mode-store", "data"),
    )
    def highlight_active_layout_mode(quad_data):
        en = quad_data.get("enabled", False)
        return (en, not en)

    @app.callback(
        [
            Output("tabs", "active_tab", allow_duplicate=True),
            Output("chart-tabs-store", "data", allow_duplicate=True),
            Output("prediction-modal", "is_open", allow_duplicate=True),
        ],
        Input({"type": "open-chart-btn", "index": ALL}, "n_clicks"),
        [State({"type": "open-chart-btn", "index": ALL}, "id"), State("chart-tabs-store", "data")],
        prevent_initial_call=True,
    )
    def open_ticker_in_charts(n_clicks_list, button_ids, tabs_data):
        from dash import callback_context

        if not callback_context.triggered or not any(n_clicks_list):
            return dash.no_update, dash.no_update, dash.no_update
        triggered_id = callback_context.triggered[0]["prop_id"].split(".")[0]
        button_id = json.loads(triggered_id)
        ticker = button_id["index"]
        existing_tab = None
        for tab in tabs_data.get("tabs", []):
            if tab["symbol"] == ticker:
                existing_tab = tab["id"]
                break
        if existing_tab:
            tabs_data["active_tab"] = existing_tab
        else:
            new_tab_id = f"tab-{ticker}-{uuid.uuid4().hex[:8]}"
            new_tab = {"id": new_tab_id, "symbol": ticker, "timeframe": "1mo", "chart_type": "candlestick"}
            tabs_data["tabs"].append(new_tab)
            tabs_data["active_tab"] = new_tab_id
        return "charts", tabs_data, dash.no_update

    @app.callback(
        [
            Output("chart-tabs-store", "data", allow_duplicate=True),
            Output("chart-overlays-store", "data", allow_duplicate=True),
            Output("chart-interaction-modes", "data", allow_duplicate=True),
            Output("chart-view-state", "data", allow_duplicate=True),
            Output("quad-mode-store", "data", allow_duplicate=True),
        ],
        Input("url", "pathname"),
        [
            State("chart-tabs-store", "data"),
            State("chart-overlays-store", "data"),
            State("chart-interaction-modes", "data"),
            State("chart-view-state", "data"),
            State("quad-mode-store", "data"),
        ],
        prevent_initial_call="initial_duplicate",
    )
    def migrate_tab_ids(pathname, tabs_data, overlays_data, interaction_modes, view_state, quad_data):
        if not tabs_data or not tabs_data.get("tabs"):
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
        tabs = tabs_data["tabs"]
        old_to_new = {}
        migrated = False
        for tab in tabs:
            tid = tab.get("id", "")
            sym = tab.get("symbol", "")
            if sym and not (f"-{sym}-" in tid or tid.startswith(f"tab-{sym}-")):
                nid = f"tab-{sym}-{uuid.uuid4().hex[:8]}"
                old_to_new[tid] = nid
                tab["id"] = nid
                migrated = True
        if not migrated:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
        if tabs_data.get("active_tab") in old_to_new:
            tabs_data["active_tab"] = old_to_new[tabs_data["active_tab"]]
        tabs_data["tabs"] = tabs
        logger.info("Migrated %d tab IDs: %s", len(old_to_new), old_to_new)
        ov = copy.deepcopy(overlays_data) if overlays_data else {"tabs": {}}
        im = copy.deepcopy(interaction_modes) if interaction_modes else {"tabs": {}}
        vs = copy.deepcopy(view_state) if view_state else {"tabs": {}}
        qd = copy.deepcopy(quad_data) if quad_data else {"enabled": False, "selected_tabs": []}
        changed = False
        for oid, nid in old_to_new.items():
            if ov.get("tabs") and oid in ov["tabs"]:
                ov["tabs"][nid] = ov["tabs"].pop(oid)
                changed = True
            if im.get("tabs") and oid in im["tabs"]:
                im["tabs"][nid] = im["tabs"].pop(oid)
                changed = True
            if vs.get("tabs") and oid in vs["tabs"]:
                vs["tabs"][nid] = vs["tabs"].pop(oid)
                changed = True
        if qd.get("selected_tabs"):
            qd["selected_tabs"] = [old_to_new.get(t, t) for t in qd["selected_tabs"]]
            changed = True
        return (
            tabs_data,
            ov if changed else dash.no_update,
            im if changed else dash.no_update,
            vs if changed else dash.no_update,
            qd if changed else dash.no_update,
        )

    @app.callback(
        Output("chart-overlays-store", "data"),
        Input("chart-tabs-store", "data"),
        State("chart-overlays-store", "data"),
    )
    def sync_chart_overlays(tabs_data, overlays_data):
        if not overlays_data or not overlays_data.get("tabs"):
            logger.info("Loading overlays from database...")
            overlays = load_overlays_from_db()
            if overlays and overlays.get("tabs"):
                logger.info("Loaded %d overlay groups from DB", len(overlays["tabs"]))
                tabs = tabs_data.get("tabs", []) if isinstance(tabs_data, dict) else []
                mapped = {"tabs": {}}
                for tab in tabs:
                    tid, sym, tf = tab.get("id"), tab.get("symbol"), tab.get("timeframe")
                    k = f"{sym}_{tf}"
                    if k in overlays["tabs"]:
                        mapped["tabs"][tid] = overlays["tabs"][k]
                overlays = mapped
            else:
                overlays = {"tabs": {}}
        else:
            overlays = normalize_overlay_store(copy.deepcopy(overlays_data))
        tabs = tabs_data.get("tabs", []) if isinstance(tabs_data, dict) else []
        tab_ids = {t.get("id") for t in tabs if t.get("id")}
        changed = False
        for tid in tab_ids:
            if tid not in overlays["tabs"]:
                overlays["tabs"][tid] = {"brackets": [], "breaks": []}
                changed = True
            else:
                e = overlays["tabs"][tid]
                if not isinstance(e, dict):
                    overlays["tabs"][tid] = {"brackets": [], "breaks": []}
                    changed = True
                else:
                    if "brackets" not in e:
                        e["brackets"] = []
                        changed = True
                    if "breaks" not in e:
                        e["breaks"] = []
                        changed = True
        for tid in list(overlays["tabs"].keys()):
            if tid not in tab_ids:
                overlays["tabs"].pop(tid, None)
                changed = True
        return overlays if changed else dash.no_update
