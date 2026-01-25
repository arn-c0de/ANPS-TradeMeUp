"""
Charts callbacks package. Register via register_charts_callbacks(app) or register_callbacks(app).
"""

from .core import register_charts_core
from .extended import register_charts_extended


def register_charts_callbacks(app):
    """Register all chart tab callbacks (core + extended)."""
    register_charts_core(app)
    register_charts_extended(app)


# Alias for consistency with statistics tab
register_callbacks = register_charts_callbacks
