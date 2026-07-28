"""Error handling utilities for GUI components."""
import logging
from functools import wraps

import dash_bootstrap_components as dbc
from dash import html

logger = logging.getLogger(__name__)


def handle_db_errors(default_message="Unable to load data", show_details=True):
    """
    Decorator to handle database errors in GUI functions.
    
    Args:
        default_message: Message to show when error occurs
        show_details: Whether to show error details in UI
    
    Returns:
        Decorated function that handles errors gracefully
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {e}", exc_info=True)

                # Create user-friendly error message
                if show_details:
                    return dbc.Alert([
                        html.H5("⚠️ " + default_message, className="alert-heading"),
                        html.Hr(),
                        html.P(str(e), className="mb-0 small")
                    ], color="warning")
                else:
                    return dbc.Alert(
                        "⚠️ " + default_message,
                        color="warning"
                    )
        return wrapper
    return decorator


def create_empty_state(title, message, icon="📭", action_text=None, action_link=None):
    """
    Create a user-friendly empty state component.
    
    Args:
        title: Title of the empty state
        message: Explanatory message
        icon: Emoji icon to display
        action_text: Optional call-to-action text
        action_link: Optional link for the action
    
    Returns:
        Dash component for empty state
    """
    components = [
        html.Div([
            html.H3([icon, " ", title], className="text-muted mb-3"),
            html.P(message, className="text-muted mb-3")
        ], className="text-center py-5")
    ]

    if action_text:
        if action_link:
            components.append(
                html.Div([
                    dbc.Button(action_text, href=action_link, color="primary", size="sm")
                ], className="text-center")
            )
        else:
            components.append(
                html.P(action_text, className="text-center text-info small")
            )

    return html.Div(components)


def create_error_boundary(component, fallback_message="An error occurred"):
    """
    Create an error boundary wrapper for a component.
    
    Args:
        component: Component to wrap
        fallback_message: Message to show if component fails
    
    Returns:
        Component with error handling
    """
    try:
        return component
    except Exception as e:
        logger.error(f"Error boundary caught: {e}", exc_info=True)
        return dbc.Alert([
            html.H5("⚠️ " + fallback_message, className="alert-heading"),
            html.P(str(e), className="mb-0 small text-muted")
        ], color="warning")


def safe_query(session, query_func, default=None, log_errors=True):
    """
    Safely execute a database query with error handling.
    
    Args:
        session: Database session
        query_func: Function that performs the query
        default: Default value to return on error
        log_errors: Whether to log errors
    
    Returns:
        Query result or default value on error
    """
    try:
        return query_func(session)
    except Exception as e:
        if log_errors:
            logger.error(f"Query error: {e}", exc_info=True)
        return default


def format_error_for_display(error, context=""):
    """
    Format an error for user-friendly display.
    
    Args:
        error: Exception object
        context: Optional context string
    
    Returns:
        Formatted error message string
    """
    error_type = type(error).__name__
    error_msg = str(error)

    # Simplify common database errors
    if "no such table" in error_msg:
        return "Database table not found. Run migrations: `alembic upgrade head`"
    elif "connection" in error_msg.lower():
        return "Database connection error. Check your database configuration."
    elif "locked" in error_msg.lower():
        return "Database is locked. Try again in a moment."

    # Generic error with context
    if context:
        return f"{context}: {error_type} - {error_msg[:100]}"

    return f"{error_type}: {error_msg[:100]}"


class DatabaseErrorHandler:
    """Context manager for database operations with error handling."""

    def __init__(self, default_return=None, log_errors=True, reraise=False):
        """
        Initialize error handler.
        
        Args:
            default_return: Value to return on error
            log_errors: Whether to log errors
            reraise: Whether to re-raise exceptions
        """
        self.default_return = default_return
        self.log_errors = log_errors
        self.reraise = reraise
        self.error = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            self.error = exc_val
            if self.log_errors:
                logger.error(f"Database operation error: {exc_val}", exc_info=True)
            if self.reraise:
                return False  # Re-raise the exception
            return True  # Suppress the exception
        return False

    def get_result(self, result):
        """Get result or default if error occurred."""
        return self.default_return if self.error else result
