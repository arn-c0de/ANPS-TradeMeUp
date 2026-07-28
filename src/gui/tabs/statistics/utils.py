"""
Statistics Tab - Utility Functions
Date handling and range resolution utilities
"""

from datetime import UTC, date, datetime, timedelta, timezone


def _coerce_datetime(value, is_end=False):
    """Coerce various date/time types to datetime objects."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.max.time() if is_end else datetime.min.time())
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if "T" in value or ":" in value:
            return parsed
        return datetime.combine(parsed.date(), datetime.max.time() if is_end else datetime.min.time())
    return None


def _parse_date_range(date_range):
    """Parse date range tuple into start and end datetimes."""
    if not date_range or len(date_range) != 2:
        return None, None
    return _coerce_datetime(date_range[0], is_end=False), _coerce_datetime(date_range[1], is_end=True)


def _resolve_stats_date_range(start_date, end_date, active_filter):
    """Resolve (start, end) from quick-select active_filter or explicit start/end dates."""
    if active_filter and active_filter != "all":
        if active_filter.endswith("h"):
            hours = None
            if active_filter.startswith("custom-"):
                try:
                    hours = int(active_filter.split("-", 1)[1].rstrip("h"))
                except ValueError:
                    hours = None
            else:
                try:
                    hours = int(active_filter.rstrip("h"))
                except ValueError:
                    hours = None
            if hours:
                end = datetime.now(UTC)
                start = end - timedelta(hours=hours)
                return (start, end)
    if start_date or end_date:
        return (start_date, end_date)
    return None
