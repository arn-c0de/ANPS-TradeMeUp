"""
URL/tab routing utilities for ANPS-TradeMeUp Dashboard.
"""

VALID_MAIN_TAB_IDS = {
    "dashboard",
    "news",
    "predictions",
    "simulations",
    "statistics",
    "charts",
    "control",
    "testing",
    "system",
    "settings",
}


def tab_from_hash(hash_val):
    """Parse tab id from URL hash. Returns 'dashboard' if missing/invalid."""
    tab = (hash_val or "").lstrip("#").strip() or "dashboard"
    return tab if tab in VALID_MAIN_TAB_IDS else "dashboard"
