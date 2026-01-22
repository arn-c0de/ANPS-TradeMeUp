"""
Dashboard Tab - Overview and Key Metrics
"""

import os
from dash import dcc, html
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta
from sqlalchemy import func, desc
from sqlalchemy.orm import Session
from pathlib import Path

from src.models.raw_news import RawNews
from src.models.data_quality import DataQualityScore
from src.models.processed_news import ProcessedNews
from src.models.predictions import Prediction
from src.models.analysis import MarketRegime
from src.gui.components import create_metric_card


def create_layout():
    """Create dashboard tab layout"""
    return dbc.Container([
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
                        html.Div(id="recent-news-table")
                    ])
                ])
            ], width=8),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("🌡️ Current Market Regime")),
                    dbc.CardBody([
                        html.Div(id="market-regime-display")
                    ])
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
                    dbc.CardHeader(html.H5("📋 Server Logs (Last 20 lines)")),
                    dbc.CardBody([
                        dcc.Textarea(
                            id="server-logs-display",
                            style={
                                'width': '100%',
                                'height': '300px',
                                'fontFamily': 'monospace',
                                'fontSize': '12px',
                                'backgroundColor': '#1a1a1a',
                                'color': '#00ff00',
                                'border': '1px solid #333',
                                'padding': '10px'
                            },
                            readOnly=True
                        )
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
        ])
    ], fluid=True)


def get_metrics(engine):
    """Get dashboard metrics"""
    try:
        with Session(engine) as db:
            total_news = db.query(func.count(RawNews.news_id)).scalar() or 0
            total_processed = db.query(func.count(ProcessedNews.news_id)).scalar() or 0
            total_predictions = db.query(func.count(Prediction.prediction_id)).scalar() or 0
            
            avg_quality = db.query(func.avg(DataQualityScore.quality_score)).scalar()
            avg_quality = round(avg_quality, 2) if avg_quality else 0
            
            recent_news = db.query(func.count(RawNews.news_id)).filter(
                RawNews.fetched_at >= datetime.now() - timedelta(hours=24)
            ).scalar() or 0
        
        return dbc.Row([
            dbc.Col([
                create_metric_card("Total Articles", f"{total_news:,}", "in database", "📰")
            ], width=3),
            dbc.Col([
                create_metric_card("LLM Processed", f"{total_processed:,}", "articles analyzed", "🧠", "success")
            ], width=3),
            dbc.Col([
                create_metric_card("Avg Quality", f"{avg_quality:.2f}", "out of 1.0", "⭐", "warning")
            ], width=3),
            dbc.Col([
                create_metric_card("Last 24h", f"+{recent_news}", "new articles", "🔥", "danger")
            ], width=3)
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


def get_recent_news(engine):
    """Get recent news table"""
    try:
        with Session(engine) as db:
            recent = db.query(RawNews).order_by(desc(RawNews.fetched_at)).limit(10).all()
            
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
                    html.P("🌡️ No market regime data yet", className="text-muted mb-2"),
                    html.Small("Run Agent 5 (Regime Detection) to generate regime data", className="text-muted")
                ])
            
            # Extract data within session context to avoid lazy loading issues
            # regime is a JSON column with volatility, trend, risk_appetite, liquidity
            regime_dict = regime.regime if isinstance(regime.regime, dict) else {}
            vol_regime = regime_dict.get('volatility', 'unknown')
            trend_regime = regime_dict.get('trend', 'unknown')
            risk_appetite = regime_dict.get('risk_appetite', 'unknown')
            liquidity = regime_dict.get('liquidity', 'unknown')
            created_str = regime.created_at.strftime('%Y-%m-%d %H:%M') if regime.created_at else "N/A"
            
            vol_colors = {"low": "success", "medium": "warning", "high": "danger"}
            trend_colors = {"bull": "success", "bear": "danger", "sideways": "secondary"}
        
            return html.Div([
                html.Div([
                    html.Strong("Volatility: "),
                    dbc.Badge(
                        vol_regime.upper(),
                        color=vol_colors.get(vol_regime, "secondary"),
                        className="ms-2"
                    )
                ], className="mb-2"),
                html.Div([
                    html.Strong("Trend: "),
                    dbc.Badge(
                        trend_regime.upper(),
                        color=trend_colors.get(trend_regime, "secondary"),
                        className="ms-2"
                    )
                ], className="mb-2"),
                html.Div([
                    html.Strong("Risk Appetite: "),
                    dbc.Badge(risk_appetite.upper(), color="info", className="ms-2")
                ], className="mb-2"),
                html.Div([
                    html.Strong("Liquidity: "),
                    dbc.Badge(liquidity.upper(), color="primary", className="ms-2")
                ], className="mb-3"),
                html.Small(
                    f"Detected: {created_str}",
                    className="text-muted"
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


def get_server_logs():
    """Get recent server logs"""
    log_file = Path("logs/dashboard.log")
    
    if not log_file.exists():
        return """╔══════════════════════════════════════════════════════════════╗
║  TradeMeUp Dashboard - Live Server Logs                     ║
╚══════════════════════════════════════════════════════════════╝

✨ Dashboard wurde erfolgreich gestartet!

📊 Status: AKTIV
🔄 Auto-Update: Alle 5 Sekunden
🎮 Bereit für Pipeline-Ausführung

──────────────────────────────────────────────────────────────

💡 So startest du die Pipeline:

   1. Gehe zum "🎮 Agent Control" Tab
   2. Klicke "Run Full Pipeline" oder "Run Quick Test"
   3. Beobachte hier die Live-Logs!

──────────────────────────────────────────────────────────────

⚡ Oder führe in einem separaten Terminal aus:
   python scripts/run_mvp_pipeline.py

──────────────────────────────────────────────────────────────

Warte auf Agent-Aktivitäten...
"""
    
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # Get last 20 lines
            recent_lines = lines[-20:] if len(lines) > 20 else lines
            return ''.join(recent_lines)
    except Exception as e:
        return f"Error reading logs: {str(e)}\n"
