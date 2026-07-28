"""
Charts Tab - Utility Functions
"""

from typing import Optional, Tuple

import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import html

from src.gui.tabs.charts.live_charts import create_candlestick_chart, create_line_chart


def _build_stats_card(stats_data: dict):
    """Build a compact statistics card from stats data."""
    if not stats_data:
        return None

    return dbc.Card([
        dbc.CardBody([
            dbc.Row([
                dbc.Col([
                    html.Span([stats_data['arrow'], f" {stats_data['symbol']} "], className="fw-bold me-2", style={"fontSize": "0.9rem"}),
                    html.Span(f"${stats_data['current_price']:.2f}", className=f"text-{stats_data['color']} fw-bold me-2", style={"fontSize": "0.9rem"}),
                    html.Span(
                        f"{stats_data['price_change']:+.2f} ({stats_data['price_change_pct']:+.2f}%)",
                        className=f"text-{stats_data['color']} me-3",
                        style={"fontSize": "0.75rem"}
                    ),
                ], width="auto", className="d-flex align-items-center"),
                dbc.Col([
                    html.Span(["H ", html.Strong(f"${stats_data['high']:.2f}")], className="me-2", style={"fontSize": "0.75rem"}),
                    html.Span(["L ", html.Strong(f"${stats_data['low']:.2f}")], className="me-2", style={"fontSize": "0.75rem"}),
                    html.Span(
                        ["Vol ", html.Strong(
                            f"{stats_data['volume']/1000000:.1f}M" if stats_data['volume'] > 1000000 else f"{stats_data['volume']/1000:.1f}K"
                        )],
                        style={"fontSize": "0.75rem"}
                    )
                ], width="auto", className="d-flex align-items-center")
            ], className="align-items-center justify-content-between")
        ], className="py-1 px-2")
    ], className="mb-1", style={"backgroundColor": "rgba(0,0,0,0.3)"})


def _build_overlay_shapes(overlays: dict):
    """Build plotly shapes for brackets/breaks overlays."""
    shapes = []
    if not overlays:
        return shapes

    def add_items(group: str, dash_style: str):
        items = overlays.get(group, []) or []
        for item in items:
            price = item.get('price')
            if price is None:
                continue
            try:
                price_value = float(price)
            except (TypeError, ValueError):
                continue
            color = item.get('color') or ("#00ff88" if group == "brackets" else "#ff4444")
            visible = item.get('visible', True)
            shapes.append({
                "type": "line",
                "xref": "paper",
                "x0": 0,
                "x1": 1,
                "yref": "y",
                "y0": price_value,
                "y1": price_value,
                "line": {"color": color, "width": 1.6, "dash": dash_style},
                "opacity": 0.9,
                "layer": "above",
                "visible": bool(visible)
            })

    add_items("brackets", "solid")
    add_items("breaks", "dot")
    return shapes


def _build_chart_figure(
    df: pd.DataFrame,
    symbol: str,
    chart_type: str,
    show_volume: bool,
    show_ma: bool,
    overlays: dict | None,
    dragmode: str,
    auto_scroll: bool,
    view_state: dict | None
) -> 'go.Figure':
    """
    Build Plotly figure from DataFrame.
    
    Args:
        df: DataFrame with OHLCV data
        symbol: Stock ticker symbol
        chart_type: Type of chart ('candlestick' or 'line')
        show_volume: Show volume subplot
        show_ma: Show moving averages
        overlays: Overlay shapes dict
        dragmode: Drag mode ('zoom' or 'pan')
        auto_scroll: Auto-scroll to latest data
        view_state: Saved view state dict
        
    Returns:
        Plotly Figure object
    """
    if chart_type == 'candlestick':
        fig = create_candlestick_chart(df, symbol, "", show_volume=show_volume, show_ma=show_ma)
    else:
        fig = create_line_chart(df, symbol)

    overlay_shapes = _build_overlay_shapes(overlays)
    if overlay_shapes:
        fig.update_layout(shapes=overlay_shapes)

    # Set dragmode (zoom or pan)
    # Note: 'pan' mode allows easier horizontal scrolling with mouse wheel
    fig.update_layout(dragmode=dragmode)

    # Enable horizontal scrolling: ensure x-axis is not fixed
    if show_volume:
        fig.update_xaxes(fixedrange=False, row=1)
        fig.update_xaxes(fixedrange=False, row=2)  # Volume subplot
    else:
        fig.update_xaxes(fixedrange=False)

    # Apply saved view state (zoom/pan position) if available
    # Only apply if auto_scroll is False (user wants to keep their view)
    if view_state and not auto_scroll:
        # Apply x-axis range if saved
        if 'xaxis_range' in view_state and view_state['xaxis_range']:
            fig.update_xaxes(range=view_state['xaxis_range'], row=1 if show_volume else None)

        # Apply y-axis range if saved (for price chart)
        if 'yaxis_range' in view_state and view_state['yaxis_range']:
            fig.update_yaxes(range=view_state['yaxis_range'], row=1 if show_volume else None)

        # Apply y-axis2 range if saved (for volume chart)
        if show_volume and 'yaxis2_range' in view_state and view_state['yaxis2_range']:
            fig.update_yaxes(range=view_state['yaxis2_range'], row=2)

    # Auto-scroll: Set x-axis range to show latest candles, with newest candle visible on the right
    elif auto_scroll and len(df) > 0:
        # Show last 50-100 candles (adjust based on data density)
        visible_candles = min(80, len(df))
        start_idx = max(0, len(df) - visible_candles)

        # For category type axes, we need to use the index positions
        # Since we're using category type, we'll set the range using index values
        if hasattr(df.index, '__len__'):
            # Convert to list if needed
            indices = list(df.index) if not isinstance(df.index, list) else df.index
            if start_idx < len(indices):
                # Set range to show last N candles
                # For category axes, range is set using the category values
                start_val = indices[start_idx] if start_idx < len(indices) else indices[0]
                end_val = indices[-1] if len(indices) > 0 else None

                if end_val is not None:
                    # Update xaxis range - for category type, use the actual index values
                    fig.update_xaxes(range=[start_val, end_val], row=1 if show_volume else None)

    return fig


def update_chart_with_prepended_data(
    existing_fig: 'go.Figure',
    new_df: pd.DataFrame,
    old_df: pd.DataFrame,
    old_range: list | None,
    show_volume: bool
) -> tuple['go.Figure', list]:
    """
    Update chart figure with prepended data while maintaining view position.
    
    Args:
        existing_fig: Existing Plotly figure
        new_df: New DataFrame to prepend
        old_df: Old DataFrame
        old_range: Old x-axis range [left_val, right_val]
        show_volume: Whether volume subplot is shown
        
    Returns:
        Tuple of (updated_figure, new_range)
    """
    from plotly.graph_objects import Figure

    # Calculate offset (how many new data points were added)
    offset = len(new_df)

    # If we have old range, calculate new range
    new_range = old_range
    if old_range and len(old_df) > 0:
        # Find indices of old range values in old DataFrame
        old_indices = list(old_df.index)
        try:
            left_idx = old_indices.index(old_range[0]) if old_range[0] in old_indices else 0
            right_idx = old_indices.index(old_range[1]) if old_range[1] in old_indices else len(old_indices) - 1

            # Calculate new indices with offset
            new_left_idx = left_idx + offset
            new_right_idx = right_idx + offset

            # Get new DataFrame with prepended data
            combined_df = pd.concat([new_df, old_df])
            combined_df = combined_df[~combined_df.index.duplicated(keep='last')]
            combined_df = combined_df.sort_index()

            # Get new range values
            new_indices = list(combined_df.index)
            if new_left_idx < len(new_indices) and new_right_idx < len(new_indices):
                new_range = [new_indices[new_left_idx], new_indices[new_right_idx]]
        except (ValueError, IndexError):
            # Fallback: use original range if calculation fails
            pass

    # Update figure with new data (this will be done by recreating traces)
    # For now, return the existing figure - actual update happens in callback
    return existing_fig, new_range or []
