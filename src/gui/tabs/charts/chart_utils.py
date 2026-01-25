"""
Chart utilities (e.g. infinite scroll, binary search).
"""

import logging

logger = logging.getLogger(__name__)


def find_index_binary(indices, target_value):
    """
    Binary search for finding index in sorted array.
    Returns index of first element >= target_value, or 0 if not found.
    O(log n) instead of O(n) for better performance.

    Handles type mismatches by attempting conversion or falling back to linear
    search.
    """
    if not indices or len(indices) == 0:
        return 0

    try:
        from pandas import to_datetime

        if hasattr(target_value, "timestamp") or isinstance(target_value, str):
            try:
                target_value = to_datetime(target_value)
            except (ValueError, TypeError):
                pass
    except Exception:
        pass

    left = 0
    right = len(indices) - 1
    result = 0

    while left <= right:
        mid = (left + right) // 2

        try:
            mid_val = indices[mid]
            if mid_val >= target_value:
                result = mid
                right = mid - 1
            else:
                left = mid + 1
        except (TypeError, ValueError) as e:
            logger.debug(
                "[Binary Search] Type mismatch, falling back to linear search: %s",
                e,
            )
            for i, idx_val in enumerate(indices):
                try:
                    if idx_val >= target_value:
                        return i
                except (TypeError, ValueError):
                    continue
            return 0

    return result
