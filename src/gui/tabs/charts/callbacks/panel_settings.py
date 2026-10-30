"""Chart tab callbacks: panel settings modal + misc UI toggles."""

import json

import dash
from dash import Input, Output, State, callback_context
from dash.exceptions import PreventUpdate

# The shared provider singleton, not a per-module instance.


def register_panel_settings_callbacks(app):
    """Panel settings modal, quad panel focus, market overview toggle, refresh bridge."""

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
        """Open/close panel settings modal and load current settings."""
        if not callback_context.triggered:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

        trigger = callback_context.triggered[0]['prop_id']

        # Close modal
        if 'cancel' in trigger or 'apply' in trigger:
            return False, None, dash.no_update, dash.no_update, dash.no_update

        # Open modal - load settings for clicked panel (only if settings button was actually clicked)
        if 'panel-settings-btn' in trigger and any(settings_clicks):
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
        """Apply settings to the selected panel/tab."""
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

    @app.callback(
        Output("chart-tabs-store", "data", allow_duplicate=True),
        Input({"type": "quad-panel", "index": dash.ALL}, "n_clicks"),
        State("chart-tabs-store", "data"),
        prevent_initial_call=True
    )
    def focus_tab_on_quad_panel_click(n_clicks_list, tabs_data):
        """Focus the corresponding tab when a quad panel is clicked (but not settings button)."""
        if not callback_context.triggered or not any(n_clicks_list):
            return dash.no_update

        # Get the clicked panel's tab ID
        trigger = callback_context.triggered[0]['prop_id']

        # Don't focus if a settings button was clicked - check if trigger is exactly quad-panel
        if 'quad-panel' in trigger and 'panel-settings-btn' not in trigger:
            try:
                trigger_dict = json.loads(trigger.split('.')[0])
                clicked_tab_id = trigger_dict['index']

                # Update active tab
                tabs_data['active_tab'] = clicked_tab_id
                return tabs_data
            except Exception:
                return dash.no_update

        return dash.no_update

    @app.callback(
        Output("market-overview-collapse", "is_open"),
        Input("toggle-market-overview", "n_clicks"),
        State("market-overview-collapse", "is_open"),
        prevent_initial_call=True
    )
    def toggle_market_overview(n_clicks, is_open):
        """Toggle market overview section."""
        return not is_open

    @app.callback(
        Output("refresh-all-panels", "n_clicks"),
        Input("refresh-all-panels-btn", "n_clicks"),
        State("refresh-all-panels", "n_clicks"),
        prevent_initial_call=True
    )
    def bridge_refresh(btn_clicks, hidden_clicks):
        """Propagate clicks from visible button to global hidden refresh trigger."""
        if not btn_clicks:
            raise PreventUpdate
        return (hidden_clicks or 0) + 1
