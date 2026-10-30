"""
Chart tab extended callbacks: price cache, tabs, overlays, infinite scroll, render, panels.

Each related group of callbacks lives in its own module in this package; this
module only registers them in the required order.
"""

from .config_modals import register_config_modal_callbacks
from .overlay_lists import register_overlay_list_callbacks
from .overlay_modal import register_overlay_modal_callbacks
from .panel_layout import register_panel_layout_callbacks
from .panel_settings import register_panel_settings_callbacks
from .price_cache import register_price_cache_callbacks
from .render import register_render_callbacks
from .scroll import register_scroll_callbacks
from .tab_management import register_tab_management_callbacks


def register_charts_extended(app):
    """Register extended chart callbacks (tabs, overlays, render, panels).

    The groups are registered in the original order, which must be preserved.
    """
    register_price_cache_callbacks(app)
    register_overlay_modal_callbacks(app)
    register_scroll_callbacks(app)
    register_tab_management_callbacks(app)
    register_render_callbacks(app)
    register_panel_settings_callbacks(app)
    register_panel_layout_callbacks(app)
    register_config_modal_callbacks(app)
    register_overlay_list_callbacks(app)
