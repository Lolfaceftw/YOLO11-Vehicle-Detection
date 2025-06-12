"""
Main Event Handlers Module (Refactored)
Acts as a facade that delegates to specialized handler modules for better organization.
"""
from . import file_handlers
from . import model_handlers
from . import control_handlers
from . import threshold_handlers
from app.utils.logger_setup import log_debug

log_debug("ui.handlers.event_handlers module initialized.")

_stop_all_processing_logic_ref = None


def init_event_handlers(stop_logic_func):
    """Initialize event handlers with stop logic reference."""
    global _stop_all_processing_logic_ref
    _stop_all_processing_logic_ref = stop_logic_func
    log_debug("Event handlers initialized with stop logic reference.")


# File handling operations
def handle_file_upload():
    """Handle file upload button click."""
    file_handlers.handle_file_upload(_stop_all_processing_logic_ref)


def handle_custom_model_upload():
    """Handle custom model file selection."""
    file_handlers.handle_custom_model_upload(_stop_all_processing_logic_ref)


# Model selection operations
def handle_model_selection_change(*args):
    """Handle model selection change."""
    model_handlers.handle_model_selection_change(_stop_all_processing_logic_ref, *args)


# Process control operations
def on_process_button_click():
    """Handle process button click for real-time processing."""
    control_handlers.on_process_button_click()


def on_fast_process_button_click():
    """Handle fast process button click."""
    control_handlers.on_fast_process_button_click(_stop_all_processing_logic_ref)


# Video control operations
def toggle_play_pause():
    """Toggle between play and pause for video playback."""
    control_handlers.toggle_play_pause()


def stop_video_stream_button_click():
    """Handle stop button click to stop video processing."""
    control_handlers.stop_video_stream_button_click(_stop_all_processing_logic_ref)


# Slider control operations
def handle_slider_value_change(*args):
    """Handle progress slider value changes."""
    control_handlers.handle_slider_value_change(*args)


def handle_slider_click_press(event):
    """Handle slider click press event to calculate exact position."""
    control_handlers.handle_slider_click_press(event)

def handle_slider_click_release(event):
    """Handle slider click release event."""
    control_handlers.handle_slider_click_release(event)


# Threshold control operations
def handle_iou_change(*args):
    """Handle IoU threshold slider changes."""
    threshold_handlers.handle_iou_change(*args)


def handle_conf_change(*args):
    """Handle confidence threshold slider changes."""
    threshold_handlers.handle_conf_change(*args)


# Utility functions for external access
def validate_custom_model_selection():
    """Validate that a custom model file has been selected when custom model is chosen."""
    return model_handlers.validate_custom_model_selection()


def get_current_selected_model():
    """Get the currently selected model from the UI."""
    return model_handlers.get_current_selected_model()


def get_current_thresholds():
    """Get current IoU and confidence threshold values."""
    return threshold_handlers.get_current_thresholds()


def update_threshold_displays():
    """Update threshold display labels with current values."""
    threshold_handlers.update_threshold_displays()