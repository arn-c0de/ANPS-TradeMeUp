"""
Simulations Tab - View trading simulation outcomes
"""

from dash import dcc, html
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta
from sqlalchemy import desc, func
from sqlalchemy.orm import Session, joinedload

from src.models.trading_simulation import TradingSimulation
from src.models.entities import Entity
from src.models.predictions import Prediction


def create_layout():
    """Create simulations tab layout"""
    return html.Div([
        dcc.Store(id="sim-delete-status"),
        dcc.Store(id="sim-filter-sync-store", data={"entities": None, "horizon": None}),
        dbc.Container([
            # Create New Simulations Section (native <details> – instant expand/collapse, no JS)
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        html.Details(
                            [
                                html.Summary(
                                    "➕ Create New Simulations",
                                    className="create-sim-summary"
                                ),
                                dbc.CardBody([
                                    dbc.Row([
                                        dbc.Col([
                                            html.Small("Entities", className="text-muted d-block mb-1"),
                                            dcc.Dropdown(
                                                id="create-sim-entity-filter",
                                                multi=True,
                                                placeholder="All entities...",
                                                persistence=True,
                                                persistence_type="local",
                                                className="small",
                                                style={"fontSize": "0.85rem"}
                                            )
                                        ], width=12, md=6, className="mb-2 mb-md-0"),
                                        dbc.Col([
                                            html.Small("Date Range", className="text-muted d-block mb-1"),
                                            dcc.DatePickerRange(
                                                id="create-sim-date-range",
                                                start_date=None,
                                                end_date=None,
                                                persistence=True,
                                                persistence_type="local",
                                                className="small",
                                            )
                                        ], width=12, md=6)
                                    ], className="g-3 mb-2"),
                                    dbc.Row([
                                        dbc.Col([
                                            html.Small("Horizon", className="text-muted d-block mb-1"),
                                            dcc.Dropdown(
                                                id="create-sim-horizon-filter",
                                                options=[
                                                    {"label": "All", "value": "all"},
                                                    {"label": "1 Day", "value": "1d"},
                                                    {"label": "5 Days", "value": "5d"},
                                                    {"label": "20 Days", "value": "20d"},
                                                ],
                                                value="all",
                                                clearable=False,
                                                persistence=True,
                                                persistence_type="local",
                                                className="small",
                                                style={"fontSize": "0.85rem"}
                                            )
                                        ], width=6, md=2),
                                        dbc.Col([
                                            html.Small("Limit", className="text-muted d-block mb-1"),
                                            dcc.Input(
                                                id="create-sim-limit",
                                                type="number",
                                                value=50,
                                                min=1,
                                                max=500,
                                                persistence=True,
                                                persistence_type="local",
                                                className="form-control form-control-sm"
                                            )
                                        ], width=4, md=2),
                                        dbc.Col([
                                            html.Small("\u00a0", className="d-block mb-1"),
                                            dbc.Button(
                                                "Create",
                                                id="btn-create-simulations",
                                                color="primary",
                                                className="w-100",
                                                size="sm"
                                            )
                                        ], width=12, md=2, className="mt-2 mt-md-0 align-self-end")
                                    ], className="g-3"),
                                    html.Div(id="create-sim-status", className="mt-2")
                                ], className="py-3")
                            ],
                            className="create-sim-details",
                            open=False
                        )
                    ], className="mb-2")
                ], width=12)
            ], className="mb-2"),

            # Filter Simulations Section
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            html.Small("Filter Simulations", className="text-muted d-block mb-1"),
                            dbc.Row([
                                dbc.Col([
                                    html.Small("Entity/Ticker", className="text-muted d-block"),
                                    dcc.Dropdown(
                                        id="sim-entity-filter",
                                        multi=True,
                                        placeholder="All entities...",
                                        persistence=True,
                                        persistence_type="local",
                                        className="small",
                                        style={"fontSize": "0.85rem"}
                                    )
                                ], width=4),
                                dbc.Col([
                                    html.Small("Date Range", className="text-muted d-block"),
                                    dcc.DatePickerRange(
                                        id="sim-date-filter",
                                        start_date=(datetime.now() - timedelta(days=7)).date(),
                                        end_date=datetime.now().date(),
                                        persistence=True,
                                        persistence_type="local",
                                        className="small",
                                    )
                                ], width=3),
                                dbc.Col([
                                    html.Small("Horizon", className="text-muted d-block"),
                                    dcc.Dropdown(
                                        id="sim-horizon-filter",
                                        options=[
                                            {"label": "All", "value": "all"},
                                            {"label": "1 Day", "value": "1d"},
                                            {"label": "5 Days", "value": "5d"},
                                            {"label": "20 Days", "value": "20d"},
                                        ],
                                        value="all",
                                        clearable=False,
                                        persistence=True,
                                        persistence_type="local",
                                        className="small",
                                        style={"fontSize": "0.85rem"}
                                    )
                                ], width=2),
                                dbc.Col([
                                    html.Small("Decision", className="text-muted d-block"),
                                    dcc.Dropdown(
                                        id="sim-decision-filter",
                                        options=[
                                            {"label": "All", "value": "all"},
                                            {"label": "Buy", "value": "buy"},
                                            {"label": "Sell", "value": "sell"},
                                            {"label": "Hold", "value": "hold"},
                                        ],
                                        value="all",
                                        clearable=False,
                                        persistence=True,
                                        persistence_type="local",
                                        className="small",
                                        style={"fontSize": "0.85rem"}
                                    )
                                ], width=3)
                            ], className="g-2")
                        ], className="py-2")
                    ], className="mb-2")
                ], width=12)
            ], className="mb-2"),

            # Simulations Table Section
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader([
                            dbc.Row([
                                dbc.Col(html.H6("🧪 Trading Simulations"), className="d-flex align-items-center"),
                                dbc.Col([
                                    dbc.Button(
                                        "🗑️ Clear All Simulations",
                                        id="btn-clear-all-simulations",
                                        color="danger",
                                        size="sm",
                                        className="float-end"
                                    )
                                ], width="auto")
                            ], className="g-0")
                        ], className="py-1"),
                        dbc.CardBody([
                            html.Small("Simulation results generated from predictions vs market data", className="text-muted d-block mb-2"),
                            html.Div(
                                id="simulation-table",
                                style={"maxHeight": "800px", "overflowY": "auto"}
                            )
                        ])
                    ])
                ], width=12)
            ]),
            
            # Clear All Simulations Confirmation Modal
            dbc.Modal([
                dbc.ModalHeader(dbc.ModalTitle("⚠️ Confirm Delete All Simulations")),
                dbc.ModalBody([
                    html.P("Are you sure you want to delete ALL simulations? This action cannot be undone."),
                    html.P(html.Strong("This will permanently remove all simulation data from the database."), className="text-danger")
                ]),
                dbc.ModalFooter([
                    dbc.Button("Cancel", id="btn-cancel-clear-simulations", color="secondary", className="me-2"),
                    dbc.Button("Delete All", id="btn-confirm-clear-simulations", color="danger")
                ])
            ], id="modal-clear-all-simulations", is_open=False)
        ], fluid=True)
    ])


def get_simulation_table(engine, entity_filter=None, date_range=None, decision_filter="all", horizon_filter="all"):
    """Get simulations table with filters."""
    try:
        with Session(engine, expire_on_commit=False) as db:
            query = db.query(TradingSimulation).options(
                joinedload(TradingSimulation.entity)
            ).order_by(desc(TradingSimulation.created_at))

            if entity_filter:
                query = query.filter(TradingSimulation.entity_id.in_(entity_filter))

            if decision_filter and decision_filter != "all":
                query = query.filter(TradingSimulation.decision == decision_filter)

            if horizon_filter and horizon_filter != "all":
                query = query.filter(TradingSimulation.horizon == horizon_filter)

            if date_range and len(date_range) == 2:
                start, end = date_range
                if start:
                    if isinstance(start, str):
                        start = datetime.fromisoformat(start).date()
                    query = query.filter(TradingSimulation.created_at >= datetime.combine(start, datetime.min.time()))
                if end:
                    if isinstance(end, str):
                        end = datetime.fromisoformat(end).date()
                    query = query.filter(TradingSimulation.created_at <= datetime.combine(end, datetime.max.time()))

            simulations = query.limit(200).all()

            if not simulations:
                return dbc.Alert("No simulations match the current filters.", color="info")

            rows = []
            for sim in simulations:
                entity = sim.entity
                decision = sim.decision or "hold"
                decision_color = {
                    "buy": "success",
                    "sell": "danger",
                    "hold": "secondary"
                }.get(decision, "secondary")

                risk_score = sim.risk_score
                risk_color = "danger" if risk_score and risk_score > 0.7 else "warning" if risk_score and risk_score > 0.4 else "success"

                expected_return = sim.expected_return_pct
                expected_color = "text-success" if expected_return and expected_return > 0 else "text-danger" if expected_return and expected_return < 0 else "text-muted"

                actual_return = sim.actual_return_pct
                actual_color = "text-success" if actual_return and actual_return > 0 else "text-danger" if actual_return and actual_return < 0 else "text-muted"

                divergence = sim.divergence_pct
                divergence_color = "text-warning" if divergence and abs(divergence) > 2 else "text-muted"

                cost_bps = sim.transaction_cost_bps

                rows.append(html.Tr([
                    html.Td(sim.created_at.strftime("%Y-%m-%d %H:%M") if sim.created_at else "N/A"),
                    html.Td(entity.entity_name if entity else sim.entity_id, className="text-primary"),
                    html.Td(sim.horizon or "N/A"),
                    html.Td(dbc.Badge(decision.upper(), color=decision_color, className="px-2")),
                    html.Td(f"{risk_score:.2f}" if risk_score is not None else "—",
                            className=f"text-{risk_color} text-center"),
                    html.Td(f"{expected_return:+.2f}%" if expected_return is not None else "—",
                            className=expected_color),
                    html.Td(f"{actual_return:+.2f}%" if actual_return is not None else "—",
                            className=actual_color),
                    html.Td(f"{divergence:+.2f}%" if divergence is not None else "—",
                            className=divergence_color),
                    html.Td(f"{cost_bps:.1f}" if cost_bps is not None else "—",
                            className="text-muted text-center"),
                    html.Td([
                        dbc.ButtonGroup([
                            dbc.Button(
                                "📊",
                                id={"type": "sim-detail-btn", "index": str(sim.prediction_id)},
                                color="primary",
                                size="sm",
                                className="me-1",
                                title="View prediction details"
                            ),
                            dbc.Button(
                                "🔄",
                                id={"type": "refresh-sim", "index": str(sim.simulation_id)},
                                color="info",
                                size="sm",
                                className="me-1",
                                title="Refresh simulation"
                            ),
                            dbc.Button(
                                "🗑️",
                                id={"type": "delete-sim", "index": str(sim.simulation_id)},
                                color="danger",
                                size="sm",
                                title="Delete simulation"
                            )
                        ], size="sm")
                    ], className="text-center")
                ]))

            return dbc.Table([
                html.Thead(html.Tr([
                    html.Th("Timestamp"),
                    html.Th("Entity"),
                    html.Th("Horizon"),
                    html.Th("Decision"),
                    html.Th("Risk"),
                    html.Th("Expected"),
                    html.Th("Actual"),
                    html.Th("Δ (E-R)"),
                    html.Th("Cost (bps)"),
                    html.Th("Actions", className="text-center")
                ])),
                html.Tbody(rows)
            ], bordered=True, hover=False, striped=True, className="table-dark")
    except Exception as e:
        return dbc.Alert(
            f"⚠️ Unable to load simulations: {str(e)}",
            color="warning"
        )


def _normalize_date(value):
    if not value:
        return None
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None
    if isinstance(value, datetime):
        return value.date()
    return value


def get_prediction_entity_options(engine, date_range=None):
    """Get available entities from predictions for creating simulations, with prediction counts."""
    try:
        with Session(engine) as db:
            # Base query: get entities with prediction counts
            query = db.query(
                Entity,
                func.count(Prediction.prediction_id).label('pred_count')
            ).join(
                Prediction,
                Prediction.entity_id == Entity.entity_id
            )

            # Apply date range filter if provided
            if date_range and len(date_range) == 2 and (date_range[0] or date_range[1]):
                start, end = date_range
                start = _normalize_date(start)
                end = _normalize_date(end)
                
                # Filter predictions by date range
                if start:
                    query = query.filter(
                        Prediction.created_at >= datetime.combine(start, datetime.min.time())
                    )
                if end:
                    query = query.filter(
                        Prediction.created_at <= datetime.combine(end, datetime.max.time())
                    )

            # Group by entity to get counts
            query = query.group_by(Entity.entity_id, Entity.entity_name).having(
                func.count(Prediction.prediction_id) > 0
            ).order_by(Entity.entity_name)

            results = query.all()

            return [
                {
                    "label": f"{entity.entity_name} ({entity.entity_id}) - {pred_count} Prediction{'s' if pred_count != 1 else ''}",
                    "value": entity.entity_id
                }
                for entity, pred_count in results
            ]
    except Exception as e:
        # Fallback: return entities without counts if there's an error
        try:
            with Session(engine) as db:
                entities = db.query(Entity).join(
                    Prediction, Prediction.entity_id == Entity.entity_id
                ).distinct().order_by(Entity.entity_name).all()
                return [
                    {"label": f"{e.entity_name} ({e.entity_id})", "value": e.entity_id}
                    for e in entities
                ]
        except Exception:
            return []


def get_entity_options(engine, date_range=None):
    """Get available entities for dropdown filter with simulation counts."""
    try:
        with Session(engine) as db:
            # Base query: get entities with simulation counts
            query = db.query(
                Entity,
                func.count(TradingSimulation.simulation_id).label('sim_count')
            ).outerjoin(
                TradingSimulation,
                TradingSimulation.entity_id == Entity.entity_id
            ).filter(Entity.entity_type == "company")

            # Apply date range filter if provided
            if date_range and len(date_range) == 2 and (date_range[0] or date_range[1]):
                start, end = date_range
                start = _normalize_date(start)
                end = _normalize_date(end)
                
                # Filter simulations by date range
                if start:
                    query = query.filter(
                        TradingSimulation.created_at >= datetime.combine(start, datetime.min.time())
                    )
                if end:
                    query = query.filter(
                        TradingSimulation.created_at <= datetime.combine(end, datetime.max.time())
                    )

            # Group by entity to get counts
            query = query.group_by(Entity.entity_id, Entity.entity_name)
            
            # If no date filter, only show entities that have simulations
            if not (date_range and len(date_range) == 2 and (date_range[0] or date_range[1])):
                query = query.having(func.count(TradingSimulation.simulation_id) > 0)
            
            query = query.order_by(Entity.entity_name)

            results = query.all()

            return [
                {
                    "label": f"{entity.entity_name} ({entity.entity_id}) - {sim_count} Simulation{'s' if sim_count != 1 else ''}",
                    "value": entity.entity_id
                }
                for entity, sim_count in results
            ]
    except Exception as e:
        # Fallback: return entities without counts if there's an error
        try:
            with Session(engine) as db:
                entities = db.query(Entity).filter(Entity.entity_type == "company").order_by(Entity.entity_name).all()
                return [
                    {"label": f"{e.entity_name} ({e.entity_id})", "value": e.entity_id}
                    for e in entities
                ]
        except Exception:
            return []
