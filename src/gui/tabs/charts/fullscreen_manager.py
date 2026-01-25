"""
Fullscreen state management utilities for charts.

This module provides centralized functions for managing fullscreen state,
reducing code duplication and improving maintainability.
"""

from typing import Dict, Optional, Tuple


DEFAULT_FULLSCREEN_STATE = {'fullscreen': False}


def get_fullscreen_state(fullscreen_data: Optional[Dict]) -> bool:
    """
    Safely extract fullscreen state from data dict.
    
    Args:
        fullscreen_data: Dictionary containing fullscreen state, or None
        
    Returns:
        Boolean indicating if fullscreen mode is active
    """
    if not fullscreen_data:
        return False
    return fullscreen_data.get('fullscreen', False)


def create_fullscreen_state(is_fullscreen: bool) -> Dict:
    """
    Create a new fullscreen state dict.
    
    Args:
        is_fullscreen: Boolean indicating desired fullscreen state
        
    Returns:
        Dictionary with fullscreen state
    """
    return {'fullscreen': bool(is_fullscreen)}


def toggle_fullscreen_state(current_state: Optional[Dict]) -> Dict:
    """
    Toggle fullscreen state and return new state.
    
    Args:
        current_state: Current fullscreen state dict, or None
        
    Returns:
        New fullscreen state dict with toggled value
    """
    current = get_fullscreen_state(current_state)
    return create_fullscreen_state(not current)


def get_container_classname(is_fullscreen: bool) -> str:
    """
    Get CSS classname for container based on fullscreen state.
    
    Args:
        is_fullscreen: Boolean indicating fullscreen state
        
    Returns:
        CSS classname string
    """
    return 'chart-container-fullscreen' if is_fullscreen else 'chart-container-normal'


def get_toggle_button_config(is_fullscreen: bool) -> Tuple[str, str]:
    """
    Get toggle button text and color based on state.
    
    Args:
        is_fullscreen: Boolean indicating fullscreen state
        
    Returns:
        Tuple of (button_text, button_color)
    """
    if is_fullscreen:
        return "⬇ Exit", "danger"
    return "⛶", "info"


def get_exit_button_style(is_fullscreen: bool) -> Dict:
    """
    Get exit button style based on fullscreen state.
    
    Args:
        is_fullscreen: Boolean indicating fullscreen state
        
    Returns:
        Dictionary with CSS style properties
    """
    return {'display': 'inline-block' if is_fullscreen else 'none'}
