"""Chart tab callbacks: config / quick-edit / favorites modals."""

import json

import dash
import dash_bootstrap_components as dbc
from dash import ALL, Input, Output, State, callback_context, html

# The shared provider singleton, not a per-module instance.
from src.services.market_data import market_data

from ._shared import _search_entity_symbols


def register_config_modal_callbacks(app):
    """Panel configuration modal, quick symbol edit, live symbol search, favorites modal."""

    @app.callback(
        Output("config-symbol-input", "options"),
        Input("config-symbol-input", "search_value"),
        prevent_initial_call=True
    )
    def search_config_symbols(search_value):
        """Search for symbols and company names in Entity database."""
        if not search_value or len(search_value) < 1:
            return []
        return _search_entity_symbols(search_value)

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
        """Toggle configuration modal and populate with panel data."""
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
            raise dash.exceptions.PreventUpdate

        # Close modal
        if 'cancel-btn' in trigger_id or 'apply-btn' in trigger_id:
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
        """Toggle quick edit modal when clicking on symbol name."""
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
            raise dash.exceptions.PreventUpdate

        # Close modal
        if 'cancel-btn' in trigger_id or 'apply-btn' in trigger_id:
            return False, None, ""

        raise dash.exceptions.PreventUpdate

    @app.callback(
        [Output("symbol-search-results", "children"),
         Output("symbol-search-cache", "data")],
        Input("quick-edit-symbol-input", "value"),
        prevent_initial_call=True
    )
    def search_symbols_live(query):
        """Search for stock symbols as user types (live search)."""
        if not query or len(query) < 1:
            return html.Div([
                html.Small("💡 Start typing to search symbols by ticker or company name",
                          className="text-muted")
            ]), []

        try:
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
        """Update input when user clicks on a search result."""
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
        """Apply symbol change from quick edit modal."""
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
        """Toggle favorites modal and show favorite symbols."""
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

        if 'close-btn' in trigger_id:
            return False, []

        return is_open, []
