"""
Settings Tab - System Configuration and Database Management
"""

import re
from datetime import datetime, timedelta
from pathlib import Path

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, html
from sqlalchemy.orm import Session

from src.config.settings import settings as _settings
from src.models.analysis import ImpactScore
from src.models.data_quality import DataQualityScore
from src.models.database import engine as _engine
from src.models.entities import Entity, NewsEntityMapping
from src.models.predictions import Prediction
from src.models.processed_news import ProcessedNews
from src.models.raw_news import RawNews
from src.utils.activity_logger import activity_logger

LLM_MODELS = {
    "ollama": [
        {"label": "Qwen 3 (8B) - Fast", "value": "qwen3:8b"},
        {"label": "Llama 3.1 (8B)", "value": "llama3.1:8b"},
        {"label": "Mistral (7B)", "value": "mistral:7b"},
        {"label": "Gemma 2 (9B)", "value": "gemma2:9b"},
        {"label": "Phi-3 (3.8B) - Lightweight", "value": "phi3"},
    ],
    "openai": [
        {"label": "GPT-4o-mini (Recommended)", "value": "gpt-4o-mini"},
        {"label": "GPT-3.5-turbo", "value": "gpt-3.5-turbo"},
        {"label": "GPT-4o", "value": "gpt-4o"},
        {"label": "GPT-4-turbo", "value": "gpt-4-turbo"},
    ],
    "anthropic": [
        {"label": "Claude 3.5 Sonnet (Best)", "value": "claude-3-5-sonnet-20241022"},
        {"label": "Claude 3 Haiku (Fast)", "value": "claude-3-haiku-20240307"},
        {"label": "Claude 3 Opus (Powerful)", "value": "claude-3-opus-20240229"},
    ],
}


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


def _env_local_path():
    return Path(__file__).resolve().parents[3] / ".env.local"


# Values written into .env.local come from Dash State, which a client controls
# freely. A newline would let a caller append arbitrary variables (DATABASE_URL,
# API keys) to the file the app reads on startup, so validate before writing.
_MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9._:/-]{1,100}$")


def _validate_provider(provider):
    """Return provider if it is one of the known LLM providers, else raise."""
    if provider not in LLM_MODELS:
        raise ValueError(f"Unknown LLM provider: {provider!r}")
    return provider


def _validate_model_name(model):
    """Return model if it is a plausible model identifier, else raise."""
    if not isinstance(model, str) or not _MODEL_NAME_RE.match(model):
        raise ValueError(f"Invalid model name: {model!r}")
    return model


def _env_bool(value) -> str:
    """Coerce any GUI value to the literal 'true'/'false' written into .env.local."""
    if isinstance(value, str):
        return "true" if value.strip().lower() in {"1", "true", "yes", "on"} else "false"
    return "true" if bool(value) else "false"


def register_callbacks(app):
    """Register settings tab callbacks."""

    @app.callback(
        Output("settings-llm-provider", "value"),
        Input("tabs", "active_tab"),
        prevent_initial_call=False,
    )
    def _load_current_llm_provider(active_tab):
        try:
            return _settings.llm_provider
        except Exception:
            return "ollama"

    @app.callback(
        [
            Output("settings-llm-model", "options"),
            Output("settings-llm-model", "value"),
            Output("llm-provider-settings", "children"),
            Output("llm-cost-info", "children"),
        ],
        Input("settings-llm-provider", "value"),
        prevent_initial_call=False,
    )
    def _update_llm_model_options(provider):
        if not provider:
            return [], None, html.Div(), ""
        try:
            if provider == "ollama" and hasattr(_settings, "ollama_model"):
                current_model = _settings.ollama_model
            elif provider == "openai" and hasattr(_settings, "openai_model"):
                current_model = _settings.openai_model
            elif provider == "anthropic" and hasattr(_settings, "anthropic_model"):
                current_model = _settings.anthropic_model
            else:
                current_model = None
        except Exception:
            current_model = None
        models = LLM_MODELS.get(provider, [])
        default_model = current_model or (models[0]["value"] if models else None)
        if provider == "ollama":
            provider_settings = html.Div([html.Small("API URL is configured in .env file", className="text-muted")])
            cost_info = html.Div([
                html.Strong("Local Ollama:"),
                html.Ul([
                    html.Li("Free (no API costs)"),
                    html.Li("~30-60s per article"),
                    html.Li("Requires local GPU (8GB+ VRAM recommended)"),
                ]),
            ])
        elif provider == "openai":
            provider_settings = html.Div([html.Small("API key in .env (OPENAI_API_KEY)", className="text-muted")])
            cost_info = html.Div([
                html.Strong("OpenAI Costs (GPT-4o-mini):"),
                html.Ul([
                    html.Li("~$0.0005 per article"),
                    html.Li("~5-10s per article"),
                    html.Li("No hardware required"),
                ]),
            ])
        elif provider == "anthropic":
            provider_settings = html.Div([html.Small("API key in .env (ANTHROPIC_API_KEY)", className="text-muted")])
            cost_info = html.Div([
                html.Strong("Anthropic Costs (Claude 3.5 Sonnet):"),
                html.Ul([
                    html.Li("~$0.003 per article"),
                    html.Li("~5-10s per article"),
                    html.Li("Best at complex reasoning"),
                ]),
            ])
        else:
            provider_settings = html.Div()
            cost_info = ""
        return models, default_model, provider_settings, cost_info

    @app.callback(
        Output("llm-settings-save-status", "children"),
        Input("btn-save-llm-settings", "n_clicks"),
        [State("settings-llm-provider", "value"), State("settings-llm-model", "value")],
        prevent_initial_call=True,
    )
    def _save_llm_settings(n_clicks, provider, model):
        if not n_clicks:
            return ""
        try:
            provider = _validate_provider(provider)
            model = _validate_model_name(model)
        except ValueError as e:
            return dbc.Alert(str(e), color="danger", dismissable=True)
        env_path = _env_local_path()
        try:
            lines = env_path.read_text().splitlines(keepends=True) if env_path.exists() else []
            new_lines = []
            updated_provider = updated_model = False
            for line in lines:
                if line.startswith("LLM_PROVIDER="):
                    new_lines.append(f"LLM_PROVIDER={provider}\n")
                    updated_provider = True
                elif provider == "ollama" and line.startswith("OLLAMA_MODEL="):
                    new_lines.append(f"OLLAMA_MODEL={model}\n")
                    updated_model = True
                elif provider == "openai" and line.startswith("OPENAI_MODEL="):
                    new_lines.append(f"OPENAI_MODEL={model}\n")
                    updated_model = True
                elif provider == "anthropic" and line.startswith("ANTHROPIC_MODEL="):
                    new_lines.append(f"ANTHROPIC_MODEL={model}\n")
                    updated_model = True
                else:
                    new_lines.append(line)
            if not updated_provider:
                new_lines.append(f"LLM_PROVIDER={provider}\n")
            if not updated_model:
                key = {"ollama": "OLLAMA_MODEL", "openai": "OPENAI_MODEL", "anthropic": "ANTHROPIC_MODEL"}.get(provider)
                if key:
                    new_lines.append(f"{key}={model}\n")
            env_path.write_text("".join(new_lines))
            return dbc.Alert([
                html.Strong("Settings saved!"),
                html.Br(),
                html.Small(f"Provider: {provider} | Model: {model}. Restart pipeline for changes."),
            ], color="success", dismissable=True)
        except Exception as e:
            return dbc.Alert(f"Error saving settings: {str(e)}", color="danger", dismissable=True)

    @app.callback(
        [
            Output("settings-enable-fact-checking", "value"),
            Output("settings-enable-calibration", "value"),
            Output("settings-enable-meta-strategy", "value"),
            Output("settings-enable-scenarios", "value"),
        ],
        Input("tabs", "active_tab"),
        prevent_initial_call=False,
    )
    def _load_pipeline_phase_settings(active_tab):
        if active_tab != "settings":
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update
        try:
            return (
                _settings.enable_fact_checking,
                _settings.enable_calibration,
                _settings.enable_meta_strategy,
                _settings.enable_scenarios,
            )
        except Exception:
            return True, True, True, True

    @app.callback(
        Output("settings-save-status", "children"),
        Input("btn-save-settings", "n_clicks"),
        [
            State("settings-interval", "value"),
            State("settings-batch-size", "value"),
            State("settings-enable-fact-checking", "value"),
            State("settings-enable-calibration", "value"),
            State("settings-enable-meta-strategy", "value"),
            State("settings-enable-scenarios", "value"),
        ],
        prevent_initial_call=True,
    )
    def _save_pipeline_settings(n_clicks, interval, batch_size, enable_fact_checking, enable_calibration, enable_meta_strategy, enable_scenarios):
        if not n_clicks:
            return ""
        env_path = _env_local_path()
        try:
            lines = env_path.read_text().splitlines(keepends=True) if env_path.exists() else []
            new_lines = []
            updated = {"ENABLE_FACT_CHECKING": False, "ENABLE_CALIBRATION": False, "ENABLE_META_STRATEGY": False, "ENABLE_SCENARIOS": False}
            for line in lines:
                if line.startswith("ENABLE_FACT_CHECKING="):
                    new_lines.append(f"ENABLE_FACT_CHECKING={_env_bool(enable_fact_checking)}\n")
                    updated["ENABLE_FACT_CHECKING"] = True
                elif line.startswith("ENABLE_CALIBRATION="):
                    new_lines.append(f"ENABLE_CALIBRATION={_env_bool(enable_calibration)}\n")
                    updated["ENABLE_CALIBRATION"] = True
                elif line.startswith("ENABLE_META_STRATEGY="):
                    new_lines.append(f"ENABLE_META_STRATEGY={_env_bool(enable_meta_strategy)}\n")
                    updated["ENABLE_META_STRATEGY"] = True
                elif line.startswith("ENABLE_SCENARIOS="):
                    new_lines.append(f"ENABLE_SCENARIOS={_env_bool(enable_scenarios)}\n")
                    updated["ENABLE_SCENARIOS"] = True
                else:
                    new_lines.append(line)
            if not updated["ENABLE_FACT_CHECKING"]:
                new_lines.append(f"ENABLE_FACT_CHECKING={_env_bool(enable_fact_checking)}\n")
            if not updated["ENABLE_CALIBRATION"]:
                new_lines.append(f"ENABLE_CALIBRATION={_env_bool(enable_calibration)}\n")
            if not updated["ENABLE_META_STRATEGY"]:
                new_lines.append(f"ENABLE_META_STRATEGY={_env_bool(enable_meta_strategy)}\n")
            if not updated["ENABLE_SCENARIOS"]:
                new_lines.append(f"ENABLE_SCENARIOS={_env_bool(enable_scenarios)}\n")
            env_path.write_text("".join(new_lines))
            return dbc.Alert([html.Strong("Settings saved!"), html.Br(), html.Small("Restart pipeline for changes.")], color="success", dismissable=True)
        except Exception as e:
            return dbc.Alert(f"Error saving settings: {str(e)}", color="danger", dismissable=True)

    @app.callback(
        Output("tabs", "active_tab", allow_duplicate=True),
        Input("btn-open-settings", "n_clicks"),
        prevent_initial_call=True,
    )
    def _open_settings(n_clicks):
        if n_clicks:
            return "settings"
        return dash.no_update

    @app.callback(
        Output("settings-news-custom-dates", "disabled"),
        Input("settings-news-timerange", "value"),
    )
    def _toggle_custom_dates(timerange):
        return timerange != "custom"

    @app.callback(
        [Output("confirm-modal", "is_open"), Output("confirm-modal-body", "children"), Output("delete-action-store", "data")],
        [
            Input("btn-clear-news", "n_clicks"),
            Input("btn-clear-predictions", "n_clicks"),
            Input("btn-clear-all", "n_clicks"),
            Input("btn-confirm-cancel", "n_clicks"),
            Input("btn-confirm-delete", "n_clicks"),
        ],
        [
            State("settings-news-timerange", "value"),
            State("settings-news-custom-dates", "start_date"),
            State("settings-news-custom-dates", "end_date"),
            State("settings-pred-timerange", "value"),
            State("delete-action-store", "data"),
            State("confirm-modal", "is_open"),
        ],
        prevent_initial_call=True,
    )
    def _handle_delete_confirmation(clear_news, clear_pred, clear_all, cancel, confirm, news_range, custom_start, custom_end, pred_range, action_store, modal_open):
        ctx = dash.callback_context
        if not ctx.triggered:
            return dash.no_update
        bid = ctx.triggered[0]["prop_id"].split(".")[0]
        if bid == "btn-clear-news":
            timerange_text = {"all": "ALL NEWS ARTICLES", "1d": "news from last 24 hours", "7d": "last 7 days", "30d": "last 30 days", "90d": "last 90 days", "custom": f"news from {custom_start} to {custom_end}"}.get(news_range, "selected news")
            return True, html.Div([
                html.H5("Delete News Articles", className="text-danger mb-3"),
                html.P(f"You are about to delete: {timerange_text}"),
                html.P("This action cannot be undone!", className="fw-bold text-warning"),
            ]), {"action": "clear_news", "params": {"range": news_range, "start": custom_start, "end": custom_end}}
        if bid == "btn-clear-predictions":
            timerange_text = {"all": "ALL PREDICTIONS", "1d": "last 24 hours", "7d": "last 7 days", "30d": "last 30 days"}.get(pred_range, "selected")
            return True, html.Div([
                html.H5("Delete Predictions", className="text-danger mb-3"),
                html.P(f"You are about to delete: {timerange_text}"),
                html.P("This action cannot be undone!", className="fw-bold text-warning"),
            ]), {"action": "clear_predictions", "params": {"range": pred_range}}
        if bid == "btn-clear-all":
            return True, html.Div([
                html.H5("NUCLEAR OPTION", className="text-danger mb-3"),
                html.P("Delete EVERYTHING from the database.", className="fw-bold"),
                html.Ul([html.Li("All news"), html.Li("All predictions"), html.Li("All entities/mappings"), html.Li("All impact/quality data")]),
                html.P("THIS ACTION CANNOT BE UNDONE!", className="fw-bold text-danger fs-5"),
            ]), {"action": "clear_all", "params": {}}
        if bid == "btn-confirm-cancel":
            return False, "", {"action": None, "params": None}
        if bid == "btn-confirm-delete":
            return False, "", action_store
        return dash.no_update

    @app.callback(
        [Output("news-clear-status", "children"), Output("pred-clear-status", "children"), Output("all-clear-status", "children")],
        Input("btn-confirm-delete", "n_clicks"),
        State("delete-action-store", "data"),
        prevent_initial_call=True,
    )
    def _execute_delete_action(n_clicks, action_data):
        if not n_clicks or not action_data or not action_data.get("action"):
            return dash.no_update
        action = action_data["action"]
        params = action_data.get("params", {})
        news_msg = pred_msg = all_msg = dash.no_update
        try:
            with Session(_engine) as db:
                if action == "clear_news":
                    time_range = params.get("range")
                    cutoff_date = None
                    if time_range == "1d":
                        cutoff_date = datetime.now() - timedelta(days=1)
                    elif time_range == "7d":
                        cutoff_date = datetime.now() - timedelta(days=7)
                    elif time_range == "30d":
                        cutoff_date = datetime.now() - timedelta(days=30)
                    elif time_range == "90d":
                        cutoff_date = datetime.now() - timedelta(days=90)
                    elif time_range == "custom" and params.get("start"):
                        cutoff_date = datetime.fromisoformat(params["start"])
                    if time_range == "all":
                        count_raw = db.query(RawNews).delete()
                        count_processed = db.query(ProcessedNews).delete()
                    elif cutoff_date:
                        count_raw = db.query(RawNews).filter(RawNews.created_at >= cutoff_date).delete()
                        count_processed = db.query(ProcessedNews).filter(ProcessedNews.created_at >= cutoff_date).delete()
                    else:
                        count_raw = count_processed = 0
                    db.commit()
                    activity_logger.log_activity(f"Deleted {count_raw + count_processed} news articles", "INFO")
                    news_msg = dbc.Alert(f"Successfully deleted {count_raw + count_processed} news articles", color="success", dismissable=True)
                elif action == "clear_predictions":
                    time_range = params.get("range")
                    cutoff_date = None
                    if time_range == "1d":
                        cutoff_date = datetime.now() - timedelta(days=1)
                    elif time_range == "7d":
                        cutoff_date = datetime.now() - timedelta(days=7)
                    elif time_range == "30d":
                        cutoff_date = datetime.now() - timedelta(days=30)
                    if time_range == "all":
                        count = db.query(Prediction).delete()
                    elif cutoff_date:
                        count = db.query(Prediction).filter(Prediction.created_at >= cutoff_date).delete()
                    else:
                        count = 0
                    db.commit()
                    activity_logger.log_activity(f"Deleted {count} predictions", "INFO")
                    pred_msg = dbc.Alert(f"Successfully deleted {count} predictions", color="success", dismissable=True)
                elif action == "clear_all":
                    db.query(Prediction).delete()
                    db.query(ImpactScore).delete()
                    db.query(NewsEntityMapping).delete()
                    db.query(Entity).delete()
                    db.query(DataQualityScore).delete()
                    db.query(ProcessedNews).delete()
                    db.query(RawNews).delete()
                    db.commit()
                    activity_logger.log_activity("DATABASE CLEARED - All data deleted", "WARNING")
                    all_msg = dbc.Alert("Database cleared! All data has been deleted.", color="danger", dismissable=True)
            return news_msg, pred_msg, all_msg
        except Exception as e:
            import traceback
            activity_logger.log_activity(f"Error deleting data ({action}): {str(e)}", "ERROR")
            activity_logger.log_activity(traceback.format_exc(), "ERROR")
            err = dbc.Alert([html.H5("Delete failed"), html.P(str(e)), html.Small("Check logs for details.")], color="danger", dismissable=True)
            if action == "clear_news":
                return err, dash.no_update, dash.no_update
            if action == "clear_predictions":
                return dash.no_update, err, dash.no_update
            return dash.no_update, dash.no_update, err
