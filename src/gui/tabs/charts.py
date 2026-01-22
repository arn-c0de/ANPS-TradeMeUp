"""
Charts Tab - Live Market Data and Visualizations
"""

from dash import dcc, html
import dash_bootstrap_components as dbc
import plotly.graph_objects as go


def create_layout():
    """Create charts tab layout"""
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("📈 Market Data & Predictions")),
                    dbc.CardBody([
                        dbc.Label("Select Entity:"),
                        dcc.Dropdown(
                            id="chart-entity-selector",
                            placeholder="Select entity..."
                        ),
                        dcc.Graph(id="price-chart", style={"height": "400px"})
                    ])
                ])
            ], width=12)
        ], className="mb-3"),
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("🔥 Sentiment Heatmap")),
                    dbc.CardBody([
                        dcc.Graph(id="sentiment-heatmap")
                    ])
                ])
            ], width=6),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("🎯 Impact Distribution")),
                    dbc.CardBody([
                        dcc.Graph(id="impact-distribution")
                    ])
                ])
            ], width=6)
        ])
    ], fluid=True)


def get_placeholder_chart():
    """Create placeholder chart"""
    fig = go.Figure()
    fig.add_annotation(
        text="Chart will be populated with real data",
        xref="paper", yref="paper",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=16, color="gray")
    )
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    return fig
