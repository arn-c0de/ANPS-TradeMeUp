"""
Statistics Tab - Callbacks
All Dash callbacks for statistics tab
"""

import json
import logging
from datetime import datetime, timedelta

import dash
import plotly.graph_objects as go
from dash import ALL, Input, Output, State, html
from dash.exceptions import PreventUpdate
from sqlalchemy.orm import Session

from src.models.database import engine as _engine
from src.models.predictions import Prediction
from src.gui.utils.callbacks import safe_callback

from .data import (
    get_statistics_metrics,
    get_event_distribution_chart,
    get_quality_distribution_chart,
    get_sentiment_distribution_chart,
    get_impact_distribution_chart,
    get_top_entities_list,
    get_entity_sentiment_chart,
    get_top_positive_entities,
    get_top_negative_entities,
    get_entity_details_table,
    get_news_volume_chart,
    get_entity_full_details,
    get_index_trends,
    get_stock_predictions_detail,
)
from .utils import _resolve_stats_date_range

logger = logging.getLogger(__name__)


def register_callbacks(app):
    """Register statistics tab callbacks."""

    @app.callback(
        Output("statistics-metrics", "children"),
        [Input("interval-component", "n_intervals"),
         Input("stats-date-range", "start_date"),
         Input("stats-date-range", "end_date"),
         Input("stats-granularity", "value"),
         Input("active-filter-store", "data")]
    )
    @safe_callback(default_return=html.Div("Unable to load statistics", className="text-warning p-3"))
    def update_statistics_metrics(n, start_date, end_date, granularity, active_filter):
        date_range = _resolve_stats_date_range(start_date, end_date, active_filter)
        return get_statistics_metrics(_engine, date_range=date_range, granularity=granularity)

    @app.callback(
        [Output("stats-date-range", "start_date"),
         Output("stats-date-range", "end_date"),
         Output("active-filter-store", "data")],
        [Input("quick-1h", "n_clicks"),
         Input("quick-12h", "n_clicks"),
         Input("quick-24h", "n_clicks"),
         Input("quick-7d", "n_clicks"),
         Input("quick-30d", "n_clicks"),
         Input("quick-90d", "n_clicks"),
         Input("quick-1y", "n_clicks"),
         Input("quick-all", "n_clicks"),
         Input("custom-hours-input", "value"),
         Input("stats-reset-filter", "n_clicks")],
        prevent_initial_call=True
    )
    def update_stats_date_range(btn_1h, btn_12h, btn_24h, btn_7d, btn_30d, btn_90d, btn_1y, btn_all, custom_hours, btn_reset):
        from dash import callback_context
        if not callback_context.triggered:
            raise PreventUpdate
        trigger_id = callback_context.triggered[0]["prop_id"].split(".")[0]
        now = datetime.now().date()
        now_dt = datetime.now()
        if trigger_id == "quick-1h":
            return (now_dt - timedelta(hours=1)).date(), now, "1h"
        elif trigger_id == "quick-12h":
            return (now_dt - timedelta(hours=12)).date(), now, "12h"
        elif trigger_id == "quick-24h":
            return (now - timedelta(days=1)), now, "24h"
        elif trigger_id == "quick-7d":
            return (now - timedelta(days=7)), now, "7d"
        elif trigger_id == "quick-30d":
            return (now - timedelta(days=30)), now, "30d"
        elif trigger_id == "quick-90d":
            return (now - timedelta(days=90)), now, "90d"
        elif trigger_id == "quick-1y":
            return (now - timedelta(days=365)), now, "1y"
        elif trigger_id == "custom-hours-input" and custom_hours:
            try:
                h = int(custom_hours)
                if 0 < h <= 8760:
                    return (now_dt - timedelta(hours=h)).date(), now, f"custom-{h}h"
            except Exception:
                pass
        elif trigger_id in ("quick-all", "stats-reset-filter"):
            return None, None, "all"
        raise PreventUpdate

    @app.callback(
        [Output("quick-1h", "outline"),
         Output("quick-12h", "outline"),
         Output("quick-24h", "outline"),
         Output("quick-7d", "outline"),
         Output("quick-30d", "outline"),
         Output("quick-90d", "outline"),
         Output("quick-1y", "outline"),
         Output("quick-all", "outline")],
        Input("active-filter-store", "data")
    )
    def update_button_styles(active_filter):
        styles = [True, True, True, True, True, True, True, True]
        if active_filter == "1h":
            styles[0] = False
        elif active_filter == "12h":
            styles[1] = False
        elif active_filter == "24h":
            styles[2] = False
        elif active_filter == "7d":
            styles[3] = False
        elif active_filter == "30d":
            styles[4] = False
        elif active_filter == "90d":
            styles[5] = False
        elif active_filter == "1y":
            styles[6] = False
        elif active_filter == "all":
            styles[7] = False
        return styles

    @app.callback(
        [Output("event-distribution-chart", "figure"),
         Output("quality-distribution-chart", "figure")],
        [Input("interval-component", "n_intervals"),
         Input("stats-date-range", "start_date"),
         Input("stats-date-range", "end_date"),
         Input("active-filter-store", "data")]
    )
    @safe_callback(default_return=(go.Figure(), go.Figure()))
    def update_statistics_charts(n, start_date, end_date, active_filter):
        date_range = _resolve_stats_date_range(start_date, end_date, active_filter)
        return (
            get_event_distribution_chart(_engine, date_range=date_range),
            get_quality_distribution_chart(_engine, date_range=date_range),
        )

    @app.callback(
        Output("sentiment-distribution-chart", "figure"),
        [Input("interval-component", "n_intervals"),
         Input("stats-date-range", "start_date"),
         Input("stats-date-range", "end_date"),
         Input("active-filter-store", "data")]
    )
    def update_sentiment_chart(n, start_date, end_date, active_filter):
        date_range = _resolve_stats_date_range(start_date, end_date, active_filter)
        return get_sentiment_distribution_chart(_engine, date_range=date_range)

    @app.callback(
        Output("impact-distribution-chart", "figure"),
        [Input("interval-component", "n_intervals"),
         Input("stats-date-range", "start_date"),
         Input("stats-date-range", "end_date"),
         Input("active-filter-store", "data")]
    )
    def update_impact_chart(n, start_date, end_date, active_filter):
        date_range = _resolve_stats_date_range(start_date, end_date, active_filter)
        return get_impact_distribution_chart(_engine, date_range=date_range)

    @app.callback(
        Output("top-entities-list", "children"),
        [Input("interval-component", "n_intervals"),
         Input("stats-date-range", "start_date"),
         Input("stats-date-range", "end_date"),
         Input("active-filter-store", "data")]
    )
    def update_top_entities(n, start_date, end_date, active_filter):
        date_range = _resolve_stats_date_range(start_date, end_date, active_filter)
        return get_top_entities_list(_engine, date_range=date_range)

    @app.callback(
        Output("news-volume-chart", "figure"),
        [Input("interval-component", "n_intervals"),
         Input("stats-date-range", "start_date"),
         Input("stats-date-range", "end_date"),
         Input("active-filter-store", "data")]
    )
    def update_news_volume(n, start_date, end_date, active_filter):
        date_range = _resolve_stats_date_range(start_date, end_date, active_filter)
        return get_news_volume_chart(_engine, date_range=date_range)

    @app.callback(
        Output("entity-sentiment-chart", "figure"),
        [Input("interval-component", "n_intervals"),
         Input("stats-date-range", "start_date"),
         Input("stats-date-range", "end_date"),
         Input("active-filter-store", "data"),
         Input("sentiment-timeframe-selector", "value")]
    )
    def update_entity_sentiment_chart(n, start_date, end_date, active_filter, timeframe):
        date_range = _resolve_stats_date_range(start_date, end_date, active_filter)
        return get_entity_sentiment_chart(_engine, date_range=date_range, timeframe=timeframe)

    @app.callback(
        [Output("top-positive-entities", "children"),
         Output("positive-entities-limit", "data")],
        [Input("interval-component", "n_intervals"),
         Input("stats-date-range", "start_date"),
         Input("stats-date-range", "end_date"),
         Input("active-filter-store", "data"),
         Input("positive-entity-search-input", "value"),
         Input("positive-entities-scroll-trigger", "value")],
        [State("positive-entities-limit", "data")]
    )
    def update_top_positive_entities(n, start_date, end_date, active_filter, search_term, scroll_trigger_value, current_limit):
        from dash import callback_context
        current_limit = current_limit or 50
        if callback_context.triggered:
            trigger_id = callback_context.triggered[0]["prop_id"]
            if "scroll-trigger" in trigger_id and scroll_trigger_value:
                try:
                    scroll_count = int(scroll_trigger_value) if scroll_trigger_value else 0
                    if scroll_count > (current_limit // 50):
                        current_limit = current_limit + 50
                except Exception:
                    pass
            if "search-input" in trigger_id or "date-range" in trigger_id or "active-filter" in trigger_id:
                current_limit = 50
        date_range = _resolve_stats_date_range(start_date, end_date, active_filter)
        result = get_top_positive_entities(_engine, search_term or "", show_all=True, date_range=date_range, limit=current_limit)
        if isinstance(result, tuple):
            entities, _ = result
        else:
            entities = result
        return entities, current_limit

    @app.callback(
        [Output("top-negative-entities", "children"),
         Output("negative-entities-limit", "data")],
        [Input("interval-component", "n_intervals"),
         Input("stats-date-range", "start_date"),
         Input("stats-date-range", "end_date"),
         Input("active-filter-store", "data"),
         Input("negative-entity-search-input", "value"),
         Input("negative-entities-scroll-trigger", "value")],
        [State("negative-entities-limit", "data")]
    )
    def update_top_negative_entities(n, start_date, end_date, active_filter, search_term, scroll_trigger_value, current_limit):
        from dash import callback_context
        current_limit = current_limit or 50
        if callback_context.triggered:
            trigger_id = callback_context.triggered[0]["prop_id"]
            if "scroll-trigger" in trigger_id and scroll_trigger_value:
                try:
                    scroll_count = int(scroll_trigger_value) if scroll_trigger_value else 0
                    if scroll_count > (current_limit // 50):
                        current_limit = current_limit + 50
                except Exception:
                    pass
            if "search-input" in trigger_id or "date-range" in trigger_id or "active-filter" in trigger_id:
                current_limit = 50
        date_range = _resolve_stats_date_range(start_date, end_date, active_filter)
        result = get_top_negative_entities(_engine, search_term or "", show_all=True, date_range=date_range, limit=current_limit)
        if isinstance(result, tuple):
            entities, _ = result
        else:
            entities = result
        return entities, current_limit

    @app.callback(
        [Output("entity-details-table", "children"),
         Output("entity-table-sort-store", "data")],
        [Input("interval-component", "n_intervals"),
         Input("stats-date-range", "start_date"),
         Input("stats-date-range", "end_date"),
         Input("active-filter-store", "data"),
         Input("entity-search-input", "value"),
         Input({"type": "sort-column-btn", "column": ALL}, "n_clicks")],
        [State("entity-table-sort-store", "data"),
         State({"type": "sort-column-btn", "column": ALL}, "id")],
        prevent_initial_call=False
    )
    def update_entity_details_table(n, start_date, end_date, active_filter, search_term, sort_clicks, sort_state, button_ids):
        from dash import callback_context
        if sort_state is None:
            sort_state = {"column": None, "direction": None}
        current_column = sort_state.get("column")
        current_direction = sort_state.get("direction")
        if callback_context.triggered:
            trigger_id = callback_context.triggered[0]["prop_id"]
            if "sort-column-btn" in trigger_id and sort_clicks and any(c for c in sort_clicks if c):
                for i, clicks in enumerate(sort_clicks):
                    if clicks and clicks > 0:
                        clicked_column = button_ids[i]["column"]
                        if current_column == clicked_column:
                            if current_direction == "asc":
                                current_direction = "desc"
                            elif current_direction == "desc":
                                current_column = None
                                current_direction = None
                            else:
                                current_direction = "asc"
                        else:
                            current_column = clicked_column
                            current_direction = "asc"
                        break
        date_range = _resolve_stats_date_range(start_date, end_date, active_filter)
        table = get_entity_details_table(
            _engine, search_term or "", current_column, current_direction, date_range=date_range
        )
        return table, {"column": current_column, "direction": current_direction}

    @app.callback(
        [Output("entity-details-modal", "is_open"),
         Output("selected-entity-store", "data")],
        [Input({"type": "entity-detail-btn", "index": ALL}, "n_clicks"),
         Input("close-entity-modal", "n_clicks")],
        [State("entity-details-modal", "is_open"),
         State({"type": "entity-detail-btn", "index": ALL}, "id")],
        prevent_initial_call=True
    )
    def toggle_entity_modal(detail_clicks, close_click, is_open, button_ids):
        from dash import callback_context
        if not callback_context.triggered:
            return dash.no_update, dash.no_update
        trigger_id = callback_context.triggered[0]["prop_id"]
        if "close-entity-modal" in trigger_id:
            return False, None
        if "entity-detail-btn" in trigger_id and detail_clicks and any(c for c in detail_clicks if c):
            for i, click_count in enumerate(detail_clicks):
                if click_count and click_count > 0:
                    return True, {"entity_name": button_ids[i]["index"]}
        return dash.no_update, dash.no_update

    @app.callback(
        [Output("entity-modal-title", "children"),
         Output("entity-modal-body", "children")],
        Input("selected-entity-store", "data"),
        State("entity-details-modal", "is_open"),
        prevent_initial_call=True
    )
    def update_entity_modal_content(entity_data, is_open):
        if not is_open or not entity_data or "entity_name" not in entity_data:
            return dash.no_update, dash.no_update
        title, body = get_entity_full_details(_engine, entity_data["entity_name"])
        return title, body

    @app.callback(
        Output("index-trends-display", "children"),
        Input("interval-component", "n_intervals")
    )
    def update_index_trends(n_intervals):
        return get_index_trends(_engine)

    @app.callback(
        [Output("stock-predictions-modal", "is_open"),
         Output("stock-modal-title", "children"),
         Output("stock-modal-body", "children")],
        [Input({"type": "stock-pred-btn", "index": ALL}, "n_clicks"),
         Input("close-stock-modal", "n_clicks")],
        [State({"type": "stock-pred-btn", "index": ALL}, "id"),
         State("stock-predictions-modal", "is_open")],
        prevent_initial_call=True
    )
    def toggle_stock_predictions_modal(stock_clicks, close_click, button_ids, is_open):
        from dash import callback_context
        if not callback_context.triggered:
            return dash.no_update, dash.no_update, dash.no_update
        trigger_id = callback_context.triggered[0]["prop_id"]
        if "close-stock-modal" in trigger_id:
            return False, dash.no_update, dash.no_update
        if "stock-pred-btn" in trigger_id and stock_clicks and any(c for c in stock_clicks if c):
            triggered_id = callback_context.triggered[0]["prop_id"].split(".")[0]
            button_id = json.loads(triggered_id)
            stock_symbol = button_id["index"]
            title, body = get_stock_predictions_detail(_engine, stock_symbol)
            return True, title, body
        return dash.no_update, dash.no_update, dash.no_update

    @app.callback(
        [Output("prediction-modal", "is_open", allow_duplicate=True),
         Output("prediction-detail-cache", "data", allow_duplicate=True),
         Output("current-prediction-id", "data", allow_duplicate=True),
         Output("entity-details-modal", "is_open", allow_duplicate=True),
         Output("no-prediction-toast", "is_open", allow_duplicate=True)],
        Input({"type": "news-pred-detail-btn", "index": ALL}, "n_clicks"),
        [State({"type": "news-pred-detail-btn", "index": ALL}, "id"),
         State("prediction-modal", "is_open"),
         State("entity-details-modal", "is_open")],
        prevent_initial_call=True
    )
    def open_news_prediction_detail(n_clicks_list, button_ids, pred_modal_open, entity_modal_open):
        if not n_clicks_list or not any(n_clicks_list):
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
        ctx = dash.callback_context
        if not ctx.triggered:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
        triggered_id = ctx.triggered[0]["prop_id"].split(".")[0]
        button_id = json.loads(triggered_id)
        news_id = button_id["index"]
        try:
            with Session(_engine) as db:
                predictions = db.query(Prediction).all()
                matching_prediction = None
                for pred in predictions:
                    if hasattr(pred, "related_news_ids") and pred.related_news_ids:
                        try:
                            news_ids = pred.related_news_ids if isinstance(pred.related_news_ids, list) else []
                            news_ids_str = [str(nid) for nid in news_ids]
                            if str(news_id) in news_ids_str:
                                matching_prediction = pred
                                break
                        except (TypeError, ValueError):
                            continue
                if not matching_prediction:
                    return dash.no_update, dash.no_update, dash.no_update, dash.no_update, True
                prediction_id = str(matching_prediction.prediction_id)
                return True, {"prediction_id": prediction_id, "load_performance": True}, prediction_id, False, False
        except Exception as e:
            logger.error("Error loading prediction for news_id %s: %s", news_id, e, exc_info=True)
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
