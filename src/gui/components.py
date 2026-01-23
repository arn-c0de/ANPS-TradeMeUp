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
                        html.H3("📊 TradeMeUp v1.0.2", className="text-primary mb-0"),
                        html.Small("AI Trading Intelligence Platform", className="text-muted")
                    ])
                ], width="auto"),
                dbc.Col([
                    dbc.ButtonGroup([
                        dbc.Button(
                            [html.I(className="bi bi-download me-2"), "Fetch RSS"],
                            id="btn-fetch-rss-only",
                            color="info",
                            size="sm",
                            className="me-2",
                            title="Fetch news from RSS feeds only (no AI analysis)"
                        ),
                        dbc.Button(
                            [html.I(className="bi bi-play-fill me-2"), "Start Auto"],
                            id="btn-start-continuous",
                            color="success",
                            size="sm",
                            className="me-2"
                        ),
                        dbc.Button(
                            [html.I(className="bi bi-stop-fill me-2"), "Stop Auto"],
                            id="btn-stop-continuous",
                            color="danger",
                            size="sm",
                            disabled=True,
                            className="me-2"
                        ),
                        dbc.Button(
                            [html.I(className="bi bi-gear-fill me-2"), "Settings"],
                            id="btn-open-settings",
                            color="secondary",
                            size="sm",
                            outline=True
                        )
                    ])
                ], width="auto", className="ms-auto"),
            ], align="center", className="g-0 w-100"),
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Div(id="continuous-status", className="me-3"),
                        html.Div(id="live-status")
                    ], className="d-flex align-items-center")
                ], className="text-end")
            ], align="center")
        ], fluid=True),
        color="dark",
        dark=True,
        className="mb-4"
    )
