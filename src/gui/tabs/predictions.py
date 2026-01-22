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


def get_predictions_table(engine):
    """Get predictions table"""
    with Session(engine) as db:
        predictions = db.query(Prediction).order_by(
            desc(Prediction.created_at)
        ).limit(20).all()
        
        if not predictions:
            return dbc.Alert("No predictions available yet. Run the pipeline to generate predictions.", color="info")
        
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
                html.Td(pred.forecast_horizon if pred.forecast_horizon else "N/A")
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
