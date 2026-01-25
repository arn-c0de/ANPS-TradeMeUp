"""
Chart tab callbacks. Register via register_charts_callbacks(app).
"""

import copy
import json
import logging
import time
import uuid

import dash
from dash import ALL, Input, Output, State

from src.gui.tabs.charts.fullscreen_manager import (
    create_fullscreen_state,
    get_container_classname,
    get_exit_button_style,
    get_fullscreen_state,
    get_toggle_button_config,
    toggle_fullscreen_state,
)
from src.gui.tabs.charts.overlay_utils import (
    load_overlays_from_db,
    normalize_overlay_store,
)

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

_CLIENTSCRIPT_CHART_RESIZE = """
function(chart_resize_trigger) {
    if (!chart_resize_trigger || !chart_resize_trigger.resize) {
        return window.dash_clientside.no_update;
    }
    
    const chartArea = document.getElementById('chart-display-area');
    if (!chartArea) return window.dash_clientside.no_update;
    
    // Optimized resize function - immediate resize, delayed redraw, overlay update
    function performResize() {
        if (!window.Plotly || !Plotly.Plots || !Plotly.Plots.resize) return;
        const graphs = chartArea.querySelectorAll('.js-plotly-plot');
        
        // Immediate resize for all charts
        graphs.forEach(graph => {
            if (graph && graph.offsetParent !== null) {
                try {
                    Plotly.Plots.resize(graph);
                    
                    // Update overlays after resize
                    const graphElement = graph.closest('[id*="chart-content"], .dash-graph') || graph.parentElement;
                    if (graphElement && window.ChartCenterLineOverlay && window.ChartCenterLineOverlay.create) {
                        try {
                            window.ChartCenterLineOverlay.create(graphElement, graph.id || '');
                        } catch (err) {
                            // ignore overlay errors
                        }
                    }
                } catch (err) {
                    // ignore resize errors for detached nodes
                }
            }
        });
        
        // Single delayed redraw after resize settles (for content rendering)
        setTimeout(function() {
            graphs.forEach(graph => {
                if (graph && graph.offsetParent !== null && Plotly.redraw) {
                    try {
                        Plotly.redraw(graph);
                    } catch (err) {
                        // ignore redraw errors
                    }
                }
            });
        }, 100);
    }
    
    // Use requestAnimationFrame for optimal performance
    if (window.requestAnimationFrame) {
        window.requestAnimationFrame(performResize);
    } else {
        // Fallback for older browsers
        setTimeout(performResize, 0);
    }
    
    return window.dash_clientside.no_update;
}
"""


def register_charts_callbacks(app):
    """Register all chart tab callbacks (including ESC, fullscreen, quad mode)."""

    app.clientside_callback(
        _CLIENTSCRIPT_ESC,
        Output("esc-key-listener", "value", allow_duplicate=True),
        Input("chart-fullscreen-state", "data"),
        prevent_initial_call="initial_duplicate",
    )

    app.clientside_callback(
        _CLIENTSCRIPT_CHART_RESIZE,
        Output("chart-resize-trigger", "data", allow_duplicate=True),
        Input("chart-resize-trigger", "data"),
        prevent_initial_call="initial_duplicate",
    )

    @app.callback(
        Output("chart-display-area", "className"),
        Input("chart-fullscreen-state", "data"),
        prevent_initial_call=False,
    )
    def update_chart_display_classname(fullscreen_data):
        is_fullscreen = get_fullscreen_state(fullscreen_data)
        return get_container_classname(is_fullscreen)

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
        if (
            ("exit-fullscreen-btn" in trigger and exit_clicks)
            or ("esc-key-listener" in trigger and esc_value)
        ):
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
        is_fullscreen = get_fullscreen_state(fullscreen_data)
        btn_text, btn_color = get_toggle_button_config(is_fullscreen)
        exit_style = get_exit_button_style(is_fullscreen)
        return btn_text, btn_color, exit_style

    @app.callback(
        [Output("layout-single", "outline"), Output("layout-quad", "outline")],
        Input("quad-mode-store", "data"),
    )
    def highlight_active_layout_mode(quad_data):
        quad_enabled = quad_data.get("enabled", False)
        return (quad_enabled, not quad_enabled)

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
        from dash import callback_context

        if not tabs_data or not tabs_data.get("tabs"):
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
        tabs = tabs_data["tabs"]
        old_to_new_id_map = {}
        migrated = False
        for tab in tabs:
            tab_id = tab.get("id", "")
            symbol = tab.get("symbol", "")
            if symbol and not (f"-{symbol}-" in tab_id or tab_id.startswith(f"tab-{symbol}-")):
                new_id = f"tab-{symbol}-{uuid.uuid4().hex[:8]}"
                old_to_new_id_map[tab_id] = new_id
                tab["id"] = new_id
                migrated = True
        if not migrated:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
        active_tab = tabs_data.get("active_tab")
        if active_tab in old_to_new_id_map:
            tabs_data["active_tab"] = old_to_new_id_map[active_tab]
        tabs_data["tabs"] = tabs
        logger.info("Migrated %d tab IDs: %s", len(old_to_new_id_map), old_to_new_id_map)
        overlays_updated = copy.deepcopy(overlays_data) if overlays_data else {"tabs": {}}
        interaction_modes_updated = copy.deepcopy(interaction_modes) if interaction_modes else {"tabs": {}}
        view_state_updated = copy.deepcopy(view_state) if view_state else {"tabs": {}}
        quad_data_updated = copy.deepcopy(quad_data) if quad_data else {"enabled": False, "selected_tabs": []}
        stores_updated = False
        if overlays_updated.get("tabs"):
            for old_id, new_id in old_to_new_id_map.items():
                if old_id in overlays_updated["tabs"]:
                    overlays_updated["tabs"][new_id] = overlays_updated["tabs"].pop(old_id)
                    stores_updated = True
        if interaction_modes_updated.get("tabs"):
            for old_id, new_id in old_to_new_id_map.items():
                if old_id in interaction_modes_updated["tabs"]:
                    interaction_modes_updated["tabs"][new_id] = interaction_modes_updated["tabs"].pop(old_id)
                    stores_updated = True
        if view_state_updated.get("tabs"):
            for old_id, new_id in old_to_new_id_map.items():
                if old_id in view_state_updated["tabs"]:
                    view_state_updated["tabs"][new_id] = view_state_updated["tabs"].pop(old_id)
                    stores_updated = True
        if quad_data_updated.get("selected_tabs"):
            updated_selected = []
            for tab_id in quad_data_updated["selected_tabs"]:
                updated_selected.append(old_to_new_id_map.get(tab_id, tab_id))
                if tab_id in old_to_new_id_map:
                    stores_updated = True
            quad_data_updated["selected_tabs"] = updated_selected
        if stores_updated:
            logger.info("Updated related stores with new tab IDs")
        return (
            tabs_data,
            overlays_updated if stores_updated else dash.no_update,
            interaction_modes_updated if stores_updated else dash.no_update,
            view_state_updated if stores_updated else dash.no_update,
            quad_data_updated if stores_updated else dash.no_update,
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
                mapped_overlays = {"tabs": {}}
                for tab in tabs:
                    tab_id = tab.get("id")
                    symbol = tab.get("symbol")
                    timeframe = tab.get("timeframe")
                    db_key = f"{symbol}_{timeframe}"
                    if db_key in overlays["tabs"]:
                        mapped_overlays["tabs"][tab_id] = overlays["tabs"][db_key]
                overlays = mapped_overlays
            else:
                overlays = {"tabs": {}}
        else:
            overlays = normalize_overlay_store(copy.deepcopy(overlays_data))
        tabs = tabs_data.get("tabs", []) if isinstance(tabs_data, dict) else []
        tab_ids = {tab.get("id") for tab in tabs if tab.get("id")}
        changed = False
        for tab_id in tab_ids:
            if tab_id not in overlays["tabs"]:
                overlays["tabs"][tab_id] = {"brackets": [], "breaks": []}
                changed = True
            else:
                entry = overlays["tabs"][tab_id]
                if not isinstance(entry, dict):
                    overlays["tabs"][tab_id] = {"brackets": [], "breaks": []}
                    changed = True
                else:
                    if "brackets" not in entry:
                        entry["brackets"] = []
                        changed = True
                    if "breaks" not in entry:
                        entry["breaks"] = []
                        changed = True
        for tab_id in list(overlays["tabs"].keys()):
            if tab_id not in tab_ids:
                overlays["tabs"].pop(tab_id, None)
                changed = True
        return overlays if changed else dash.no_update

    @app.callback(
        Output("chart-resize-trigger", "data", allow_duplicate=True),
        Input("tabs", "active_tab"),
        prevent_initial_call=True,
    )
    def handle_charts_tab_activation(active_tab):
        """Trigger chart resize when charts tab becomes active."""
        if active_tab == "charts":
            return {"resize": True, "timestamp": time.time()}
        return dash.no_update

    @app.callback(
        Output("chart-resize-trigger", "data", allow_duplicate=True),
        Input("chart-tabs-store", "data"),
        State("chart-resize-trigger", "data"),
        prevent_initial_call=True,
    )
    def handle_chart_tab_change(tabs_data, current_trigger):
        """Trigger chart resize when chart tab changes."""
        from dash import callback_context

        if not callback_context.triggered:
            return dash.no_update

        # Only trigger if active_tab changed (not other properties)
        trigger_id = callback_context.triggered[0]["prop_id"]
        if trigger_id == "chart-tabs-store.data" and tabs_data:
            active_tab = tabs_data.get("active_tab")
            if active_tab:
                return {"resize": True, "timestamp": time.time()}

        return dash.no_update

    @app.callback(
        Output("chart-resize-trigger", "data", allow_duplicate=True),
        Input("quad-mode-store", "data"),
        prevent_initial_call=True,
    )
    def handle_layout_mode_change(quad_data):
        """Trigger chart resize when layout mode changes (single/quad)."""
        if quad_data is not None:
            return {"resize": True, "timestamp": time.time()}
        return dash.no_update
