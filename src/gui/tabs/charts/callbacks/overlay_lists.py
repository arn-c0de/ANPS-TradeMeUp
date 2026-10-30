"""Chart tab callbacks: per-panel overlay lists and panel refresh."""

import copy
import json
import logging

import dash
from dash import ALL, MATCH, Input, Output, State, callback_context, html

from src.gui.tabs.charts.components import (
    create_overlay_list,
    get_stock_chart_with_stats,
)

# The shared provider singleton, not a per-module instance.

logger = logging.getLogger(__name__)


def register_overlay_list_callbacks(app):
    """Per-panel overlay list rendering, centering on an overlay line, panel refresh."""

    @app.callback(
        Output({"type": "overlay-list", "index": MATCH}, "children"),
        [Input("chart-overlays-store", "data"),
         Input("chart-panels-config", "data")],
        [State({"type": "overlay-list", "index": MATCH}, "id")],
        prevent_initial_call=False
    )
    def update_overlay_list(overlays_data, panels_config, list_id):
        """Update overlay list when overlays change."""
        if not list_id or not panels_config:
            return html.Div("No overlays", style={'padding': '2px 4px', 'fontSize': '0.65rem', 'color': '#888', 'fontStyle': 'italic'})

        panel_id = list_id.get('index')
        if not panel_id:
            return dash.no_update

        # Get panel config to get symbol and timeframe
        panel_config = panels_config.get('panels', {}).get(panel_id, {})
        symbol = panel_config.get('symbol')
        timeframe = panel_config.get('timeframe')

        if not symbol:
            return html.Div("No symbol", style={'padding': '2px 4px', 'fontSize': '0.65rem', 'color': '#888', 'fontStyle': 'italic'})

        # Ensure overlays_data has proper structure if None or empty
        if not overlays_data:
            overlays_data = {'tabs': {}}

        # Create overlay list using the helper function with timeframe
        return create_overlay_list(panel_id, symbol, overlays_data, timeframe)

    @app.callback(
        Output("chart-view-state", "data", allow_duplicate=True),
        Input({"type": "overlay-list-item", "index": ALL, "overlay_id": ALL}, "n_clicks"),
        [State({"type": "overlay-list-item", "index": ALL, "overlay_id": ALL}, "id"),
         State("chart-overlays-store", "data"),
         State("chart-panels-config", "data"),
         State("chart-view-state", "data")],
        prevent_initial_call=True
    )
    def center_overlay_line(n_clicks_list, item_ids, overlays_data, panels_config, view_state_data):
        """Center chart on overlay line when clicked."""
        if not callback_context.triggered:
            return dash.no_update

        # Find which item was clicked
        triggered = callback_context.triggered[0]
        trigger_prop = triggered["prop_id"]

        if not trigger_prop or not trigger_prop.startswith('{"'):
            return dash.no_update

        try:
            trigger_id = json.loads(trigger_prop.split('.')[0])
            panel_id = trigger_id.get('index')
            overlay_id = trigger_id.get('overlay_id')

            if not panel_id or not overlay_id:
                return dash.no_update

            # Get overlay data
            panel_overlays = overlays_data.get('tabs', {}).get(panel_id, {})
            brackets = panel_overlays.get('brackets', []) or []
            breaks = panel_overlays.get('breaks', []) or []

            # Find the clicked overlay
            clicked_overlay = None
            for item in brackets + breaks:
                if str(item.get('id', '')) == str(overlay_id):
                    clicked_overlay = item
                    break

            if not clicked_overlay:
                return dash.no_update

            price = clicked_overlay.get('price')
            if price is None:
                return dash.no_update

            try:
                price_value = float(price)
            except (TypeError, ValueError):
                return dash.no_update

            # Calculate y-axis range centered on price (±5% range)
            range_percent = 0.05  # 5% above and below
            y_min = price_value * (1 - range_percent)
            y_max = price_value * (1 + range_percent)

            # Update view state
            state = copy.deepcopy(view_state_data) if view_state_data else {'tabs': {}}
            if 'tabs' not in state:
                state['tabs'] = {}

            if panel_id not in state['tabs']:
                state['tabs'][panel_id] = {}

            state['tabs'][panel_id]['yaxis_range'] = [y_min, y_max]

            logger.debug(f"[Overlay List] Centering chart {panel_id} on price {price_value}")
            return state

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Error centering overlay line: {e}", exc_info=True)
            return dash.no_update

    @app.callback(
        Output({"type": "chart-content", "index": MATCH}, "children"),
        Input({"type": "refresh-btn", "index": MATCH}, "n_clicks"),
        [State({"type": "chart-content", "index": MATCH}, "id"),
         State("chart-panels-config", "data")],
        prevent_initial_call=True
    )
    def refresh_individual_panel(n_clicks, component_id, panels_config):
        """Refresh individual chart panel."""
        panel_id = component_id['index']
        panel_config = panels_config.get('panels', {}).get(panel_id, {})

        symbol = panel_config.get('symbol', 'AAPL')
        timeframe = panel_config.get('timeframe', '1mo')
        chart_type = panel_config.get('chart_type', 'candlestick')

        return get_stock_chart_with_stats(symbol, timeframe, chart_type)
