"""
Statistics Tab - Layout Definition
"""

import dash_bootstrap_components as dbc
from dash import dcc, html


def create_layout():
    """Create statistics tab layout"""
    return dbc.Container([
        # Time Period Filter (compact control section)
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.Small("Granularity:", className="text-muted mb-1 d-block", style={"fontSize": "0.7em"}),
                                dcc.Dropdown(
                                    id="stats-granularity",
                                    options=[
                                        {"label": "Minutes", "value": "minutes"},
                                        {"label": "Days", "value": "days"},
                                        {"label": "Weeks", "value": "weeks"},
                                        {"label": "Months", "value": "months"},
                                        {"label": "Years", "value": "years"},
                                        {"label": "All Time", "value": "all"}
                                    ],
                                    value="all",
                                    clearable=False,
                                    style={"fontSize": "0.75em"}
                                )
                            ], width=2),
                            dbc.Col([
                                html.Small("Date Range:", className="text-muted mb-1 d-block", style={"fontSize": "0.7em"}),
                                dcc.DatePickerRange(
                                    id="stats-date-range",
                                    start_date=None,
                                    end_date=None,
                                    display_format="YYYY-MM-DD",
                                    style={"fontSize": "0.75em"}
                                )
                            ], width=2),
                            dbc.Col([
                                html.Small("Quick Select:", className="text-muted mb-1 d-block", style={"fontSize": "0.7em"}),
                                dbc.ButtonGroup([
                                    dbc.Button("1h", id="quick-1h", size="sm", outline=True, color="primary", style={"fontSize": "0.7em"}),
                                    dbc.Button("12h", id="quick-12h", size="sm", outline=True, color="primary", style={"fontSize": "0.7em"}),
                                    dbc.Button("24h", id="quick-24h", size="sm", outline=True, color="primary", style={"fontSize": "0.7em"}),
                                    dbc.Button("7d", id="quick-7d", size="sm", outline=True, color="primary", style={"fontSize": "0.7em"}),
                                    dbc.Button("30d", id="quick-30d", size="sm", outline=True, color="primary", style={"fontSize": "0.7em"}),
                                    dbc.Button("90d", id="quick-90d", size="sm", outline=True, color="primary", style={"fontSize": "0.7em"}),
                                    dbc.Button("1y", id="quick-1y", size="sm", outline=True, color="primary", style={"fontSize": "0.7em"}),
                                    dbc.Button("All", id="quick-all", size="sm", outline=True, color="primary", style={"fontSize": "0.7em"})
                                ], size="sm")
                            ], width=5),
                            dbc.Col([
                                html.Small("Custom (h):", className="text-muted mb-1 d-block", style={"fontSize": "0.7em"}),
                                dbc.Input(
                                    id="custom-hours-input",
                                    type="number",
                                    placeholder="e.g. 6",
                                    min=1,
                                    max=8760,
                                    debounce=True,
                                    size="sm",
                                    style={"fontSize": "0.75em"}
                                )
                            ], width=2),
                            dbc.Col([
                                html.Small("\u00a0", className="mb-1 d-block", style={"fontSize": "0.7em"}),
                                dbc.Button(
                                    "Reset",
                                    id="stats-reset-filter",
                                    size="sm",
                                    color="secondary",
                                    outline=True,
                                    className="w-100",
                                    style={"fontSize": "0.75em"}
                                )
                            ], width=1)
                        ], className="g-2")
                    ], className="py-2 px-3")
                ], className="border-primary", style={"borderWidth": "1px"})
            ], width=12)
        ], className="mb-2"),

        # Overall Metrics (compact top bar)
        dbc.Row([
            dbc.Col([
                html.Div(id="statistics-metrics")
            ], width=12)
        ], className="mb-2"),
        
        # Event & Quality Distribution
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("📈 Event Type Distribution")),
                    dbc.CardBody([
                        dcc.Graph(id="event-distribution-chart")
                    ])
                ])
            ], width=6),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("🎯 Quality Distribution")),
                    dbc.CardBody([
                        dcc.Graph(id="quality-distribution-chart")
                    ])
                ])
            ], width=6)
        ], className="mb-3"),
        
        # Sentiment, Impact & Top Entities
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("🎭 Sentiment Distribution")),
                    dbc.CardBody([
                        dcc.Graph(id="sentiment-distribution-chart", style={"height": "100%", "width": "100%"})
                    ], style={"overflow": "hidden"})
                ])
            ], width=4),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("💥 Impact Score Distribution")),
                    dbc.CardBody([
                        dcc.Graph(id="impact-distribution-chart", style={"height": "100%", "width": "100%"})
                    ], style={"overflow": "hidden"})
                ])
            ], width=4),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("🏢 Top Entities")),
                    dbc.CardBody([
                        html.Div(id="top-entities-list")
                    ])
                ])
            ], width=4)
        ], className="mb-3"),
        
        # Index Trends & Stock Performance
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("📈 Market Index Trends & Tracked Stocks")),
                    dbc.CardBody([
                        html.Div(id="index-trends-display")
                    ])
                ])
            ], width=12)
        ], className="mb-3"),
        
        # NEW: Entity Sentiment Analysis
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.Div([
                            html.H5("📊 Entity Sentiment Analysis", className="mb-0 d-inline"),
                            dbc.Select(
                                id="sentiment-timeframe-selector",
                                options=[
                                    {"label": "Last 7 Days", "value": "7d"},
                                    {"label": "Last 30 Days", "value": "30d"},
                                    {"label": "Last 90 Days", "value": "90d"},
                                    {"label": "All Time", "value": "all"}
                                ],
                                value="30d",
                                className="w-auto d-inline-block ms-3",
                                style={"width": "150px"}
                            )
                        ], className="d-flex align-items-center justify-content-between")
                    ]),
                    dbc.CardBody([
                        dcc.Graph(id="entity-sentiment-chart")
                    ])
                ])
            ], width=12)
        ], className="mb-3"),
        
        # NEW: Top Positive & Negative Entities
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.Div([
                            html.H5("📈 Positive Entities (Selected Range)", className="mb-0 d-inline"),
                            dbc.Input(
                                id="positive-entity-search-input",
                                type="text",
                                placeholder="Search entities...",
                                className="d-inline-block ms-3",
                                style={"width": "200px"},
                                debounce=True
                            )
                        ], className="d-flex align-items-center justify-content-between")
                    ]),
                    dbc.CardBody([
                        html.Div(
                            id="top-positive-entities",
                            style={
                                "maxHeight": "650px",
                                "overflowY": "auto",
                                "overflowX": "hidden"
                            }
                        ),
                        dcc.Input(id="positive-entities-scroll-trigger", type="hidden", value="0"),
                        html.Small("💡 Showing entities sorted by average sentiment score", className="text-muted d-block mt-2")
                    ])
                ])
            ], width=6),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.Div([
                            html.H5("📉 Negative Entities (Selected Range)", className="mb-0 d-inline"),
                            dbc.Input(
                                id="negative-entity-search-input",
                                type="text",
                                placeholder="Search entities...",
                                className="d-inline-block ms-3",
                                style={"width": "200px"},
                                debounce=True
                            )
                        ], className="d-flex align-items-center justify-content-between")
                    ]),
                    dbc.CardBody([
                        html.Div(
                            id="top-negative-entities",
                            style={
                                "maxHeight": "650px",
                                "overflowY": "auto",
                                "overflowX": "hidden"
                            }
                        ),
                        dcc.Input(id="negative-entities-scroll-trigger", type="hidden", value="0"),
                        html.Small("💡 Showing entities sorted by average sentiment score", className="text-muted d-block mt-2")
                    ])
                ])
            ], width=6)
        ], className="mb-3"),
        
        # NEW: Entity Details Table
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.Div([
                            html.H5("🏢 Entity Details", className="mb-0 d-inline"),
                            dbc.Input(
                                id="entity-search-input",
                                type="text",
                                placeholder="Search entities...",
                                className="d-inline-block ms-3",
                                style={"width": "300px"}
                            )
                        ], className="d-flex align-items-center")
                    ]),
                    dbc.CardBody([
                        html.Div(
                            id="entity-details-table",
                            style={
                                "maxHeight": "500px",
                                "overflowY": "auto",
                                "overflowX": "auto"
                            }
                        )
                    ])
                ])
            ], width=12)
        ], className="mb-3"),
        
        # News Volume Over Time
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("📰 News Volume Over Time")),
                    dbc.CardBody([
                        dcc.Graph(id="news-volume-chart")
                    ])
                ])
            ], width=12)
        ]),
        
        # Entity Details Modal
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="entity-modal-title")),
            dbc.ModalBody(id="entity-modal-body"),
            dbc.ModalFooter([
                dbc.Button("Close", id="close-entity-modal", className="ms-auto")
            ])
        ], id="entity-details-modal", size="xl", scrollable=True),
        
        # Stock Predictions Modal
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="stock-modal-title")),
            dbc.ModalBody(id="stock-modal-body"),
            dbc.ModalFooter([
                dbc.Button("Close", id="close-stock-modal", className="ms-auto")
            ])
        ], id="stock-predictions-modal", size="xl", scrollable=True),
        
        # Toast notification for missing predictions
        dbc.Toast(
            "No prediction found for this news article. The prediction may not have been created yet.",
            id="no-prediction-toast",
            header="⚠️ No Prediction Found",
            is_open=False,
            dismissable=True,
            icon="warning",
            duration=4000,
            style={
                "position": "fixed",
                "top": 66,
                "right": 10,
                "width": 350,
                "zIndex": 9999,
                "backgroundColor": "#1e1e1e",
                "border": "1px solid #ffc107",
                "boxShadow": "0 4px 8px rgba(0,0,0,0.3)"
            }
        ),
        
        # Store for selected entity
        dcc.Store(id="selected-entity-store", data=None),

        # Store for active time filter
        dcc.Store(id="active-filter-store", data="all"),
        
        # Store for table sorting state
        dcc.Store(id="entity-table-sort-store", data={"column": None, "direction": None}),
        
        # Stores for infinite scroll limits
        dcc.Store(id="positive-entities-limit", data=50),
        dcc.Store(id="negative-entities-limit", data=50)
    ], fluid=True)
