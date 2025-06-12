"""
Model Handlers Module
Handles model selection, validation, and related UI interactions.
"""
import os
from tkinter import messagebox

from . import shared_refs as refs
from . import model_async
from app.core import globals as app_globals
from app.utils.logger_setup import log_debug
from app.processing.model_loader import get_custom_model_path

log_debug("ui.handlers.model_handlers module initialized.")


def handle_model_selection_change(stop_all_processing_logic_ref, *args):
    """Handle model selection change."""
    selected_model_from_event = refs.ui_components["model_var"].get() 
    log_debug(f"handle_model_selection_change: Model selection changed to '{selected_model_from_event}'. Args: {args}")
    
    root = refs.get_root()
    ui_comps = refs.ui_components
        
    if not ui_comps or root is None or not root.winfo_exists():
        log_debug("Model selection: UI components or root window not available.")
        return
    
    selected_model = ui_comps["model_var"].get() 
    if not selected_model:
        log_debug("No model selected after change event.")
        return
    
    # Validate custom model path if custom model is selected
    if selected_model == "Select Custom Model":
        custom_path = get_custom_model_path()
        if not custom_path or not os.path.exists(custom_path):
            log_debug("Custom model selected but no valid .pt file has been chosen.")
            messagebox.showwarning("Custom Model", "Please select a valid .pt model file using the 'Browse .pt File' button.")
            return
    
    if selected_model == app_globals.active_model_key and app_globals.active_model_object_global is not None:
        log_debug(f"Model {selected_model} is already loaded and active. No action taken.")
        return

    log_debug(f"Selected model for loading: {selected_model}")
    model_async.run_model_load_in_thread(selected_model, stop_all_processing_logic_ref)


def validate_custom_model_selection():
    """Validate that a custom model file has been selected when custom model is chosen."""
    ui_comps = refs.ui_components
    if not ui_comps:
        return False
        
    selected_model = ui_comps["model_var"].get()
    if selected_model == "Select Custom Model":
        custom_path = get_custom_model_path()
        if not custom_path or not os.path.exists(custom_path):
            log_debug("Custom model validation failed: no valid .pt file selected.")
            return False
    
    return True


def get_current_selected_model():
    """Get the currently selected model from the UI."""
    ui_comps = refs.ui_components
    if ui_comps and ui_comps.get("model_var"):
        return ui_comps["model_var"].get()
    return None