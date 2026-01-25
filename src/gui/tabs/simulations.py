"""
Simulations Tab - View trading simulation outcomes
"""

import json
import logging
from datetime import datetime, timedelta

import dash
from dash import ALL, MATCH, Input, Output, State, dcc, html
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
from sqlalchemy import delete, desc, func
from sqlalchemy.orm import Session, joinedload

from src.models.trading_simulation import TradingSimulation
from src.models.entities import Entity
from src.models.predictions import Prediction
from src.models.database import engine as _engine, get_scoped_session
from src.utils.activity_logger import activity_logger

logger = logging.getLogger(__name__)


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


def register_callbacks(app):
    """Register simulations tab callbacks."""

    @app.callback(
        Output("sim-entity-filter", "options"),
        [Input("interval-component", "n_intervals"),
         Input("sim-date-filter", "start_date"),
         Input("sim-date-filter", "end_date")]
    )
    def update_simulation_entity_options(n, start_date, end_date):
        date_range = (start_date, end_date) if start_date or end_date else None
        return get_entity_options(_engine, date_range=date_range)

    @app.callback(
        Output("simulation-table", "children"),
        [Input("sim-entity-filter", "value"),
         Input("sim-date-filter", "start_date"),
         Input("sim-date-filter", "end_date"),
         Input("sim-horizon-filter", "value"),
         Input("sim-decision-filter", "value"),
         Input("create-sim-status", "children"),
         Input("sim-delete-status", "data")]
    )
    def update_simulation_table(entities, start_date, end_date, horizon, decision, _, __):
        date_range = (start_date, end_date) if start_date or end_date else None
        return get_simulation_table(
            _engine,
            entity_filter=entities,
            date_range=date_range,
            decision_filter=decision or "all",
            horizon_filter=horizon or "all"
        )

    @app.callback(
        Output("create-sim-entity-filter", "options"),
        [Input("interval-component", "n_intervals"),
         Input("create-sim-date-range", "start_date"),
         Input("create-sim-date-range", "end_date")]
    )
    def update_create_simulation_entity_options(n, start_date, end_date):
        date_range = (start_date, end_date) if start_date or end_date else None
        return get_prediction_entity_options(_engine, date_range=date_range)

    @app.callback(
        [Output("create-sim-status", "children"),
         Output("sim-filter-sync-store", "data")],
        Input("btn-create-simulations", "n_clicks"),
        [State("create-sim-entity-filter", "value"),
         State("create-sim-date-range", "start_date"),
         State("create-sim-date-range", "end_date"),
         State("create-sim-horizon-filter", "value"),
         State("create-sim-limit", "value")],
        prevent_initial_call=True
    )
    def create_simulations_from_predictions(n_clicks, entities, start_date, end_date, horizon, limit):
        if not n_clicks:
            return "", dash.no_update
        try:
            from src.simulations.trading_simulator import TradingSimulationEngine
            engine_sim = TradingSimulationEngine()
            date_range = None
            if start_date and end_date:
                try:
                    start = datetime.fromisoformat(start_date) if isinstance(start_date, str) else start_date
                    end = datetime.fromisoformat(end_date) if isinstance(end_date, str) else end_date
                    if hasattr(start, "date") and not isinstance(start, datetime):
                        start = datetime.combine(start, datetime.min.time())
                    if hasattr(end, "date") and not isinstance(end, datetime):
                        end = datetime.combine(end, datetime.max.time())
                    date_range = (start, end)
                except Exception as e:
                    logger.warning("Error parsing date range: %s", e)
            stats = engine_sim.create_simulations_from_predictions(
                entity_filter=entities if entities and len(entities) > 0 else None,
                horizon_filter=horizon if horizon != "all" else None,
                date_range=date_range,
                limit=limit or 50
            )
            filter_sync_data = {
                "entities": entities if entities and len(entities) > 0 else None,
                "horizon": horizon if horizon != "all" else None,
                "timestamp": datetime.utcnow().isoformat()
            }
            return dbc.Alert(
                f"Created {stats['created']} simulations, updated {stats['updated']}, skipped {stats['skipped']}, errors {stats['errors']}",
                color="success" if stats["errors"] == 0 else "warning",
                dismissable=True,
                duration=5000
            ), filter_sync_data
        except Exception as e:
            logger.error("Error creating simulations: %s", e, exc_info=True)
            return dbc.Alert(f"Error creating simulations: {str(e)}", color="danger", dismissable=True, duration=5000), dash.no_update

    @app.callback(
        [Output("sim-entity-filter", "value"),
         Output("sim-horizon-filter", "value")],
        Input("sim-filter-sync-store", "data"),
        [State("sim-entity-filter", "value"),
         State("sim-horizon-filter", "value")],
        prevent_initial_call=True
    )
    def sync_simulation_filters(sync_data, current_entities, current_horizon):
        if not sync_data or not sync_data.get("timestamp"):
            raise PreventUpdate
        new_entities = sync_data.get("entities")
        new_horizon = sync_data.get("horizon")
        if new_entities:
            return new_entities, new_horizon if new_horizon else current_horizon
        if new_horizon:
            return current_entities, new_horizon
        raise PreventUpdate

    @app.callback(
        [Output({"type": "delete-sim", "index": ALL}, "disabled"),
         Output("sim-delete-status", "data")],
        [Input({"type": "delete-sim", "index": ALL}, "n_clicks"),
         Input("btn-confirm-clear-simulations", "n_clicks")],
        [State({"type": "delete-sim", "index": ALL}, "id")],
        prevent_initial_call=True
    )
    def delete_simulation(n_clicks, clear_all_clicks, button_ids):
        ctx = dash.callback_context
        if not ctx.triggered:
            raise PreventUpdate
        triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
        if triggered_id == "btn-confirm-clear-simulations":
            if not clear_all_clicks:
                raise PreventUpdate
            try:
                with get_scoped_session() as db:
                    count = db.query(TradingSimulation).count()
                    db.execute(delete(TradingSimulation))
                    db.commit()
                    remaining = db.query(TradingSimulation).count()
                    activity_logger.log_activity(f"Deleted all {count} simulations (remaining: {remaining})", "WARNING")
                disabled_states = [False] * (len(button_ids) if button_ids else 0)
                return disabled_states, {
                    "action": "clear_all",
                    "count": count,
                    "remaining": remaining,
                    "deleted": True,
                    "ts": datetime.utcnow().isoformat()
                }
            except Exception as e:
                logger.error("Error clearing all simulations: %s", e)
                activity_logger.log_activity(f"Error clearing all simulations: {e}", "ERROR")
                disabled_states = [False] * (len(button_ids) if button_ids else 0)
                return disabled_states, {
                    "action": "clear_all",
                    "error": str(e),
                    "deleted": False,
                    "ts": datetime.utcnow().isoformat()
                }
        if not n_clicks or not any(n_clicks):
            raise PreventUpdate
        try:
            button_id = json.loads(triggered_id)
        except Exception:
            return dash.no_update, dash.no_update
        if not button_ids:
            return dash.no_update, dash.no_update
        target_index = None
        for i, item in enumerate(button_ids):
            if item == button_id:
                target_index = i
                break
        if target_index is None:
            return dash.no_update, dash.no_update
        try:
            from src.simulations.trading_simulator import TradingSimulationEngine
            simulation_id = button_id["index"]
            engine_sim = TradingSimulationEngine()
            success = engine_sim.delete_simulation(simulation_id)
            if success:
                disabled_states = [False] * len(button_ids)
                disabled_states[target_index] = True
                return disabled_states, {"simulation_id": simulation_id, "deleted": True, "ts": datetime.utcnow().isoformat()}
            return [False] * len(button_ids), dash.no_update
        except Exception as e:
            logger.error("Error deleting simulation: %s", e)
            return [False] * len(button_ids), dash.no_update

    @app.callback(
        Output({"type": "refresh-sim", "index": MATCH}, "disabled"),
        Input({"type": "refresh-sim", "index": MATCH}, "n_clicks"),
        State({"type": "refresh-sim", "index": MATCH}, "id"),
        prevent_initial_call=True
    )
    def refresh_simulation(n_clicks, button_id):
        if not n_clicks:
            return False
        try:
            from src.simulations.trading_simulator import TradingSimulationEngine
            simulation_id = button_id["index"]
            engine_sim = TradingSimulationEngine()
            engine_sim.refresh_simulation(simulation_id)
        except Exception as e:
            logger.error("Error refreshing simulation: %s", e)
        return False

    @app.callback(
        Output("modal-clear-all-simulations", "is_open"),
        [Input("btn-clear-all-simulations", "n_clicks"),
         Input("btn-cancel-clear-simulations", "n_clicks"),
         Input("btn-confirm-clear-simulations", "n_clicks")],
        State("modal-clear-all-simulations", "is_open"),
        prevent_initial_call=True
    )
    def toggle_clear_all_simulations_modal(open_clicks, cancel_clicks, confirm_clicks, is_open):
        ctx = dash.callback_context
        if not ctx.triggered:
            raise PreventUpdate
        button_id = ctx.triggered[0]["prop_id"].split(".")[0]
        if button_id == "btn-clear-all-simulations":
            return True
        if button_id in ("btn-cancel-clear-simulations", "btn-confirm-clear-simulations"):
            return False
        return is_open
