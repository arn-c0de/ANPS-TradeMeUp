"""
Dashboard Tab - Overview and Key Metrics
"""

from dash import dcc, html
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

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
                    dbc.CardHeader(html.H5("📊 Model Performance (30d)")),
                    dbc.CardBody([
                        dcc.Graph(id="performance-chart")
                    ])
                ])
            ], width=12)
        ])
    ], fluid=True)


def get_metrics(engine):
    """Get dashboard metrics"""
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


def get_recent_news(engine):
    """Get recent news table"""
    with Session(engine) as db:
        recent = db.query(RawNews).order_by(desc(RawNews.fetched_at)).limit(10).all()
        
        if not recent:
            return html.P("No news available.", className="text-muted")
        
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


def get_market_regime(engine):
    """Get current market regime"""
    with Session(engine) as db:
        regime = db.query(MarketRegime).order_by(desc(MarketRegime.created_at)).first()
        
        if not regime:
            return html.P("No regime data available.", className="text-muted")
        
        vol_colors = {"low": "success", "medium": "warning", "high": "danger"}
        trend_colors = {"bull": "success", "bear": "danger", "sideways": "secondary"}
        
        return html.Div([
            html.Div([
                html.Strong("Volatility: "),
                dbc.Badge(
                    regime.volatility_regime.upper(),
                    color=vol_colors.get(regime.volatility_regime, "secondary"),
                    className="ms-2"
                )
            ], className="mb-2"),
            html.Div([
                html.Strong("Trend: "),
                dbc.Badge(
                    regime.trend_regime.upper(),
                    color=trend_colors.get(regime.trend_regime, "secondary"),
                    className="ms-2"
                )
            ], className="mb-2"),
            html.Div([
                html.Strong("Risk Appetite: "),
                dbc.Badge(regime.risk_appetite.upper(), color="info", className="ms-2")
            ], className="mb-2"),
            html.Div([
                html.Strong("Liquidity: "),
                dbc.Badge(regime.liquidity_regime.upper(), color="primary", className="ms-2")
            ], className="mb-3"),
            html.Small(
                f"Detected: {regime.created_at.strftime('%Y-%m-%d %H:%M')}",
                className="text-muted"
            )
        ])
