"""Chart tab callbacks: chart display rendering."""

import logging
import time

import dash
import dash_bootstrap_components as dbc
import pandas as pd
from dash import Input, Output, State, callback_context, html

from src.gui.tabs.charts.chart_data_manager import get_chart_data_manager
from src.gui.tabs.charts.components import (
    create_trading_overlay,
    get_stock_chart_components,
)
from src.gui.tabs.charts.fullscreen_manager import get_fullscreen_state

# The shared provider singleton, not a per-module instance.

logger = logging.getLogger(__name__)


def _get_loaded_data_with_offset(tab: dict, tab_loaded: dict,
                                 view_state: dict | None) -> pd.DataFrame | None:
    """Fetch cached infinite-scroll data for a tab and shift the saved view range if needed.

    If new data was recently prepended (fresh index_offset), the saved x-axis
    range in view_state is shifted right in place so the visible window stays put.
    """
    data_manager = get_chart_data_manager()
    cache_start = time.time()
    loaded_data = data_manager.get_cached_data(tab['symbol'], tab['timeframe'])
    cache_time = time.time() - cache_start
    if cache_time > 0.1:  # Log if cache access takes more than 100ms
        logger.debug(f"[Performance] Cache access took {cache_time:.2f}s for {tab['symbol']} ({tab['timeframe']})")

    index_offset = tab_loaded.get('index_offset', 0)
    offset_timestamp = tab_loaded.get('offset_timestamp', 0)

    # Apply offset to view_state range only if it is fresh (set within the last
    # 2 seconds) to avoid applying it multiple times
    if index_offset > 0 and view_state and 'xaxis_range' in view_state:
        time_since_offset = time.time() - offset_timestamp
        if time_since_offset < 2.0:
            old_range = view_state['xaxis_range']
            try:
                # For category-type x-axis, range is in index form (numeric):
                # shift range right by the number of prepended points
                new_range = [old_range[0] + index_offset, old_range[1] + index_offset]
                view_state['xaxis_range'] = new_range
                logger.info(f"[Infinite Scroll] Adjusted view range by offset {index_offset}: {old_range} -> {new_range}")
            except (TypeError, ValueError, IndexError) as e:
                logger.warning(f"[Infinite Scroll] Could not adjust range: {e}")
        else:
            logger.debug(f"[Infinite Scroll] Offset too old ({time_since_offset:.2f}s), skipping adjustment")

    return loaded_data


def _select_quad_tabs(tabs: list, selected_tab_ids: list, max_panels: int) -> list:
    """Pick up to max_panels distinct tabs for quad view: selected tabs first, then remaining tabs."""
    tabs_by_id = {tab['id']: tab for tab in tabs}
    quad_tabs: list = []
    seen_tabs: set = set()

    def add_tab(tab):
        if not tab:
            return
        tab_id = tab.get('id')
        if tab_id and tab_id not in seen_tabs:
            quad_tabs.append(tab)
            seen_tabs.add(tab_id)

    for tab_id in selected_tab_ids:
        add_tab(tabs_by_id.get(tab_id))
        if len(quad_tabs) >= max_panels:
            break

    if len(quad_tabs) < max_panels:
        for tab in tabs:
            add_tab(tab)
            if len(quad_tabs) >= max_panels:
                break

    return quad_tabs


def _arrange_quad_layout(panel_wrappers: list, left_width: int, right_width: int,
                         row_class: str, margin_class: str) -> html.Div:
    """Arrange 1-4 panel wrappers into the quad-view grid."""
    count = len(panel_wrappers)
    if count == 1:
        return html.Div([
            dbc.Row([dbc.Col(panel_wrappers[0], md=12)], className=row_class)
        ])

    rows = [
        dbc.Row([
            dbc.Col(panel_wrappers[0], md=left_width, className=margin_class),
            dbc.Col(panel_wrappers[1], md=right_width, className=margin_class)
        ], className=row_class)
    ]
    if count == 3:
        rows.append(dbc.Row([dbc.Col(panel_wrappers[2], md=12)], className=row_class))
    elif count >= 4:
        rows.append(dbc.Row([
            dbc.Col(panel_wrappers[2], md=left_width, className=margin_class),
            dbc.Col(panel_wrappers[3], md=right_width, className=margin_class)
        ], className=row_class))

    return html.Div(rows)


def register_render_callbacks(app):
    """Main chart display rendering (single and quad mode)."""

    @app.callback(
        Output("chart-display-area", "children"),
        [Input("chart-tabs-store", "data"),
         Input("quad-mode-store", "data"),
         Input("chart-overlays-store", "data"),
         Input("chart-options-checklist", "value"),
         Input("chart-fullscreen-state", "data"),  # Keep for height calculation
         Input("layout-preset-dropdown", "value"),
         Input("refresh-all-panels", "n_clicks"),
         Input("chart-update-interval", "n_intervals"),
         Input("chart-interaction-modes", "data"),
         Input("chart-view-state", "data"),
         Input("chart-loaded-data-store", "data"),
         Input("tabs", "active_tab")],  # Check if Charts tab is active
        [State("chart-display-area", "children")],  # Track previous render for optimization
        prevent_initial_call='initial_duplicate'
    )
    def render_chart_display(tabs_data, quad_data, overlays_data, chart_options, fullscreen_data, layout_preset, refresh_clicks, n_intervals, interaction_modes, view_state_data, loaded_data_store, active_main_tab, previous_children):
        """
        Render chart display area - OPTIMIZED to only render active tab.
        This significantly improves tab switching performance.
        Only executes when Charts tab is active to prevent unnecessary heavy operations.
        Uses State to track previous render and optimize re-rendering logic.
        """
        start_time = time.time()

        # Early return if Charts tab is not active
        if active_main_tab != "charts":
            return dash.no_update

        tabs = tabs_data.get('tabs', [])
        active_tab_id = tabs_data.get('active_tab')

        # Find active tab early for optimization checks
        active_tab = None
        if active_tab_id:
            for tab in tabs:
                if tab['id'] == active_tab_id:
                    active_tab = tab
                    break

        # Ensure quad_data is properly initialized and preserve quad_enabled state
        if quad_data is None:
            quad_data = {'enabled': False, 'selected_tabs': []}
        quad_enabled = quad_data.get('enabled', False)
        is_fullscreen = get_fullscreen_state(fullscreen_data)

        show_volume = 'volume' in (chart_options or [])
        show_ma = 'ma' in (chart_options or [])
        show_overlay = 'stats' in (chart_options or [])

        if not tabs:
            return dbc.Alert("No charts open. Click '+ New' to add a chart.", color="info", className="mt-3")

        # Log tab switches for performance monitoring
        if callback_context.triggered:
            trigger_id = callback_context.triggered[0]["prop_id"]
            if trigger_id == "chart-tabs-store.data" and active_tab:
                logger.debug(f"[Performance] Chart tab switch to {active_tab.get('symbol', 'unknown')} ({active_tab.get('timeframe', 'unknown')})")

        def build_tab_panel(tab, panel_height, is_active, clickable=True):
            tab_show_volume = tab.get('show_volume', show_volume)
            tab_show_ma = tab.get('show_ma', show_ma)
            tab_overlays = (overlays_data or {}).get('tabs', {}).get(tab['id'], {}) if show_overlay else {}

            # Get interaction mode for this tab (default: zoom, auto_scroll for 1min/5min charts)
            tab_modes = (interaction_modes or {}).get('tabs', {}).get(tab['id'], {})
            dragmode = tab_modes.get('dragmode', 'zoom')
            auto_scroll = tab_modes.get('auto_scroll', tab.get('timeframe') in ['1d_1m', '5d_5m'])

            # Get saved view state (zoom/pan position) for this tab
            view_state = None
            if view_state_data and view_state_data.get('tabs'):
                view_state = view_state_data.get('tabs', {}).get(tab['id'])

            # Get loaded data from cache (for infinite scroll)
            loaded_data = None
            if loaded_data_store and loaded_data_store.get('tabs'):
                tab_loaded = loaded_data_store.get('tabs', {}).get(tab['id'])
                if tab_loaded:
                    loaded_data = _get_loaded_data_with_offset(tab, tab_loaded, view_state)

            # Performance logging for chart component creation
            component_start = time.time()
            chart_component, stats_data = get_stock_chart_components(
                tab['symbol'],
                tab['timeframe'],
                tab['chart_type'],
                show_volume=tab_show_volume,
                show_ma=tab_show_ma,
                overlays=tab_overlays,
                graph_id={"type": "chart-graph", "index": tab['id']},
                dragmode=dragmode,
                auto_scroll=auto_scroll,
                view_state=view_state,
                loaded_data=loaded_data  # Pass loaded data for infinite scroll (uses cache)
            )
            component_time = time.time() - component_start
            if component_time > 1.0:
                logger.warning(f"[Performance] get_stock_chart_components took {component_time:.2f}s for {tab['symbol']} ({tab['timeframe']})")
            elif component_time > 0.5:
                logger.debug(f"[Performance] get_stock_chart_components took {component_time:.2f}s for {tab['symbol']} ({tab['timeframe']})")

            chart_div = html.Div(
                [chart_component],
                style={'height': '100%', 'display': 'flex', 'flexDirection': 'column'}
            )
            trading_overlay = create_trading_overlay(stats_data, show_overlay, panel_id=tab['id']) if show_overlay else None

            panel_content = html.Div(
                ([trading_overlay] if trading_overlay else []) + [chart_div],
                style={'position': 'relative', 'height': '100%'}
            )

            panel_style = {
                'height': panel_height,
                'overflow': 'hidden'
            }

            if clickable:
                panel_style.update({
                    'minHeight': '260px',
                    'border': '2px solid rgba(255,255,255,0.1)',
                    'borderRadius': '6px',
                    'cursor': 'pointer'
                })
                panel_class = "quad-panel-hover"
                if is_active:
                    panel_class = f"{panel_class} panel-focused"

                return html.Div(
                    panel_content,
                    id={"type": "quad-panel", "index": tab['id']},
                    className=panel_class,
                    style=panel_style
                )

            return html.Div(panel_content, style=panel_style)

        if quad_enabled:
            selected_tabs = (quad_data or {}).get('selected_tabs', []) or []
            max_panels = min(4, len(tabs))
            if max_panels == 0:
                return dbc.Alert("No charts available for quad view.", color="info", className="mt-3")

            quad_tabs = _select_quad_tabs(tabs, selected_tabs, max_panels)

            panel_height = 'calc(50vh - 80px)' if is_fullscreen else '500px'
            row_class = "g-1" if is_fullscreen else "g-2"
            margin_class = "mb-1" if is_fullscreen else "mb-3"

            left_width, right_width = (6, 6)
            if layout_preset == 'left-focus':
                left_width, right_width = (8, 4)
            elif layout_preset == 'right-focus':
                left_width, right_width = (4, 8)

            panel_wrappers = [
                build_tab_panel(tab, panel_height, tab['id'] == active_tab_id)
                for tab in quad_tabs
            ]

            return _arrange_quad_layout(panel_wrappers, left_width, right_width, row_class, margin_class)

        # PERFORMANCE OPTIMIZATION: Only render the active tab
        # This avoids expensive API calls and chart rendering for hidden tabs
        # (active_tab was already found above for optimization checks)

        # In single mode, if active tab not found, fallback to first tab for rendering
        # But don't update the store here - let a separate callback handle that
        # IMPORTANT: Only fallback if active_tab_id is None or empty, not if it's just not found
        # This prevents resetting the tab when it's being switched (race condition)
        if not active_tab and tabs and (not active_tab_id or active_tab_id == ''):
            active_tab = tabs[0]

        if not active_tab:
            return dbc.Alert("No active chart.", color="info", className="mt-3")

        # Only render the single active tab (in single mode)
        height = 'calc(100vh - 180px)' if is_fullscreen else 'calc(100vh - 320px)'
        final_style = {'display': 'block', 'height': height, 'minHeight': '600px'}

        # Log performance metrics
        render_start = time.time()
        panel_content = build_tab_panel(active_tab, "100%", True, clickable=False)
        render_time = time.time() - render_start

        if render_time > 0.5:
            logger.warning(f"[Performance] Chart rendering took {render_time:.2f}s for {active_tab.get('symbol', 'unknown')} ({active_tab.get('timeframe', 'unknown')})")
        else:
            logger.debug(f"[Performance] Chart rendering took {render_time:.2f}s for {active_tab.get('symbol', 'unknown')} ({active_tab.get('timeframe', 'unknown')})")

        total_time = time.time() - start_time
        if total_time > 1.0:
            logger.warning(f"[Performance] render_chart_display total time: {total_time:.2f}s")

        return html.Div(panel_content, style=final_style)
