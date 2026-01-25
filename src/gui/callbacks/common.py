"""
Common callbacks: URL-tab routing, live status.
"""

from datetime import datetime

import dash
from dash import Input, Output, State, html

from src.gui.utils.routing import tab_from_hash


def register_common_callbacks(app):
    """Register URL-tab routing and live status callbacks."""

    @app.callback(
        Output("tabs", "active_tab", allow_duplicate=True),
        Input("url", "hash"),
        State("tabs", "active_tab"),
        prevent_initial_call=True,
    )
    def set_tab_from_url_hash_change(hash_val, current_tab):
        want = tab_from_hash(hash_val)
        if current_tab == want:
            return dash.no_update
        return want

    @app.callback(
        Output("tabs", "active_tab", allow_duplicate=True),
        Input("url-tab-startup", "n_intervals"),
        State("url", "hash"),
        State("tabs", "active_tab"),
        prevent_initial_call=True,
    )
    def set_tab_from_url_on_load(n_intervals, hash_val, current_tab):
        if not n_intervals:
            return dash.no_update
        want = tab_from_hash(hash_val)
        if current_tab == want:
            return dash.no_update
        return want

    @app.callback(
        Output("url", "hash"),
        Input("tabs", "active_tab"),
        State("url", "hash"),
        prevent_initial_call=True,
    )
    def set_url_from_tab(active_tab, current_hash):
        new_hash = "#%s" % (active_tab or "dashboard")
        if current_hash == new_hash:
            return dash.no_update
        return new_hash

    @app.callback(
        Output("live-status", "children"),
        Input("interval-component", "n_intervals"),
    )
    def update_live_status(n):
        now = datetime.now().strftime("%H:%M:%S")
        return html.Div([
            html.Span("● ", className="text-success"),
            html.Small("Live • Updated %s" % now),
        ])
