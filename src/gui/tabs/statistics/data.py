"""
Statistics Tab - Data Retrieval Functions

All data retrieval functions for the statistics tab.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import html
from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from src.models.raw_news import RawNews
from src.models.data_quality import DataQualityScore
from src.models.processed_news import ProcessedNews
from src.models.predictions import Prediction, PredictionOutcome
from src.models.entities import Entity, NewsEntityMapping
from src.models.analysis import ImpactScore, SurpriseScore, FactVerification, MarketRegime
from src.models.trading_simulation import TradingSimulation
from src.gui.error_handling import handle_db_errors

from .utils import _parse_date_range

logger = logging.getLogger(__name__)

# Sentiment scores above/below +/- this threshold count as positive/negative.
SENTIMENT_THRESHOLD = 0.3


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _message_figure(text: str, *, color: str = "gray", size: int = 14,
                    hide_axes: bool = True) -> go.Figure:
    """Build an empty, transparent dark-themed figure showing a centered message."""
    fig = go.Figure()
    fig.add_annotation(
        text=text,
        xref="paper", yref="paper",
        x=0.5, y=0.5, showarrow=False,
        font=dict(size=size, color=color)
    )
    layout = dict(
        template="plotly_dark",
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    if hide_axes:
        layout.update(xaxis=dict(visible=False), yaxis=dict(visible=False))
    fig.update_layout(**layout)
    return fig


def _parse_sentiment_overall(sentiment_value):
    """Extract the 'overall' score from a sentiment dict/JSON string, or None."""
    if not sentiment_value:
        return None
    try:
        parsed = sentiment_value if isinstance(sentiment_value, dict) else json.loads(sentiment_value)
        if 'overall' in parsed:
            return parsed['overall']
    except Exception:
        pass
    return None


def _classify_sentiment(score: float) -> str:
    """Classify a sentiment score as 'positive', 'negative' or 'neutral'."""
    if score > SENTIMENT_THRESHOLD:
        return "positive"
    if score < -SENTIMENT_THRESHOLD:
        return "negative"
    return "neutral"


def _query_entity_sentiment_rows(db: Session, start_date, end_date):
    """Fetch (entity_name, entity_id, sentiment, fetched_at) rows with sentiment in range."""
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
    return query.all()


# ---------------------------------------------------------------------------
# Overview metrics
# ---------------------------------------------------------------------------

def _count_in_range(db: Session, count_column, timestamp_column, start_date, end_date) -> int:
    """Count rows of one column, optionally restricted to a timestamp range."""
    query = db.query(func.count(count_column))
    if start_date:
        query = query.filter(timestamp_column >= start_date)
    if end_date:
        query = query.filter(timestamp_column <= end_date)
    return query.scalar() or 0


def _count_unique_mentioned_entities(db: Session, start_date=None, end_date=None) -> int:
    """Count distinct entities mentioned in news within the given range."""
    query = db.query(
        func.count(func.distinct(NewsEntityMapping.entity_id))
    ).join(
        RawNews, NewsEntityMapping.news_id == RawNews.news_id
    )
    if start_date:
        query = query.filter(RawNews.fetched_at >= start_date)
    if end_date:
        query = query.filter(RawNews.fetched_at <= end_date)
    return query.scalar() or 0


def _average_quality(db: Session, start_date=None, end_date=None):
    """Average data-quality score within the given range (None when no rows)."""
    query = db.query(func.avg(DataQualityScore.quality_score))
    if start_date:
        query = query.filter(DataQualityScore.created_at >= start_date)
    if end_date:
        query = query.filter(DataQualityScore.created_at <= end_date)
    return query.scalar()


def _collect_total_counts(db: Session, start_date, end_date) -> dict:
    """Collect overall totals for the metric cards, optionally date-filtered."""
    avg_quality = _average_quality(db, start_date, end_date)
    return {
        "news": _count_in_range(db, RawNews.news_id, RawNews.fetched_at, start_date, end_date),
        "processed": _count_in_range(db, ProcessedNews.news_id, ProcessedNews.processing_timestamp, start_date, end_date),
        "entities": _count_in_range(db, Entity.entity_id, Entity.created_at, start_date, end_date),
        "unique_entities": _count_unique_mentioned_entities(db, start_date, end_date),
        "predictions": _count_in_range(db, Prediction.prediction_id, Prediction.created_at, start_date, end_date),
        "impacts": _count_in_range(db, ImpactScore.score_id, ImpactScore.created_at, start_date, end_date),
        "surprises": _count_in_range(db, SurpriseScore.surprise_id, SurpriseScore.created_at, start_date, end_date),
        "regimes": _count_in_range(db, MarketRegime.regime_id, MarketRegime.created_at, start_date, end_date),
        "fact_checks": _count_in_range(db, FactVerification.verification_id, FactVerification.verified_at, start_date, end_date),
        "simulations": _count_in_range(db, TradingSimulation.simulation_id, TradingSimulation.created_at, start_date, end_date),
        # Queried for parity with the historical implementation; not currently
        # shown on a metric card.
        "avg_quality": round(avg_quality, 2) if avg_quality else 0,
    }


def _collect_recent_counts(db: Session, since: datetime) -> dict:
    """Collect activity counts since a timestamp (used for the 1h/24h deltas)."""
    avg_quality = _average_quality(db, start_date=since)
    return {
        "news": _count_in_range(db, RawNews.news_id, RawNews.fetched_at, since, None),
        "processed": _count_in_range(db, ProcessedNews.news_id, ProcessedNews.processing_timestamp, since, None),
        "entities": _count_in_range(db, Entity.entity_id, Entity.created_at, since, None),
        "unique_entities": _count_unique_mentioned_entities(db, start_date=since),
        "predictions": _count_in_range(db, Prediction.prediction_id, Prediction.created_at, since, None),
        "impacts": _count_in_range(db, ImpactScore.score_id, ImpactScore.created_at, since, None),
        "surprises": _count_in_range(db, SurpriseScore.surprise_id, SurpriseScore.created_at, since, None),
        "fact_checks": _count_in_range(db, FactVerification.verification_id, FactVerification.verified_at, since, None),
        "simulations": _count_in_range(db, TradingSimulation.simulation_id, TradingSimulation.created_at, since, None),
        # Queried for parity with the historical implementation; not currently
        # shown on a metric card.
        "avg_quality": round(avg_quality, 2) if avg_quality is not None else None,
    }


def _prediction_performance(db: Session, start_date, end_date) -> tuple:
    """Average actual return (%) across tracked prediction outcomes.

    Returns:
        Tuple of (average_return_pct, tracked_count).
    """
    query = db.query(PredictionOutcome).join(
        Prediction, PredictionOutcome.prediction_id == Prediction.prediction_id
    ).filter(
        PredictionOutcome.actual_return.isnot(None)
    )
    if start_date:
        query = query.filter(Prediction.created_at >= start_date)
    if end_date:
        query = query.filter(Prediction.created_at <= end_date)

    total_return_pct = 0.0
    tracked_count = 0
    for outcome in query.all():
        try:
            if outcome.actual_return is not None and abs(outcome.actual_return) > 0.001:
                # actual_return is already stored as a percentage (e.g. -17.03 = -17.03%)
                total_return_pct += outcome.actual_return
                tracked_count += 1
        except Exception as e:
            logger.debug(f"Error calculating performance: {e}")

    average = (total_return_pct / tracked_count) if tracked_count > 0 else 0.0
    return average, tracked_count


def _metric_card(icon: str, label: str, value: str, value_class: str,
                 meta_left, meta_right) -> dbc.Card:
    """Build one small metric card for the overview row."""
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


def _build_metrics_row(totals: dict, recent_1h: dict, recent_24h: dict,
                       avg_return_pct: float, tracked_count: int) -> html.Div:
    """Assemble the overview metric cards into a responsive row."""
    if tracked_count > 0:
        sign = "+" if avg_return_pct >= 0 else ""
        revenue_value = f"{sign}{avg_return_pct:.2f}%"
        revenue_meta_left = f"{tracked_count} tracked"
        revenue_meta_right = "Performance"
        if avg_return_pct > 0:
            revenue_class = "text-success"
        elif avg_return_pct < 0:
            revenue_class = "text-danger"
        else:
            revenue_class = "text-secondary"
    else:
        revenue_value = "—"
        revenue_meta_left = "0 tracked"
        revenue_meta_right = "No data yet"
        revenue_class = "text-secondary"

    count_cards = [
        # (icon, label, key into totals/recent dicts, value CSS class)
        ("📰", "Articles", "news", "text-primary"),
        ("🧠", "LLM", "processed", "text-success"),
        ("🏢", "Entities Created", "entities", "text-info"),
        ("📊", "Tracked in News", "unique_entities", "text-cyan"),
        ("🔮", "Predictions", "predictions", "text-warning"),
        ("💥", "Impacts", "impacts", "text-danger"),
        ("🎯", "Surprises", "surprises", "text-warning"),
        ("✅", "Fact Checks", "fact_checks", "text-success"),
        ("🧪", "Simulations", "simulations", "text-primary"),
    ]
    columns = [
        dbc.Col(
            _metric_card(icon, label, f"{totals[key]:,}", value_class,
                         f"+{recent_1h[key]} 1h", f"+{recent_24h[key]} 24h"),
            xs=6, sm=4, md=2
        )
        for icon, label, key, value_class in count_cards
    ]
    columns.append(
        dbc.Col(
            _metric_card("💰", "Revenue", revenue_value, revenue_class,
                         revenue_meta_left, revenue_meta_right),
            xs=6, sm=4, md=2
        )
    )
    return html.Div([dbc.Row(columns, className="g-2 mb-2")])


@handle_db_errors(default_message="Unable to load statistics", show_details=False)
def get_statistics_metrics(engine, date_range=None, granularity="all"):
    """Get overall statistics with optional date filtering.

    Args:
        engine: Database engine
        date_range: Tuple of (start_date, end_date) or None for all time
        granularity: Time granularity ('minutes', 'days', 'weeks', 'months',
            'years', 'all'); currently unused but kept for API compatibility
    """
    try:
        now = datetime.now(timezone.utc)
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(hours=24)
        start_date, end_date = _parse_date_range(date_range)

        with Session(engine) as db:
            totals = _collect_total_counts(db, start_date, end_date)
            # The 1h/24h increments always show recent activity regardless of filter.
            recent_1h = _collect_recent_counts(db, hour_ago)
            recent_24h = _collect_recent_counts(db, day_ago)
            avg_return_pct, tracked_count = _prediction_performance(db, start_date, end_date)

        return _build_metrics_row(totals, recent_1h, recent_24h, avg_return_pct, tracked_count)
    except Exception as e:
        logger.error(f"Error loading statistics: {e}", exc_info=True)
        return dbc.Row([
            dbc.Col([
                html.Div([
                    html.P("⚠️ Unable to load statistics", className="text-warning mb-2"),
                    html.Small(f"Error: {str(e)}", className="text-muted")
                ], className="text-center")
            ], width=12)
        ])


# ---------------------------------------------------------------------------
# Distribution charts
# ---------------------------------------------------------------------------

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
    except Exception:
        return _message_figure("No data available yet<br>Run the pipeline to see event distribution")


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
    except Exception:
        return _message_figure("No data available yet<br>Run the pipeline to see quality distribution")


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
            return _message_figure("No sentiment data yet<br>Run content analysis")

        sentiment_scores = []
        for (sentiment_value,) in sentiments_data:
            score = _parse_sentiment_overall(sentiment_value)
            if score is not None:
                sentiment_scores.append(score)

        if not sentiment_scores:
            return _message_figure("No valid sentiment scores", hide_axes=False)

        positive = sum(1 for s in sentiment_scores if s > SENTIMENT_THRESHOLD)
        neutral = sum(1 for s in sentiment_scores if -SENTIMENT_THRESHOLD <= s <= SENTIMENT_THRESHOLD)
        negative = sum(1 for s in sentiment_scores if s < -SENTIMENT_THRESHOLD)

        fig = px.pie(
            names=['Positive', 'Neutral', 'Negative'],
            values=[positive, neutral, negative],
            color_discrete_sequence=['#28a745', '#6c757d', '#dc3545'],
            template="plotly_dark"
        )
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=20, r=20, t=20, b=20),
            autosize=True,
            height=None
        )
        return fig
    except Exception as e:
        return _message_figure(f"Error: {str(e)[:30]}", size=12, hide_axes=False)


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
            return _message_figure("No impact scores yet<br>Run impact analysis")

        scores = [s[0] for s in impact_scores if s[0] is not None]

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
            margin=dict(l=40, r=20, t=20, b=40),
            autosize=True,
            height=None
        )
        fig.update_xaxes(automargin=True)
        fig.update_yaxes(automargin=True)
        return fig
    except Exception as e:
        return _message_figure(f"Error: {str(e)[:30]}", size=12, hide_axes=False)


# ---------------------------------------------------------------------------
# Entity lists and charts
# ---------------------------------------------------------------------------

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


def _sentiment_window_start(timeframe: str):
    """Translate a timeframe label ('7d'/'30d'/'90d') into a start datetime."""
    days = {"7d": 7, "30d": 30, "90d": 90}.get(timeframe)
    if days is None:
        return None
    return datetime.now(timezone.utc) - timedelta(days=days)


def _average_sentiment_per_entity(rows) -> list:
    """Aggregate sentiment rows into per-entity averages, sorted descending."""
    scores_by_entity = {}
    for name, _entity_id, sentiment_value, _fetched_at in rows:
        scores_by_entity.setdefault(name, [])
        score = _parse_sentiment_overall(sentiment_value)
        if score is not None:
            scores_by_entity[name].append(score)

    averages = [
        {
            'entity': name,
            'avg_sentiment': sum(scores) / len(scores),
            'count': len(scores)
        }
        for name, scores in scores_by_entity.items()
        if scores
    ]
    averages.sort(key=lambda item: item['avg_sentiment'], reverse=True)
    return averages


def _build_entity_sentiment_figure(top_entities: list) -> go.Figure:
    """Build the horizontal bar chart of average sentiment per entity."""
    df_chart = pd.DataFrame(top_entities)
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


def get_entity_sentiment_chart(engine, date_range=None, timeframe="30d"):
    """Get entity sentiment analysis chart over time"""
    try:
        start_date, end_date = _parse_date_range(date_range)
        if not start_date and not end_date:
            # Fall back to the timeframe when no explicit range is set
            start_date = _sentiment_window_start(timeframe)

        with Session(engine) as db:
            entity_sentiments = _query_entity_sentiment_rows(db, start_date, end_date)

        if not entity_sentiments:
            return _message_figure(
                "No sentiment data available<br>Run content analysis to see entity sentiments"
            )

        averages = _average_sentiment_per_entity(entity_sentiments)
        # Take the top 15 entities by average sentiment
        return _build_entity_sentiment_figure(averages[:15])
    except Exception as e:
        logger.error(f"Error creating entity sentiment chart: {e}", exc_info=True)
        return _message_figure(f"Error loading chart<br>{str(e)[:50]}", color="red", hide_axes=False)


# ---------------------------------------------------------------------------
# Top positive/negative entities
# ---------------------------------------------------------------------------

def _aggregate_entity_sentiment_stats(rows) -> dict:
    """Aggregate sentiment rows into per-entity positive/neutral/negative counts."""
    entity_stats = {}
    for name, _entity_id, sentiment_value, _fetched_at in rows:
        stats = entity_stats.setdefault(
            name, {'positive': 0, 'negative': 0, 'neutral': 0, 'total': 0, 'avg': 0}
        )
        score = _parse_sentiment_overall(sentiment_value)
        if score is None:
            continue
        stats['total'] += 1
        stats['avg'] += score
        stats[_classify_sentiment(score)] += 1

    for stats in entity_stats.values():
        if stats['total'] > 0:
            stats['avg'] /= stats['total']
    return entity_stats


def _rank_entity_row(rank: int, name: str, stats: dict, direction: str) -> html.Div:
    """Build one ranked entity row for the top positive/negative lists."""
    if direction == "positive":
        rank_color = "success" if rank <= 3 else "info"
        badge_order = ["positive", "neutral", "negative"]
    else:
        rank_color = "danger" if rank <= 3 else "warning"
        badge_order = ["negative", "neutral", "positive"]
    badge_colors = {"positive": "success", "neutral": "secondary", "negative": "danger"}

    return html.Div([
        html.Div([
            dbc.Badge(f"#{rank}", color=rank_color, className="me-2"),
            dbc.Button(
                name,
                id={"type": "entity-detail-btn", "index": name},
                color="link",
                className="text-light fw-bold p-0 text-start",
                style={"textDecoration": "none"}
            )
        ], className="mb-1"),
        html.Div([
            *[
                dbc.Badge(f"{stats[kind]} {kind.capitalize()}",
                          color=badge_colors[kind], className="me-1")
                for kind in badge_order
            ],
            html.Small(f" | Avg: {stats['avg']:.2f}", className="text-muted ms-2")
        ])
    ], className="mb-3 p-2 border-bottom border-secondary")


def _get_top_entities(engine, direction: str, search_term: str = "", show_all: bool = False,
                      date_range=None, limit: int = 50):
    """Shared implementation behind get_top_positive_entities/get_top_negative_entities.

    Args:
        engine: Database engine
        direction: 'positive' or 'negative'
        search_term: Search filter string
        show_all: Deprecated, kept for compatibility (ignored)
        date_range: Tuple of (start_date, end_date) or None
        limit: Maximum number of entities to return

    Returns:
        Tuple of (component, total_count); when there is no sentiment data at
        all or an error occurs, a bare component is returned instead (kept for
        backward compatibility).
    """
    try:
        start_date, end_date = _parse_date_range(date_range)
        using_default_range = not (start_date or end_date)
        if using_default_range:
            start_date = datetime.utcnow() - timedelta(days=30)
        range_label = "last 30 days" if using_default_range else "selected range"

        with Session(engine) as db:
            results = _query_entity_sentiment_rows(db, start_date, end_date)

        if not results:
            return html.P(f"No sentiment data in {range_label}", className="text-muted")

        entity_stats = _aggregate_entity_sentiment_stats(results)

        if direction == "positive":
            # Best average sentiment first, ties broken by positive count
            ranked = sorted(
                entity_stats.items(),
                key=lambda item: (item[1]['avg'], item[1]['positive']),
                reverse=True
            )
        else:
            # Worst average sentiment first, ties broken by negative count
            ranked = sorted(
                entity_stats.items(),
                key=lambda item: (item[1]['avg'], -item[1]['negative'])
            )

        # Only show entities with at least one matching sentiment
        ranked = [(name, stats) for name, stats in ranked if stats[direction] > 0]

        if search_term:
            search_lower = search_term.lower()
            ranked = [(name, stats) for name, stats in ranked if search_lower in name.lower()]

        total_count = len(ranked)
        ranked = ranked[:limit]

        if search_term and not ranked:
            return html.P(f"No entities found matching '{search_term}'", className="text-muted"), total_count
        if not ranked:
            return html.P(f"No {direction} sentiment entities in {range_label}", className="text-muted"), total_count

        rows = []
        if search_term:
            rows.append(html.Div([
                html.Small(f"Showing {len(ranked)} of {total_count} result(s) for '{search_term}'",
                           className="text-info mb-2")
            ]))
        elif len(ranked) < total_count:
            rows.append(html.Div([
                html.Small(f"Showing {len(ranked)} of {total_count} entities",
                           className="text-info mb-2")
            ]))

        for rank, (name, stats) in enumerate(ranked, 1):
            rows.append(_rank_entity_row(rank, name, stats, direction))

        # Scroll trigger element at the end when there are more entities to load
        if len(ranked) < total_count:
            rows.append(
                html.Div(
                    id=f"{direction}-entities-scroll-sentinel",
                    style={"height": "1px", "visibility": "hidden"}
                )
            )

        return html.Div(rows), total_count
    except Exception as e:
        logger.error(f"Error getting top {direction} entities: {e}", exc_info=True)
        return html.P(f"Error: {str(e)[:50]}", className="text-danger")


def get_top_positive_entities(engine, search_term="", show_all=False, date_range=None, limit=50):
    """Get entities with positive news in selected range, optionally filtered by search

    Args:
        engine: Database engine
        search_term: Search filter string
        show_all: Deprecated, kept for compatibility
        date_range: Tuple of (start_date, end_date) or None
        limit: Maximum number of entities to return

    Returns:
        Tuple of (html.Div with entities, total_count)
    """
    return _get_top_entities(engine, "positive", search_term, show_all, date_range, limit)


def get_top_negative_entities(engine, search_term="", show_all=False, date_range=None, limit=50):
    """Get entities with negative news in selected range, optionally filtered by search

    Args:
        engine: Database engine
        search_term: Search filter string
        show_all: Deprecated, kept for compatibility
        date_range: Tuple of (start_date, end_date) or None
        limit: Maximum number of entities to return

    Returns:
        Tuple of (html.Div with entities, total_count)
    """
    return _get_top_entities(engine, "negative", search_term, show_all, date_range, limit)


# ---------------------------------------------------------------------------
# Entity details table
# ---------------------------------------------------------------------------

def _entity_sort_expression(sort_column: str):
    """Map a sort column name from the UI to a SQLAlchemy expression."""
    columns = {
        "entity_name": Entity.entity_name,
        "type": Entity.entity_type,
        "id": Entity.entity_id,
        "mentions": func.count(NewsEntityMapping.mapping_id.distinct()),
        "impact_count": func.count(ImpactScore.score_id.distinct()),
        "avg_impact": func.avg(ImpactScore.impact_score),
    }
    return columns.get(sort_column, func.count(NewsEntityMapping.mapping_id))


def _query_entity_details(db: Session, search_term: str, sort_column, sort_direction,
                          start_date, end_date):
    """Query up to 50 entities with mention/impact aggregates, filtered and sorted."""
    impact_join_conditions = [Entity.entity_id == ImpactScore.entity_id]
    if start_date:
        impact_join_conditions.append(ImpactScore.created_at >= start_date)
    if end_date:
        impact_join_conditions.append(ImpactScore.created_at <= end_date)

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

    if search_term:
        query = query.filter(
            or_(
                Entity.entity_name.ilike(f"%{search_term}%"),
                Entity.entity_id.ilike(f"%{search_term}%")
            )
        )

    if sort_column and sort_direction:
        sort_expr = _entity_sort_expression(sort_column)
        query = query.order_by(sort_expr.asc() if sort_direction == "asc" else sort_expr.desc())
    else:
        # Default sorting: by mentions descending
        query = query.order_by(func.count(NewsEntityMapping.mapping_id).desc())

    return query.limit(50).all()


def _entity_table_header(sort_column, sort_direction) -> list:
    """Build the entity table header with clickable, sort-aware column buttons."""
    def sort_icon(column_name: str) -> str:
        if sort_column != column_name:
            return ""
        if sort_direction == "asc":
            return " ▲"
        if sort_direction == "desc":
            return " ▼"
        return ""

    def sortable_header(label: str, column_name: str, width: str) -> html.Th:
        return html.Th(
            html.Button(
                f"{label}{sort_icon(column_name)}",
                id={"type": "sort-column-btn", "column": column_name},
                className="btn btn-link text-light p-0 text-decoration-none",
                style={"cursor": "pointer"}
            ),
            style={"width": width}
        )

    return [
        html.Thead(html.Tr([
            sortable_header("Entity", "entity_name", "25%"),
            sortable_header("Type", "type", "10%"),
            sortable_header("ID/Ticker", "id", "15%"),
            sortable_header("Mentions", "mentions", "10%"),
            sortable_header("Impact Scores", "impact_count", "10%"),
            sortable_header("Avg Impact", "avg_impact", "15%"),
            html.Th("Metadata", style={"width": "15%"})
        ]))
    ]


def _format_metadata_preview(metadata_json) -> str:
    """Format the first two metadata key/value pairs, or an em dash."""
    if not metadata_json:
        return "—"
    try:
        meta = metadata_json if isinstance(metadata_json, dict) else json.loads(metadata_json)
        return ", ".join(f"{k}: {v}" for k, v in list(meta.items())[:2])
    except Exception:
        return "—"


def _avg_impact_badge(avg_impact) -> dbc.Badge:
    """Badge showing the average impact, color-coded by severity."""
    if avg_impact is None:
        return dbc.Badge("—", color="secondary")
    if avg_impact >= 0.7:
        color = "danger"
    elif avg_impact >= 0.4:
        color = "warning"
    else:
        color = "info"
    return dbc.Badge(f"{avg_impact:.2f}", color=color)


def _entity_table_row(name, entity_id, entity_type, metadata_json,
                      mentions, impact_count, avg_impact) -> html.Tr:
    """Build one row of the entity details table."""
    return html.Tr([
        html.Td(html.Strong(name, className="text-light")),
        html.Td(dbc.Badge(entity_type, color="info")),
        html.Td(html.Code(entity_id, className="text-warning")),
        html.Td(dbc.Badge(str(mentions), color="primary")),
        html.Td(dbc.Badge(str(impact_count), color="success")),
        html.Td(_avg_impact_badge(avg_impact)),
        html.Td(html.Small(_format_metadata_preview(metadata_json), className="text-muted"))
    ])


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
        start_date, end_date = _parse_date_range(date_range)
        with Session(engine) as db:
            entities = _query_entity_details(db, search_term, sort_column, sort_direction,
                                             start_date, end_date)

        if not entities:
            message = "No entities found" if search_term else "No entities tracked yet"
            return html.P(message, className="text-muted text-center")

        table_header = _entity_table_header(sort_column, sort_direction)
        table_rows = [_entity_table_row(*row) for row in entities]

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
        logger.error(f"Error creating entity details table: {e}", exc_info=True)
        return html.P(f"Error loading table: {str(e)[:50]}", className="text-danger")


# ---------------------------------------------------------------------------
# News volume chart
# ---------------------------------------------------------------------------

def get_news_volume_chart(engine, date_range=None):
    """Get news volume over time chart"""
    try:
        start_date, end_date = _parse_date_range(date_range)
        with Session(engine) as db:
            # Query news counts by date (SQLite-compatible)
            query = db.query(
                func.date(RawNews.fetched_at).label('date'),
                func.count(RawNews.news_id).label('count')
            ).filter(
                RawNews.fetched_at.isnot(None)
            )
            if start_date:
                query = query.filter(RawNews.fetched_at >= start_date)
            if end_date:
                query = query.filter(RawNews.fetched_at <= end_date)

            volume_data = query.group_by(
                func.date(RawNews.fetched_at)
            ).order_by('date').all()

        if not volume_data:
            return _message_figure("No data available yet<br>Run the pipeline to ingest news")

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
        logger.error(f"Error creating news volume chart: {e}", exc_info=True)
        return _message_figure(f"Error loading chart<br>{str(e)[:50]}", color="red")


# ---------------------------------------------------------------------------
# Entity full details (modal)
# ---------------------------------------------------------------------------

def _query_entity_news(db: Session, entity: Entity):
    """Fetch the 50 most recent news rows mentioning the entity, with context."""
    return db.query(
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


def _summarize_entity_news(news_mappings) -> tuple:
    """Aggregate sentiment stats, impact scores and event type counts.

    Returns:
        Tuple of (sentiment_stats, impact_scores, event_types).
    """
    sentiment_stats = {'positive': 0, 'neutral': 0, 'negative': 0, 'avg': 0, 'total': 0}
    impact_scores = []
    event_types = {}

    for mapping in news_mappings:
        score = _parse_sentiment_overall(mapping.sentiment)
        if score is not None:
            sentiment_stats['avg'] += score
            sentiment_stats['total'] += 1
            sentiment_stats[_classify_sentiment(score)] += 1

        if mapping.impact_score is not None:
            impact_scores.append(mapping.impact_score)

        if mapping.event_type:
            event_types[mapping.event_type] = event_types.get(mapping.event_type, 0) + 1

    if sentiment_stats['total'] > 0:
        sentiment_stats['avg'] /= sentiment_stats['total']

    return sentiment_stats, impact_scores, event_types


def _metadata_list_items(metadata) -> list:
    """Parse entity metadata into a list of html.Li items (empty on failure)."""
    if not metadata:
        return []
    try:
        meta = metadata if isinstance(metadata, dict) else json.loads(metadata)
        return [html.Li(f"{k}: {v}") for k, v in meta.items()]
    except Exception:
        return []


def _entity_stat_card(value: str, label: str, value_class: str) -> dbc.Col:
    """Build one statistics card for the entity details modal."""
    return dbc.Col([
        dbc.Card([
            dbc.CardBody([
                html.H3(value, className=f"{value_class} mb-0"),
                html.Small(label, className="text-muted")
            ], className="text-center")
        ])
    ], width=3)


def _sentiment_breakdown_column(sentiment_stats: dict) -> dbc.Col:
    """Build the sentiment breakdown column (progress bar plus badges)."""
    return dbc.Col([
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
    ], width=6)


def _event_types_column(event_types: dict) -> dbc.Col:
    """Build the event types column with the ten most frequent types."""
    if event_types:
        content = html.Div([
            dbc.Badge(f"{event_type}: {count}", color="info", className="me-1 mb-1")
            for event_type, count in sorted(event_types.items(), key=lambda x: x[1], reverse=True)[:10]
        ])
    else:
        content = html.P("No event types classified", className="text-muted")
    return dbc.Col([html.H5("📈 Event Types"), content], width=6)


def _metadata_section(metadata_items: list, raw_metadata):
    """Build the metadata section, or None when the entity has no metadata."""
    if not (metadata_items or raw_metadata):
        return None
    if metadata_items:
        content = html.Ul(metadata_items, className="text-muted")
    else:
        content = html.P("No metadata available", className="text-muted")
    return html.Div([html.H5("ℹ️ Metadata"), content], className="mb-4")


def _news_sentiment_badge(sentiment_value):
    """Badge with the article's overall sentiment score (None when absent)."""
    if not sentiment_value:
        return None
    parsed = sentiment_value if isinstance(sentiment_value, dict) else json.loads(sentiment_value)
    overall = parsed['overall']
    if overall > SENTIMENT_THRESHOLD:
        color = "success"
    elif overall < -SENTIMENT_THRESHOLD:
        color = "danger"
    else:
        color = "secondary"
    return dbc.Badge(f"Sent: {overall:.2f}", color=color, className="me-2")


def _news_impact_badge(impact_score):
    """Badge with the article's impact score (None when absent)."""
    if impact_score is None:
        return None
    if impact_score >= 0.7:
        color = "danger"
    elif impact_score >= 0.4:
        color = "warning"
    else:
        color = "info"
    return dbc.Badge(f"Impact: {impact_score:.2f}", color=color, className="me-2")


def _entity_news_card(mapping) -> dbc.Card:
    """Build the card for one news article in the entity details modal."""
    return dbc.Card([
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
                    _news_sentiment_badge(mapping.sentiment),
                    _news_impact_badge(mapping.impact_score),
                    dbc.Badge(f"{mapping.exposure_type}", color="warning", className="me-2") if mapping.exposure_type else None,
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


def get_entity_full_details(engine, entity_name):
    """Get comprehensive entity details for modal display"""
    try:
        with Session(engine) as db:
            entity = db.query(Entity).filter(Entity.entity_name == entity_name).first()
            if not entity:
                return "Entity not found", html.P("No data available", className="text-muted")

            news_mappings = _query_entity_news(db, entity)

        total_mentions = len(news_mappings)
        sentiment_stats, impact_scores, event_types = _summarize_entity_news(news_mappings)
        avg_impact = sum(impact_scores) / len(impact_scores) if impact_scores else 0
        metadata_items = _metadata_list_items(entity.metadata_)

        title = html.Div([
            html.H4(entity_name, className="mb-0"),
            html.Small(f"{entity.entity_type.upper()} | {entity.entity_id}", className="text-muted")
        ])

        if news_mappings:
            news_list = html.Div(
                [_entity_news_card(mapping) for mapping in news_mappings],
                style={"maxHeight": "400px", "overflowY": "auto"}
            )
        else:
            news_list = html.P("No news articles found", className="text-muted text-center")

        body = html.Div([
            dbc.Row([
                _entity_stat_card(f"{total_mentions}", "Total Mentions", "text-primary"),
                _entity_stat_card(f"{sentiment_stats['avg']:.2f}", "Avg Sentiment", "text-info"),
                _entity_stat_card(f"{avg_impact:.2f}", "Avg Impact", "text-warning"),
                _entity_stat_card(f"{len(impact_scores)}", "Impact Scores", "text-success")
            ], className="mb-4"),
            dbc.Row([
                _sentiment_breakdown_column(sentiment_stats),
                _event_types_column(event_types)
            ], className="mb-4"),
            _metadata_section(metadata_items, entity.metadata_),
            html.H5(f"📰 Recent News Articles (Last {len(news_mappings)})"),
            news_list
        ])

        return title, body
    except Exception as e:
        logger.error(f"Error loading entity details for {entity_name}: {e}", exc_info=True)
        return "Error", html.P(f"Error loading details: {str(e)[:100]}", className="text-danger")


# ---------------------------------------------------------------------------
# Index trends
# ---------------------------------------------------------------------------

def _load_index_constituents() -> dict:
    """Load config/index_constituents.json from the project root."""
    # Go up 4 levels: statistics -> tabs -> gui -> src -> project root
    project_root = Path(__file__).resolve().parents[4]
    config_path = project_root / "config" / "index_constituents.json"
    with open(config_path, 'r') as f:
        return json.load(f)


def _index_monthly_trend(market_provider, index_symbol: str) -> tuple:
    """Get the index performance over the last month.

    Returns:
        Tuple of (change_pct, badge_color, trend_icon).
    """
    try:
        index_df = market_provider.get_historical_data(index_symbol, period="1mo")
        if index_df is not None and not index_df.empty:
            current_price = index_df['Close'].iloc[-1]
            start_price = index_df['Close'].iloc[0]
            change_pct = ((current_price - start_price) / start_price) * 100
            if change_pct > 0:
                return change_pct, "success", "📈"
            return change_pct, "danger", "📉"
    except Exception:
        pass
    return 0, "secondary", "➡️"


def _tracked_stocks_for_index(engine, index_data: dict, entity_symbols: dict) -> list:
    """Find stocks from an index that exist as entities and have predictions."""
    tracked_stocks = []
    for stock_symbol in index_data["top_stocks"]:
        entity = entity_symbols.get(stock_symbol)
        if entity is None:
            continue

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
    return tracked_stocks


def _index_card(index_name: str, change_pct: float, trend_color: str,
                trend_icon: str, tracked_stocks: list) -> dbc.Card:
    """Build the card for one index with its tracked stock buttons."""
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
    return dbc.Card([
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


def get_index_trends(engine):
    """Get index trends and related stock predictions"""
    from src.services.market_data import MarketDataProvider

    try:
        indices = _load_index_constituents()
        market_provider = MarketDataProvider()

        # Get entities from database that match stocks in indices
        with Session(engine) as db:
            all_entities = db.query(Entity).all()
            entity_symbols = {e.entity_name: e for e in all_entities}

        index_displays = []
        for index_name, index_data in indices.items():
            change_pct, trend_color, trend_icon = _index_monthly_trend(
                market_provider, index_data["index_symbol"]
            )
            tracked_stocks = _tracked_stocks_for_index(engine, index_data, entity_symbols)
            if tracked_stocks:
                index_displays.append(
                    _index_card(index_name, change_pct, trend_color, trend_icon, tracked_stocks)
                )

        if not index_displays:
            return html.P("No tracked stocks found in major indices", className="text-muted text-center")

        return html.Div(index_displays)
    except Exception as e:
        logger.error(f"Error loading index trends: {e}", exc_info=True)
        return html.P(f"Error loading index trends: {str(e)[:100]}", className="text-danger")


# ---------------------------------------------------------------------------
# Stock predictions detail (modal)
# ---------------------------------------------------------------------------

def _prediction_status_badge(status) -> dbc.Badge:
    """Badge for the prediction status ('active'/'expired'/anything else)."""
    if status == 'active':
        return dbc.Badge("Active", color="success")
    if status == 'expired':
        return dbc.Badge("Expired", color="secondary")
    return dbc.Badge("Unknown", color="warning")


def _prediction_reasoning_text(pred) -> str:
    """Prediction reasoning, truncated to 200 characters."""
    if hasattr(pred, 'reasoning') and len(pred.reasoning) > 200:
        return pred.reasoning[:200] + "..."
    return getattr(pred, 'reasoning', 'No reasoning available')


def _prediction_card(pred, perf_data: dict) -> dbc.Card:
    """Build the card for one prediction in the stock predictions modal."""
    status_badge = _prediction_status_badge(perf_data.get('status'))
    total_return = perf_data.get('total_return_pct', 0)
    return_color = "success" if total_return > 0 else "danger" if total_return < 0 else "secondary"

    return dbc.Card([
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
                html.Span([
                    dbc.Badge(
                        f"{total_return:+.2f}%",
                        color=return_color,
                        className="me-2",
                        style={"fontSize": "1rem"}
                    ),
                    dbc.Button(
                        "Details",
                        id={"type": "pred-detail-btn", "index": str(pred.prediction_id)},
                        size="sm",
                        color="primary",
                        outline=True,
                        title="View full prediction details"
                    )
                ])
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
            html.P(_prediction_reasoning_text(pred), className="small text-muted mb-0")
        ])
    ], className="mb-3")


def _stock_summary_card(predictions: list, entity: Entity) -> dbc.Card:
    """Build the summary card shown above the prediction list."""
    avg_confidence = sum(p.confidence for p in predictions) / len(predictions) if predictions else 0
    return dbc.Card([
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


def get_stock_predictions_detail(engine, stock_symbol):
    """Get all predictions for a specific stock with performance data"""
    from src.gui.tabs.predictions import _format_saved_performance

    try:
        with Session(engine) as db:
            entity = db.query(Entity).filter(Entity.entity_name == stock_symbol).first()
            if not entity:
                return f"{stock_symbol} - Not Found", html.P("Stock not found in database", className="text-muted")

            # Limit to the 5 most recent predictions for performance
            predictions = db.query(Prediction).filter(
                Prediction.entity_id == entity.entity_id
            ).order_by(desc(Prediction.created_at)).limit(5).all()

            if not predictions:
                return f"{stock_symbol} - No Predictions", html.P("No predictions found for this stock", className="text-muted")

            pred_cards = []
            for pred in predictions:
                try:
                    outcome = db.query(PredictionOutcome).filter(
                        PredictionOutcome.prediction_id == pred.prediction_id
                    ).first()

                    # Always load live prices for this modal (limited to 5 predictions)
                    perf_data = _format_saved_performance(pred, entity, outcome, load_live_prices=True)
                    if not perf_data:
                        continue

                    pred_cards.append(_prediction_card(pred, perf_data))
                except Exception as e:
                    # Skip predictions that cause errors
                    logger.error(f"Error processing prediction {pred.prediction_id}: {e}")
                    continue

            if not pred_cards:
                return f"{stock_symbol} - No Data", html.P("No performance data available", className="text-muted")

            body = html.Div([
                _stock_summary_card(predictions, entity),
                html.H5("All Predictions", className="mt-3 mb-3"),
                html.Div(pred_cards, style={"maxHeight": "600px", "overflowY": "auto"})
            ])

            return f"{stock_symbol} - {len(predictions)} Predictions", body
    except Exception as e:
        logger.error(f"Error loading stock predictions for {stock_symbol}: {e}", exc_info=True)
        return "Error", html.P(f"Error: {str(e)[:100]}", className="text-danger")
