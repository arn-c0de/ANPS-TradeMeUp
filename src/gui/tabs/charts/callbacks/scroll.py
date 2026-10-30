"""Chart tab callbacks: view state persistence + infinite scroll."""

import copy
import logging
import time
from typing import Any

import dash
import pandas as pd
from dash import ALL, Input, Output, State

from src.gui.tabs.charts.chart_data_manager import ChartDataManager, get_chart_data_manager
from src.gui.tabs.charts.chart_utils import find_index_binary

# The shared provider singleton, not a per-module instance.
from ._shared import _get_triggered_relayout, _isoformat_or_str

logger = logging.getLogger(__name__)


def _parse_visible_range(relayout_data: dict) -> list | None:
    """Extract the visible [left, right] x-axis range from relayout data, or None."""
    if 'xaxis.range' in relayout_data:
        visible_range = relayout_data['xaxis.range']
    elif 'xaxis.range[0]' in relayout_data and 'xaxis.range[1]' in relayout_data:
        visible_range = [relayout_data['xaxis.range[0]'], relayout_data['xaxis.range[1]']]
    else:
        return None

    if not visible_range or not isinstance(visible_range, list) or len(visible_range) != 2:
        return None
    return visible_range


def _to_axis_value(value: Any) -> Any | None:
    """Convert a Plotly axis bound to a comparable value.

    Numbers (category-type x-axis indices) pass through unchanged; ISO strings
    (date-type x-axis) are parsed to datetimes. Returns None if unparseable.
    """
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return pd.to_datetime(value)
        except (ValueError, TypeError):
            logger.debug(f"[Infinite Scroll] Could not parse axis value: {value}")
            return None
    return value


def _resolve_visible_indices(indices: list, left_value: Any, right_value: Any,
                             total_points: int) -> tuple[int, int]:
    """Map visible range bounds to (left_index, right_index) within the loaded data."""
    # With type='category' x-axis, Plotly sends numeric indices (0, 1, 2...) not timestamps
    if isinstance(left_value, (int, float)) and isinstance(right_value, (int, float)):
        left_index = int(round(left_value))
        right_index = int(round(right_value))
        logger.debug(f"[Infinite Scroll] Using numeric indices: left={left_index}, right={right_index}")
    else:
        # Timestamp values - use binary search (legacy behavior)
        left_index = find_index_binary(indices, left_value)
        right_index = find_index_binary(indices, right_value)
        logger.debug("[Infinite Scroll] Using binary search for timestamps")

    # Clamp indices into valid bounds
    if left_index < 0 or left_index >= total_points:
        left_index = 0
    if right_index < 0 or right_index >= total_points:
        right_index = total_points - 1
    if right_index < left_index:
        right_index = left_index
    return left_index, right_index


def _load_adjacent_data(data_manager: ChartDataManager, symbol: str, timeframe: str,
                        cached_df: pd.DataFrame, should_load_left: bool,
                        should_load_right: bool) -> tuple[pd.DataFrame, bool, int]:
    """Load historical (left) and/or future (right) data around the cached range.

    Returns (combined_df, data_loaded, index_offset) where index_offset is the
    number of points prepended at the beginning (shifts existing indices right).
    """
    combined_df = cached_df.copy()
    data_loaded = False
    index_offset = 0

    if should_load_left:
        earliest_date = cached_df.index[0]
        new_historical_df = data_manager.load_more_historical(symbol, timeframe, earliest_date)

        if new_historical_df is not None and not new_historical_df.empty:
            old_len = len(combined_df)
            combined_df = data_manager.prepend_data(combined_df, new_historical_df)
            index_offset = len(combined_df) - old_len  # How many points were added at the beginning
            data_loaded = True
            logger.info(f"[Infinite Scroll] Loaded {len(new_historical_df)} historical points for {symbol} ({timeframe}), index_offset={index_offset}")
        else:
            logger.debug(f"[Infinite Scroll] No more historical data for {symbol} ({timeframe})")

    if should_load_right:
        latest_date = combined_df.index[-1]
        new_future_df = data_manager.load_more_future(symbol, timeframe, latest_date)

        if new_future_df is not None and not new_future_df.empty:
            # Append new data (no index offset needed - data added at end)
            combined_df = data_manager.append_data(combined_df, new_future_df)
            data_loaded = True
            logger.info(f"[Infinite Scroll] Loaded {len(new_future_df)} future points for {symbol} ({timeframe})")
        else:
            logger.debug(f"[Infinite Scroll] No more future data for {symbol} ({timeframe})")

    return combined_df, data_loaded, index_offset


def register_scroll_callbacks(app):
    """Chart zoom/pan persistence and infinite scroll data loading."""

    @app.callback(
        Output("chart-view-state", "data", allow_duplicate=True),
        Input({"type": "chart-graph", "index": ALL}, "relayoutData"),
        [State("chart-view-state", "data"),
         State("chart-tabs-store", "data"),
         State({"type": "chart-graph", "index": ALL}, "id")],
        prevent_initial_call=True
    )
    def save_chart_view_state(relayout_data_list, view_state_data, tabs_data, graph_ids):
        """Save chart zoom/pan state to localStorage for persistence."""
        tab_id, relayout_data = _get_triggered_relayout(relayout_data_list, graph_ids)
        if not relayout_data:
            return dash.no_update

        # Extract zoom/pan information (ignore shape-related changes)
        zoom_pan_keys = ['xaxis.range', 'yaxis.range', 'xaxis2.range', 'yaxis2.range',
                         'xaxis.autorange', 'yaxis.autorange', 'xaxis2.autorange', 'yaxis2.autorange']
        view_state = {key: relayout_data[key] for key in zoom_pan_keys if key in relayout_data}

        # Only save if we have actual zoom/pan data (not just shape movements)
        if not view_state:
            return dash.no_update

        # Update view state store
        state = copy.deepcopy(view_state_data) if view_state_data else {'tabs': {}}
        if 'tabs' not in state:
            state['tabs'] = {}

        # Convert Plotly format to our format
        saved_state = {}
        if 'xaxis.range' in view_state:
            saved_state['xaxis_range'] = view_state['xaxis.range']
        if 'yaxis.range' in view_state:
            saved_state['yaxis_range'] = view_state['yaxis.range']
        if 'yaxis2.range' in view_state:
            saved_state['yaxis2_range'] = view_state['yaxis2.range']

        state['tabs'][tab_id] = saved_state

        logger.debug(f"[Chart View] Saved view state for chart {tab_id}")
        return state

    @app.callback(
        [Output("chart-loaded-data-store", "data", allow_duplicate=True),
         Output("chart-scroll-state-store", "data", allow_duplicate=True)],
        Input({"type": "chart-graph", "index": ALL}, "relayoutData"),
        [State("chart-loaded-data-store", "data"),
         State("chart-scroll-state-store", "data"),
         State("chart-tabs-store", "data"),
         State("chart-interaction-modes", "data"),
         State({"type": "chart-graph", "index": ALL}, "id")],
        prevent_initial_call=True
    )
    def handle_infinite_scroll(relayout_data_list, loaded_data_store, scroll_state_store, tabs_data, interaction_modes, graph_ids):
        """
        Handle infinite scroll: detect when user scrolls and load more data symmetrically.

        Features:
        - Tracks visible range and centered candle
        - Symmetric loading: loads historical data (left) and future data (right)
        - Buffer zone: maintains 2x visible range for smooth scrolling
        - Position persistence: saves position to view_state to prevent jumping on refresh
        - Optimized with binary search and improved throttling
        """
        tab_id, relayout_data = _get_triggered_relayout(relayout_data_list, graph_ids)
        if not relayout_data:
            return dash.no_update, dash.no_update

        # Only process x-axis range changes (ignore other relayout events like y-axis, shapes, etc.)
        if 'xaxis.range' not in relayout_data and 'xaxis.range[0]' not in relayout_data:
            return dash.no_update, dash.no_update

        # Get chart configuration
        tabs = tabs_data.get('tabs', []) if tabs_data else []
        tab_config = next((tab for tab in tabs if tab.get('id') == tab_id), None)
        if not tab_config:
            return dash.no_update, dash.no_update

        symbol = tab_config.get('symbol')
        timeframe = tab_config.get('timeframe', '1mo')
        if not symbol:
            return dash.no_update, dash.no_update

        # Check scroll state to prevent race conditions
        scroll_state = copy.deepcopy(scroll_state_store) if scroll_state_store else {'tabs': {}}
        if 'tabs' not in scroll_state:
            scroll_state['tabs'] = {}

        tab_scroll_state = scroll_state['tabs'].get(tab_id, {})

        # Check if already loading
        if tab_scroll_state.get('loading', False):
            return dash.no_update, dash.no_update

        # Debounce: check last load time (200ms for responsive loading)
        current_time = time.time()
        last_load_time = tab_scroll_state.get('last_load_time', 0)
        if current_time - last_load_time < 0.2:
            return dash.no_update, dash.no_update

        # Get and validate visible range
        visible_range = _parse_visible_range(relayout_data)
        if not visible_range:
            return dash.no_update, dash.no_update

        logger.debug(f"[Infinite Scroll] Received range: left={visible_range[0]} (type={type(visible_range[0]).__name__}), right={visible_range[1]} (type={type(visible_range[1]).__name__})")

        left_value = _to_axis_value(visible_range[0])
        right_value = _to_axis_value(visible_range[1])
        if left_value is None or right_value is None:
            return dash.no_update, dash.no_update

        # Get loaded data metadata
        loaded_store = copy.deepcopy(loaded_data_store) if loaded_data_store else {'tabs': {}}
        if 'tabs' not in loaded_store:
            loaded_store['tabs'] = {}

        # Get cached data to check total points
        data_manager = get_chart_data_manager()
        cached_df = data_manager.get_cached_data(symbol, timeframe)
        if cached_df is None or cached_df.empty:
            # No cached data yet, initialize
            cached_df = data_manager.get_initial_data(symbol, timeframe)
            if cached_df is None or cached_df.empty:
                return dash.no_update, dash.no_update

        total_points = len(cached_df)
        if total_points == 0:
            return dash.no_update, dash.no_update

        indices = list(cached_df.index)

        try:
            left_index, right_index = _resolve_visible_indices(indices, left_value, right_value, total_points)

            # Calculate visible candle count and centered candle
            visible_candle_count = right_index - left_index + 1
            centered_index = left_index + (visible_candle_count // 2)
            centered_candle = indices[centered_index] if centered_index < len(indices) else indices[-1]

            # Calculate buffer zone (2x visible range for smooth scrolling)
            buffer_size = max(visible_candle_count * 2, 50)  # Minimum 50 candles buffer

            # Save current visible range and centered candle to scroll_state_store
            scroll_state['tabs'][tab_id] = {
                'loading': tab_scroll_state.get('loading', False),
                'last_load_time': tab_scroll_state.get('last_load_time', 0),
                'last_threshold_check': current_time,
                'xaxis_range': visible_range,
                'centered_candle': _isoformat_or_str(centered_candle),
                'visible_candle_count': visible_candle_count,
                'left_index': left_index,  # Saved for position restoration
                'right_index': right_index
            }

            # Check if we need to load more data (symmetric loading: left AND right)
            should_load_left = data_manager.should_load_more_left(left_index, total_points, buffer_size)
            should_load_right = data_manager.should_load_more_right(right_index, total_points, buffer_size)

            logger.info(f"[Infinite Scroll] Threshold check for {symbol} ({timeframe}): left_index={left_index}, right_index={right_index}, total={total_points}, buffer={buffer_size}, should_load_left={should_load_left}, should_load_right={should_load_right}")

            # If no loading needed, just save the state and return
            if not should_load_left and not should_load_right:
                return dash.no_update, scroll_state

            # Set loading flag BEFORE starting async operation
            scroll_state['tabs'][tab_id]['loading'] = True

            combined_df, data_loaded, index_offset = _load_adjacent_data(
                data_manager, symbol, timeframe, cached_df, should_load_left, should_load_right
            )

            # Only update if we actually loaded data
            if data_loaded:
                # Update cache
                data_manager.update_cached_data(symbol, timeframe, combined_df)

                # Update loaded data store (safely serialize dates)
                earliest_date_str = _isoformat_or_str(combined_df.index[0]) if len(combined_df) > 0 else None
                latest_date_str = _isoformat_or_str(combined_df.index[-1]) if len(combined_df) > 0 else None

                loaded_store['tabs'][tab_id] = {
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'earliest_date': earliest_date_str,
                    'latest_date': latest_date_str,
                    'data_points': len(combined_df),
                    'index_offset': index_offset,  # Stored for position correction
                    'offset_timestamp': time.time()  # Timestamp when offset was set
                }

                # Note: view_state is saved automatically by save_chart_view_state callback
                # which listens to the same relayoutData events
                load_direction = "left" if should_load_left else "right" if should_load_right else "both"
                logger.info(f"[Infinite Scroll] Loaded data ({load_direction}) for {symbol} ({timeframe}): {len(combined_df)} total points, index_offset={index_offset}")

            # Reset loading flag
            scroll_state['tabs'][tab_id]['loading'] = False
            scroll_state['tabs'][tab_id]['last_load_time'] = current_time

            return loaded_store, scroll_state

        except Exception as e:
            logger.error(f"[Infinite Scroll] Error handling scroll for tab {tab_id}: {e}", exc_info=True)
            # Reset the loading flag so the chart is not stuck in a loading state
            if tab_id not in scroll_state['tabs']:
                scroll_state['tabs'][tab_id] = {}
            scroll_state['tabs'][tab_id]['loading'] = False
            return dash.no_update, scroll_state
