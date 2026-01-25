"""
News Feed Tab - Browse and Filter News Articles
"""

from dash import dcc, html
import dash_bootstrap_components as dbc
from sqlalchemy import desc, cast, Float, func
from sqlalchemy.orm import Session

from src.models.raw_news import RawNews
from src.models.processed_news import ProcessedNews
from src.models.analysis import ImpactScore


def create_layout():
    """Create news feed tab layout"""
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("Filter News", className="mb-3"),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Source:"),
                                dcc.Dropdown(
                                    id="news-source-filter",
                                    multi=True,
                                    placeholder="All sources..."
                                )
                            ], width=3),
                            dbc.Col([
                                dbc.Label("Event Type:"),
                                dcc.Dropdown(
                                    id="news-event-filter",
                                    options=[
                                        {"label": "Earnings", "value": "earnings"},
                                        {"label": "M&A", "value": "ma"},
                                        {"label": "Guidance", "value": "guidance"},
                                        {"label": "Product", "value": "product"},
                                        {"label": "Regulatory", "value": "regulatory"}
                                    ],
                                    multi=True,
                                    placeholder="All types..."
                                )
                            ], width=3),
                            dbc.Col([
                                dbc.Label("Sentiment:"),
                                dcc.Dropdown(
                                    id="news-sentiment-filter",
                                    options=[
                                        {"label": "Positive (>0.3)", "value": "positive"},
                                        {"label": "Neutral", "value": "neutral"},
                                        {"label": "Negative (<-0.3)", "value": "negative"}
                                    ],
                                    placeholder="All sentiment..."
                                )
                            ], width=3),
                            dbc.Col([
                                dbc.Label("Search:"),
                                dbc.Input(
                                    id="news-search-input",
                                    type="text",
                                    placeholder="Search keywords..."
                                )
                            ], width=3)
                        ])
                    ])
                ])
            ], width=12)
        ], className="mb-3"),
        dbc.Row([
            dbc.Col([
                html.Div(
                    id="news-feed",
                    style={"maxHeight": "1200px", "overflowY": "auto"}
                )
            ], width=12)
        ])
    ], fluid=True)


def get_news_feed(engine, sources=None, events=None, sentiment=None, search=None):
    """Get news feed with filters"""
    with Session(engine) as db:
        query = db.query(RawNews, ProcessedNews).outerjoin(
            ProcessedNews, RawNews.news_id == ProcessedNews.news_id
        )
        
        # Apply filters
        if sources:
            query = query.filter(RawNews.source.in_(sources))
        
        if events:
            query = query.filter(ProcessedNews.event_type.in_(events))
        
        # Note: Sentiment filtering done in Python (post-query) due to SQLite JSON limitations
        
        if search and len(search) > 0:
            search_term = f"%{search.lower()}%"
            query = query.filter(
                (RawNews.title.ilike(search_term)) |
                (RawNews.full_text.ilike(search_term))
            )
        
        query = query.order_by(desc(RawNews.fetched_at)).limit(500)
        results = query.all()
        
        # Apply sentiment filter in Python
        if sentiment and results:
            filtered_results = []
            for raw_news, processed in results:
                if processed and processed.sentiment:
                    sent_val = processed.sentiment.get('overall', 0) if isinstance(processed.sentiment, dict) else 0
                    if sentiment == "positive" and sent_val > 0.3:
                        filtered_results.append((raw_news, processed))
                    elif sentiment == "negative" and sent_val < -0.3:
                        filtered_results.append((raw_news, processed))
                    elif sentiment == "neutral" and -0.3 <= sent_val <= 0.3:
                        filtered_results.append((raw_news, processed))
            results = filtered_results
        
        # Limit results after filtering
        results = results[:100]
        
        if not results:
            return dbc.Alert("No news articles match your filters.", color="info")
        
        # Get all news IDs for batch loading impact scores
        news_ids = [raw_news.news_id for raw_news, _ in results]
        
        # Load all impact scores in one query
        impact_scores_dict = {}
        if news_ids:
            try:
                impact_scores_list = db.query(ImpactScore).filter(
                    ImpactScore.news_id.in_(news_ids)
                ).all()
                
                # Group by news_id and get max impact score per news
                # Convert UUIDs to strings for reliable comparison (SQLite stores as strings)
                for impact in impact_scores_list:
                    # Convert UUID to string for dictionary key (handles both UUID objects and strings)
                    news_id_key = str(impact.news_id) if impact.news_id else None
                    if news_id_key:
                        if news_id_key not in impact_scores_dict:
                            impact_scores_dict[news_id_key] = impact.impact_score
                        else:
                            impact_scores_dict[news_id_key] = max(impact_scores_dict[news_id_key], impact.impact_score)
            except Exception as e:
                # Log error but continue - impact scores are optional
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Error loading impact scores: {e}")
        
        cards = []
        for raw_news, processed in results:
            # Get max impact score for this news article
            # Convert UUID to string for lookup (handles both UUID objects and strings)
            news_id_key = str(raw_news.news_id) if raw_news.news_id else None
            max_impact = impact_scores_dict.get(news_id_key) if news_id_key else None
            
            # Sentiment badge
            sentiment_badge = None
            if processed and processed.sentiment:
                sent_val = processed.sentiment.get('overall', 0) if isinstance(processed.sentiment, dict) else 0
                if sent_val > 0.3:
                    sentiment_badge = dbc.Badge("😊 Positive", color="success", className="ms-2")
                elif sent_val < -0.3:
                    sentiment_badge = dbc.Badge("😟 Negative", color="danger", className="ms-2")
                else:
                    sentiment_badge = dbc.Badge("😐 Neutral", color="secondary", className="ms-2")
            
            # Event badge
            event_badge = None
            if processed and processed.event_type:
                event_badge = dbc.Badge(processed.event_type.upper(), color="primary", className="ms-2")
            
            # Impact score badge with color coding
            impact_badge = None
            if max_impact is not None:
                # Color coding: high (>=0.4) = success, medium (0.3-0.4) = warning, low (<0.3) = secondary
                if max_impact >= 0.4:
                    impact_color = "success"
                elif max_impact >= 0.3:
                    impact_color = "warning"
                else:
                    impact_color = "secondary"
                
                impact_badge = dbc.Badge(
                    f"Impact: {max_impact:.2f}",
                    color=impact_color,
                    className="ms-2"
                )
            else:
                # Show "No Impact" badge if no impact score calculated yet
                impact_badge = dbc.Badge(
                    "No Impact",
                    color="secondary",
                    className="ms-2",
                    style={"opacity": "0.6"}
                )
            
            card = dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.Div([
                            html.A(
                                raw_news.title, 
                                href=raw_news.url, 
                                target="_blank", 
                                className="text-light text-decoration-none news-title"
                            ),
                            html.Span([sentiment_badge, event_badge, impact_badge], className="ms-2")
                        ], className="d-flex align-items-start mb-1"),
                        html.Div([
                            dbc.Badge(raw_news.source, color="secondary", className="me-2 badge-sm"),
                            html.Small(
                                raw_news.fetched_at.strftime("%H:%M") if raw_news.fetched_at else "N/A", 
                                className="text-muted"
                            )
                        ], className="d-flex align-items-center")
                    ])
                ], className="py-2 px-3")
            ], className="mb-2 news-card-compact")
            
            cards.append(card)
        
        return html.Div(cards)
