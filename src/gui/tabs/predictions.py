"""
Predictions Tab - View and Filter Predictions
"""

from dash import dcc, html
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta
from sqlalchemy import desc
from sqlalchemy.orm import Session

from src.models.predictions import Prediction
from src.models.entities import Entity


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
                            ], width=4),
                            dbc.Col([
                                dbc.Label("Date Range:"),
                                dcc.DatePickerRange(
                                    id="pred-date-filter",
                                    start_date=(datetime.now() - timedelta(days=7)).date(),
                                    end_date=datetime.now().date(),
                                )
                            ], width=4),
                            dbc.Col([
                                dbc.Label("Min Confidence:"),
                                dcc.Slider(
                                    id="pred-confidence-filter",
                                    min=0, max=100, step=10, value=0,
                                    marks={i: f"{i}%" for i in range(0, 101, 20)}
                                )
                            ], width=4)
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
                        html.Div(id="predictions-table")
                    ])
                ])
            ], width=12)
        ])
    ], fluid=True)


def get_predictions_table(engine, entity_filter=None, date_range=None, min_confidence=0):
    """Get predictions table with filters
    
    Args:
        engine: Database engine
        entity_filter: List of entity IDs to filter by
        date_range: Tuple of (start_date, end_date)
        min_confidence: Minimum confidence threshold (0-1)
    """
    try:
        with Session(engine) as db:
            query = db.query(Prediction).join(
                Entity, Prediction.entity_id == Entity.entity_id
            ).order_by(desc(Prediction.created_at))
            
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
                    html.Td(pred.horizon if pred.horizon else "N/A")
                ]))

            return dbc.Table([
                html.Thead(html.Tr([
                    html.Th("Timestamp"),
                    html.Th("Entity"),
                    html.Th("Direction"),
                    html.Th("Confidence"),
                    html.Th("Horizon")
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