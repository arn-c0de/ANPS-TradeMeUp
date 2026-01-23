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
from src.models.analysis import ImpactScore, SurpriseScore, SignalDecayModel, FactVerification, MarketRegime
from src.gui.error_handling import handle_db_errors, create_empty_state


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
                    dbc.CardHeader(html.H5("🎭 Sentiment Distribution")),
                    dbc.CardBody([
                        dcc.Graph(id="sentiment-distribution-chart")
                    ])
                ])
            ], width=4),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("💥 Impact Score Distribution")),
                    dbc.CardBody([
                        dcc.Graph(id="impact-distribution-chart")
                    ])
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


@handle_db_errors(default_message="Unable to load statistics", show_details=False)
def get_statistics_metrics(engine):
    """Get overall statistics"""
    try:
        with Session(engine) as db:
            total_news = db.query(func.count(RawNews.news_id)).scalar() or 0
            total_processed = db.query(func.count(ProcessedNews.news_id)).scalar() or 0
            total_entities = db.query(func.count(Entity.entity_id)).scalar() or 0
            total_predictions = db.query(func.count(Prediction.prediction_id)).scalar() or 0
            total_impacts = db.query(func.count(ImpactScore.score_id)).scalar() or 0
            total_surprises = db.query(func.count(SurpriseScore.surprise_id)).scalar() or 0
            total_regimes = db.query(func.count(MarketRegime.regime_id)).scalar() or 0
            total_fact_checks = db.query(func.count(FactVerification.verification_id)).scalar() or 0
            
            avg_quality = db.query(func.avg(DataQualityScore.quality_score)).scalar()
            avg_quality = round(avg_quality, 2) if avg_quality else 0
        
        return html.Div([
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.H4(f"{total_news:,}", className="text-primary mb-1"),
                        html.Small("Total Articles", className="text-muted")
                    ], className="text-center")
                ], width=2),
                dbc.Col([
                    html.Div([
                        html.H4(f"{total_processed:,}", className="text-success mb-1"),
                        html.Small("Processed", className="text-muted")
                    ], className="text-center")
                ], width=2),
                dbc.Col([
                    html.Div([
                        html.H4(f"{total_entities:,}", className="text-info mb-1"),
                        html.Small("Entities", className="text-muted")
                    ], className="text-center")
                ], width=1),
                dbc.Col([
                    html.Div([
                        html.H4(f"{total_predictions:,}", className="text-warning mb-1"),
                        html.Small("Predictions", className="text-muted")
                    ], className="text-center")
                ], width=2),
                dbc.Col([
                    html.Div([
                        html.H4(f"{total_impacts:,}", className="text-danger mb-1"),
                        html.Small("Impact Scores", className="text-muted")
                    ], className="text-center")
                ], width=2),
                dbc.Col([
                    html.Div([
                        html.H4(f"{total_surprises:,}", className="text-warning mb-1"),
                        html.Small("Surprises", className="text-muted")
                    ], className="text-center")
                ], width=1),
                dbc.Col([
                    html.Div([
                        html.H4(f"{total_fact_checks:,}", className="text-success mb-1"),
                        html.Small("Fact Checks", className="text-muted")
                    ], className="text-center")
                ], width=1),
                dbc.Col([
                    html.Div([
                        html.H4(f"{avg_quality:.2f}", className="text-primary mb-1"),
                        html.Small("Avg Quality", className="text-muted")
                    ], className="text-center")
                ], width=1)
            ])
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


def get_sentiment_distribution_chart(engine):
    """Get sentiment distribution chart"""
    try:
        with Session(engine) as db:
            sentiments_data = db.query(ProcessedNews.sentiment).filter(
                ProcessedNews.sentiment.isnot(None)
            ).all()
        
        if not sentiments_data:
            import plotly.graph_objects as go
            fig = go.Figure()
            fig.add_annotation(
                text="No sentiment data yet<br>Run content analysis",
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
        
        # Extract overall sentiment scores
        import json
        sentiment_scores = []
        for s in sentiments_data:
            if s[0]:
                try:
                    sent_dict = s[0] if isinstance(s[0], dict) else json.loads(s[0])
                    if 'overall' in sent_dict:
                        sentiment_scores.append(sent_dict['overall'])
                except:
                    pass
        
        if not sentiment_scores:
            import plotly.graph_objects as go
            fig = go.Figure()
            fig.add_annotation(
                text="No valid sentiment scores",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=14, color="gray")
            )
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)'
            )
            return fig
        
        # Categorize sentiments
        positive = sum(1 for s in sentiment_scores if s > 0.3)
        neutral = sum(1 for s in sentiment_scores if -0.3 <= s <= 0.3)
        negative = sum(1 for s in sentiment_scores if s < -0.3)
        
        fig = px.pie(
            names=['Positive', 'Neutral', 'Negative'],
            values=[positive, neutral, negative],
            color_discrete_sequence=['#28a745', '#6c757d', '#dc3545'],
            template="plotly_dark"
        )
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=20, r=20, t=20, b=20)
        )
        return fig
    except Exception as e:
        import plotly.graph_objects as go
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error: {str(e)[:30]}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=12, color="gray")
        )
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        return fig


def get_impact_distribution_chart(engine):
    """Get impact score distribution chart"""
    try:
        with Session(engine) as db:
            impact_scores = db.query(ImpactScore.impact_score).all()
        
        if not impact_scores:
            import plotly.graph_objects as go
            fig = go.Figure()
            fig.add_annotation(
                text="No impact scores yet<br>Run impact analysis",
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
        
        scores = [s[0] for s in impact_scores if s[0] is not None]
        
        # Categorize
        high = sum(1 for s in scores if s >= 0.7)
        medium = sum(1 for s in scores if 0.4 <= s < 0.7)
        low = sum(1 for s in scores if s < 0.4)
        
        fig = px.bar(
            x=['Low (<0.4)', 'Medium (0.4-0.7)', 'High (≥0.7)'],
            y=[low, medium, high],
            color=['Low', 'Medium', 'High'],
            color_discrete_sequence=['#6c757d', '#ffc107', '#dc3545'],
            template="plotly_dark"
        )
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            showlegend=False,
            xaxis_title="Impact Level",
            yaxis_title="Count",
            margin=dict(l=40, r=20, t=20, b=40)
        )
        return fig
    except Exception as e:
        import plotly.graph_objects as go
        fig = go.Figure()
        fig.add_annotation(
            text=f"Error: {str(e)[:30]}",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=12, color="gray")
        )
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        return fig


def get_top_entities_list(engine):
    """Get top entities by mentions"""
    try:
        with Session(engine) as db:
            top_entities = db.query(
                Entity.entity_name,
                Entity.ticker,
                func.count(NewsEntityMapping.mapping_id).label('mentions')
            ).join(
                NewsEntityMapping,
                Entity.entity_id == NewsEntityMapping.entity_id
            ).group_by(
                Entity.entity_name,
                Entity.ticker
            ).order_by(
                func.count(NewsEntityMapping.mapping_id).desc()
            ).limit(10).all()
        
        if not top_entities:
            return html.P("No entities tracked yet", className="text-muted")
        
        rows = []
        for i, (name, ticker, mentions) in enumerate(top_entities, 1):
            badge_color = "danger" if i <= 3 else "warning" if i <= 6 else "secondary"
            rows.append(
                html.Div([
                    dbc.Badge(f"#{i}", color=badge_color, className="me-2"),
                    html.Span(name, className="text-light"),
                    html.Small(f" ({ticker})" if ticker else "", className="text-muted ms-1"),
                    dbc.Badge(f"{mentions}", color="info", className="ms-auto")
                ], className="d-flex align-items-center mb-2")
            )
        
        return html.Div(rows)
    except Exception as e:
        return html.P(f"Error loading entities: {str(e)[:50]}", className="text-danger")


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
