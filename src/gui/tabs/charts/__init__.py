"""
Charts Tab Package
Entry point for charts tab module
"""

from .callbacks import register_callbacks, register_charts_callbacks

# Export functions for backward compatibility and callbacks
from .components import (
    create_chart_panel,
    create_trading_overlay,
    get_comparison_chart,
    get_market_indices_cards,
    get_price_indicator,
    get_stock_chart_components,
    get_stock_chart_with_stats,
    render_multi_panel_layout,
)
from .layout import create_layout

__all__ = [
    'create_layout',
    'register_charts_callbacks',
    'register_callbacks',
    'render_multi_panel_layout',
    'get_stock_chart_components',
    'create_trading_overlay',
    'create_chart_panel',
    'get_stock_chart_with_stats',
    'get_comparison_chart',
    'get_market_indices_cards',
    'get_price_indicator'
]
