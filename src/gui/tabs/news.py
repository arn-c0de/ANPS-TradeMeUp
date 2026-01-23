"""
News Feed Tab - Browse and Filter News Articles
"""

from dash import dcc, html
import dash_bootstrap_components as dbc
from sqlalchemy import desc, cast, Float
from sqlalchemy.orm import Session

from src.models.raw_news import RawNews
from src.models.processed_news import ProcessedNews


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
                html.Div(id="news-feed")
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
        
        query = query.order_by(desc(RawNews.fetched_at)).limit(100)
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
            results = filtered_results[:50]
        else:
            results = results[:50]
        
        if not results:
            return dbc.Alert("No news articles match your filters.", color="info")
        
        cards = []
        for raw_news, processed in results:
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
                            html.Span([sentiment_badge, event_badge], className="ms-2")
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
