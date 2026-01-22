"""
Shared GUI components for TradeMeUp Dashboard
"""

import dash_bootstrap_components as dbc
from dash import html


def create_metric_card(title, value, subtitle="", icon="📈", color="primary"):
    """Create a metric display card"""
    return dbc.Card([
        dbc.CardBody([
            html.Div([
                html.Span(icon, className="fs-2 me-3"),
                html.Div([
                    html.H6(title, className="text-muted mb-1"),
                    html.H3(value, className=f"text-{color} mb-0"),
                    html.Small(subtitle, className="text-muted") if subtitle else None
                ], className="d-inline-block")
            ], className="d-flex align-items-center")
        ])
    ], className="mb-3")


def create_navbar():
    """Create navigation bar"""
    return dbc.Navbar(
        dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.H3("📊 TradeMeUp", className="text-primary mb-0"),
                        html.Small("AI Trading Intelligence Platform", className="text-muted")
                    ])
                ], width="auto"),
            ], align="center", className="g-0"),
            dbc.Row([
                dbc.Col([
                    html.Div(id="live-status", className="text-end")
                ], width="auto")
            ], align="center")
        ], fluid=True),
        color="dark",
        dark=True,
        className="mb-4"
    )
