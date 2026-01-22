"""
System Health Tab - Monitor Agent Status and Performance
"""

from dash import html
import dash_bootstrap_components as dbc
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.raw_news import RawNews
from src.models.processed_news import ProcessedNews
from src.models.entities import Entity
from src.models.predictions import Prediction
from src.models.analysis import ImpactScore


def create_layout():
    """Create system health tab layout"""
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("🤖 Agent Pipeline Status")),
                    dbc.CardBody([
                        html.Div(id="agent-status")
                    ])
                ])
            ], width=12)
        ], className="mb-3"),
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("📊 Database Statistics")),
                    dbc.CardBody([
                        html.Div(id="db-statistics")
                    ])
                ])
            ], width=6),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("⚡ Processing Pipeline")),
                    dbc.CardBody([
                        html.Div(id="pipeline-stats")
                    ])
                ])
            ], width=6)
        ])
    ], fluid=True)


def get_agent_status():
    """Get agent status display"""
    agents = [
        ("Agent 1", "Data Ingestion", "✅ Running", "success"),
        ("Agent 1.5", "Data Quality", "✅ Running", "success"),
        ("Agent 2", "Content Understanding", "✅ Running", "success"),
        ("Agent 3", "Entity Mapping", "⚠️ Needs Tuning", "warning"),
        ("Agent 4", "Impact Scoring", "✅ Running", "success"),
        ("Agent 4.5", "Surprise Quantification", "✅ Running", "success"),
        ("Agent 5", "Market Regime", "✅ Running", "success"),
        ("Agent 6", "Predictions", "✅ Running", "success")
    ]
    
    rows = []
    for agent_id, name, status, color in agents:
        rows.append(html.Tr([
            html.Td(agent_id, className="text-primary"),
            html.Td(name),
            html.Td(status, className=f"text-{color}")
        ]))
    
    return dbc.Table([
        html.Thead(html.Tr([
            html.Th("Agent ID"),
            html.Th("Name"),
            html.Th("Status")
        ])),
        html.Tbody(rows)
    ], bordered=True, hover=True, className="table-dark")


def get_db_statistics(engine):
    """Get database statistics"""
    try:
        with Session(engine) as db:
            stats = {
                "📰 Raw News": db.query(func.count(RawNews.news_id)).scalar() or 0,
                "🧠 Processed News": db.query(func.count(ProcessedNews.news_id)).scalar() or 0,
                "🏢 Entities": db.query(func.count(Entity.entity_id)).scalar() or 0,
                "🎯 Predictions": db.query(func.count(Prediction.prediction_id)).scalar() or 0,
                "⚡ Impact Scores": db.query(func.count(ImpactScore.impact_id)).scalar() or 0
            }
        
        items = []
        for key, value in stats.items():
            items.append(html.Div([
                html.Strong(f"{key}: "),
                html.Span(f"{value:,}", className="text-primary")
            ], className="mb-2"))
        
        return html.Div(items)
    except Exception as e:
        return html.Div([
            html.P("⚠️ Unable to load database statistics", className="text-warning mb-2"),
            html.Small("Database may be empty. Run the pipeline to generate data.", className="text-muted")
        ])


def get_pipeline_stats(engine):
    """Get pipeline processing stats"""
    try:
        with Session(engine) as db:
            total_news = db.query(func.count(RawNews.news_id)).scalar() or 0
            processed = db.query(func.count(ProcessedNews.news_id)).scalar() or 0
            
            processing_rate = (processed / total_news * 100) if total_news > 0 else 0
        
        return html.Div([
            html.Div([
                html.H4(f"{processing_rate:.1f}%", className="text-success"),
                html.P("Processing Completion Rate", className="text-muted")
            ], className="text-center mb-3"),
            dbc.Progress(value=processing_rate, color="success", className="mb-2"),
            html.Small(f"{processed:,} of {total_news:,} articles processed", className="text-muted")
        ])
    except Exception as e:
        return html.Div([
            html.P("⚠️ Unable to load pipeline stats", className="text-warning mb-2"),
            html.Small("Database may be empty. Run the pipeline to generate data.", className="text-muted")
        ])
