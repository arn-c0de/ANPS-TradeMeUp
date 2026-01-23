"""
Predictions Tab - View and Filter Predictions
"""

from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta
from sqlalchemy import desc
from sqlalchemy.orm import Session
import json

from src.models.predictions import Prediction
from src.models.entities import Entity
from src.models.raw_news import RawNews
from src.models.processed_news import ProcessedNews
from src.models.analysis import ImpactScore, SurpriseScore, FactVerification


def create_layout():
    """Create predictions tab layout"""
    return dbc.Container([
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H6("Filter Predictions", className="mb-3"),
                        dbc.Row([
                            dbc.Col([
                                dbc.Label("Entity/Ticker:"),
                                dcc.Dropdown(
                                    id="pred-entity-filter",
                                    multi=True,
                                    placeholder="All entities..."
                                )
                            ], width=3),
                            dbc.Col([
                                dbc.Label("Date Range:"),
                                dcc.DatePickerRange(
                                    id="pred-date-filter",
                                    start_date=(datetime.now() - timedelta(days=7)).date(),
                                    end_date=datetime.now().date(),
                                )
                            ], width=3),
                            dbc.Col([
                                dbc.Label("Horizon:"),
                                dcc.Dropdown(
                                    id="pred-horizon-filter",
                                    options=[
                                        {'label': '1 Day (Short-term)', 'value': '1d'},
                                        {'label': '5 Days (Swing)', 'value': '5d'},
                                        {'label': '20 Days (Position)', 'value': '20d'}
                                    ],
                                    value='5d',
                                    clearable=False
                                )
                            ], width=3),
                            dbc.Col([
                                dbc.Label("Min Confidence:"),
                                dcc.Slider(
                                    id="pred-confidence-filter",
                                    min=0, max=100, step=10, value=0,
                                    marks={i: f"{i}%" for i in range(0, 101, 20)}
                                )
                            ], width=3)
                        ])
                    ])
                ])
            ], width=12)
        ], className="mb-3"),
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardHeader(html.H5("🎯 Active Predictions")),
                    dbc.CardBody([
                        html.P("Click on a prediction to see details", className="text-muted mb-3"),
                        html.Div(id="predictions-table")
                    ])
                ])
            ], width=12)
        ]),

        # Modal for prediction details
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="prediction-modal-title")),
            dbc.ModalBody(id="prediction-modal-body"),
            dbc.ModalFooter(
                dbc.Button("Close", id="close-prediction-modal", className="ms-auto", n_clicks=0)
            )
        ], id="prediction-modal", size="xl", is_open=False),

        # Hidden store for cached prediction details
        dcc.Store(id="prediction-detail-cache", data={})
    ], fluid=True)


def get_predictions_table(engine, entity_filter=None, date_range=None, min_confidence=0, horizon='5d'):
    """Get predictions table with filters

    Args:
        engine: Database engine
        entity_filter: List of entity IDs to filter by
        date_range: Tuple of (start_date, end_date)
        min_confidence: Minimum confidence threshold (0-1)
        horizon: Prediction horizon (1d, 5d, 20d)
    """
    try:
        with Session(engine) as db:
            query = db.query(Prediction).join(
                Entity, Prediction.entity_id == Entity.entity_id
            ).order_by(desc(Prediction.created_at))

            # Filter by selected horizon
            query = query.filter(Prediction.horizon == horizon)

            # Apply filters
            if entity_filter:
                query = query.filter(Prediction.entity_id.in_(entity_filter))
            
            if date_range and len(date_range) == 2:
                start, end = date_range
                if start:
                    # Convert string to date if needed
                    if isinstance(start, str):
                        start = datetime.fromisoformat(start).date()
                    # Start of day
                    query = query.filter(Prediction.created_at >= datetime.combine(start, datetime.min.time()))
                if end:
                    # Convert string to date if needed
                    if isinstance(end, str):
                        end = datetime.fromisoformat(end).date()
                    # End of day (23:59:59)
                    query = query.filter(Prediction.created_at <= datetime.combine(end, datetime.max.time()))
            
            if min_confidence > 0:
                query = query.filter(Prediction.confidence >= min_confidence / 100)
            
            predictions = query.limit(50).all()

            if not predictions:
                return dbc.Alert("No predictions match the current filters.", color="info")

            rows = []
            for pred in predictions:
                entity = db.query(Entity).filter(Entity.entity_id == pred.entity_id).first()

                # Get direction from probabilities
                probs = pred.direction_probabilities or {}
                direction = max(probs, key=probs.get) if probs else "unknown"
                direction_emoji = {"up": "🔼", "down": "🔽", "flat": "➡️"}.get(direction, "❓")

                # Get confidence color
                conf_color = "text-success" if pred.confidence and pred.confidence > 0.7 else "text-warning"

                rows.append(html.Tr([
                    html.Td(pred.created_at.strftime("%Y-%m-%d %H:%M") if pred.created_at else "N/A"),
                    html.Td(entity.entity_name if entity else "Unknown", className="text-primary"),
                    html.Td([direction_emoji, " ", direction.upper()]),
                    html.Td(f"{pred.confidence:.2%}" if pred.confidence else "N/A", className=conf_color),
                    html.Td(pred.horizon if pred.horizon else "N/A"),
                    html.Td(
                        dbc.Button("Details", id={"type": "pred-detail-btn", "index": str(pred.prediction_id)},
                                   size="sm", color="info", outline=True)
                    )
                ], style={"cursor": "pointer"}))

            return dbc.Table([
                html.Thead(html.Tr([
                    html.Th("Timestamp"),
                    html.Th("Entity"),
                    html.Th("Direction"),
                    html.Th("Confidence"),
                    html.Th("Horizon"),
                    html.Th("Actions")
                ])),
                html.Tbody(rows)
            ], bordered=True, hover=True, striped=True, className="table-dark")
    except Exception as e:
        return dbc.Alert(
            f"⚠️ Unable to load predictions: {str(e)}",
            color="warning"
        )


def get_entity_options(engine):
    """Get available entities for dropdown filter"""
    try:
        with Session(engine) as db:
            entities = db.query(Entity).filter(
                Entity.entity_type == 'company'
            ).order_by(Entity.entity_name).all()

            return [
                {'label': f"{e.entity_name} ({e.entity_id})", 'value': e.entity_id}
                for e in entities
            ]
    except Exception:
        return []


def get_prediction_details(engine, prediction_id):
    """Get detailed information about a prediction

    Args:
        engine: Database engine
        prediction_id: UUID of prediction to show details for

    Returns:
        Tuple of (title, body_content)
    """
    try:
        with Session(engine) as db:
            # Get prediction
            pred = db.query(Prediction).filter(
                Prediction.prediction_id == prediction_id
            ).first()

            if not pred:
                return "Error", dbc.Alert("Prediction not found", color="danger")

            # Get entity
            entity = db.query(Entity).filter(Entity.entity_id == pred.entity_id).first()
            entity_name = entity.entity_name if entity else pred.entity_id

            # Get direction
            probs = pred.direction_probabilities or {}
            direction = max(probs, key=probs.get) if probs else "unknown"
            direction_emoji = {"up": "🔼", "down": "🔽", "flat": "➡️"}.get(direction, "❓")

            # Get related news
            news_ids = pred.related_news_ids or []
            if not news_ids:
                news_content = dbc.Alert("No related news found", color="warning")
            else:
                news_id = news_ids[0] if isinstance(news_ids, list) else news_ids

                raw_news = db.query(RawNews).filter(RawNews.news_id == news_id).first()
                processed = db.query(ProcessedNews).filter(ProcessedNews.news_id == news_id).first()
                impact = db.query(ImpactScore).filter(
                    ImpactScore.news_id == news_id,
                    ImpactScore.entity_id == pred.entity_id
                ).first()

                news_content = dbc.Card([
                    dbc.CardHeader(html.H6("📰 Related News")),
                    dbc.CardBody([
                        html.H6(raw_news.title if raw_news else "Unknown", className="text-primary"),
                        html.P([
                            html.Strong("Source: "),
                            raw_news.source if raw_news else "Unknown",
                            html.Br(),
                            html.Strong("Published: "),
                            raw_news.published_at.strftime("%Y-%m-%d %H:%M") if raw_news and raw_news.published_at else "Unknown",
                            html.Br(),
                            html.Strong("URL: "),
                            html.A(raw_news.url, href=raw_news.url, target="_blank") if raw_news and raw_news.url else "N/A"
                        ], className="mb-2"),
                        html.Hr(),
                        html.H6("Content Summary"),
                        html.P(raw_news.full_text[:500] + "..." if raw_news and raw_news.full_text and len(raw_news.full_text) > 500
                               else raw_news.full_text if raw_news and raw_news.full_text else "No content available",
                               className="text-muted", style={"maxHeight": "200px", "overflowY": "auto"}),
                        html.Hr() if processed else None,
                        html.H6("Sentiment Analysis") if processed else None,
                        dbc.Row([
                            dbc.Col([
                                html.Strong("Overall: "),
                                html.Span(f"{processed.sentiment.get('overall', 0):.2f}",
                                         className="text-success" if processed and processed.sentiment.get('overall', 0) > 0 else "text-danger")
                            ], width=4) if processed and processed.sentiment else None,
                            dbc.Col([
                                html.Strong("Market: "),
                                html.Span(f"{processed.sentiment.get('market', 0):.2f}",
                                         className="text-success" if processed and processed.sentiment.get('market', 0) > 0 else "text-danger")
                            ], width=4) if processed and processed.sentiment else None,
                            dbc.Col([
                                html.Strong("Company: "),
                                html.Span(f"{processed.sentiment.get('company', 0):.2f}",
                                         className="text-success" if processed and processed.sentiment.get('company', 0) > 0 else "text-danger")
                            ], width=4) if processed and processed.sentiment else None
                        ]) if processed else None,
                        html.Hr() if processed and processed.event_type else None,
                        html.P([
                            html.Strong("Event Type: "),
                            dbc.Badge(processed.event_type, color="primary")
                        ]) if processed and processed.event_type else None,
                        html.Hr() if impact else None,
                        html.P([
                            html.Strong("Impact Score: "),
                            html.Span(f"{impact.impact_score:.3f}", className="text-warning" if impact else "")
                        ]) if impact else None
                    ])
                ], className="mb-3")

            # Expected returns
            expected = pred.expected_return or {}

            # Key drivers
            drivers = pred.key_drivers or []
            drivers_content = dbc.Card([
                dbc.CardHeader(html.H6("🎯 Key Drivers")),
                dbc.CardBody([
                    dbc.Table([
                        html.Thead(html.Tr([
                            html.Th("Feature"),
                            html.Th("Importance"),
                            html.Th("Weight")
                        ])),
                        html.Tbody([
                            html.Tr([
                                html.Td(d.get('driver', 'Unknown')),
                                html.Td(
                                    dbc.Progress(value=d.get('importance', 0) * 100,
                                               className="mb-0", style={"height": "20px"})
                                ),
                                html.Td(f"{d.get('importance', 0):.1%}")
                            ]) for d in drivers[:5]  # Top 5
                        ])
                    ], bordered=True, striped=True) if drivers else html.P("No driver data available", className="text-muted")
                ])
            ], className="mb-3")

            # Build modal content
            title = f"{direction_emoji} {entity_name} - {direction.upper()} Prediction"

            body = dbc.Container([
                # Overview
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.H4(f"{direction_emoji} {direction.upper()}", className="text-center"),
                                html.P("Direction", className="text-center text-muted")
                            ])
                        ])
                    ], width=3),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.H4(f"{pred.confidence:.1%}", className="text-center"),
                                html.P("Confidence", className="text-center text-muted")
                            ])
                        ])
                    ], width=3),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.H4(f"{expected.get('mean', 0):.2%}", className="text-center"),
                                html.P("Expected Return", className="text-center text-muted")
                            ])
                        ])
                    ], width=3),
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.H4(pred.horizon, className="text-center"),
                                html.P("Horizon", className="text-center text-muted")
                            ])
                        ])
                    ], width=3)
                ], className="mb-3"),

                # Direction Probabilities
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader(html.H6("📊 Direction Probabilities")),
                            dbc.CardBody([
                                dbc.Row([
                                    dbc.Col([
                                        html.P("🔼 UP", className="mb-1"),
                                        dbc.Progress(value=probs.get('up', 0) * 100,
                                                   color="success", className="mb-2",
                                                   style={"height": "25px"},
                                                   label=f"{probs.get('up', 0):.1%}")
                                    ], width=12),
                                    dbc.Col([
                                        html.P("➡️ FLAT", className="mb-1"),
                                        dbc.Progress(value=probs.get('flat', 0) * 100,
                                                   color="warning", className="mb-2",
                                                   style={"height": "25px"},
                                                   label=f"{probs.get('flat', 0):.1%}")
                                    ], width=12),
                                    dbc.Col([
                                        html.P("🔽 DOWN", className="mb-1"),
                                        dbc.Progress(value=probs.get('down', 0) * 100,
                                                   color="danger", className="mb-2",
                                                   style={"height": "25px"},
                                                   label=f"{probs.get('down', 0):.1%}")
                                    ], width=12)
                                ])
                            ])
                        ])
                    ], width=12)
                ], className="mb-3"),

                # News and Drivers
                dbc.Row([
                    dbc.Col([news_content], width=7),
                    dbc.Col([drivers_content], width=5)
                ]),

                # Model Info
                dbc.Row([
                    dbc.Col([
                        dbc.Card([
                            dbc.CardHeader(html.H6("🤖 Model Information")),
                            dbc.CardBody([
                                html.P([
                                    html.Strong("Model Version: "),
                                    pred.model_version or "Unknown"
                                ]),
                                html.P([
                                    html.Strong("Created: "),
                                    pred.created_at.strftime("%Y-%m-%d %H:%M:%S") if pred.created_at else "Unknown"
                                ]),
                                html.P([
                                    html.Strong("Prediction ID: "),
                                    html.Code(str(pred.prediction_id))
                                ])
                            ])
                        ])
                    ], width=12)
                ], className="mt-3")
            ], fluid=True)

            return title, body

    except Exception as e:
        return "Error", dbc.Alert(f"Error loading prediction details: {str(e)}", color="danger")