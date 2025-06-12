"""
UI package initialization
Contains all user interface components, layouts, styles, and event handlers.
"""
from app.utils.logger_setup import log_debug
log_debug("ui package initialized.")

# Import main UI creation functions
from .elements import create_ui_components
from .callbacks import init_callbacks
from .styles import setup_material_theme

# Import commonly used widgets
from .custom_widgets import *
from .layout_sections import *

__all__ = [
    'create_ui_components',
    'init_callbacks', 
    'setup_material_theme',
]