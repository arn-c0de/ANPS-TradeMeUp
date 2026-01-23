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
from src.models.entities import Entity, NewsEntityMapping
from src.models.analysis import ImpactScore, SurpriseScore, SignalDecayModel, FactVerification, MarketRegime
from src.gui.error_handling import handle_db_errors, create_empty_state


def create_layout():
    """Create statistics tab layout"""
    return dbc.Container([
        # Overall Metrics
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
        
        # Event & Quality Distribution
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
        
        # Sentiment, Impact & Top Entities
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
        
        # NEW: Entity Sentiment Analysis
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.Div([
                            html.H5("📊 Entity Sentiment Analysis", className="mb-0 d-inline"),
                            dbc.Select(
                                id="sentiment-timeframe-selector",
                                options=[
                                    {"label": "Last 7 Days", "value": "7d"},
                                    {"label": "Last 30 Days", "value": "30d"},
                                    {"label": "Last 90 Days", "value": "90d"},
                                    {"label": "All Time", "value": "all"}
                                ],
                                value="30d",
                                className="w-auto d-inline-block ms-3",
                                style={"width": "150px"}
                            )
                        ], className="d-flex align-items-center justify-content-between")
                    ]),
                    dbc.CardBody([
                        dcc.Graph(id="entity-sentiment-chart")
                    ])
                ])
            ], width=12)
        ], className="mb-3"),
        
        # NEW: Top Positive & Negative Entities
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("📈 Top Positive Entities (Last 30 Days)")),
                    dbc.CardBody([
                        html.Div(id="top-positive-entities")
                    ])
                ])
            ], width=6),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("📉 Top Negative Entities (Last 30 Days)")),
                    dbc.CardBody([
                        html.Div(id="top-negative-entities")
                    ])
                ])
            ], width=6)
        ], className="mb-3"),
        
        # NEW: Entity Details Table
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.Div([
                            html.H5("🏢 Entity Details", className="mb-0 d-inline"),
                            dbc.Input(
                                id="entity-search-input",
                                type="text",
                                placeholder="Search entities...",
                                className="d-inline-block ms-3",
                                style={"width": "300px"}
                            )
                        ], className="d-flex align-items-center")
                    ]),
                    dbc.CardBody([
                        html.Div(id="entity-details-table")
                    ])
                ])
            ], width=12)
        ], className="mb-3"),
        
        # News Volume Over Time
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("📰 News Volume Over Time")),
                    dbc.CardBody([
                        dcc.Graph(id="news-volume-chart")
                    ])
                ])
            ], width=12)
        ]),
        
        # Entity Details Modal
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="entity-modal-title")),
            dbc.ModalBody(id="entity-modal-body"),
            dbc.ModalFooter(
                dbc.Button("Close", id="close-entity-modal", className="ms-auto")
            )
        ], id="entity-details-modal", size="xl", scrollable=True),
        
        # Store for selected entity
        dcc.Store(id="selected-entity-store", data=None)
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
                Entity.entity_id,
                func.count(NewsEntityMapping.mapping_id).label('mentions')
            ).join(
                NewsEntityMapping,
                Entity.entity_id == NewsEntityMapping.entity_id
            ).group_by(
                Entity.entity_name,
                Entity.entity_id
            ).order_by(
                func.count(NewsEntityMapping.mapping_id).desc()
            ).limit(10).all()
        
        if not top_entities:
            return html.P("No entities tracked yet", className="text-muted")
        
        rows = []
        for i, (name, entity_id, mentions) in enumerate(top_entities, 1):
            badge_color = "danger" if i <= 3 else "warning" if i <= 6 else "secondary"
            rows.append(
                html.Div([
                    dbc.Badge(f"#{i}", color=badge_color, className="me-2"),
                    dbc.Button(
                        name,
                        id={"type": "entity-detail-btn", "index": name},
                        color="link",
                        className="text-light p-0 text-start",
                        style={"textDecoration": "none", "flex": "1"}
                    ),
                    html.Small(f" ({entity_id})" if entity_id else "", className="text-muted ms-1"),
                    dbc.Badge(f"{mentions}", color="info", className="ms-2")
                ], className="d-flex align-items-center mb-2")
            )
        
        return html.Div(rows)
    except Exception as e:
        return html.P(f"Error loading entities: {str(e)[:50]}", className="text-danger")


def get_entity_sentiment_chart(engine, timeframe="30d"):
    """Get entity sentiment analysis chart over time"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import and_
        import json
        
        with Session(engine) as db:
            # Calculate cutoff date
            cutoff_date = None
            if timeframe == "7d":
                cutoff_date = datetime.now() - timedelta(days=7)
            elif timeframe == "30d":
                cutoff_date = datetime.now() - timedelta(days=30)
            elif timeframe == "90d":
                cutoff_date = datetime.now() - timedelta(days=90)
            
            # Query entity-news mappings with sentiment
            query = db.query(
                Entity.entity_name,
                Entity.entity_id,
                ProcessedNews.sentiment,
                RawNews.fetched_at
            ).join(
                NewsEntityMapping, Entity.entity_id == NewsEntityMapping.entity_id
            ).join(
                RawNews, NewsEntityMapping.news_id == RawNews.news_id
            ).join(
                ProcessedNews, RawNews.news_id == ProcessedNews.news_id
            ).filter(
                ProcessedNews.sentiment.isnot(None)
            )
            
            if cutoff_date:
                query = query.filter(RawNews.fetched_at >= cutoff_date)
            
            entity_sentiments = query.all()
        
        if not entity_sentiments:
            import plotly.graph_objects as go
            fig = go.Figure()
            fig.add_annotation(
                text="No sentiment data available<br>Run content analysis to see entity sentiments",
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
        
        # Aggregate sentiments by entity
        entity_data = {}
        for name, entity_id, sentiment_json, fetched_at in entity_sentiments:
            if name not in entity_data:
                entity_data[name] = []
            
            try:
                sent_dict = sentiment_json if isinstance(sentiment_json, dict) else json.loads(sentiment_json)
                if 'overall' in sent_dict:
                    entity_data[name].append(sent_dict['overall'])
            except:
                pass
        
        # Calculate average sentiment per entity
        entity_avg_sentiments = []
        for entity, sentiments in entity_data.items():
            if sentiments:
                avg_sent = sum(sentiments) / len(sentiments)
                entity_avg_sentiments.append({
                    'entity': entity,
                    'avg_sentiment': avg_sent,
                    'count': len(sentiments)
                })
        
        # Sort by average sentiment
        entity_avg_sentiments.sort(key=lambda x: x['avg_sentiment'], reverse=True)
        
        # Take top 15 (best and worst)
        top_entities = entity_avg_sentiments[:15] if len(entity_avg_sentiments) > 15 else entity_avg_sentiments
        
        # Create bar chart
        df_chart = pd.DataFrame(top_entities)
        
        # Color by sentiment
        colors = ['#28a745' if s > 0.2 else '#dc3545' if s < -0.2 else '#6c757d' 
                  for s in df_chart['avg_sentiment']]
        
        fig = px.bar(
            df_chart,
            x='avg_sentiment',
            y='entity',
            orientation='h',
            template="plotly_dark",
            color='avg_sentiment',
            color_continuous_scale=['#dc3545', '#6c757d', '#28a745']
        )
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            xaxis_title="Average Sentiment Score",
            yaxis_title="Entity",
            showlegend=False,
            height=max(400, len(top_entities) * 30),
            margin=dict(l=150, r=40, t=40, b=40)
        )
        return fig
    except Exception as e:
        import plotly.graph_objects as go
        import logging
        logging.error(f"Error creating entity sentiment chart: {e}", exc_info=True)
        
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
            plot_bgcolor='rgba(0,0,0,0)'
        )
        return fig


def get_top_positive_entities(engine):
    """Get top entities with most positive news in last 30 days"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import and_
        import json
        
        with Session(engine) as db:
            cutoff = datetime.now() - timedelta(days=30)
            
            # Get entity-news with sentiments
            results = db.query(
                Entity.entity_name,
                Entity.entity_id,
                ProcessedNews.sentiment,
                RawNews.fetched_at
            ).join(
                NewsEntityMapping, Entity.entity_id == NewsEntityMapping.entity_id
            ).join(
                RawNews, NewsEntityMapping.news_id == RawNews.news_id
            ).join(
                ProcessedNews, RawNews.news_id == ProcessedNews.news_id
            ).filter(
                and_(
                    RawNews.fetched_at >= cutoff,
                    ProcessedNews.sentiment.isnot(None)
                )
            ).all()
        
        if not results:
            return html.P("No sentiment data in last 30 days", className="text-muted")
        
        # Calculate entity sentiment stats
        entity_stats = {}
        for name, entity_id, sentiment_json, _ in results:
            if name not in entity_stats:
                entity_stats[name] = {'positive': 0, 'negative': 0, 'neutral': 0, 'total': 0, 'avg': 0}
            
            try:
                sent_dict = sentiment_json if isinstance(sentiment_json, dict) else json.loads(sentiment_json)
                if 'overall' in sent_dict:
                    score = sent_dict['overall']
                    entity_stats[name]['total'] += 1
                    entity_stats[name]['avg'] += score
                    
                    if score > 0.3:
                        entity_stats[name]['positive'] += 1
                    elif score < -0.3:
                        entity_stats[name]['negative'] += 1
                    else:
                        entity_stats[name]['neutral'] += 1
            except:
                pass
        
        # Calculate averages and sort by positive sentiment
        for name in entity_stats:
            if entity_stats[name]['total'] > 0:
                entity_stats[name]['avg'] /= entity_stats[name]['total']
        
        # Sort by average sentiment (descending) and positive count
        sorted_entities = sorted(
            entity_stats.items(),
            key=lambda x: (x[1]['avg'], x[1]['positive']),
            reverse=True
        )[:10]
        
        # Create display
        rows = []
        for i, (name, stats) in enumerate(sorted_entities, 1):
            badge_color = "success" if i <= 3 else "info"
            rows.append(
                html.Div([
                    html.Div([
                        dbc.Badge(f"#{i}", color=badge_color, className="me-2"),
                        dbc.Button(
                            name,
                            id={"type": "entity-detail-btn", "index": name},
                            color="link",
                            className="text-light fw-bold p-0 text-start",
                            style={"textDecoration": "none"}
                        )
                    ], className="mb-1"),
                    html.Div([
                        dbc.Badge(f"{stats['positive']} Positive", color="success", className="me-1"),
                        dbc.Badge(f"{stats['neutral']} Neutral", color="secondary", className="me-1"),
                        dbc.Badge(f"{stats['negative']} Negative", color="danger", className="me-1"),
                        html.Small(f" | Avg: {stats['avg']:.2f}", className="text-muted ms-2")
                    ])
                ], className="mb-3 p-2 border-bottom border-secondary")
            )
        
        return html.Div(rows)
    except Exception as e:
        import logging
        logging.error(f"Error getting top positive entities: {e}", exc_info=True)
        return html.P(f"Error: {str(e)[:50]}", className="text-danger")


def get_top_negative_entities(engine):
    """Get top entities with most negative news in last 30 days"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import and_
        import json
        
        with Session(engine) as db:
            cutoff = datetime.now() - timedelta(days=30)
            
            results = db.query(
                Entity.entity_name,
                Entity.entity_id,
                ProcessedNews.sentiment,
                RawNews.fetched_at
            ).join(
                NewsEntityMapping, Entity.entity_id == NewsEntityMapping.entity_id
            ).join(
                RawNews, NewsEntityMapping.news_id == RawNews.news_id
            ).join(
                ProcessedNews, RawNews.news_id == ProcessedNews.news_id
            ).filter(
                and_(
                    RawNews.fetched_at >= cutoff,
                    ProcessedNews.sentiment.isnot(None)
                )
            ).all()
        
        if not results:
            return html.P("No sentiment data in last 30 days", className="text-muted")
        
        # Calculate entity sentiment stats
        entity_stats = {}
        for name, entity_id, sentiment_json, _ in results:
            if name not in entity_stats:
                entity_stats[name] = {'positive': 0, 'negative': 0, 'neutral': 0, 'total': 0, 'avg': 0}
            
            try:
                sent_dict = sentiment_json if isinstance(sentiment_json, dict) else json.loads(sentiment_json)
                if 'overall' in sent_dict:
                    score = sent_dict['overall']
                    entity_stats[name]['total'] += 1
                    entity_stats[name]['avg'] += score
                    
                    if score > 0.3:
                        entity_stats[name]['positive'] += 1
                    elif score < -0.3:
                        entity_stats[name]['negative'] += 1
                    else:
                        entity_stats[name]['neutral'] += 1
            except:
                pass
        
        # Calculate averages
        for name in entity_stats:
            if entity_stats[name]['total'] > 0:
                entity_stats[name]['avg'] /= entity_stats[name]['total']
        
        # Sort by average sentiment (ascending) and negative count
        sorted_entities = sorted(
            entity_stats.items(),
            key=lambda x: (x[1]['avg'], -x[1]['negative']),
            reverse=False
        )[:10]
        
        # Create display
        rows = []
        for i, (name, stats) in enumerate(sorted_entities, 1):
            badge_color = "danger" if i <= 3 else "warning"
            rows.append(
                html.Div([
                    html.Div([
                        dbc.Badge(f"#{i}", color=badge_color, className="me-2"),
                        dbc.Button(
                            name,
                            id={"type": "entity-detail-btn", "index": name},
                            color="link",
                            className="text-light fw-bold p-0 text-start",
                            style={"textDecoration": "none"}
                        )
                    ], className="mb-1"),
                    html.Div([
                        dbc.Badge(f"{stats['negative']} Negative", color="danger", className="me-1"),
                        dbc.Badge(f"{stats['neutral']} Neutral", color="secondary", className="me-1"),
                        dbc.Badge(f"{stats['positive']} Positive", color="success", className="me-1"),
                        html.Small(f" | Avg: {stats['avg']:.2f}", className="text-muted ms-2")
                    ])
                ], className="mb-3 p-2 border-bottom border-secondary")
            )
        
        return html.Div(rows)
    except Exception as e:
        import logging
        logging.error(f"Error getting top negative entities: {e}", exc_info=True)
        return html.P(f"Error: {str(e)[:50]}", className="text-danger")


def get_entity_details_table(engine, search_term=""):
    """Get detailed entity table with all tracked metrics"""
    try:
        import json
        from sqlalchemy import or_
        
        with Session(engine) as db:
            # Base query
            query = db.query(
                Entity.entity_name,
                Entity.entity_id,
                Entity.entity_type,
                Entity.metadata_,
                func.count(NewsEntityMapping.mapping_id.distinct()).label('mentions'),
                func.count(ImpactScore.score_id.distinct()).label('impact_count'),
                func.avg(ImpactScore.impact_score).label('avg_impact')
            ).outerjoin(
                NewsEntityMapping, Entity.entity_id == NewsEntityMapping.entity_id
            ).outerjoin(
                ImpactScore, Entity.entity_id == ImpactScore.entity_id
            ).group_by(
                Entity.entity_name,
                Entity.entity_id,
                Entity.entity_type,
                Entity.metadata_
            )
            
            # Apply search filter
            if search_term:
                query = query.filter(
                    or_(
                        Entity.entity_name.ilike(f"%{search_term}%"),
                        Entity.entity_id.ilike(f"%{search_term}%")
                    )
                )
            
            entities = query.order_by(func.count(NewsEntityMapping.mapping_id).desc()).limit(50).all()
        
        if not entities:
            return html.P("No entities found" if search_term else "No entities tracked yet", className="text-muted text-center")
        
        # Build table
        table_header = [
            html.Thead(html.Tr([
                html.Th("Entity", style={"width": "25%"}),
                html.Th("Type", style={"width": "10%"}),
                html.Th("ID/Ticker", style={"width": "15%"}),
                html.Th("Mentions", style={"width": "10%"}),
                html.Th("Impact Scores", style={"width": "10%"}),
                html.Th("Avg Impact", style={"width": "15%"}),
                html.Th("Metadata", style={"width": "15%"})
            ]))
        ]
        
        table_rows = []
        for name, entity_id, entity_type, metadata_json, mentions, impact_count, avg_impact in entities:
            # Parse metadata
            metadata_display = "—"
            if metadata_json:
                try:
                    meta = metadata_json if isinstance(metadata_json, dict) else json.loads(metadata_json)
                    metadata_display = ", ".join([f"{k}: {v}" for k, v in list(meta.items())[:2]])
                except:
                    pass
            
            # Format average impact
            impact_display = "—"
            impact_color = "secondary"
            if avg_impact is not None:
                impact_display = f"{avg_impact:.2f}"
                if avg_impact >= 0.7:
                    impact_color = "danger"
                elif avg_impact >= 0.4:
                    impact_color = "warning"
                else:
                    impact_color = "info"
            
            table_rows.append(html.Tr([
                html.Td(html.Strong(name, className="text-light")),
                html.Td(dbc.Badge(entity_type, color="info")),
                html.Td(html.Code(entity_id, className="text-warning")),
                html.Td(dbc.Badge(str(mentions), color="primary")),
                html.Td(dbc.Badge(str(impact_count), color="success")),
                html.Td(dbc.Badge(impact_display, color=impact_color)),
                html.Td(html.Small(metadata_display, className="text-muted"))
            ]))
        
        return dbc.Table(
            table_header + [html.Tbody(table_rows)],
            striped=True,
            hover=True,
            bordered=True,
            color="dark",
            responsive=True,
            size="sm",
            className="mb-0"
        )
    except Exception as e:
        import logging
        logging.error(f"Error creating entity details table: {e}", exc_info=True)
        return html.P(f"Error loading table: {str(e)[:50]}", className="text-danger")


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


def get_entity_full_details(engine, entity_name):
    """Get comprehensive entity details for modal display"""
    try:
        from datetime import datetime, timedelta
        import json
        from sqlalchemy import desc, and_
        
        with Session(engine) as db:
            # Get entity basic info
            entity = db.query(Entity).filter(Entity.entity_name == entity_name).first()
            
            if not entity:
                return "Entity not found", html.P("No data available", className="text-muted")
            
            # Get all news articles mentioning this entity
            news_mappings = db.query(
                RawNews.title,
                RawNews.source,
                RawNews.url,
                RawNews.fetched_at,
                ProcessedNews.sentiment,
                ProcessedNews.event_type,
                ProcessedNews.summary_short,
                ImpactScore.impact_score,
                NewsEntityMapping.confidence,
                NewsEntityMapping.exposure_type
            ).join(
                NewsEntityMapping, RawNews.news_id == NewsEntityMapping.news_id
            ).outerjoin(
                ProcessedNews, RawNews.news_id == ProcessedNews.news_id
            ).outerjoin(
                ImpactScore, and_(
                    ImpactScore.news_id == RawNews.news_id,
                    ImpactScore.entity_id == entity.entity_id
                )
            ).filter(
                NewsEntityMapping.entity_id == entity.entity_id
            ).order_by(desc(RawNews.fetched_at)).limit(50).all()
            
            # Calculate statistics
            total_mentions = len(news_mappings)
            
            sentiment_stats = {'positive': 0, 'neutral': 0, 'negative': 0, 'avg': 0, 'total': 0}
            impact_scores = []
            event_types = {}
            
            for mapping in news_mappings:
                # Sentiment
                if mapping.sentiment:
                    try:
                        sent_dict = mapping.sentiment if isinstance(mapping.sentiment, dict) else json.loads(mapping.sentiment)
                        if 'overall' in sent_dict:
                            score = sent_dict['overall']
                            sentiment_stats['avg'] += score
                            sentiment_stats['total'] += 1
                            if score > 0.3:
                                sentiment_stats['positive'] += 1
                            elif score < -0.3:
                                sentiment_stats['negative'] += 1
                            else:
                                sentiment_stats['neutral'] += 1
                    except:
                        pass
                
                # Impact
                if mapping.impact_score is not None:
                    impact_scores.append(mapping.impact_score)
                
                # Event types
                if mapping.event_type:
                    event_types[mapping.event_type] = event_types.get(mapping.event_type, 0) + 1
            
            if sentiment_stats['total'] > 0:
                sentiment_stats['avg'] /= sentiment_stats['total']
            
            avg_impact = sum(impact_scores) / len(impact_scores) if impact_scores else 0
            
            # Parse metadata
            metadata_display = []
            if entity.metadata_:
                try:
                    meta = entity.metadata_ if isinstance(entity.metadata_, dict) else json.loads(entity.metadata_)
                    metadata_display = [html.Li(f"{k}: {v}") for k, v in meta.items()]
                except:
                    pass
        
        # Build modal title
        title = html.Div([
            html.H4(entity_name, className="mb-0"),
            html.Small(f"{entity.entity_type.upper()} | {entity.entity_id}", className="text-muted")
        ])
        
        # Build modal body
        body = html.Div([
            # Statistics Overview
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H3(f"{total_mentions}", className="text-primary mb-0"),
                            html.Small("Total Mentions", className="text-muted")
                        ], className="text-center")
                    ])
                ], width=3),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H3(f"{sentiment_stats['avg']:.2f}", className="text-info mb-0"),
                            html.Small("Avg Sentiment", className="text-muted")
                        ], className="text-center")
                    ])
                ], width=3),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H3(f"{avg_impact:.2f}", className="text-warning mb-0"),
                            html.Small("Avg Impact", className="text-muted")
                        ], className="text-center")
                    ])
                ], width=3),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.H3(f"{len(impact_scores)}", className="text-success mb-0"),
                            html.Small("Impact Scores", className="text-muted")
                        ], className="text-center")
                    ])
                ], width=3)
            ], className="mb-4"),
            
            # Sentiment Breakdown & Event Types
            dbc.Row([
                dbc.Col([
                    html.H5("📊 Sentiment Breakdown"),
                    html.Div([
                        dbc.Progress([
                            dbc.Progress(value=sentiment_stats['positive'], color="success", bar=True),
                            dbc.Progress(value=sentiment_stats['neutral'], color="secondary", bar=True),
                            dbc.Progress(value=sentiment_stats['negative'], color="danger", bar=True)
                        ], className="mb-2", style={"height": "30px"}),
                        html.Div([
                            dbc.Badge(f"{sentiment_stats['positive']} Positive", color="success", className="me-2"),
                            dbc.Badge(f"{sentiment_stats['neutral']} Neutral", color="secondary", className="me-2"),
                            dbc.Badge(f"{sentiment_stats['negative']} Negative", color="danger")
                        ])
                    ])
                ], width=6),
                dbc.Col([
                    html.H5("📈 Event Types"),
                    html.Div([
                        dbc.Badge(f"{event_type}: {count}", color="info", className="me-1 mb-1") 
                        for event_type, count in sorted(event_types.items(), key=lambda x: x[1], reverse=True)[:10]
                    ]) if event_types else html.P("No event types classified", className="text-muted")
                ], width=6)
            ], className="mb-4"),
            
            # Metadata
            html.Div([
                html.H5("ℹ️ Metadata"),
                html.Ul(metadata_display, className="text-muted") if metadata_display else html.P("No metadata available", className="text-muted")
            ], className="mb-4") if metadata_display or entity.metadata_ else None,
            
            # News Articles List
            html.H5(f"📰 Recent News Articles (Last {len(news_mappings)})"),
            html.Div([
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            html.A(
                                html.Strong(mapping.title or "No title", className="text-light"),
                                href=mapping.url if mapping.url else "#",
                                target="_blank",
                                className="text-decoration-none"
                            ),
                            html.Div([
                                dbc.Badge(mapping.source or "Unknown", color="info", className="me-2"),
                                dbc.Badge(mapping.event_type or "No type", color="secondary", className="me-2") if mapping.event_type else None,
                                dbc.Badge(
                                    f"Sent: {(mapping.sentiment if isinstance(mapping.sentiment, dict) else json.loads(mapping.sentiment))['overall']:.2f}",
                                    color="success" if mapping.sentiment and (mapping.sentiment if isinstance(mapping.sentiment, dict) else json.loads(mapping.sentiment)).get('overall', 0) > 0.3 else "danger" if mapping.sentiment and (mapping.sentiment if isinstance(mapping.sentiment, dict) else json.loads(mapping.sentiment)).get('overall', 0) < -0.3 else "secondary",
                                    className="me-2"
                                ) if mapping.sentiment else None,
                                dbc.Badge(
                                    f"Impact: {mapping.impact_score:.2f}",
                                    color="danger" if mapping.impact_score >= 0.7 else "warning" if mapping.impact_score >= 0.4 else "info",
                                    className="me-2"
                                ) if mapping.impact_score is not None else None,
                                dbc.Badge(
                                    f"{mapping.exposure_type}",
                                    color="warning",
                                    className="me-2"
                                ) if mapping.exposure_type else None,
                                html.Small(
                                    mapping.fetched_at.strftime("%Y-%m-%d %H:%M") if mapping.fetched_at else "Unknown date",
                                    className="text-muted"
                                )
                            ], className="mt-2"),
                            html.P(
                                mapping.summary_short or "No summary available",
                                className="text-muted mt-2 mb-0 small"
                            ) if mapping.summary_short else None
                        ])
                    ])
                ], className="mb-2")
                for mapping in news_mappings
            ], style={"maxHeight": "400px", "overflowY": "auto"}) if news_mappings else html.P("No news articles found", className="text-muted text-center")
        ])
        
        return title, body
        
    except Exception as e:
        import logging
        logging.error(f"Error loading entity details for {entity_name}: {e}", exc_info=True)
        return "Error", html.P(f"Error loading details: {str(e)[:100]}", className="text-danger")
