"""
Settings Tab - System Configuration and Database Management
"""

from dash import dcc, html
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta


def _section_header(title: str, icon: str):
    """Compact section header for settings cards."""
    return html.Div([
        html.Span(icon, className="me-2", style={"fontSize": "1.1rem"}),
        html.Span(title, className="fw-semibold")
    ], className="d-flex align-items-center")


def create_layout():
    """Create settings tab layout."""
    return dbc.Container([
        # Page header
        dbc.Row([
            dbc.Col([
                html.H2("Settings", className="mb-1 fw-bold"),
                html.P("Configure pipeline, LLM, and database.", className="text-muted mb-0")
            ], width=12)
        ], className="mb-4"),

        # ---- 1. Pipeline Configuration (top) ----
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        _section_header("Pipeline", "⚙️"),
                        html.P("Intervals, batch size, and pipeline phases.", className="text-muted small mb-0 mt-1")
                    ], className="py-3"),
                    dbc.CardBody([
                        html.H6("Continuous Pipeline", className="fw-semibold mb-3 mt-2"),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Check Interval (min)", className="small text-muted"),
                                dcc.Slider(
                                    id="settings-interval",
                                    min=1,
                                    max=60,
                                    step=1,
                                    value=5,
                                    marks={1: "1m", 5: "5m", 10: "10m", 30: "30m", 60: "1h"},
                                    tooltip={"placement": "bottom", "always_visible": True},
                                    className="mb-2"
                                )
                            ], md=6),
                            dbc.Col([
                                dbc.Label("Articles per Batch", className="small text-muted"),
                                dcc.Slider(
                                    id="settings-batch-size",
                                    min=5,
                                    max=100,
                                    step=5,
                                    value=50,
                                    marks={5: "5", 25: "25", 50: "50", 75: "75", 100: "100"},
                                    tooltip={"placement": "bottom", "always_visible": True},
                                    className="mb-2"
                                )
                            ], md=6)
                        ], className="mb-4"),

                        html.Hr(className="my-4"),
                        html.H6("Pipeline Phases", className="fw-semibold mb-2"),
                        html.P("Enable or disable phases to control token usage and performance.",
                               className="text-muted small mb-3"),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Phase 13: Fact Verification", className="fw-bold small"),
                                html.P("Verify factual claims (uses many tokens).", className="text-muted small mb-2"),
                                dbc.Switch(id="settings-enable-fact-checking", label="Enable", value=True, className="mb-3")
                            ], md=6),
                            dbc.Col([
                                dbc.Label("Phase 14: Confidence Calibration", className="fw-bold small"),
                                html.P("Calibrate prediction confidence scores.", className="text-muted small mb-2"),
                                dbc.Switch(id="settings-enable-calibration", label="Enable", value=True, className="mb-3")
                            ], md=6)
                        ]),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Phase 15: Meta-Strategy Ensemble", className="fw-bold small"),
                                html.P("Ensemble predictions from multiple models.", className="text-muted small mb-2"),
                                dbc.Switch(id="settings-enable-meta-strategy", label="Enable", value=True, className="mb-3")
                            ], md=6),
                            dbc.Col([
                                dbc.Label("Phase 12: Scenario Generation", className="fw-bold small"),
                                html.P("Stress-test scenarios for predictions.", className="text-muted small mb-2"),
                                dbc.Switch(id="settings-enable-scenarios", label="Enable", value=True, className="mb-3")
                            ], md=6)
                        ]),

                        html.Hr(className="my-4"),
                        dbc.Button("Save Pipeline Settings", id="btn-save-settings",
                                   color="success", className="w-100 rounded-2"),
                        html.Div(id="settings-save-status", className="mt-3")
                    ], className="pt-2")
                ], className="rounded-3 border-0 shadow-sm mb-4")
            ], md=8)
        ]),

        # ---- 2. LLM Configuration ----
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        _section_header("LLM", "🤖"),
                        html.P("AI model for content analysis.", className="text-muted small mb-0 mt-1")
                    ], className="py-3"),
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Provider", className="small text-muted fw-semibold"),
                                dcc.Dropdown(
                                    id="settings-llm-provider",
                                    options=[
                                        {"label": "Ollama (local)", "value": "ollama"},
                                        {"label": "OpenAI", "value": "openai"},
                                        {"label": "Anthropic (Claude)", "value": "anthropic"}
                                    ],
                                    value="ollama",
                                    clearable=False,
                                    className="mb-3"
                                )
                            ], md=6),
                            dbc.Col([
                                dbc.Label("Model", className="small text-muted fw-semibold"),
                                dcc.Dropdown(
                                    id="settings-llm-model",
                                    placeholder="Select model…",
                                    clearable=False,
                                    className="mb-3"
                                )
                            ], md=6)
                        ]),
                        html.Div(id="llm-provider-settings"),
                        dbc.Alert(id="llm-cost-info", color="info", className="mt-3 rounded-2"),
                        html.Hr(className="my-4"),
                        dbc.Button("Save LLM Settings", id="btn-save-llm-settings",
                                   color="primary", className="w-100 rounded-2"),
                        html.Div(id="llm-settings-save-status", className="mt-3")
                    ], className="pt-2")
                ], className="rounded-3 border-0 shadow-sm mb-4")
            ], md=8)
        ]),

        # ---- 3. Database Management ----
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        _section_header("Database", "🗄️"),
                        html.P("Delete data. Actions cannot be undone.",
                               className="text-warning small mb-0 mt-1")
                    ], className="py-3"),
                    dbc.CardBody([
                        html.H6("Clear News", className="fw-semibold mb-3 mt-2"),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Time Range", className="small text-muted"),
                                dcc.Dropdown(
                                    id="settings-news-timerange",
                                    options=[
                                        {"label": "All News", "value": "all"},
                                        {"label": "Last 24h", "value": "1d"},
                                        {"label": "Last 7 Days", "value": "7d"},
                                        {"label": "Last 30 Days", "value": "30d"},
                                        {"label": "Last 90 Days", "value": "90d"},
                                        {"label": "Custom", "value": "custom"}
                                    ],
                                    value="7d",
                                    clearable=False
                                )
                            ], md=6),
                            dbc.Col([
                                html.Div([
                                    dbc.Label("Custom Date Range", className="small text-muted"),
                                    dcc.DatePickerRange(
                                        id="settings-news-custom-dates",
                                        start_date=(datetime.now() - timedelta(days=7)).date(),
                                        end_date=datetime.now().date(),
                                        display_format="YYYY-MM-DD",
                                        disabled=True
                                    )
                                ], id="custom-date-container")
                            ], md=6)
                        ], className="mb-3"),
                        dbc.Button("Clear News", id="btn-clear-news", color="danger",
                                   className="w-100 mb-3 rounded-2"),
                        html.Div(id="news-clear-status"),

                        html.Hr(className="my-4"),
                        html.H6("Clear Predictions", className="fw-semibold mb-3"),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Time Range", className="small text-muted"),
                                dcc.Dropdown(
                                    id="settings-pred-timerange",
                                    options=[
                                        {"label": "All Predictions", "value": "all"},
                                        {"label": "Last 24h", "value": "1d"},
                                        {"label": "Last 7 Days", "value": "7d"},
                                        {"label": "Last 30 Days", "value": "30d"}
                                    ],
                                    value="7d",
                                    clearable=False
                                )
                            ], md=6)
                        ], className="mb-3"),
                        dbc.Button("Clear Predictions", id="btn-clear-predictions", color="danger",
                                   className="w-100 mb-3 rounded-2"),
                        html.Div(id="pred-clear-status"),

                        html.Hr(className="my-4"),
                        html.H6("⚠️ Clear Entire Database", className="fw-semibold text-danger mb-2"),
                        html.P("All data (News, Predictions, Entities, …) will be deleted.",
                               className="text-danger small mb-3"),
                        dbc.Button("Clear Entire Database", id="btn-clear-all",
                                   color="danger", outline=True, className="w-100 rounded-2"),
                        html.Div(id="all-clear-status", className="mt-3")
                    ], className="pt-2")
                ], className="rounded-3 border-0 shadow-sm mb-4")
            ], md=8)
        ]),

        # Confirmation modal
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle("Confirm Action")),
            dbc.ModalBody(html.Div(id="confirm-modal-body")),
            dbc.ModalFooter([
                dbc.Button("Cancel", id="btn-confirm-cancel", color="secondary", className="me-2 rounded-2"),
                dbc.Button("Confirm Delete", id="btn-confirm-delete", color="danger", className="rounded-2")
            ])
        ], id="confirm-modal", is_open=False, backdrop="static", className="rounded-3"),
    ], fluid=True)
