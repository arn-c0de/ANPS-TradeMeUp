"""
GUI callbacks package.
Common, chart, and cross-tab callbacks are registered via register_* functions.
"""

from .charts import register_charts_callbacks
from .common import register_common_callbacks

__all__ = ["register_charts_callbacks", "register_common_callbacks"]
