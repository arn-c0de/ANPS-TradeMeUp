"""
Settings Tab - System Configuration and Database Management
"""

from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta


def create_layout():
    """Create settings tab layout"""
    return dbc.Container([
        # Header
        dbc.Row([
            dbc.Col([
                html.H3("⚙️ System Settings", className="mb-4")
            ])
        ]),
        
        # Database Management Section
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("🗄️ Database Management", className="mb-0")),
                    dbc.CardBody([
                        html.P("Clear data from the database. This action cannot be undone!", 
                               className="text-warning fw-bold"),
                        
                        # Clear News Section
                        html.Hr(),
                        html.H6("Clear News Articles", className="mb-3"),
                        
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Select Time Range:"),
                                dcc.Dropdown(
                                    id="settings-news-timerange",
                                    options=[
                                        {'label': '🗑️ All News', 'value': 'all'},
                                        {'label': '📅 Last 24 Hours', 'value': '1d'},
                                        {'label': '📅 Last 7 Days', 'value': '7d'},
                                        {'label': '📅 Last 30 Days', 'value': '30d'},
                                        {'label': '📅 Last 90 Days', 'value': '90d'},
                                        {'label': '📅 Custom Date Range', 'value': 'custom'}
                                    ],
                                    value='7d',
                                    clearable=False
                                )
                            ], md=6),
                            dbc.Col([
                                html.Div([
                                    dbc.Label("Custom Date Range:"),
                                    dcc.DatePickerRange(
                                        id="settings-news-custom-dates",
                                        start_date=(datetime.now() - timedelta(days=7)).date(),
                                        end_date=datetime.now().date(),
                                        display_format='YYYY-MM-DD',
                                        disabled=True
                                    )
                                ], id="custom-date-container")
                            ], md=6)
                        ], className="mb-3"),
                        
                        dbc.Button(
                            "🗑️ Clear News Articles",
                            id="btn-clear-news",
                            color="danger",
                            className="w-100 mb-3"
                        ),
                        
                        html.Div(id="news-clear-status"),
                        
                        # Clear Predictions Section
                        html.Hr(),
                        html.H6("Clear Predictions", className="mb-3"),
                        
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Select Time Range:"),
                                dcc.Dropdown(
                                    id="settings-pred-timerange",
                                    options=[
                                        {'label': '🗑️ All Predictions', 'value': 'all'},
                                        {'label': '📅 Last 24 Hours', 'value': '1d'},
                                        {'label': '📅 Last 7 Days', 'value': '7d'},
                                        {'label': '📅 Last 30 Days', 'value': '30d'}
                                    ],
                                    value='7d',
                                    clearable=False
                                )
                            ], md=6)
                        ], className="mb-3"),
                        
                        dbc.Button(
                            "🗑️ Clear Predictions",
                            id="btn-clear-predictions",
                            color="danger",
                            className="w-100 mb-3"
                        ),
                        
                        html.Div(id="pred-clear-status"),
                        
                        # Clear All Section
                        html.Hr(),
                        html.H6("⚠️ Nuclear Option", className="mb-3 text-danger"),
                        html.P("Delete ALL data from database (News, Predictions, Entities, etc.)", 
                               className="text-danger"),
                        
                        dbc.Button(
                            "💣 Clear Entire Database",
                            id="btn-clear-all",
                            color="danger",
                            outline=True,
                            className="w-100"
                        ),
                        
                        html.Div(id="all-clear-status", className="mt-3")
                    ])
                ])
            ], md=8)
        ], className="mb-4"),
        
        # LLM Configuration Section
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("🤖 LLM Configuration", className="mb-0")),
                    dbc.CardBody([
                        html.P("Configure AI model for content analysis", className="text-muted mb-3"),

                        dbc.Row([
                            dbc.Col([
                                dbc.Label("LLM Provider:", className="fw-bold"),
                                dcc.Dropdown(
                                    id="settings-llm-provider",
                                    options=[
                                        {'label': '🏠 Ollama (Local)', 'value': 'ollama'},
                                        {'label': '🌐 OpenAI', 'value': 'openai'},
                                        {'label': '🧠 Anthropic (Claude)', 'value': 'anthropic'}
                                    ],
                                    value='ollama',
                                    clearable=False,
                                    className="mb-3"
                                )
                            ], md=6),
                            dbc.Col([
                                dbc.Label("Model:", className="fw-bold"),
                                dcc.Dropdown(
                                    id="settings-llm-model",
                                    placeholder="Select a model...",
                                    clearable=False,
                                    className="mb-3"
                                )
                            ], md=6)
                        ]),

                        # Provider-specific settings
                        html.Div(id="llm-provider-settings"),

                        # Cost & Performance Info
                        dbc.Alert(id="llm-cost-info", color="info", className="mt-3"),

                        html.Hr(),

                        dbc.Button(
                            "💾 Save LLM Settings",
                            id="btn-save-llm-settings",
                            color="primary",
                            className="w-100"
                        ),

                        html.Div(id="llm-settings-save-status", className="mt-3")
                    ])
                ])
            ], md=8)
        ], className="mb-4"),

        # Pipeline Configuration Section
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("⚙️ Pipeline Configuration", className="mb-0")),
                    dbc.CardBody([
                        html.H6("Continuous Pipeline Settings", className="mb-3"),

                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Check Interval (minutes):"),
                                dcc.Slider(
                                    id="settings-interval",
                                    min=1,
                                    max=60,
                                    step=1,
                                    value=5,
                                    marks={1: '1m', 5: '5m', 10: '10m', 30: '30m', 60: '1h'},
                                    tooltip={"placement": "bottom", "always_visible": True}
                                )
                            ], md=6),
                            dbc.Col([
                                dbc.Label("Articles per Batch:"),
                                dcc.Slider(
                                    id="settings-batch-size",
                                    min=5,
                                    max=100,
                                    step=5,
                                    value=50,
                                    marks={5: '5', 25: '25', 50: '50', 75: '75', 100: '100'},
                                    tooltip={"placement": "bottom", "always_visible": True}
                                )
                            ], md=6)
                        ]),

                        html.Hr(),
                        
                        # Pipeline Phase Toggles
                        html.H6("Pipeline Phases", className="mb-3 mt-4"),
                        html.P("Enable or disable specific pipeline phases to optimize token usage and performance", 
                               className="text-muted small mb-3"),
                        
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Phase 13: Fact Verification", className="fw-bold"),
                                html.P("Verify factual claims in articles (costs many tokens)", 
                                       className="text-muted small mb-2"),
                                dbc.Switch(
                                    id="settings-enable-fact-checking",
                                    label="Enable Fact Checking",
                                    value=True,
                                    className="mb-3"
                                )
                            ], md=6),
                            dbc.Col([
                                dbc.Label("Phase 14: Confidence Calibration", className="fw-bold"),
                                html.P("Calibrate prediction confidence scores", 
                                       className="text-muted small mb-2"),
                                dbc.Switch(
                                    id="settings-enable-calibration",
                                    label="Enable Calibration",
                                    value=True,
                                    className="mb-3"
                                )
                            ], md=6)
                        ]),
                        
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Phase 15: Meta-Strategy Ensemble", className="fw-bold"),
                                html.P("Create ensemble predictions from multiple models", 
                                       className="text-muted small mb-2"),
                                dbc.Switch(
                                    id="settings-enable-meta-strategy",
                                    label="Enable Meta-Strategy",
                                    value=True,
                                    className="mb-3"
                                )
                            ], md=6),
                            dbc.Col([
                                dbc.Label("Phase 12: Scenario Generation", className="fw-bold"),
                                html.P("Generate stress test scenarios for predictions", 
                                       className="text-muted small mb-2"),
                                dbc.Switch(
                                    id="settings-enable-scenarios",
                                    label="Enable Scenarios",
                                    value=True,
                                    className="mb-3"
                                )
                            ], md=6)
                        ]),

                        html.Hr(),

                        dbc.Button(
                            "💾 Save Pipeline Settings",
                            id="btn-save-settings",
                            color="success",
                            className="w-100"
                        ),

                        html.Div(id="settings-save-status", className="mt-3")
                    ])
                ])
            ], md=8)
        ]),
        
        # Confirmation Modals
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("⚠️ Confirm Action")),
            dbc.ModalBody([
                html.Div(id="confirm-modal-body")
            ]),
            dbc.ModalFooter([
                dbc.Button("Cancel", id="btn-confirm-cancel", color="secondary", className="me-2"),
                dbc.Button("Confirm Delete", id="btn-confirm-delete", color="danger")
            ])
        ], id="confirm-modal", is_open=False, backdrop="static"),
        
    ], fluid=True)
