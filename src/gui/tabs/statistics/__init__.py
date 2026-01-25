"""
Statistics Tab Package
Entry point for statistics tab module
"""

from .layout import create_layout
from .callbacks import register_callbacks

__all__ = ['create_layout', 'register_callbacks']
