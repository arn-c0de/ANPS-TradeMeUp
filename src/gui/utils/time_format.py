"""Human-readable formatting of time spans for the GUI.

These helpers exist because ``timedelta.seconds`` is not the span's length in
seconds - it is the sub-day remainder. Formatting straight off that attribute
renders a 25-hour-old record as "1h ago".
"""
from datetime import timedelta

SECONDS_PER_HOUR = 3600
SECONDS_PER_MINUTE = 60


def format_duration(delta: timedelta, *, suffix: str = "") -> str:
    """Render a positive duration as ``3d`` / ``5h`` / ``12m`` / ``just now``.

    Args:
        delta: The span to render. Negative spans render as ``just now``.
        suffix: Appended to the number, e.g. ``" ago"`` or ``" left"``.
    """
    total_seconds = delta.total_seconds()
    if total_seconds < SECONDS_PER_MINUTE:
        return "just now" if not suffix.strip() or suffix.strip() == "ago" else f"0m{suffix}"

    if total_seconds >= 86400:
        return f"{int(total_seconds // 86400)}d{suffix}"
    if total_seconds >= SECONDS_PER_HOUR:
        return f"{int(total_seconds // SECONDS_PER_HOUR)}h{suffix}"
    return f"{int(total_seconds // SECONDS_PER_MINUTE)}m{suffix}"


def format_time_ago(delta: timedelta) -> str:
    """Render how long ago something happened, e.g. ``3d ago``."""
    return format_duration(delta, suffix=" ago")


def format_time_left(delta: timedelta) -> str:
    """Render how much time remains, e.g. ``5h left``; ``expired`` once past."""
    if delta.total_seconds() <= 0:
        return "expired"
    return format_duration(delta, suffix=" left")
