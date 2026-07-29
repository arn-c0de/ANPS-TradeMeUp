"""
JSON and JSONB Helper Functions

Utilities for handling JSON data, particularly when migrating from SQLite to PostgreSQL.
SQLite stores JSON as TEXT, while PostgreSQL has native JSONB support.
"""
import json
from typing import Any

import numpy as np


def ensure_dict(value: Any, default: dict | None = None) -> dict:
    """
    Ensure a JSONB value is deserialized to a dictionary.
    
    Handles cases where:
    - PostgreSQL JSONB might be returned as string (from SQLite migration)
    - Value is None
    - Value is already a dict
    
    Args:
        value: The value to ensure is a dict (could be str, dict, or None)
        default: Default value to return if value is None or invalid (defaults to {})
        
    Returns:
        Dict: The deserialized dictionary, or default if invalid
        
    Example:
        >>> ensure_dict('{"key": "value"}')
        {'key': 'value'}
        >>> ensure_dict(None)
        {}
        >>> ensure_dict(None, {"default": True})
        {'default': True}
    """
    if default is None:
        default = {}

    if value is None:
        return default

    if isinstance(value, dict):
        return value

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
            return default
        except (json.JSONDecodeError, ValueError, TypeError):
            return default

    return default


def ensure_list(value: Any, default: list | None = None) -> list:
    """
    Ensure a JSONB value is deserialized to a list.
    
    Handles cases where:
    - PostgreSQL JSONB might be returned as string (from SQLite migration)
    - Value is None
    - Value is already a list
    
    Args:
        value: The value to ensure is a list (could be str, list, or None)
        default: Default value to return if value is None or invalid (defaults to [])
        
    Returns:
        List: The deserialized list, or default if invalid
        
    Example:
        >>> ensure_list('[1, 2, 3]')
        [1, 2, 3]
        >>> ensure_list(None)
        []
        >>> ensure_list(None, [0])
        [0]
    """
    if default is None:
        default = []

    if value is None:
        return default

    if isinstance(value, list):
        return value

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
            return default
        except (json.JSONDecodeError, ValueError, TypeError):
            return default

    return default


def ensure_json(value: Any, default: Any = None) -> dict | list | Any:
    """
    Ensure a JSONB value is deserialized (dict, list, or other JSON type).
    
    More flexible than ensure_dict or ensure_list - returns whatever JSON type it is.
    
    Args:
        value: The value to ensure is deserialized
        default: Default value to return if value is None or invalid
        
    Returns:
        The deserialized JSON value, or default if invalid
        
    Example:
        >>> ensure_json('{"key": "value"}')
        {'key': 'value'}
        >>> ensure_json('[1, 2, 3]')
        [1, 2, 3]
        >>> ensure_json('"string"')
        'string'
    """
    if value is None:
        return default

    if not isinstance(value, str):
        return value

    try:
        return json.loads(value)
    except (json.JSONDecodeError, ValueError, TypeError):
        return default


def to_python_type(value: Any) -> Any:
    """
    Convert numpy types and other non-native types to Python native types.
    
    This is essential for PostgreSQL compatibility, as numpy types like np.float64
    cause SQL errors when passed directly to database queries.
    
    Args:
        value: The value to convert (can be numpy type, None, or native Python type)
        
    Returns:
        The value converted to a Python native type, or None if input is None
        
    Example:
        >>> to_python_type(np.float64(3.14))
        3.14
        >>> to_python_type(np.int64(42))
        42
        >>> to_python_type(None)
        None
        >>> to_python_type(3.14)
        3.14
    """
    if value is None:
        return None

    # Handle numpy types
    if hasattr(value, 'item'):  # numpy scalars have .item() method
        return value.item()

    # Handle numpy bool specifically (doesn't always have .item())
    # Note: np.bool8 was removed in newer numpy versions, only use np.bool_
    if isinstance(value, np.bool_):
        return bool(value)

    # Handle numpy integers
    if isinstance(value, (np.integer, np.signedinteger, np.unsignedinteger)):
        return int(value)

    # Handle numpy floats
    if isinstance(value, (np.floating, np.float16, np.float32, np.float64)):
        return float(value)

    # Already a native Python type
    return value


def clean_numpy_types(obj: Any) -> Any:
    """
    Recursively convert numpy types in nested structures to Python native types.
    
    Useful for cleaning JSONB data that might contain numpy types from calculations.
    
    Args:
        obj: The object to clean (can be dict, list, numpy type, or native type)
        
    Returns:
        The object with all numpy types converted to Python native types
        
    Example:
        >>> clean_numpy_types({'a': np.float64(3.14), 'b': [np.int64(1), 2]})
        {'a': 3.14, 'b': [1, 2]}
        >>> clean_numpy_types([np.float64(1.5), np.float64(2.5)])
        [1.5, 2.5]
    """
    if obj is None:
        return None

    if isinstance(obj, dict):
        return {key: clean_numpy_types(value) for key, value in obj.items()}

    if isinstance(obj, list):
        return [clean_numpy_types(item) for item in obj]

    if isinstance(obj, tuple):
        return tuple(clean_numpy_types(item) for item in obj)

    # Convert numpy types
    return to_python_type(obj)
