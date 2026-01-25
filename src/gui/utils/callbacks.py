"""
Callback utilities for TradeMeUp Dashboard.
"""

import functools
import logging

import dash

logger = logging.getLogger(__name__)


def safe_callback(default_return=dash.no_update, log_errors=True):
    """
    Decorator to wrap Dash callbacks with error handling.
    Prevents "Callback failed: the server did not respond" errors.

    Args:
        default_return: Value to return on error (default: dash.no_update)
        log_errors: Whether to log errors (default: True)
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except dash.exceptions.PreventUpdate:
                raise
            except Exception as e:
                if log_errors:
                    logger.error("Error in callback %s: %s", func.__name__, e, exc_info=True)
                return default_return

        return wrapper

    return decorator
