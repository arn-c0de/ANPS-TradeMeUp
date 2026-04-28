"""
Dashboard Tab - Overview and Key Metrics
"""

import os
from datetime import datetime, timedelta
from pathlib import Path
import logging
import re

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html, Input, Output, State
from sqlalchemy import desc, func
from sqlalchemy.orm import Session, joinedload

from src.gui.utils.callbacks import safe_callback
from src.utils.log_retention import LOG_RETENTION_HOURS
from src.models.raw_news import RawNews
from src.models.database import engine
from src.models.data_quality import DataQualityScore
from src.models.processed_news import ProcessedNews
from src.models.predictions import Prediction, PredictionOutcome
from src.models.analysis import MarketRegime, SurpriseScore, FactVerification
from src.models.trading_simulation import TradingSimulation
from src.gui.components import create_metric_card
from src.utils.json_helpers import ensure_dict as _ensure_dict

logger = logging.getLogger(__name__)

_SERVER_LOG_CARD_LIMIT = 120
_SERVER_LOG_MODAL_LIMIT = 500
_FLAT_LOG_FILES = (
    Path("logs/pipeline_activity.log"),
    Path("logs/dashboard.log"),
)
_FLAT_LOG_PATTERN = re.compile(
    r"^\[(?P<timestamp>[^\]]+)\]\s+(?P<level>[A-Z]+):\s*(?P<message>.*)$"
)


def _as_naive_datetime(value):
    if value is None:
        return datetime.min
    return value.replace(tzinfo=None) if getattr(value, "tzinfo", None) else value


def _build_log_viewer(content_id: str, end_marker_id: str, height: str) -> html.Div:
    return html.Div(
        [
            html.Pre(
                id=content_id,
                className="mb-0",
                style={
                    "margin": "0",
                    "whiteSpace": "pre-wrap",
                    "wordBreak": "break-word",
                    "color": "#7CFFB2",
                    "fontFamily": "monospace",
                    "fontSize": "12px",
                    "lineHeight": "1.45",
                },
            ),
            html.Div(id=end_marker_id, style={"height": "1px"}),
        ],
        style={
            "height": height,
            "overflowY": "auto",
            "backgroundColor": "#11161c",
            "border": "1px solid #26313d",
            "borderRadius": "8px",
            "padding": "12px",
        },
    )


_CLIENTSCRIPT_SERVER_LOGS_SCROLL = """
function(cardLogs, modalLogs, modalOpen, liveEnabled) {
    window.serverLogFollowState = window.serverLogFollowState || {};

    const configs = [
        ['server-logs-scroll-container', 'server-logs-end-marker'],
        ['server-logs-modal-scroll-container', 'server-logs-modal-end-marker']
    ];

    function bindScroll(containerId) {
        const container = document.getElementById(containerId);
        if (!container || container.dataset.logFollowBound === '1') {
            return;
        }
        container.dataset.logFollowBound = '1';
        window.serverLogFollowState[containerId] = true;
        container.addEventListener('scroll', function() {
            const nearBottom = container.scrollTop + container.clientHeight >= container.scrollHeight - 80;
            window.serverLogFollowState[containerId] = nearBottom;
        });
    }

    configs.forEach(function(config) {
        bindScroll(config[0]);
    });

    if (!liveEnabled) {
        return '';
    }

    setTimeout(function() {
        configs.forEach(function(config) {
            const containerId = config[0];
            const markerId = config[1];
            const container = document.getElementById(containerId);
            const marker = document.getElementById(markerId);
            if (!container || !marker) {
                return;
            }
            if (containerId === 'server-logs-modal-scroll-container' && !modalOpen) {
                return;
            }
            const shouldFollow = window.serverLogFollowState[containerId] !== false;
            if (shouldFollow) {
                marker.scrollIntoView({block: 'center'});
            }
        });
    }, 0);

    return '';
}
"""


def create_layout():
    """Create dashboard tab layout"""
    return html.Div([
        # Note: Shared stores are now in main app.py layout
        
        dbc.Container([
        dbc.Row([
            dbc.Col([
                html.Div(id="dashboard-metrics")
            ], width=12)
        ]),
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("📰 Recent News (Last 24h)")),
                    dbc.CardBody([
                        html.Div(
                            id="recent-news-table",
                            style={
                                'maxHeight': '420px',
                                'overflowY': 'auto',
                                'overflowX': 'hidden'
                            }
                        )
                    ])
                ])
            ], width=8),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.Small("🌡️ Current Market Regime", className="fw-bold", style={"fontSize": "0.85rem"}), className="py-1"),
                    dbc.CardBody([
                        html.Div(id="market-regime-display")
                    ], className="py-2")
                ], className="mb-2"),
                dbc.Card([
                    dbc.CardHeader([
                        html.Div([
                            html.Small("🏆 Top Performers", className="fw-bold mb-1 d-block", style={"fontSize": "0.85rem"}),
                            dcc.Dropdown(
                                id="top-performers-timeframe",
                                options=[
                                    {'label': '1h', 'value': '1h'},
                                    {'label': '12h', 'value': '12h'},
                                    {'label': '24h', 'value': '24h'},
                                    {'label': '5d', 'value': '5d'},
                                    {'label': '30d', 'value': '30d'},
                                    {'label': '1y', 'value': '1y'},
                                    {'label': 'All', 'value': 'all'}
                                ],
                                value='24h',
                                clearable=False,
                                style={"fontSize": "0.7rem", "height": "24px", "minHeight": "24px"}
                            )
                        ])
                    ], className="py-1"),
                    dbc.CardBody([
                        html.Div(
                            id="top-performers-list",
                            style={
                                'maxHeight': '180px',
                                'overflowY': 'auto',
                                'overflowX': 'hidden'
                            }
                        )
                    ], className="py-1 px-2")
                ])
            ], width=4)
        ], className="mb-3"),
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("� Live Agent Activity")),
                    dbc.CardBody([
                        html.Div(id="live-agent-activity")
                    ])
                ])
            ], width=6),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(
                        dbc.Row(
                            [
                                dbc.Col(html.H5("📋 Server Logs", className="mb-0"), width="auto"),
                                dbc.Col(
                                    dbc.Switch(
                                        id="server-logs-live-toggle",
                                        label="Live",
                                        value=True,
                                        className="mb-0",
                                    ),
                                    width="auto",
                                    className="ms-auto d-flex align-items-center",
                                ),
                                dbc.Col(
                                    dbc.Button(
                                        "⛶ Fullscreen",
                                        id="open-server-logs-modal",
                                        color="outline-info",
                                        size="sm",
                                    ),
                                    width="auto",
                                ),
                            ],
                            align="center",
                            className="g-2",
                        )
                    ),
                    dbc.CardBody([
                        html.Small(
                            f"DB-Retention: {LOG_RETENTION_HOURS}h. Auto-follow pausiert automatisch, sobald du hochscrollst.",
                            className="text-muted d-block mb-2",
                        ),
                        html.Div(
                            id="server-logs-scroll-container",
                            children=_build_log_viewer(
                                "server-logs-display",
                                "server-logs-end-marker",
                                "300px",
                            ),
                        ),
                        html.Div(id="server-logs-scroll-trigger", style={"display": "none"}),
                    ])
                ])
            ], width=6)
        ], className="mb-3"),
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("�📊 Model Performance (30d)")),
                    dbc.CardBody([
                        dcc.Graph(id="performance-chart")
                    ])
                ])
            ], width=12)
        ]),
        dbc.Modal(
            [
                dbc.ModalHeader(
                    dbc.ModalTitle("📋 Server Logs Fullscreen"),
                    close_button=False,
                ),
                dbc.ModalBody(
                    [
                        html.Small(
                            "Live-Ansicht folgt neuen Einträgen nur solange du am unteren Rand bleibst.",
                            className="text-muted d-block mb-2",
                        ),
                        html.Div(
                            id="server-logs-modal-scroll-container",
                            children=_build_log_viewer(
                                "server-logs-modal-display",
                                "server-logs-modal-end-marker",
                                "70vh",
                            ),
                        ),
                    ]
                ),
                dbc.ModalFooter(
                    dbc.Button("Close", id="close-server-logs-modal", color="secondary")
                ),
            ],
            id="server-logs-modal",
            is_open=False,
            size="xl",
            scrollable=False,
            centered=True,
        )
        ], fluid=True)
    ])


def get_metrics(engine):
    """Get dashboard metrics"""
    try:
        with Session(engine) as db:
            # Use timezone-aware UTC time for PostgreSQL compatibility
            from datetime import timezone
            import logging
            logger = logging.getLogger(__name__)
            
            now = datetime.now(timezone.utc)
            hour_ago = now - timedelta(hours=1)
            day_ago = now - timedelta(hours=24)
            
            # Debug: Log the time windows being used
            logger.debug(f"Dashboard time windows - Now: {now}, Hour ago: {hour_ago}, Day ago: {day_ago}")
            
            # Total counts
            total_news = db.query(func.count(RawNews.news_id)).scalar() or 0
            total_processed = db.query(func.count(ProcessedNews.news_id)).scalar() or 0
            total_predictions = db.query(func.count(Prediction.prediction_id)).scalar() or 0
            total_surprises = db.query(func.count(SurpriseScore.surprise_id)).scalar() or 0
            total_fact_checks = db.query(func.count(FactVerification.verification_id)).scalar() or 0
            try:
                total_simulations = db.query(func.count(TradingSimulation.simulation_id)).scalar() or 0
            except Exception:
                total_simulations = 0
            
            # Debug: Check latest timestamps
            latest_news = db.query(RawNews.fetched_at).order_by(RawNews.fetched_at.desc()).first()
            if latest_news:
                logger.debug(f"Latest news timestamp: {latest_news[0]}, Type: {type(latest_news[0])}, TZ: {latest_news[0].tzinfo if latest_news[0] else None}")
            
            # Hourly increments
            news_1h = db.query(func.count(RawNews.news_id)).filter(RawNews.fetched_at >= hour_ago).scalar() or 0
            processed_1h = db.query(func.count(ProcessedNews.news_id)).filter(ProcessedNews.processing_timestamp >= hour_ago).scalar() or 0
            predictions_1h = db.query(func.count(Prediction.prediction_id)).filter(Prediction.created_at >= hour_ago).scalar() or 0
            
            logger.debug(f"Dashboard counts - News 1h: {news_1h}, Processed 1h: {processed_1h}, Predictions 1h: {predictions_1h}")
            surprises_1h = db.query(func.count(SurpriseScore.surprise_id)).filter(SurpriseScore.created_at >= hour_ago).scalar() or 0
            fact_checks_1h = db.query(func.count(FactVerification.verification_id)).filter(FactVerification.verified_at >= hour_ago).scalar() or 0
            try:
                simulations_1h = db.query(func.count(TradingSimulation.simulation_id)).filter(
                    TradingSimulation.created_at >= hour_ago
                ).scalar() or 0
            except Exception:
                simulations_1h = 0
            
            # Daily increments
            news_24h = db.query(func.count(RawNews.news_id)).filter(RawNews.fetched_at >= day_ago).scalar() or 0
            processed_24h = db.query(func.count(ProcessedNews.news_id)).filter(ProcessedNews.processing_timestamp >= day_ago).scalar() or 0
            predictions_24h = db.query(func.count(Prediction.prediction_id)).filter(Prediction.created_at >= day_ago).scalar() or 0
            surprises_24h = db.query(func.count(SurpriseScore.surprise_id)).filter(SurpriseScore.created_at >= day_ago).scalar() or 0
            fact_checks_24h = db.query(func.count(FactVerification.verification_id)).filter(FactVerification.verified_at >= day_ago).scalar() or 0
            try:
                simulations_24h = db.query(func.count(TradingSimulation.simulation_id)).filter(
                    TradingSimulation.created_at >= day_ago
                ).scalar() or 0
            except Exception:
                simulations_24h = 0
            
            avg_quality = db.query(func.avg(DataQualityScore.quality_score)).scalar()
            avg_quality = round(avg_quality, 2) if avg_quality else 0
        
        # Show different layout depending on whether data exists
        if total_news == 0:
            return dbc.Row([
                dbc.Col([
                    dbc.Alert([
                        html.H4("🚀 Willkommen bei ANPS-TradeMeUp!", className="alert-heading"),
                        html.Hr(),
                        html.P("Die Datenbank ist leer. Starte die Pipeline um Daten zu sammeln:", className="mb-3"),
                        html.Ul([
                            html.Li([html.Strong("Option 1:"), " Gehe zum 🎮 Agent Control Tab und klicke 'Run Full Pipeline'"]),
                            html.Li([html.Strong("Option 2:"), " Führe aus: ", html.Code("python scripts/run_mvp_pipeline.py")]),
                            html.Li([html.Strong("Option 3:"), " Quick Test: ", html.Code("python scripts/run_ingestion.py")])
                        ]),
                        html.P(["📖 Mehr Info: ", html.Code("docs/setup/QUICKSTART.md")], className="mb-0")
                    ], color="info", className="shadow")
                ], width=12)
            ])
        
        def metric_card(icon, label, value, value_class, inc_1h, inc_24h):
            return dbc.Card(
                dbc.CardBody([
                    html.Div([
                        html.Span(icon, className="me-1", style={"fontSize": "20px"}),
                        html.Small(label, className="text-muted", style={"fontSize": "0.85rem"})
                    ], className="d-flex align-items-center"),
                    html.Div(f"{value:,}", className=f"{value_class} fw-bold", style={"fontSize": "1.5rem"}),
                    html.Div([
                        html.Small(f"+{inc_1h} 1h", className="text-success me-2"),
                        html.Small(f"+{inc_24h} 24h", className="text-info")
                    ], className="d-flex flex-wrap", style={"fontSize": "0.75rem"})
                ], className="py-2 px-2"),
                className="h-100"
            )

        return html.Div([
            dbc.Row([
                dbc.Col(metric_card("📰", "Articles", total_news, "text-primary", news_1h, news_24h), xs=6, sm=4, md=2),
                dbc.Col(metric_card("🧠", "LLM", total_processed, "text-success", processed_1h, processed_24h), xs=6, sm=4, md=2),
                dbc.Col(metric_card("🔮", "Predictions", total_predictions, "text-info", predictions_1h, predictions_24h), xs=6, sm=4, md=2),
                dbc.Col(metric_card("🎯", "Surprises", total_surprises, "text-warning", surprises_1h, surprises_24h), xs=6, sm=4, md=2),
                dbc.Col(metric_card("✅", "Fact Checks", total_fact_checks, "text-success", fact_checks_1h, fact_checks_24h), xs=6, sm=4, md=2),
                dbc.Col(metric_card("🧪", "Simulations", total_simulations, "text-primary", simulations_1h, simulations_24h), xs=6, sm=4, md=2),
            ], className="g-2 mb-2")
        ])
    except Exception as e:
        return dbc.Row([
            dbc.Col([
                dbc.Alert(
                    "⚠️ Unable to load metrics. Database may be empty. Run the pipeline to generate data.",
                    color="warning"
                )
            ], width=12)
        ])


def get_recent_news(engine, limit=50):
    """Get recent news table with configurable limit"""
    try:
        with Session(engine) as db:
            recent = db.query(RawNews).order_by(desc(RawNews.fetched_at)).limit(limit).all()
            
            if not recent:
                return html.P("No news available. Run Agent 1 (Ingestion) to fetch news.", className="text-muted")
        
        rows = []
        for news in recent:
            rows.append(html.Tr([
                html.Td(news.fetched_at.strftime("%H:%M") if news.fetched_at else "N/A"),
                html.Td(news.source, className="text-primary"),
                html.Td([
                    html.A(
                        news.title[:80] + "..." if len(news.title) > 80 else news.title,
                        href=news.url,
                        target="_blank",
                        className="text-decoration-none"
                    )
                ])
            ]))
        
        return dbc.Table([
            html.Thead(html.Tr([
                html.Th("Time"),
                html.Th("Source"),
                html.Th("Title")
            ])),
            html.Tbody(rows)
        ], bordered=True, hover=True, size="sm", className="table-dark")
    except Exception as e:
        return html.P("⚠️ Unable to load recent news. Database may be empty.", className="text-warning")


def get_market_regime(engine):
    """Get current market regime"""
    try:
        with Session(engine) as db:
            regime = db.query(MarketRegime).order_by(desc(MarketRegime.created_at)).first()
            
            if not regime:
                return html.Div([
                    html.Small("🌡️ No market regime data yet", className="text-muted mb-1", style={"fontSize": "0.75rem"}),
                    html.Small("Run Agent 5 (Regime Detection)", className="text-muted", style={"fontSize": "0.65rem"})
                ])
            
            # Extract data within session context to avoid lazy loading issues
            # regime is a JSONB column with volatility, trend, risk_appetite, liquidity
            regime_dict = _ensure_dict(regime.regime, {})
            vol_regime = regime_dict.get('volatility', 'unknown')
            trend_regime = regime_dict.get('trend', 'unknown')
            risk_appetite = regime_dict.get('risk_appetite', 'unknown')
            liquidity = regime_dict.get('liquidity', 'unknown')
            created_str = regime.created_at.strftime('%Y-%m-%d %H:%M') if regime.created_at else "N/A"
            
            vol_colors = {"low": "success", "medium": "warning", "high": "danger"}
            trend_colors = {"bull": "success", "bear": "danger", "sideways": "secondary"}
        
            return html.Div([
                html.Div([
                    html.Small("Volatility: ", className="text-muted", style={"fontSize": "0.75rem"}),
                    dbc.Badge(
                        vol_regime.upper(),
                        color=vol_colors.get(vol_regime, "secondary"),
                        text_color="dark",
                        className="ms-1",
                        style={"fontSize": "0.65rem"}
                    )
                ], className="mb-1"),
                html.Div([
                    html.Small("Trend: ", className="text-muted", style={"fontSize": "0.75rem"}),
                    dbc.Badge(
                        trend_regime.upper(),
                        color=trend_colors.get(trend_regime, "secondary"),
                        text_color="dark",
                        className="ms-1",
                        style={"fontSize": "0.65rem"}
                    )
                ], className="mb-1"),
                html.Div([
                    html.Small("Risk Appetite: ", className="text-muted", style={"fontSize": "0.75rem"}),
                    dbc.Badge(risk_appetite.upper(), color="info", text_color="dark", className="ms-1", style={"fontSize": "0.65rem"})
                ], className="mb-1"),
                html.Div([
                    html.Small("Liquidity: ", className="text-muted", style={"fontSize": "0.75rem"}),
                    dbc.Badge(liquidity.upper(), color="primary", text_color="dark", className="ms-1", style={"fontSize": "0.65rem"})
                ], className="mb-2"),
                html.Small(
                    f"Detected: {created_str}",
                    className="text-muted",
                    style={"fontSize": "0.65rem"}
                )
            ])
    except Exception as e:
        import traceback
        error_detail = str(e)
        traceback.print_exc()
        return html.Div([
            html.P("⚠️ Error loading regime data", className="text-warning mb-2"),
            html.Small(f"Error: {error_detail}", className="text-muted")
        ])


def get_live_agent_activity():
    """Get live agent activity status"""
    # Check if pipeline log file exists
    log_file = Path("logs/pipeline_activity.log")
    
    if not log_file.exists():
        # Show friendly startup message instead of "No logs available"
        return html.Div([
            html.Div([
                html.Span("● ", className="text-success", style={"font-size": "20px"}),
                html.Strong("Dashboard Active", className="text-success")
            ], className="mb-3"),
            html.Hr(),
            html.P([
                "✨ System bereit für Pipeline-Ausführung",
            ], className="text-muted mb-2"),
            html.P([
                "🎮 Gehe zu ",
                html.Strong("Agent Control", className="text-info"),
                " Tab um Pipeline zu starten"
            ], className="text-muted mb-2"),
            html.P([
                "⚡ Oder führe aus: ",
                html.Code("python scripts/run_mvp_pipeline.py", style={
                    "backgroundColor": "#1a1a1a",
                    "padding": "2px 6px",
                    "borderRadius": "3px",
                    "fontSize": "12px"
                })
            ], className="text-muted small")
        ])
    
    try:
        # Read last few lines from activity log
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            recent_lines = lines[-10:] if len(lines) > 10 else lines
        
        if not recent_lines:
            return html.Div([
                html.Div([
                    html.Span("● ", className="text-secondary"),
                    html.Strong("System Idle", className="text-muted")
                ], className="mb-2")
            ])
        
        # Parse and display activity
        activities = []
        for line in recent_lines:
            line = line.strip()
            if not line:
                continue
            
            # Determine status color based on keywords
            if "ERROR" in line or "FAILED" in line:
                color = "danger"
                icon = "❌"
            elif "SUCCESS" in line or "COMPLETED" in line:
                color = "success"
                icon = "✅"
            elif "PROCESSING" in line or "RUNNING" in line:
                color = "primary"
                icon = "🔄"
            elif "STARTING" in line:
                color = "info"
                icon = "▶️"
            else:
                color = "secondary"
                icon = "●"
            
            activities.append(
                html.Div([
                    html.Span(f"{icon} ", className=f"text-{color}"),
                    html.Small(line[:100], className="text-light")
                ], className="mb-1")
            )
        
        return html.Div(activities if activities else [
            html.Div([
                html.Span("● ", className="text-secondary"),
                html.Strong("System Idle", className="text-muted")
            ])
        ])
        
    except Exception as e:
        return html.Div([
            html.Span("⚠️ ", className="text-warning"),
            html.Small(f"Error reading activity log: {str(e)}", className="text-muted")
        ])


def get_top_performers(engine, timeframe='24h', limit=10):
    """Get top performing simulations with validity check based on horizon"""
    try:
        with Session(engine, expire_on_commit=False) as db:
            # Use timezone-aware datetime for PostgreSQL compatibility
            from datetime import timezone
            now = datetime.now(timezone.utc)
            
            # Calculate timeframe cutoff
            timeframe_map = {
                '1h': timedelta(hours=1),
                '12h': timedelta(hours=12),
                '24h': timedelta(hours=24),
                '5d': timedelta(days=5),
                '30d': timedelta(days=30),
                '1y': timedelta(days=365),
                'all': timedelta(days=10000)  # Effectively no limit
            }
            cutoff = now - timeframe_map.get(timeframe, timedelta(hours=24))
            
            # Horizon validity map (how long a prediction is valid)
            horizon_validity = {
                '1d': timedelta(days=1),
                '5d': timedelta(days=5),
                '20d': timedelta(days=20)
            }
            
            # Query simulations with eager loading (including prediction outcomes)
            query = db.query(TradingSimulation).options(
                joinedload(TradingSimulation.entity),
                joinedload(TradingSimulation.prediction).joinedload(Prediction.outcome)
            ).filter(
                TradingSimulation.created_at >= cutoff,
                TradingSimulation.decision != 'hold',  # Only active positions
                TradingSimulation.expected_return_pct.isnot(None)
            )
            
            simulations = query.all()
            
            # Filter for validity based on prediction date + horizon
            valid_sims = []
            for sim in simulations:
                # Skip simulations without real market data
                # Check if simulation has valid outcome data with non-zero returns
                has_valid_data = False
                
                # Check actual_return_pct from simulation (may be outdated)
                if sim.actual_return_pct is not None and abs(sim.actual_return_pct) > 0.001:
                    has_valid_data = True
                
                # Check outcome data (more reliable, from performance calculation)
                if sim.prediction and sim.prediction.outcome:
                    outcome = sim.prediction.outcome[0] if isinstance(sim.prediction.outcome, list) and len(sim.prediction.outcome) > 0 else None
                    if outcome and outcome.actual_return is not None and abs(outcome.actual_return) > 0.001:
                        has_valid_data = True
                
                # Skip if no valid market data (excludes $0.0000 cases)
                if not has_valid_data:
                    continue
                
                if sim.prediction:
                    pred_created = sim.prediction.created_at
                    horizon = sim.horizon
                    
                    # Check if prediction is still valid
                    if horizon in horizon_validity:
                        validity_end = pred_created + horizon_validity[horizon]
                        if now <= validity_end:
                            valid_sims.append(sim)
                    else:
                        # Unknown horizon, include it
                        valid_sims.append(sim)
                else:
                    # No prediction link, include it
                    valid_sims.append(sim)
            
            if not valid_sims:
                return html.Div([
                    html.Small("No valid simulations in this timeframe", className="text-muted text-center d-block my-2", style={"fontSize": "0.75rem"}),
                    html.Small("Run simulations to see top performers", className="text-muted", style={"fontSize": "0.65rem"})
                ], className="text-center")
            
            # Sort by expected return (descending), then by risk (ascending)
            valid_sims.sort(
                key=lambda s: (
                    -(s.expected_return_pct or 0),  # Higher return first
                    s.risk_score or 1.0              # Lower risk second
                ),
            )
            
            # Deduplicate by entity - keep only the best simulation per firm
            seen_entities = {}
            deduplicated_sims = []
            for sim in valid_sims:
                entity_id = sim.entity_id
                if entity_id not in seen_entities:
                    seen_entities[entity_id] = True
                    deduplicated_sims.append(sim)
            
            # Take top performers (max 10 for display)
            top_sims = deduplicated_sims[:min(limit, 10)]
            
            items = []
            for i, sim in enumerate(top_sims, 1):
                entity = sim.entity
                
                # Get actual performance from PredictionOutcome
                actual_performance = None
                time_ago_str = ""
                if sim.prediction and sim.prediction.outcome:
                    outcome = sim.prediction.outcome[0] if isinstance(sim.prediction.outcome, list) and len(sim.prediction.outcome) > 0 else None
                    if outcome and outcome.actual_return is not None:
                        actual_performance = outcome.actual_return
                        
                        # Calculate time ago
                        if outcome.evaluation_timestamp:
                            time_diff = now - outcome.evaluation_timestamp
                            if time_diff.days > 0:
                                time_ago_str = f"{time_diff.days}d ago"
                            elif time_diff.seconds > 3600:
                                time_ago_str = f"{time_diff.seconds // 3600}h ago"
                            elif time_diff.seconds > 60:
                                time_ago_str = f"{time_diff.seconds // 60}m ago"
                            else:
                                time_ago_str = "just now"
                
                # Calculate time remaining
                if sim.prediction:
                    pred_created = sim.prediction.created_at
                    horizon = sim.horizon
                    if horizon in horizon_validity:
                        validity_end = pred_created + horizon_validity[horizon]
                        time_left = validity_end - now
                        
                        if time_left.days > 0:
                            time_left_str = f"{time_left.days}d left"
                        elif time_left.seconds > 3600:
                            time_left_str = f"{time_left.seconds // 3600}h left"
                        else:
                            time_left_str = f"{time_left.seconds // 60}m left"
                    else:
                        time_left_str = "N/A"
                else:
                    time_left_str = "N/A"
                
                # Color coding
                decision_color = {
                    "buy": "success",
                    "sell": "danger"
                }.get(sim.decision, "secondary")
                
                risk_color = "success" if sim.risk_score and sim.risk_score < 0.3 else "warning" if sim.risk_score and sim.risk_score < 0.6 else "danger"
                
                return_color = "text-success" if sim.expected_return_pct and sim.expected_return_pct > 0 else "text-danger"
                actual_color = "text-success" if actual_performance and actual_performance > 0 else "text-danger" if actual_performance and actual_performance < 0 else "text-muted"
                
                items.append(
                    html.Div([
                        html.Div([
                            html.Div([
                                html.Span(f"#{i}", className="text-muted me-1", style={"fontSize": "0.65rem", "fontWeight": "bold"}),
                                dbc.Button(
                                    entity.entity_name if entity else sim.entity_id,
                                    id={"type": "top-perf-detail-btn", "index": str(sim.prediction_id)},
                                    color="link",
                                    className="p-0 text-primary fw-bold text-decoration-none",
                                    style={"fontSize": "0.75rem", "border": "none", "background": "none"},
                                    title="View prediction details"
                                ),
                                dbc.Badge(sim.decision.upper(), color=decision_color, text_color="dark", className="ms-1", style={"fontSize": "0.6rem", "padding": "2px 4px"})
                            ], className="d-flex align-items-center mb-1"),
                            html.Div([
                                html.Div([
                                    html.Span("Exp: ", className="text-muted", style={"fontSize": "0.65rem"}),
                                    html.Span(
                                        f"{sim.expected_return_pct:+.2f}%" if sim.expected_return_pct else "N/A",
                                        className=f"{return_color} fw-bold",
                                        style={"fontSize": "0.7rem"}
                                    )
                                ], className="me-2"),
                                html.Div([
                                    html.Span("Risk: ", className="text-muted", style={"fontSize": "0.65rem"}),
                                    html.Span(
                                        f"{sim.risk_score:.2f}" if sim.risk_score else "N/A",
                                        className=f"text-{risk_color} fw-bold",
                                        style={"fontSize": "0.7rem"}
                                    )
                                ], className="me-2")
                            ], className="d-flex flex-wrap mb-1"),
                            # Actual Performance Row
                            html.Div([
                                html.Span("📊 ", style={"fontSize": "0.65rem"}),
                                html.Span(
                                    f"{actual_performance:+.2f}%" if actual_performance is not None else "—",
                                    className=f"{actual_color} fw-bold",
                                    style={"fontSize": "0.7rem"}
                                ),
                                html.Span(f" ({time_ago_str})" if time_ago_str else "", className="text-muted", style={"fontSize": "0.6rem", "marginLeft": "3px"})
                            ], className="mb-1"),
                            html.Div([
                                html.Span(sim.horizon or "N/A", className="text-info me-2", style={"fontSize": "0.65rem"}),
                                html.Span(
                                    f"⏱️ {time_left_str}",
                                    className="text-muted",
                                    style={"fontSize": "0.6rem"}
                                )
                            ], className="d-flex")
                        ], className="py-1 px-1"),
                        html.Hr(className="my-0", style={"opacity": "0.3"}) if i < len(top_sims) else None
                    ])
                )
            
            return html.Div(items)
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return html.Div([
            html.Small("⚠️ Error loading top performers", className="text-warning mb-1 d-block", style={"fontSize": "0.75rem"}),
            html.Small(f"Error: {str(e)}", className="text-muted", style={"fontSize": "0.65rem"})
        ])


def _get_server_log_lines(limit: int):
    """Get recent server log lines, including historical flat-file entries."""
    db_rows = []
    earliest_db_timestamp = None

    try:
        from src.models.system_logs import SystemLog

        with Session(engine) as db:
            db_rows = (
                db.query(SystemLog)
                .order_by(SystemLog.timestamp.desc())
                .limit(limit)
                .all()
            )
        if db_rows:
            timestamps = [row.timestamp for row in db_rows if row.timestamp]
            if timestamps:
                earliest_db_timestamp = min(timestamps)
    except Exception:
        db_rows = []

    entries = []
    seen = set()

    for row in db_rows:
        timestamp = row.timestamp.strftime("%Y-%m-%d %H:%M:%S") if row.timestamp else ""
        level = (row.level or "INFO").ljust(7)
        source = (row.source or "system").ljust(12)
        component = f"[{row.component}] " if row.component else ""
        line = f"[{timestamp}] {level} {source} {component}{row.message}"
        key = ("db", timestamp, row.level or "INFO", row.source or "system", row.component or "", row.message or "")
        if key in seen:
            continue
        seen.add(key)
        entries.append((_as_naive_datetime(row.timestamp), line))

    for log_file in _FLAT_LOG_FILES:
        if not log_file.exists():
            continue
        try:
            with open(log_file, "r", encoding="utf-8", errors="ignore") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line:
                        continue
                    match = _FLAT_LOG_PATTERN.match(line)
                    if not match:
                        continue
                    try:
                        parsed_ts = datetime.strptime(
                            match.group("timestamp"), "%Y-%m-%d %H:%M:%S"
                        )
                    except ValueError:
                        continue
                    if earliest_db_timestamp and parsed_ts >= _as_naive_datetime(earliest_db_timestamp):
                        continue
                    key = ("file", parsed_ts.isoformat(), match.group("level"), match.group("message"))
                    if key in seen:
                        continue
                    seen.add(key)
                    entries.append((parsed_ts, line))
        except OSError:
            continue

    if not entries:
        return []

    entries.sort(key=lambda item: item[0])
    lines = [line for _, line in entries[-limit:]]
    return lines


def get_server_logs(limit: int):
    """Get recent server logs as a formatted string."""
    lines = _get_server_log_lines(limit)
    if not lines:
        return "No logs yet. Start the pipeline or wait for activity...\n"
    return "\n".join(lines) + "\n"


def register_callbacks(app):
    """Register dashboard tab callbacks."""

    app.clientside_callback(
        _CLIENTSCRIPT_SERVER_LOGS_SCROLL,
        Output("server-logs-scroll-trigger", "children"),
        Input("server-logs-display", "children"),
        Input("server-logs-modal-display", "children"),
        Input("server-logs-modal", "is_open"),
        Input("server-logs-live-toggle", "value"),
        prevent_initial_call=False,
    )

    @app.callback(
        Output("dashboard-metrics", "children"),
        Input("interval-component", "n_intervals"),
    )
    @safe_callback(default_return=html.Div("⚠️ Unable to load metrics", className="text-warning"))
    def update_dashboard_metrics(n):
        return get_metrics(engine)

    @app.callback(
        Output("recent-news-table", "children"),
        Input("interval-component", "n_intervals"),
    )
    @safe_callback(default_return=html.Div("⚠️ Unable to load news", className="text-warning"))
    def update_recent_news(n):
        return get_recent_news(engine, limit=50)

    @app.callback(
        Output("market-regime-display", "children"),
        Input("interval-component", "n_intervals"),
    )
    @safe_callback(default_return=html.Div("⚠️ Unable to load market regime", className="text-warning"))
    def update_market_regime(n):
        return get_market_regime(engine)

    @app.callback(
        Output("live-agent-activity", "children"),
        Input("interval-component", "n_intervals"),
    )
    @safe_callback(default_return=html.Div("⚠️ Unable to load activity", className="text-warning"))
    def update_live_agent_activity(n):
        return get_live_agent_activity()

    @app.callback(
        [
            Output("server-logs-display", "children"),
            Output("server-logs-modal-display", "children"),
        ],
        Input("interval-component", "n_intervals"),
    )
    @safe_callback(default_return=["", ""])
    def update_server_logs(n):
        return (
            get_server_logs(_SERVER_LOG_CARD_LIMIT),
            get_server_logs(_SERVER_LOG_MODAL_LIMIT),
        )

    @app.callback(
        Output("server-logs-modal", "is_open"),
        [
            Input("open-server-logs-modal", "n_clicks"),
            Input("close-server-logs-modal", "n_clicks"),
        ],
        State("server-logs-modal", "is_open"),
        prevent_initial_call=True,
    )
    def toggle_server_logs_modal(open_clicks, close_clicks, is_open):
        from dash import callback_context

        if not callback_context.triggered:
            return is_open

        trigger = callback_context.triggered[0]["prop_id"].split(".")[0]
        if trigger == "open-server-logs-modal" and open_clicks:
            return True
        if trigger == "close-server-logs-modal" and close_clicks:
            return False
        return is_open

    @app.callback(
        Output("performance-chart", "figure"),
        Input("interval-component", "n_intervals"),
    )
    def update_performance_chart(n):
        from datetime import timezone
        dates = pd.date_range(end=datetime.now(timezone.utc), periods=30, freq="D")
        accuracy = [0.65 + (i % 10) * 0.03 for i in range(30)]
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=accuracy,
                mode="lines+markers",
                name="Accuracy",
                line=dict(color="#00d9ff", width=3),
            )
        )
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title="Date",
            yaxis_title="Accuracy",
            yaxis=dict(range=[0, 1]),
            margin=dict(l=40, r=40, t=40, b=40),
        )
        return fig

    @app.callback(
        Output("top-performers-list", "children"),
        [Input("interval-component", "n_intervals"),
         Input("top-performers-timeframe", "value")]
    )
    @safe_callback(default_return=html.Div("⚠️ Unable to load top performers", className="text-warning"))
    def update_top_performers(n, timeframe):
        return get_top_performers(engine, timeframe=timeframe or '24h', limit=10)

    @app.callback(
        [Output("prediction-modal", "is_open", allow_duplicate=True),
         Output("prediction-detail-cache", "data", allow_duplicate=True),
         Output("current-prediction-id", "data", allow_duplicate=True)],
        [Input({"type": "top-perf-detail-btn", "index": dash.ALL}, "n_clicks"),
         Input("close-prediction-modal", "n_clicks")],
        [State("prediction-modal", "is_open"),
         State({"type": "top-perf-detail-btn", "index": dash.ALL}, "id")],
        prevent_initial_call=True
    )
    def toggle_top_performer_modal(detail_clicks, close_click, is_open, button_ids):
        """Open/close prediction detail modal from top performers"""
        import json
        import dash
        from dash import callback_context
        
        if not callback_context.triggered:
            return dash.no_update, dash.no_update, dash.no_update
        
        trigger_id = callback_context.triggered[0]["prop_id"]
        trigger_value = callback_context.triggered[0].get("value")
        
        # Skip if no actual click (None or 0)
        if trigger_value is None or trigger_value == 0:
            return dash.no_update, dash.no_update, dash.no_update
        
        # Close button clicked
        if "close-prediction-modal" in trigger_id:
            return False, dash.no_update, dash.no_update
        
        # Detail button clicked
        if "top-perf-detail-btn" in trigger_id and ".n_clicks" in trigger_id:
            try:
                id_str = trigger_id.split('.')[0]
                id_dict = json.loads(id_str)
                prediction_id = id_dict.get("index")
                
                if prediction_id:
                    logger.info(f"Opening modal for prediction: {prediction_id}")
                    # Load live performance to get price data
                    return True, {"prediction_id": prediction_id, "load_performance": True}, prediction_id
            except Exception as e:
                logger.error(f"Error parsing top performer button: {e}")
        
        return dash.no_update, dash.no_update, dash.no_update

    # NOTE: Modal content update is now handled by predictions tab callback
    # to avoid duplicate callback conflicts. The predictions tab callback
    # reads from both portfolio-capital-input and portfolio-capital-store.
