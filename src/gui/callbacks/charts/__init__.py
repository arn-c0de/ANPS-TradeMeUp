"""
Charts callbacks package. Register via register_charts_callbacks(app).
"""

from .core import register_charts_core
from .extended import register_charts_extended


def register_charts_callbacks(app):
    """Register all chart tab callbacks (core + extended)."""
    register_charts_core(app)
    register_charts_extended(app)
