"""
Statistics Tab - Analytics and Metrics
"""

from dash import dcc, html
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.raw_news import RawNews
from src.models.data_quality import DataQualityScore
from src.models.processed_news import ProcessedNews
from src.models.predictions import Prediction
from src.models.entities import Entity
from src.models.analysis import ImpactScore


def create_layout():
    """Create statistics tab layout"""
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("📊 Overall Metrics")),
                    dbc.CardBody([
                        html.Div(id="statistics-metrics")
                    ])
                ])
            ], width=12)
        ], className="mb-3"),
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
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("📰 News Volume Over Time")),
                    dbc.CardBody([
                        dcc.Graph(id="news-volume-chart")
                    ])
                ])
            ], width=12)
        ])
    ], fluid=True)


def get_statistics_metrics(engine):
    """Get overall statistics"""
    try:
        with Session(engine) as db:
            total_news = db.query(func.count(RawNews.news_id)).scalar() or 0
            total_processed = db.query(func.count(ProcessedNews.news_id)).scalar() or 0
            total_entities = db.query(func.count(Entity.entity_id)).scalar() or 0
            total_predictions = db.query(func.count(Prediction.prediction_id)).scalar() or 0
            total_impacts = db.query(func.count(ImpactScore.score_id)).scalar() or 0
            
            avg_quality = db.query(func.avg(DataQualityScore.quality_score)).scalar()
            avg_quality = round(avg_quality, 2) if avg_quality else 0
        
        return dbc.Row([
            dbc.Col([
                html.Div([
                    html.H3(f"{total_news:,}", className="text-primary"),
                    html.P("Total Articles", className="text-muted mb-0")
                ], className="text-center")
            ], width=2),
            dbc.Col([
                html.Div([
                    html.H3(f"{total_processed:,}", className="text-success"),
                    html.P("Processed", className="text-muted mb-0")
                ], className="text-center")
            ], width=2),
            dbc.Col([
                html.Div([
                    html.H3(f"{total_entities:,}", className="text-info"),
                    html.P("Entities", className="text-muted mb-0")
                ], className="text-center")
            ], width=2),
            dbc.Col([
                html.Div([
                    html.H3(f"{total_predictions:,}", className="text-warning"),
                    html.P("Predictions", className="text-muted mb-0")
                ], className="text-center")
            ], width=2),
            dbc.Col([
                html.Div([
                    html.H3(f"{total_impacts:,}", className="text-danger"),
                    html.P("Impact Scores", className="text-muted mb-0")
                ], className="text-center")
            ], width=2),
            dbc.Col([
                html.Div([
                    html.H3(f"{avg_quality:.2f}", className="text-primary"),
                    html.P("Avg Quality", className="text-muted mb-0")
                ], className="text-center")
            ], width=2)
        ])
    except Exception as e:
        import logging
        logging.error(f"Error loading statistics: {e}", exc_info=True)
        return dbc.Row([
            dbc.Col([
                html.Div([
                    html.P("⚠️ Unable to load statistics", className="text-warning mb-2"),
                    html.Small(f"Error: {str(e)}", className="text-muted")
                ], className="text-center")
            ], width=12)
        ])


def get_event_distribution_chart(engine):
    """Get event type distribution chart"""
    try:
        with Session(engine) as db:
            event_data = db.query(
                ProcessedNews.event_type,
            func.count(ProcessedNews.news_id).label('count')
        ).group_by(ProcessedNews.event_type).all()
        
        if not event_data:
            return {}
        
        event_df = pd.DataFrame(event_data, columns=['event_type', 'count'])
        fig = px.bar(
            event_df, x='event_type', y='count',
            color='event_type',
            template="plotly_dark"
        )
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            showlegend=False,
            xaxis_title="Event Type",
            yaxis_title="Count"
        )
        return fig
    except Exception as e:
        # Return empty figure with message
        import plotly.graph_objects as go
        fig = go.Figure()
        fig.add_annotation(
            text="No data available yet<br>Run the pipeline to see event distribution",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(visible=False),
            yaxis=dict(visible=False)
        )
        return fig


def get_quality_distribution_chart(engine):
    """Get quality distribution chart"""
    try:
        with Session(engine) as db:
            quality_data = db.query(DataQualityScore.quality_score).all()
        
        if not quality_data:
            return {}
        
        scores = [q[0] for q in quality_data if q[0] is not None]
        fig = px.histogram(
            x=scores,
            nbins=20,
            template="plotly_dark"
        )
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis_title="Quality Score",
            yaxis_title="Count"
        )
        return fig
    except Exception as e:
        # Return empty figure with message
        import plotly.graph_objects as go
        fig = go.Figure()
        fig.add_annotation(
            text="No data available yet<br>Run the pipeline to see quality distribution",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="gray")
        )
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(visible=False),
            yaxis=dict(visible=False)
        )
        return fig


def get_news_volume_chart(engine):
    """Get news volume over time chart"""
    try:
        with Session(engine) as db:
            # Query news by date (SQLite-compatible)
            from sqlalchemy import func as sql_func
            
            volume_data = db.query(
                sql_func.date(RawNews.fetched_at).label('date'),
                sql_func.count(RawNews.news_id).label('count')
            ).filter(
                RawNews.fetched_at.isnot(None)
            ).group_by(
                sql_func.date(RawNews.fetched_at)
            ).order_by('date').all()
        
        if not volume_data:
            import plotly.graph_objects as go
            fig = go.Figure()
            fig.add_annotation(
                text="No data available yet<br>Run the pipeline to ingest news",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=14, color="gray")
            )
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(visible=False),
                yaxis=dict(visible=False)
            )
            return fig
        
        volume_df = pd.DataFrame(volume_data, columns=['date', 'count'])
        
        fig = px.line(
            volume_df,
            x='date',
            y='count',
            template="plotly_dark",
            markers=True
        )
        fig.update_traces(
            line=dict(color='#00d9ff', width=2),
            marker=dict(size=6)
        )
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis_title="Date",
            yaxis_title="Number of Articles",
            hovermode='x unified',
            margin=dict(l=40, r=40, t=40, b=40)
        )
        return fig
    except Exception as e:
        import plotly.graph_objects as go
        import logging
        logging.error(f"Error creating news volume chart: {e}", exc_info=True)
        
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error loading chart<br>{str(e)[:50]}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color="red")
        )
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(visible=False),
            yaxis=dict(visible=False)
        )
        return fig
