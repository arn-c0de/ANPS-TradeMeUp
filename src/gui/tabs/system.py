"""System Health Tab — agent status, DB stats, and centralised log viewer."""

import json

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, dcc, html
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from src.models.database import engine as _engine
from src.gui.utils.callbacks import safe_callback
from src.models.raw_news import RawNews
from src.models.processed_news import ProcessedNews
from src.models.entities import Entity
from src.models.predictions import Prediction
from src.models.analysis import ImpactScore, SurpriseScore, SignalDecayModel, FactVerification, MarketRegime
from src.models.data_quality import DataQualityScore
from src.models.system_logs import SystemLog

# ── constants ─────────────────────────────────────────────────────────────────
_SOURCES = ["all", "pipeline", "agent", "simulation", "ingestion", "api", "gui", "system"]
_LEVELS  = ["all", "ERROR", "WARNING", "SUCCESS", "INFO", "DEBUG"]
_COUNTS  = [50, 100, 250, 500]

_LEVEL_COLOR = {
    "ERROR":   "danger",
    "WARNING": "warning",
    "SUCCESS": "success",
    "INFO":    "secondary",
    "DEBUG":   "light",
}


# ── layout ────────────────────────────────────────────────────────────────────
def create_layout():
    return dbc.Container([
        # Row 1 — agent status
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("🤖 Agent Pipeline Status")),
                    dbc.CardBody(html.Div(id="agent-status"))
                ])
            ], width=12)
        ], className="mb-3"),

        # Row 2 — DB stats + pipeline stats
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("📊 Database Statistics")),
                    dbc.CardBody(html.Div(id="db-statistics"))
                ])
            ], width=6),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("⚡ Processing Pipeline")),
                    dbc.CardBody(html.Div(id="pipeline-stats"))
                ])
            ], width=6)
        ], className="mb-3"),

        # Row 3 — Server Log Viewer
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        dbc.Row([
                            dbc.Col(html.H5("🖥️ Server Logs", className="mb-0"), width="auto"),
                            dbc.Col([
                                dbc.Switch(
                                    id="logs-live-toggle",
                                    label="Live tail",
                                    value=False,
                                    className="mb-0 ms-3",
                                )
                            ], width="auto", className="d-flex align-items-center"),
                            dbc.Col(
                                dbc.Button("↻ Refresh", id="logs-refresh-btn",
                                           size="sm", color="outline-secondary"),
                                width="auto", className="ms-auto"
                            ),
                            dbc.Col(
                                dbc.Button("⬇ Export", id="logs-export-btn",
                                           size="sm", color="outline-info"),
                                width="auto"
                            ),
                            dbc.Col(
                                dbc.Button("🗑 Clear", id="logs-clear-btn",
                                           size="sm", color="outline-danger"),
                                width="auto"
                            ),
                        ], align="center", className="g-2")
                    ]),
                    dbc.CardBody([
                        # Filter bar
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Source", className="small text-muted mb-1"),
                                dcc.Dropdown(
                                    id="logs-source-filter",
                                    options=[{"label": s.capitalize(), "value": s}
                                             for s in _SOURCES],
                                    value="all",
                                    clearable=False,
                                    className="mb-0",
                                )
                            ], md=2),
                            dbc.Col([
                                dbc.Label("Level", className="small text-muted mb-1"),
                                dcc.Dropdown(
                                    id="logs-level-filter",
                                    options=[{"label": l, "value": l} for l in _LEVELS],
                                    value="all",
                                    clearable=False,
                                )
                            ], md=2),
                            dbc.Col([
                                dbc.Label("Show last", className="small text-muted mb-1"),
                                dcc.Dropdown(
                                    id="logs-count-filter",
                                    options=[{"label": str(n), "value": n} for n in _COUNTS],
                                    value=100,
                                    clearable=False,
                                )
                            ], md=2),
                            dbc.Col([
                                dbc.Label("Search", className="small text-muted mb-1"),
                                dbc.Input(
                                    id="logs-search",
                                    placeholder="Filter messages…",
                                    size="sm",
                                    debounce=True,
                                )
                            ], md=4),
                            dbc.Col([
                                html.Div(id="logs-count-badge", className="mt-4")
                            ], md=2),
                        ], className="mb-3"),

                        # Log table
                        html.Div(
                            id="logs-table-container",
                            style={
                                "maxHeight": "520px",
                                "overflowY": "auto",
                                "fontFamily": "monospace",
                                "fontSize": "0.78rem",
                            }
                        ),
                        html.Div(id="logs-action-status", className="mt-2"),
                        dcc.Download(id="logs-download"),

                        # Live-tail interval (only active when toggle is on)
                        dcc.Interval(
                            id="logs-live-interval",
                            interval=5_000,
                            n_intervals=0,
                            disabled=True,
                        ),
                    ])
                ])
            ], width=12)
        ])
    ], fluid=True)


# ── helpers ───────────────────────────────────────────────────────────────────
def _query_logs(source: str, level: str, count: int, search: str) -> list:
    try:
        with Session(_engine) as db:
            q = db.query(SystemLog).order_by(SystemLog.timestamp.desc())
            if source and source != "all":
                q = q.filter(SystemLog.source == source)
            if level and level != "all":
                q = q.filter(SystemLog.level == level)
            if search:
                q = q.filter(SystemLog.message.ilike(f"%{search}%"))
            rows = q.limit(count).all()
            return [{
                "log_id":    r.log_id,
                "timestamp": r.timestamp.strftime("%Y-%m-%d %H:%M:%S") if r.timestamp else "",
                "level":     r.level or "INFO",
                "source":    r.source or "",
                "component": r.component or "",
                "message":   r.message or "",
                "details":   r.details,
            } for r in rows]
    except Exception:
        return []


def _render_log_table(rows: list) -> html.Div:
    if not rows:
        return html.Div(html.P("No log entries found.", className="text-muted small p-2"))

    tr_list = []
    for r in rows:
        color = _LEVEL_COLOR.get(r["level"], "secondary")
        badge = dbc.Badge(r["level"], color=color, className="me-1",
                          style={"minWidth": "64px", "textAlign": "center"})

        detail_section = html.Div()
        if r["details"]:
            try:
                pretty = json.dumps(r["details"], indent=2)
                detail_section = html.Pre(
                    pretty,
                    className="text-muted small mt-1 mb-0 p-1",
                    style={"background": "#111", "borderRadius": "4px",
                           "fontSize": "0.72rem", "whiteSpace": "pre-wrap",
                           "maxHeight": "120px", "overflowY": "auto"},
                )
            except Exception:
                pass

        tr_list.append(html.Tr([
            html.Td(r["timestamp"], className="text-muted small pe-2",
                    style={"whiteSpace": "nowrap", "verticalAlign": "top"}),
            html.Td(badge, style={"verticalAlign": "top"}),
            html.Td(
                dbc.Badge(r["source"], color="dark", className="me-1 small"),
                style={"verticalAlign": "top", "whiteSpace": "nowrap"},
            ),
            html.Td([
                html.Span(r["component"] + " · ", className="text-muted small")
                if r["component"] else html.Span(),
                html.Span(r["message"]),
                detail_section,
            ], style={"wordBreak": "break-word"}),
        ], className=f"table-{'danger' if r['level']=='ERROR' else 'warning' if r['level']=='WARNING' else ''}"))

    return dbc.Table(
        [html.Tbody(tr_list)],
        bordered=False, hover=True, responsive=True,
        size="sm", className="text-light mb-0",
    )


def get_agent_status():
    agents = [
        ("1",    "Data Ingestion",            "✅ Operational", "success"),
        ("1.5",  "Data Quality",              "✅ Operational", "success"),
        ("2",    "Content Understanding",     "✅ Operational", "success"),
        ("2.5",  "Fact Verification",         "✅ Operational", "success"),
        ("3",    "Entity Mapping",            "✅ Operational", "success"),
        ("4",    "Impact Scoring",            "✅ Operational", "success"),
        ("4.5",  "Surprise Quantification",   "✅ Operational", "success"),
        ("5",    "Market Regime Detection",   "✅ Operational", "success"),
        ("5.5",  "Signal Decay",              "✅ Operational", "success"),
        ("5.6",  "Correlation Analysis",      "✅ Operational", "success"),
        ("6",    "Predictions",               "✅ Operational", "success"),
        ("6.5",  "Confidence Calibration",    "✅ Operational", "success"),
        ("7",    "Meta-Strategy",             "✅ Operational", "success"),
        ("7.5",  "Scenario Generation",       "✅ Operational", "success"),
        ("12.5", "Model Performance Monitor", "✅ Operational", "success"),
        ("13",   "A/B Testing Framework",     "✅ Operational", "success"),
    ]
    rows = [html.Tr([
        html.Td(f"Agent {aid}", className="text-primary"),
        html.Td(name),
        html.Td(status, className=f"text-{color}"),
    ]) for aid, name, status, color in agents]
    return dbc.Table([
        html.Thead(html.Tr([html.Th("Agent"), html.Th("Name"), html.Th("Status")])),
        html.Tbody(rows),
    ], bordered=True, hover=True, className="table-dark")


def get_db_statistics(engine):
    try:
        with Session(engine) as db:
            stats = {
                "📰 Raw News":           db.query(func.count(RawNews.news_id)).scalar() or 0,
                "✅ Quality Scores":     db.query(func.count(DataQualityScore.news_id)).scalar() or 0,
                "🧠 Processed News":     db.query(func.count(ProcessedNews.news_id)).scalar() or 0,
                "🏢 Entities":           db.query(func.count(Entity.entity_id)).scalar() or 0,
                "⚡ Impact Scores":      db.query(func.count(ImpactScore.score_id)).scalar() or 0,
                "🎯 Surprise Scores":    db.query(func.count(SurpriseScore.surprise_id)).scalar() or 0,
                "🔍 Fact Verifications": db.query(func.count(FactVerification.verification_id)).scalar() or 0,
                "🌡️ Market Regimes":     db.query(func.count(MarketRegime.regime_id)).scalar() or 0,
                "📉 Signal Decay":       db.query(func.count(SignalDecayModel.news_id)).scalar() or 0,
                "🔮 Predictions":        db.query(func.count(Prediction.prediction_id)).scalar() or 0,
            }
        return html.Div([
            html.Div([
                html.Strong(f"{k}: "),
                html.Span(f"{v:,}", className="text-primary ms-2")
            ], className="mb-2")
            for k, v in stats.items()
        ])
    except Exception:
        return html.Div([
            html.P("⚠️ Unable to load statistics", className="text-warning mb-2"),
            html.Small("Run the pipeline to generate data.", className="text-muted")
        ])


def get_pipeline_stats(engine):
    try:
        with Session(engine) as db:
            total_news = db.query(func.count(RawNews.news_id)).scalar() or 0
            processed  = db.query(func.count(ProcessedNews.news_id)).scalar() or 0
            rate = (processed / total_news * 100) if total_news > 0 else 0
        return html.Div([
            html.Div([
                html.H4(f"{rate:.1f}%", className="text-success"),
                html.P("Processing Completion Rate", className="text-muted"),
            ], className="text-center mb-3"),
            dbc.Progress(value=rate, color="success", className="mb-2"),
            html.Small(f"{processed:,} of {total_news:,} articles processed", className="text-muted"),
        ])
    except Exception:
        return html.Div([
            html.P("⚠️ Unable to load pipeline stats", className="text-warning mb-2"),
            html.Small("Database may be empty.", className="text-muted"),
        ])


# ── callbacks ─────────────────────────────────────────────────────────────────
def register_callbacks(app):

    # ── existing callbacks ────────────────────────────────────────────────────
    @app.callback(Output("agent-status", "children"),
                  Input("interval-component", "n_intervals"))
    def _agent_status(n):
        return get_agent_status()

    @app.callback(Output("db-statistics", "children"),
                  Input("interval-component", "n_intervals"))
    @safe_callback(default_return=html.Div("Unable to load statistics", className="text-warning"))
    def _db_stats(n):
        return get_db_statistics(_engine)

    @app.callback(Output("pipeline-stats", "children"),
                  Input("interval-component", "n_intervals"))
    @safe_callback(default_return=html.Div("Unable to load pipeline statistics", className="text-warning"))
    def _pipeline_stats(n):
        return get_pipeline_stats(_engine)

    # ── live tail toggle ──────────────────────────────────────────────────────
    @app.callback(
        Output("logs-live-interval", "disabled"),
        Input("logs-live-toggle", "value"),
        prevent_initial_call=True,
    )
    def _toggle_live(enabled):
        return not enabled

    # ── main log refresh ──────────────────────────────────────────────────────
    @app.callback(
        [Output("logs-table-container", "children"),
         Output("logs-count-badge", "children")],
        [Input("logs-refresh-btn",   "n_clicks"),
         Input("logs-live-interval", "n_intervals"),
         Input("logs-source-filter", "value"),
         Input("logs-level-filter",  "value"),
         Input("logs-count-filter",  "value"),
         Input("logs-search",        "value"),
         Input("logs-action-status", "children"),
         Input("tabs", "active_tab")],
        prevent_initial_call=False,
    )
    def _refresh_logs(btn, live_n, source, level, count, search, _action, _tab):
        rows = _query_logs(source or "all", level or "all", count or 100, search or "")
        badge = dbc.Badge(f"{len(rows)} entries", color="secondary", className="small")
        return _render_log_table(rows), badge

    # ── export ────────────────────────────────────────────────────────────────
    @app.callback(
        Output("logs-download", "data"),
        Input("logs-export-btn", "n_clicks"),
        [State("logs-source-filter", "value"),
         State("logs-level-filter",  "value"),
         State("logs-count-filter",  "value"),
         State("logs-search",        "value")],
        prevent_initial_call=True,
    )
    def _export_logs(n_clicks, source, level, count, search):
        if not n_clicks:
            return dash.no_update
        rows = _query_logs(source or "all", level or "all", count or 100, search or "")
        lines = [
            f"[{r['timestamp']}] [{r['level']:7}] [{r['source']:12}] "
            f"{(r['component'] + ' | ') if r['component'] else ''}{r['message']}"
            + (f"\n  details: {json.dumps(r['details'])}" if r['details'] else "")
            for r in rows
        ]
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        return dcc.send_string("\n".join(lines), f"trademeup_logs_{ts}.txt")

    # ── clear ─────────────────────────────────────────────────────────────────
    @app.callback(
        Output("logs-action-status", "children"),
        Input("logs-clear-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def _clear_logs(n_clicks):
        if not n_clicks:
            return dash.no_update
        try:
            with Session(_engine) as db:
                deleted = db.query(SystemLog).delete()
                db.commit()
            return dbc.Alert(f"Cleared {deleted:,} log entries.",
                             color="success", dismissable=True, duration=4000)
        except Exception as e:
            return dbc.Alert(f"Clear failed: {e}", color="danger", dismissable=True)
