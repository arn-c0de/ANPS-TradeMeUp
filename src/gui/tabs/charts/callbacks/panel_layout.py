"""Chart tab callbacks: multi-panel layout (panel config, rendering, refresh interval, interaction mode)."""

import copy
import json
import logging

import dash
from dash import ALL, Input, Output, State, callback_context, html

from src.gui.tabs.charts.components import (
    render_multi_panel_layout,
)
from src.gui.tabs.charts.fullscreen_manager import get_container_classname, get_fullscreen_state

# The shared provider singleton, not a per-module instance.

logger = logging.getLogger(__name__)


def register_panel_layout_callbacks(app):
    """Panel configuration store, multi-panel rendering, refresh interval, zoom/pan toggle."""

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
        """Update chart panels configuration."""
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
        """Update multi-panel chart area className based on fullscreen state."""
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
         Input("chart-loaded-data-store", "data")],  # Listen to loaded data changes
        prevent_initial_call='initial_duplicate'
    )
    def render_chart_panels(config, n_intervals, refresh_clicks, overlays_data, fullscreen_state, interaction_modes, view_state_data, loaded_data_store):
        """Render the multi-panel chart layout with fullscreen support."""
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
            return render_multi_panel_layout(layout, panels, is_fullscreen, overlays_data, view_state_data, loaded_data_store)
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
        timeframes = [panel_config.get('timeframe', '1mo') for panel_config in panels.values()]

        if not timeframes:
            return True, 60000  # Disabled if no panels

        # Determine refresh interval based on shortest timeframe
        # Priority: 1-minute > 5-minute > disabled
        if any(tf == '1d_1m' for tf in timeframes):
            return False, 60000  # 1-minute charts: refresh every 60 seconds
        if any(tf == '5d_5m' for tf in timeframes):
            return False, 300000  # 5-minute charts: refresh every 5 minutes
        return True, 60000  # Longer timeframes: disable auto-refresh

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
        """Toggle between zoom and pan mode for charts."""
        if not callback_context.triggered or not any(n_clicks_list):
            return dash.no_update

        # Get the clicked button's panel/tab ID
        trigger_id = callback_context.triggered[0]["prop_id"].split(".")[0]
        button_id = json.loads(trigger_id)
        panel_id = button_id.get("index")

        if not panel_id:
            return dash.no_update

        # Initialize modes data if needed
        modes = copy.deepcopy(modes_data) if modes_data else {'tabs': {}}
        if 'tabs' not in modes:
            modes['tabs'] = {}

        # Toggle between zoom and pan (default: zoom)
        current_mode = modes['tabs'].get(panel_id, {}).get('dragmode', 'zoom')
        new_mode = 'pan' if current_mode == 'zoom' else 'zoom'

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
