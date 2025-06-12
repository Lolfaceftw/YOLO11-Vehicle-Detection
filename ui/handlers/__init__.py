"""
UI Handlers package initialization
Contains all UI event handlers, async operations, and specialized UI logic modules.
"""
from app.utils.logger_setup import log_debug
log_debug("ui.handlers package initialized.")

# Import main handler coordinators
from .event_handlers import *
from . import async_logic

# Import commonly used handlers
from .loading_manager import show_loading, hide_loading_and_update_controls, update_progress
from .shared_refs import get_ui_refs

# Import async operations
from .file_async import *
from .video_async import *
from .model_async import *

__all__ = [
    # Main coordinators
    'handle_file_upload',
    'handle_custom_model_file',
    'handle_model_selection',
    'handle_process_button',
    'handle_play_pause_button',
    'handle_conf_slider_change',
    'handle_iou_slider_change',
    'handle_seek_bar_change',
    'stop_all_processing_logic',
    
    # Loading management
    'show_loading',
    'hide_loading_and_update_controls',
    'update_progress',
    
    # Shared references
    'get_ui_refs',
    
    # Async operations
    'get_async_operations_status',
    'format_time_display',
]