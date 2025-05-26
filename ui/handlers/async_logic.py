"""
Main Async Logic Coordinator (Refactored)
Acts as a coordinator that delegates to specialized async modules for better organization.
This module maintains backward compatibility while using the new modular structure.
"""
from . import video_async
from . import file_async
from . import model_async
from app.utils.logger_setup import log_debug

log_debug("ui.handlers.async_logic module initialized.")

# Video operations delegation
def _video_playback_loop():
    """Main video playback loop - delegates to video async module."""
    return video_async._video_playback_loop()


def _perform_seek_action_in_thread(target_frame_number, is_real_time_mode=False):
    """Perform video seeking - delegates to video async module."""
    return video_async._perform_seek_action_in_thread(target_frame_number, is_real_time_mode)


def run_fast_video_processing_in_thread(uploaded_video_path, stop_all_processing_logic_ref):
    """Start fast video processing - delegates to video async module."""
    return video_async.run_fast_video_processing_in_thread(uploaded_video_path, stop_all_processing_logic_ref)


# File operations delegation
def _process_uploaded_file_in_thread(file_path, stop_all_processing_logic_ref):
    """Process uploaded file - delegates to file async module."""
    return file_async._process_uploaded_file_in_thread(file_path, stop_all_processing_logic_ref)


def run_image_processing_in_thread(file_path):
    """Process image file - delegates to file async module."""
    return file_async.run_image_processing_in_thread(file_path)


# Model operations delegation
def run_model_load_in_thread(selected_model_key, stop_all_processing_logic_ref):
    """Load model - delegates to model async module."""
    return model_async.run_model_load_in_thread(selected_model_key, stop_all_processing_logic_ref)


# Utility functions for backward compatibility and coordination
def get_async_operations_status():
    """Get status of ongoing async operations."""
    from app.core import globals as app_globals
    
    status = {
        'video_playing': app_globals.is_playing_via_after_loop,
        'video_paused': app_globals.video_paused_flag.is_set(),
        'fast_processing_active': app_globals.fast_processing_active_flag.is_set(),
        'stop_flag_set': app_globals.stop_video_processing_flag.is_set(),
        'model_loaded': app_globals.active_model_object_global is not None,
        'video_loaded': app_globals.video_capture_global is not None
    }
    
    return status


def coordinate_stop_all_operations(stop_all_processing_logic_ref):
    """Coordinate stopping all async operations across modules."""
    log_debug("Coordinating stop of all async operations.")
    
    if stop_all_processing_logic_ref:
        stop_all_processing_logic_ref()
    
    log_debug("All async operations stop coordination completed.")


def initialize_async_modules():
    """Initialize all async modules (if needed for future configuration)."""
    log_debug("Async logic coordinator initialized with modular structure.")
    return True


# Legacy support - maintain old function names for backward compatibility
# These can be removed once all references are updated
def format_time_display(current_seconds, total_seconds=None):
    """Legacy time formatting - delegates to video handler."""
    from app.processing.video_handler import format_time_display as video_format_time
    if total_seconds is not None:
        return f"{video_format_time(current_seconds)} / {video_format_time(total_seconds)}"
    return video_format_time(current_seconds)


# Module initialization