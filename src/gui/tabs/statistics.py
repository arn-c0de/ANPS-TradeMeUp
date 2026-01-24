
"""
Statistics Tab - Analytics and Metrics
"""

from dash import dcc, html
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
from sqlalchemy import func
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, date

from src.models.raw_news import RawNews
from src.models.data_quality import DataQualityScore
from src.models.processed_news import ProcessedNews
from src.models.predictions import Prediction, PredictionOutcome
from src.models.entities import Entity, NewsEntityMapping
from src.models.analysis import ImpactScore, SurpriseScore, SignalDecayModel, FactVerification, MarketRegime
from src.gui.error_handling import handle_db_errors, create_empty_state


def _coerce_datetime(value, is_end=False):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.max.time() if is_end else datetime.min.time())
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if "T" in value or ":" in value:
            return parsed
        return datetime.combine(parsed.date(), datetime.max.time() if is_end else datetime.min.time())
    return None


def _parse_date_range(date_range):
    if not date_range or len(date_range) != 2:
        return None, None
    return _coerce_datetime(date_range[0], is_end=False), _coerce_datetime(date_range[1], is_end=True)

def create_layout():
    """Create statistics tab layout"""
    return dbc.Container([
        # Time Period Filter (compact control section)
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        dbc.Row([
                            dbc.Col([
                                html.Small("Granularity:", className="text-muted mb-1 d-block", style={"fontSize": "0.7em"}),
                                dcc.Dropdown(
                                    id="stats-granularity",
                                    options=[
                                        {"label": "Minutes", "value": "minutes"},
                                        {"label": "Days", "value": "days"},
                                        {"label": "Weeks", "value": "weeks"},
                                        {"label": "Months", "value": "months"},
                                        {"label": "Years", "value": "years"},
                                        {"label": "All Time", "value": "all"}
                                    ],
                                    value="all",
                                    clearable=False,
                                    style={"fontSize": "0.75em"}
                                )
                            ], width=2),
                            dbc.Col([
                                html.Small("Date Range:", className="text-muted mb-1 d-block", style={"fontSize": "0.7em"}),
                                dcc.DatePickerRange(
                                    id="stats-date-range",
                                    start_date=None,
                                    end_date=None,
                                    display_format="YYYY-MM-DD",
                                    style={"fontSize": "0.75em"}
                                )
                            ], width=2),
                            dbc.Col([
                                html.Small("Quick Select:", className="text-muted mb-1 d-block", style={"fontSize": "0.7em"}),
                                dbc.ButtonGroup([
                                    dbc.Button("1h", id="quick-1h", size="sm", outline=True, color="primary", style={"fontSize": "0.7em"}),
                                    dbc.Button("12h", id="quick-12h", size="sm", outline=True, color="primary", style={"fontSize": "0.7em"}),
                                    dbc.Button("24h", id="quick-24h", size="sm", outline=True, color="primary", style={"fontSize": "0.7em"}),
                                    dbc.Button("7d", id="quick-7d", size="sm", outline=True, color="primary", style={"fontSize": "0.7em"}),
                                    dbc.Button("30d", id="quick-30d", size="sm", outline=True, color="primary", style={"fontSize": "0.7em"}),
                                    dbc.Button("90d", id="quick-90d", size="sm", outline=True, color="primary", style={"fontSize": "0.7em"}),
                                    dbc.Button("1y", id="quick-1y", size="sm", outline=True, color="primary", style={"fontSize": "0.7em"}),
                                    dbc.Button("All", id="quick-all", size="sm", outline=True, color="primary", style={"fontSize": "0.7em"})
                                ], size="sm")
                            ], width=5),
                            dbc.Col([
                                html.Small("Custom (h):", className="text-muted mb-1 d-block", style={"fontSize": "0.7em"}),
                                dbc.Input(
                                    id="custom-hours-input",
                                    type="number",
                                    placeholder="e.g. 6",
                                    min=1,
                                    max=8760,
                                    debounce=True,
                                    size="sm",
                                    style={"fontSize": "0.75em"}
                                )
                            ], width=2),
                            dbc.Col([
                                html.Small("\u00a0", className="mb-1 d-block", style={"fontSize": "0.7em"}),
                                dbc.Button(
                                    "Reset",
                                    id="stats-reset-filter",
                                    size="sm",
                                    color="secondary",
                                    outline=True,
                                    className="w-100",
                                    style={"fontSize": "0.75em"}
                                )
                            ], width=1)
                        ], className="g-2")
                    ], className="py-2 px-3")
                ], className="border-primary", style={"borderWidth": "1px"})
            ], width=12)
        ], className="mb-2"),

        # Overall Metrics (compact top bar)
        dbc.Row([
            dbc.Col([
                html.Div(id="statistics-metrics")
            ], width=12)
        ], className="mb-2"),
        
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
        
        # Index Trends & Stock Performance
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("📈 Market Index Trends & Tracked Stocks")),
                    dbc.CardBody([
                        html.Div(id="index-trends-display")
                    ])
                ])
            ], width=12)
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
                    dbc.CardHeader([
                        html.Div([
                            html.H5("📈 Positive Entities (Selected Range)", className="mb-0 d-inline"),
                            dbc.Input(
                                id="positive-entity-search-input",
                                type="text",
                                placeholder="Search entities...",
                                className="d-inline-block ms-3",
                                style={"width": "200px"},
                                debounce=True
                            )
                        ], className="d-flex align-items-center justify-content-between")
                    ]),
                    dbc.CardBody([
                        html.Div(id="top-positive-entities"),
                        dbc.Button(
                            "Show More",
                            id="positive-entities-toggle",
                            color="link",
                            size="sm",
                            className="mt-2"
                        ),
                        html.Small("💡 Showing entities sorted by average sentiment score", className="text-muted d-block mt-2")
                    ])
                ])
            ], width=6),
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader([
                        html.Div([
                            html.H5("📉 Negative Entities (Selected Range)", className="mb-0 d-inline"),
                            dbc.Input(
                                id="negative-entity-search-input",
                                type="text",
                                placeholder="Search entities...",
                                className="d-inline-block ms-3",
                                style={"width": "200px"},
                                debounce=True
                            )
                        ], className="d-flex align-items-center justify-content-between")
                    ]),
                    dbc.CardBody([
                        html.Div(id="top-negative-entities"),
                        dbc.Button(
                            "Show More",
                            id="negative-entities-toggle",
                            color="link",
                            size="sm",
                            className="mt-2"
                        ),
                        html.Small("💡 Showing entities sorted by average sentiment score", className="text-muted d-block mt-2")
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
            dbc.ModalFooter([
                dbc.Button("Close", id="close-entity-modal", className="ms-auto")
            ])
        ], id="entity-details-modal", size="xl", scrollable=True),
        
        # Stock Predictions Modal
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="stock-modal-title")),
            dbc.ModalBody(id="stock-modal-body"),
            dbc.ModalFooter([
                dbc.Button("Close", id="close-stock-modal", className="ms-auto")
            ])
        ], id="stock-predictions-modal", size="xl", scrollable=True),
        
        # Toast notification for missing predictions
        dbc.Toast(
            "No prediction found for this news article. The prediction may not have been created yet.",
            id="no-prediction-toast",
            header="⚠️ No Prediction Found",
            is_open=False,
            dismissable=True,
            icon="warning",
            duration=4000,
            style={
                "position": "fixed",
                "top": 66,
                "right": 10,
                "width": 350,
                "zIndex": 9999,
                "backgroundColor": "#1e1e1e",
                "border": "1px solid #ffc107",
                "boxShadow": "0 4px 8px rgba(0,0,0,0.3)"
            }
        ),
        
        # Store for selected entity
        dcc.Store(id="selected-entity-store", data=None),

        # Store for active time filter
        dcc.Store(id="active-filter-store", data="all"),
        
        # Store for table sorting state
        dcc.Store(id="entity-table-sort-store", data={"column": None, "direction": None}),
        
        # Store for expand state
        dcc.Store(id="positive-entities-expanded", data=False),
        dcc.Store(id="negative-entities-expanded", data=False)
    ], fluid=True)


@handle_db_errors(default_message="Unable to load statistics", show_details=False)
def get_statistics_metrics(engine, date_range=None, granularity="all"):
    """Get overall statistics with optional date filtering

    Args:
        engine: Database engine
        date_range: Tuple of (start_date, end_date) or None for all time
        granularity: Time granularity ('minutes', 'days', 'weeks', 'months', 'years', 'all')
    """
    try:
        with Session(engine) as db:
            # Simple COUNT queries - these are fast and don't need complex optimization
            now = datetime.utcnow()
            hour_ago = now - timedelta(hours=1)
            day_ago = now - timedelta(hours=24)

            # Parse date range filter
            start_date, end_date = _parse_date_range(date_range)

            # Apply date range filtering to all queries
            # Total counts with date range
            news_query = db.query(func.count(RawNews.news_id))
            if start_date:
                news_query = news_query.filter(RawNews.fetched_at >= start_date)
            if end_date:
                news_query = news_query.filter(RawNews.fetched_at <= end_date)
            total_news = news_query.scalar() or 0

            processed_query = db.query(func.count(ProcessedNews.news_id))
            if start_date:
                processed_query = processed_query.filter(ProcessedNews.processing_timestamp >= start_date)
            if end_date:
                processed_query = processed_query.filter(ProcessedNews.processing_timestamp <= end_date)
            total_processed = processed_query.scalar() or 0

            entities_query = db.query(func.count(Entity.entity_id))
            if start_date:
                entities_query = entities_query.filter(Entity.created_at >= start_date)
            if end_date:
                entities_query = entities_query.filter(Entity.created_at <= end_date)
            total_entities = entities_query.scalar() or 0

            predictions_query = db.query(func.count(Prediction.prediction_id))
            if start_date:
                predictions_query = predictions_query.filter(Prediction.created_at >= start_date)
            if end_date:
                predictions_query = predictions_query.filter(Prediction.created_at <= end_date)
            total_predictions = predictions_query.scalar() or 0

            impacts_query = db.query(func.count(ImpactScore.score_id))
            if start_date:
                impacts_query = impacts_query.filter(ImpactScore.created_at >= start_date)
            if end_date:
                impacts_query = impacts_query.filter(ImpactScore.created_at <= end_date)
            total_impacts = impacts_query.scalar() or 0

            surprises_query = db.query(func.count(SurpriseScore.surprise_id))
            if start_date:
                surprises_query = surprises_query.filter(SurpriseScore.created_at >= start_date)
            if end_date:
                surprises_query = surprises_query.filter(SurpriseScore.created_at <= end_date)
            total_surprises = surprises_query.scalar() or 0

            regimes_query = db.query(func.count(MarketRegime.regime_id))
            if start_date:
                regimes_query = regimes_query.filter(MarketRegime.created_at >= start_date)
            if end_date:
                regimes_query = regimes_query.filter(MarketRegime.created_at <= end_date)
            total_regimes = regimes_query.scalar() or 0

            fact_checks_query = db.query(func.count(FactVerification.verification_id))
            if start_date:
                fact_checks_query = fact_checks_query.filter(FactVerification.verified_at >= start_date)
            if end_date:
                fact_checks_query = fact_checks_query.filter(FactVerification.verified_at <= end_date)
            total_fact_checks = fact_checks_query.scalar() or 0

            quality_query = db.query(func.avg(DataQualityScore.quality_score))
            if start_date:
                quality_query = quality_query.filter(DataQualityScore.created_at >= start_date)
            if end_date:
                quality_query = quality_query.filter(DataQualityScore.created_at <= end_date)
            avg_quality = quality_query.scalar()
            avg_quality = round(avg_quality, 2) if avg_quality else 0

            # 1h / 24h increments (always show recent activity regardless of filter)
            news_1h = db.query(func.count(RawNews.news_id)).filter(RawNews.fetched_at >= hour_ago).scalar() or 0
            news_24h = db.query(func.count(RawNews.news_id)).filter(RawNews.fetched_at >= day_ago).scalar() or 0

            processed_1h = db.query(func.count(ProcessedNews.news_id)).filter(
                ProcessedNews.processing_timestamp >= hour_ago
            ).scalar() or 0
            processed_24h = db.query(func.count(ProcessedNews.news_id)).filter(
                ProcessedNews.processing_timestamp >= day_ago
            ).scalar() or 0

            entities_1h = db.query(func.count(Entity.entity_id)).filter(Entity.created_at >= hour_ago).scalar() or 0
            entities_24h = db.query(func.count(Entity.entity_id)).filter(Entity.created_at >= day_ago).scalar() or 0

            predictions_1h = db.query(func.count(Prediction.prediction_id)).filter(
                Prediction.created_at >= hour_ago
            ).scalar() or 0
            predictions_24h = db.query(func.count(Prediction.prediction_id)).filter(
                Prediction.created_at >= day_ago
            ).scalar() or 0

            impacts_1h = db.query(func.count(ImpactScore.score_id)).filter(
                ImpactScore.created_at >= hour_ago
            ).scalar() or 0
            impacts_24h = db.query(func.count(ImpactScore.score_id)).filter(
                ImpactScore.created_at >= day_ago
            ).scalar() or 0

            surprises_1h = db.query(func.count(SurpriseScore.surprise_id)).filter(
                SurpriseScore.created_at >= hour_ago
            ).scalar() or 0
            surprises_24h = db.query(func.count(SurpriseScore.surprise_id)).filter(
                SurpriseScore.created_at >= day_ago
            ).scalar() or 0

            fact_checks_1h = db.query(func.count(FactVerification.verification_id)).filter(
                FactVerification.verified_at >= hour_ago
            ).scalar() or 0
            fact_checks_24h = db.query(func.count(FactVerification.verification_id)).filter(
                FactVerification.verified_at >= day_ago
            ).scalar() or 0

            avg_quality_1h = db.query(func.avg(DataQualityScore.quality_score)).filter(
                DataQualityScore.created_at >= hour_ago
            ).scalar()
            avg_quality_24h = db.query(func.avg(DataQualityScore.quality_score)).filter(
                DataQualityScore.created_at >= day_ago
            ).scalar()
            avg_quality_1h = round(avg_quality_1h, 2) if avg_quality_1h is not None else None
            avg_quality_24h = round(avg_quality_24h, 2) if avg_quality_24h is not None else None
        
        def metric_card(icon, label, value, value_class, meta_left, meta_right):
            return dbc.Card(
                dbc.CardBody([
                    html.Div([
                        html.Span(icon, className="me-1", style={"fontSize": "18px"}),
                        html.Small(label, className="text-muted", style={"fontSize": "0.75rem"})
                    ], className="d-flex align-items-center"),
                    html.Div(f"{value}", className=f"{value_class} fw-bold", style={"fontSize": "1.3rem"}),
                    html.Div([
                        html.Small(meta_left, className="text-success me-2") if meta_left else None,
                        html.Small(meta_right, className="text-info") if meta_right else None
                    ], className="d-flex flex-wrap", style={"fontSize": "0.7rem"})
                ], className="py-2 px-2"),
                className="h-100"
            )

        quality_meta_1h = f"{avg_quality_1h:.2f} 1h" if avg_quality_1h is not None else "— 1h"
        quality_meta_24h = f"{avg_quality_24h:.2f} 24h" if avg_quality_24h is not None else "— 24h"

        return html.Div([
            dbc.Row([
                dbc.Col(metric_card("📰", "Articles", f"{total_news:,}", "text-primary",
                                    f"+{news_1h} 1h", f"+{news_24h} 24h"), xs=6, sm=4, md=2),
                dbc.Col(metric_card("🧠", "Processed", f"{total_processed:,}", "text-success",
                                    f"+{processed_1h} 1h", f"+{processed_24h} 24h"), xs=6, sm=4, md=2),
                dbc.Col(metric_card("🏢", "Entities", f"{total_entities:,}", "text-info",
                                    f"+{entities_1h} 1h", f"+{entities_24h} 24h"), xs=6, sm=4, md=2),
                dbc.Col(metric_card("🔮", "Predictions", f"{total_predictions:,}", "text-warning",
                                    f"+{predictions_1h} 1h", f"+{predictions_24h} 24h"), xs=6, sm=4, md=2),
                dbc.Col(metric_card("💥", "Impacts", f"{total_impacts:,}", "text-danger",
                                    f"+{impacts_1h} 1h", f"+{impacts_24h} 24h"), xs=6, sm=4, md=2),
                dbc.Col(metric_card("🎯", "Surprises", f"{total_surprises:,}", "text-warning",
                                    f"+{surprises_1h} 1h", f"+{surprises_24h} 24h"), xs=6, sm=4, md=2),
                dbc.Col(metric_card("✅", "Fact Checks", f"{total_fact_checks:,}", "text-success",
                                    f"+{fact_checks_1h} 1h", f"+{fact_checks_24h} 24h"), xs=6, sm=4, md=2),
                dbc.Col(metric_card("⭐", "Avg Quality", f"{avg_quality:.2f}", "text-primary",
                                    quality_meta_1h, quality_meta_24h), xs=6, sm=4, md=2),
            ], className="g-2 mb-2")
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


def get_event_distribution_chart(engine, date_range=None):
    """Get event type distribution chart"""
    try:
        start_date, end_date = _parse_date_range(date_range)
        with Session(engine) as db:
            query = db.query(
                ProcessedNews.event_type,
                func.count(ProcessedNews.news_id).label('count')
            ).group_by(ProcessedNews.event_type)

            if start_date:
                query = query.filter(ProcessedNews.processing_timestamp >= start_date)
            if end_date:
                query = query.filter(ProcessedNews.processing_timestamp <= end_date)

            event_data = query.all()
        
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


def get_quality_distribution_chart(engine, date_range=None):
    """Get quality distribution chart"""
    try:
        start_date, end_date = _parse_date_range(date_range)
        with Session(engine) as db:
            query = db.query(DataQualityScore.quality_score)
            if start_date:
                query = query.filter(DataQualityScore.created_at >= start_date)
            if end_date:
                query = query.filter(DataQualityScore.created_at <= end_date)
            quality_data = query.all()
        
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


def get_sentiment_distribution_chart(engine, date_range=None):
    """Get sentiment distribution chart"""
    try:
        start_date, end_date = _parse_date_range(date_range)
        with Session(engine) as db:
            query = db.query(ProcessedNews.sentiment).filter(
                ProcessedNews.sentiment.isnot(None)
            )
            if start_date:
                query = query.filter(ProcessedNews.processing_timestamp >= start_date)
            if end_date:
                query = query.filter(ProcessedNews.processing_timestamp <= end_date)
            sentiments_data = query.all()
        
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


def get_impact_distribution_chart(engine, date_range=None):
    """Get impact score distribution chart"""
    try:
        start_date, end_date = _parse_date_range(date_range)
        with Session(engine) as db:
            query = db.query(ImpactScore.impact_score)
            if start_date:
                query = query.filter(ImpactScore.created_at >= start_date)
            if end_date:
                query = query.filter(ImpactScore.created_at <= end_date)
            impact_scores = query.all()
        
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


def get_top_entities_list(engine, date_range=None):
    """Get top entities by mentions"""
    try:
        start_date, end_date = _parse_date_range(date_range)
        with Session(engine) as db:
            query = db.query(
                Entity.entity_name,
                Entity.entity_id,
                func.count(NewsEntityMapping.mapping_id).label('mentions')
            ).join(
                NewsEntityMapping,
                Entity.entity_id == NewsEntityMapping.entity_id
            ).join(
                RawNews,
                NewsEntityMapping.news_id == RawNews.news_id
            )

            if start_date:
                query = query.filter(RawNews.fetched_at >= start_date)
            if end_date:
                query = query.filter(RawNews.fetched_at <= end_date)

            top_entities = query.group_by(
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


def get_entity_sentiment_chart(engine, date_range=None, timeframe="30d"):
    """Get entity sentiment analysis chart over time"""
    try:
        from datetime import datetime, timedelta
        import json
        
        with Session(engine) as db:
            start_date, end_date = _parse_date_range(date_range)
            if not start_date and not end_date:
                # Fallback to timeframe when no explicit range is set
                if timeframe == "7d":
                    start_date = datetime.utcnow() - timedelta(days=7)
                elif timeframe == "30d":
                    start_date = datetime.utcnow() - timedelta(days=30)
                elif timeframe == "90d":
                    start_date = datetime.utcnow() - timedelta(days=90)
            
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
            
            if start_date:
                query = query.filter(RawNews.fetched_at >= start_date)
            if end_date:
                query = query.filter(RawNews.fetched_at <= end_date)
            
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


def get_top_positive_entities(engine, search_term="", show_all=False, date_range=None):
    """Get entities with positive news in selected range, optionally filtered by search"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import and_
        import json
        
        with Session(engine) as db:
            start_date, end_date = _parse_date_range(date_range)
            using_default_range = not (start_date or end_date)
            if using_default_range:
                start_date = datetime.utcnow() - timedelta(days=30)
            range_label = "selected range" if not using_default_range else "last 30 days"
            
            # Get entity-news with sentiments
            filters = [ProcessedNews.sentiment.isnot(None)]
            if start_date:
                filters.append(RawNews.fetched_at >= start_date)
            if end_date:
                filters.append(RawNews.fetched_at <= end_date)

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
            ).filter(and_(*filters)).all()
        
        if not results:
            return html.P(f"No sentiment data in {range_label}", className="text-muted")
        
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
        )
        
        # Filter by search term if provided
        if search_term:
            search_lower = search_term.lower()
            sorted_entities = [(name, stats) for name, stats in sorted_entities 
                             if search_lower in name.lower()]
        
        # Limit to top 50 to avoid overwhelming display
        sorted_entities = sorted_entities[:50]
        
        # Show message if search yielded no results
        if search_term and not sorted_entities:
            return html.P(f"No entities found matching '{search_term}'", className="text-muted")
        
        if not sorted_entities:
            return html.P(f"No positive sentiment entities in {range_label}", className="text-muted")
        
        # Create display
        rows = []
        # Add result count header
        if search_term:
            rows.append(
                html.Div([
                    html.Small(f"Showing {len(sorted_entities)} result(s) for '{search_term}'", className="text-info mb-2")
                ])
            )
        
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


def get_top_negative_entities(engine, search_term="", show_all=False, date_range=None):
    """Get entities with negative news in selected range, optionally filtered by search"""
    try:
        from datetime import datetime, timedelta
        from sqlalchemy import and_
        import json
        
        with Session(engine) as db:
            start_date, end_date = _parse_date_range(date_range)
            using_default_range = not (start_date or end_date)
            if using_default_range:
                start_date = datetime.utcnow() - timedelta(days=30)
            range_label = "selected range" if not using_default_range else "last 30 days"
            
            filters = [ProcessedNews.sentiment.isnot(None)]
            if start_date:
                filters.append(RawNews.fetched_at >= start_date)
            if end_date:
                filters.append(RawNews.fetched_at <= end_date)

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
            ).filter(and_(*filters)).all()
        
        if not results:
            return html.P(f"No sentiment data in {range_label}", className="text-muted")
        
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
        )
        
        # Filter by search term if provided
        if search_term:
            search_lower = search_term.lower()
            sorted_entities = [(name, stats) for name, stats in sorted_entities 
                             if search_lower in name.lower()]
        
        # Limit display based on state
        total_count = len(sorted_entities)
        if not search_term and not show_all:
            # Show only top 15 by default
            sorted_entities = sorted_entities[:15]
        else:
            # Show up to 50 when searching or expanded
            sorted_entities = sorted_entities[:50]
        
        # Show message if search yielded no results
        if search_term and not sorted_entities:
            return html.P(f"No entities found matching '{search_term}'", className="text-muted")
        
        if not sorted_entities:
            return html.P(f"No negative sentiment entities in {range_label}", className="text-muted")
        
        # Create display
        rows = []
        # Add result count header
        if search_term:
            rows.append(
                html.Div([
                    html.Small(f"Showing {len(sorted_entities)} result(s) for '{search_term}'", className="text-info mb-2")
                ])
            )
        elif not show_all and total_count > 15:
            rows.append(
                html.Div([
                    html.Small(f"Showing top 15 of {total_count} entities", className="text-info mb-2")
                ])
            )
        
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


def get_entity_details_table(engine, search_term="", sort_column=None, sort_direction=None, date_range=None):
    """
    Get detailed entity table with all tracked metrics and sortable columns
    
    Args:
        engine: Database engine
        search_term: Search filter
        sort_column: Column to sort by (entity_name, type, id, mentions, impact_count, avg_impact)
        sort_direction: 'asc' or 'desc', None for default
        date_range: Tuple of (start_date, end_date) or None for all time
    """
    try:
        import json
        from sqlalchemy import or_, and_
        
        with Session(engine) as db:
            start_date, end_date = _parse_date_range(date_range)
            impact_join_conditions = [Entity.entity_id == ImpactScore.entity_id]
            if start_date:
                impact_join_conditions.append(ImpactScore.created_at >= start_date)
            if end_date:
                impact_join_conditions.append(ImpactScore.created_at <= end_date)

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
                RawNews, NewsEntityMapping.news_id == RawNews.news_id
            ).outerjoin(
                ImpactScore, and_(*impact_join_conditions)
            ).group_by(
                Entity.entity_name,
                Entity.entity_id,
                Entity.entity_type,
                Entity.metadata_
            )

            if start_date:
                query = query.filter(RawNews.fetched_at >= start_date)
            if end_date:
                query = query.filter(RawNews.fetched_at <= end_date)
            
            # Apply search filter
            if search_term:
                query = query.filter(
                    or_(
                        Entity.entity_name.ilike(f"%{search_term}%"),
                        Entity.entity_id.ilike(f"%{search_term}%")
                    )
                )
            
            # Apply sorting based on column and direction
            if sort_column and sort_direction:
                if sort_column == "entity_name":
                    sort_col = Entity.entity_name
                elif sort_column == "type":
                    sort_col = Entity.entity_type
                elif sort_column == "id":
                    sort_col = Entity.entity_id
                elif sort_column == "mentions":
                    sort_col = func.count(NewsEntityMapping.mapping_id.distinct())
                elif sort_column == "impact_count":
                    sort_col = func.count(ImpactScore.score_id.distinct())
                elif sort_column == "avg_impact":
                    sort_col = func.avg(ImpactScore.impact_score)
                else:
                    sort_col = func.count(NewsEntityMapping.mapping_id)  # default
                
                if sort_direction == "asc":
                    query = query.order_by(sort_col.asc())
                else:  # desc
                    query = query.order_by(sort_col.desc())
            else:
                # Default sorting: by mentions descending
                query = query.order_by(func.count(NewsEntityMapping.mapping_id).desc())
            
            entities = query.limit(50).all()
        
        if not entities:
            return html.P("No entities found" if search_term else "No entities tracked yet", className="text-muted text-center")
        
        # Determine sort indicators
        def get_sort_icon(column_name):
            if sort_column == column_name:
                if sort_direction == "asc":
                    return " ▲"
                elif sort_direction == "desc":
                    return " ▼"
            return ""
        
        # Build table with clickable headers
        table_header = [
            html.Thead(html.Tr([
                html.Th(
                    html.Button(
                        f"Entity{get_sort_icon('entity_name')}", 
                        id={"type": "sort-column-btn", "column": "entity_name"},
                        className="btn btn-link text-light p-0 text-decoration-none",
                        style={"cursor": "pointer"}
                    ),
                    style={"width": "25%"}
                ),
                html.Th(
                    html.Button(
                        f"Type{get_sort_icon('type')}", 
                        id={"type": "sort-column-btn", "column": "type"},
                        className="btn btn-link text-light p-0 text-decoration-none",
                        style={"cursor": "pointer"}
                    ),
                    style={"width": "10%"}
                ),
                html.Th(
                    html.Button(
                        f"ID/Ticker{get_sort_icon('id')}", 
                        id={"type": "sort-column-btn", "column": "id"},
                        className="btn btn-link text-light p-0 text-decoration-none",
                        style={"cursor": "pointer"}
                    ),
                    style={"width": "15%"}
                ),
                html.Th(
                    html.Button(
                        f"Mentions{get_sort_icon('mentions')}", 
                        id={"type": "sort-column-btn", "column": "mentions"},
                        className="btn btn-link text-light p-0 text-decoration-none",
                        style={"cursor": "pointer"}
                    ),
                    style={"width": "10%"}
                ),
                html.Th(
                    html.Button(
                        f"Impact Scores{get_sort_icon('impact_count')}", 
                        id={"type": "sort-column-btn", "column": "impact_count"},
                        className="btn btn-link text-light p-0 text-decoration-none",
                        style={"cursor": "pointer"}
                    ),
                    style={"width": "10%"}
                ),
                html.Th(
                    html.Button(
                        f"Avg Impact{get_sort_icon('avg_impact')}", 
                        id={"type": "sort-column-btn", "column": "avg_impact"},
                        className="btn btn-link text-light p-0 text-decoration-none",
                        style={"cursor": "pointer"}
                    ),
                    style={"width": "15%"}
                ),
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


def get_news_volume_chart(engine, date_range=None):
    """Get news volume over time chart"""
    try:
        start_date, end_date = _parse_date_range(date_range)
        with Session(engine) as db:
            # Query news by date (SQLite-compatible)
            from sqlalchemy import func as sql_func
            
            query = db.query(
                sql_func.date(RawNews.fetched_at).label('date'),
                sql_func.count(RawNews.news_id).label('count')
            ).filter(
                RawNews.fetched_at.isnot(None)
            )
            if start_date:
                query = query.filter(RawNews.fetched_at >= start_date)
            if end_date:
                query = query.filter(RawNews.fetched_at <= end_date)

            volume_data = query.group_by(
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
                RawNews.news_id,
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
                            html.Div([
                                html.A(
                                    html.Strong(mapping.title or "No title", className="text-light"),
                                    href=mapping.url if mapping.url else "#",
                                    target="_blank",
                                    className="text-decoration-none"
                                ),
                                dbc.Button(
                                    ["📊 Prediction"],
                                    id={"type": "news-pred-detail-btn", "index": str(mapping.news_id)},
                                    size="sm",
                                    color="primary",
                                    outline=True,
                                    className="ms-2",
                                    title="View prediction details for this news"
                                )
                            ], className="d-flex justify-content-between align-items-start mb-2"),
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


def get_index_trends(engine):
    """Get index trends and related stock predictions"""
    import json
    import os
    from datetime import datetime, timedelta
    from src.gui.charts.market_data import MarketDataProvider
    
    try:
        # Load index constituents
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "config", "index_constituents.json")
        with open(config_path, 'r') as f:
            indices = json.load(f)
        
        market_provider = MarketDataProvider()
        
        # Get entities from database that match stocks in indices
        with Session(engine) as db:
            all_entities = db.query(Entity).all()
            entity_symbols = {e.entity_name: e for e in all_entities}
        
        index_displays = []
        
        for index_name, index_data in indices.items():
            index_symbol = index_data["index_symbol"]
            
            # Get index performance
            try:
                index_df = market_provider.get_historical_data(index_symbol, period="1mo")
                if index_df is not None and not index_df.empty:
                    current_price = index_df['Close'].iloc[-1]
                    start_price = index_df['Close'].iloc[0]
                    change_pct = ((current_price - start_price) / start_price) * 100
                    
                    trend_color = "success" if change_pct > 0 else "danger"
                    trend_icon = "📈" if change_pct > 0 else "📉"
                else:
                    change_pct = 0
                    trend_color = "secondary"
                    trend_icon = "➡️"
            except:
                change_pct = 0
                trend_color = "secondary"
                trend_icon = "➡️"
            
            # Find tracked stocks from this index
            tracked_stocks = []
            for stock_symbol in index_data["top_stocks"]:
                if stock_symbol in entity_symbols:
                    entity = entity_symbols[stock_symbol]
                    
                    # Count predictions for this stock
                    with Session(engine) as db:
                        pred_count = db.query(func.count(Prediction.prediction_id)).filter(
                            Prediction.entity_id == entity.entity_id
                        ).scalar()
                    
                    if pred_count > 0:
                        tracked_stocks.append({
                            "symbol": stock_symbol,
                            "entity_id": entity.entity_id,
                            "pred_count": pred_count
                        })
            
            if tracked_stocks:
                # Create stock buttons
                stock_buttons = [
                    dbc.Button(
                        f"{stock['symbol']} ({stock['pred_count']})",
                        id={"type": "stock-pred-btn", "index": stock["symbol"]},
                        size="sm",
                        color="primary",
                        outline=True,
                        className="me-2 mb-2"
                    )
                    for stock in tracked_stocks[:20]  # Limit to 20 stocks
                ]
                
                index_displays.append(
                    dbc.Card([
                        dbc.CardHeader([
                            html.Div([
                                html.H6(f"{trend_icon} {index_name}", className="mb-0"),
                                dbc.Badge(
                                    f"{change_pct:+.2f}% (30d)",
                                    color=trend_color,
                                    className="ms-2"
                                )
                            ], className="d-flex align-items-center justify-content-between")
                        ]),
                        dbc.CardBody([
                            html.P(f"{len(tracked_stocks)} tracked stocks with predictions:", className="mb-2"),
                            html.Div(stock_buttons)
                        ])
                    ], className="mb-3")
                )
        
        if not index_displays:
            return html.P("No tracked stocks found in major indices", className="text-muted text-center")
        
        return html.Div(index_displays)
        
    except Exception as e:
        import logging
        logging.error(f"Error loading index trends: {e}", exc_info=True)
        return html.P(f"Error loading index trends: {str(e)[:100]}", className="text-danger")


def get_stock_predictions_detail(engine, stock_symbol):
    """Get all predictions for a specific stock with performance data"""
    import json
    from datetime import datetime
    from sqlalchemy import desc
    from src.gui.tabs.predictions import _format_saved_performance
    
    try:
        with Session(engine) as db:
            # Find entity by symbol
            entity = db.query(Entity).filter(Entity.entity_name == stock_symbol).first()
            
            if not entity:
                return f"{stock_symbol} - Not Found", html.P("Stock not found in database", className="text-muted")
            
            # Get all predictions for this entity
            predictions = db.query(Prediction).filter(
                Prediction.entity_id == entity.entity_id
            ).order_by(desc(Prediction.created_at)).limit(5).all()  # Limit to 5 most recent for performance
            
            if not predictions:
                return f"{stock_symbol} - No Predictions", html.P("No predictions found for this stock", className="text-muted")
            
            # Create prediction cards
            pred_cards = []
            for pred in predictions:
                try:
                    # Get prediction outcome
                    outcome = db.query(PredictionOutcome).filter(
                        PredictionOutcome.prediction_id == pred.prediction_id
                    ).first()
                    
                    # Always load live prices for this modal (limited to 5 predictions)
                    perf_data = _format_saved_performance(pred, entity, outcome, load_live_prices=True)
                    
                    # If no cached data available, skip this prediction
                    if not perf_data:
                        continue
                    
                    # Status badge
                    if perf_data.get('status') == 'active':
                        status_badge = dbc.Badge("Active", color="success")
                    elif perf_data.get('status') == 'expired':
                        status_badge = dbc.Badge("Expired", color="secondary")
                    else:
                        status_badge = dbc.Badge("Unknown", color="warning")
                    
                    # Return badge
                    total_return = perf_data.get('total_return_pct', 0)
                    return_color = "success" if total_return > 0 else "danger" if total_return < 0 else "secondary"
                    
                    pred_cards.append(
                        dbc.Card([
                            dbc.CardHeader([
                                html.Div([
                                    html.Span([
                                        status_badge,
                                        dbc.Badge(
                                            pred.horizon,
                                            color="info",
                                            className="ms-2"
                                        ),
                                        dbc.Badge(
                                            f"{pred.confidence:.1%}",
                                            color="primary",
                                            className="ms-2"
                                        )
                                    ]),
                                    dbc.Badge(
                                        f"{total_return:+.2f}%",
                                        color=return_color,
                                        className="ms-auto",
                                        style={"fontSize": "1rem"}
                                    )
                                ], className="d-flex justify-content-between align-items-center")
                            ]),
                            dbc.CardBody([
                                dbc.Row([
                                    dbc.Col([
                                        html.Small("Entry Price", className="text-muted"),
                                        html.H6(f"${perf_data.get('prediction_price', 0):.2f}")
                                    ], width=3),
                                    dbc.Col([
                                        html.Small("Current Price", className="text-muted"),
                                        html.H6(f"${perf_data.get('current_price', 0):.2f}")
                                    ], width=3),
                                    dbc.Col([
                                        html.Small("Target", className="text-muted"),
                                        html.H6(f"{pred.predicted_direction.upper()}" if hasattr(pred, 'predicted_direction') else "N/A")
                                    ], width=3),
                                    dbc.Col([
                                        html.Small("Created", className="text-muted"),
                                        html.H6(pred.created_at.strftime("%Y-%m-%d %H:%M"))
                                    ], width=3)
                                ]),
                                html.Hr(),
                                html.P(pred.reasoning[:200] + "..." if hasattr(pred, 'reasoning') and len(pred.reasoning) > 200 else getattr(pred, 'reasoning', 'No reasoning available'), 
                                      className="small text-muted mb-0")
                            ])
                        ], className="mb-3")
                    )
                except Exception as e:
                    # Skip predictions that cause errors
                    import logging
                    logging.error(f"Error processing prediction {pred.prediction_id}: {e}")
                    continue
            
            if not pred_cards:
                return f"{stock_symbol} - No Data", html.P("No performance data available", className="text-muted")
            
            # Summary stats
            active_count = sum(1 for p in predictions if p.created_at)
            avg_confidence = sum(p.confidence for p in predictions) / len(predictions) if predictions else 0
            
            summary = dbc.Card([
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.H4(len(predictions), className="mb-0"),
                            html.Small("Total Predictions", className="text-muted")
                        ], width=4),
                        dbc.Col([
                            html.H4(f"{avg_confidence:.1%}", className="mb-0"),
                            html.Small("Avg Confidence", className="text-muted")
                        ], width=4),
                        dbc.Col([
                            html.H4(entity.entity_name, className="mb-0"),
                            html.Small("Symbol", className="text-muted")
                        ], width=4)
                    ])
                ])
            ], className="mb-3", color="dark", outline=True)
            
            body = html.Div([
                summary,
                html.H5("All Predictions", className="mt-3 mb-3"),
                html.Div(pred_cards, style={"maxHeight": "600px", "overflowY": "auto"})
            ])
            
            return f"{stock_symbol} - {len(predictions)} Predictions", body
            
    except Exception as e:
        import logging
        logging.error(f"Error loading stock predictions for {stock_symbol}: {e}", exc_info=True)
        return "Error", html.P(f"Error: {str(e)[:100]}", className="text-danger")
