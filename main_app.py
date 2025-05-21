"""
Main Application Module for Vehicle Detection and Tracking
This module initializes and launches the application.
"""

import tkinter as tk
from tkinter import ttk
import sys
import threading

from . import config
from . import globals as app_globals
from .logger_setup import log_debug, setup_logging as app_setup_logging
from .model_loader import (
    load_model as initial_load_model, 
    get_available_model_keys, 
    get_default_model_key,
    AVAILABLE_MODELS
)
from .tk_ui_elements import create_ui_components
from .tk_ui_callbacks import init_callbacks, show_loading, hide_loading_and_update_controls


def setup_model_selector(ui_components):
    """Set up the model selector with available models
    
    Args:
        ui_components: Dictionary of UI components
    """
    log_debug("Setting up model selector...")
    
    model_keys = get_available_model_keys()
    default_model = get_default_model_key()
    
    if not model_keys:
        log_debug("CRITICAL: No models defined in AVAILABLE_MODELS.")
        sys.stderr.write("CRITICAL ERROR: No models configured. Application cannot start.\n")
        return False
    
    # Create radio buttons for models
    model_selector_frame = ui_components["model_selector_frame"]
    model_var = ui_components["model_var"]
    model_buttons = []
    
    for i, model_key in enumerate(model_keys):
        rb = ttk.Radiobutton(
            model_selector_frame,
            text=model_key,
            variable=model_var,
            value=model_key
        )
        rb.pack(anchor="w", padx=10, pady=2)
        model_buttons.append(rb)
    
    # Set default model
    if default_model in model_keys:
        model_var.set(default_model)
    elif model_keys:
        model_var.set(model_keys[0])
        log_debug(f"Default model key '{default_model}' not found. Using first available: {model_keys[0]}")
    else:
        model_var.set("")
    
    # Store model buttons in components
    ui_components["model_buttons"] = model_buttons
    
    return True


def create_ui_layout(root, ui_components):
    """Create the layout for the UI components
    
    Args:
        root: Root Tkinter window
        ui_components: Dictionary of UI components
    """
    log_debug("Creating UI layout...")
    
    # Configure root window with Material Design styling
    root.title("Vehicle Detection and Tracking")
    root.geometry("900x800")
    root.configure(background=config.COLOR_BACKGROUND)
    
    # Create title bar with app name
    title_frame = ttk.Frame(root, style="Card.TFrame")
    title_frame.pack(fill="x", padx=config.SPACING_MEDIUM, pady=(config.SPACING_MEDIUM, 0))
    
    title_label = ttk.Label(
        title_frame, 
        text="Vehicle Detection and Tracking",
        style="Title.TLabel",
        font=config.FONT_TITLE
    )
    title_label.pack(padx=config.SPACING_LARGE, pady=config.SPACING_MEDIUM)
    
    # Create main content area with proper spacing
    main_frame = ttk.Frame(root, style="TFrame")
    main_frame.pack(fill="both", expand=True, padx=config.SPACING_MEDIUM, pady=config.SPACING_MEDIUM)
    
    # Left sidebar for controls
    left_panel = ttk.Frame(main_frame, style="TFrame")
    left_panel.pack(side="left", fill="y", padx=(0, config.SPACING_MEDIUM), pady=0, anchor="n")
    
    # Right panel for video display and output
    right_panel = ttk.Frame(main_frame, style="TFrame")
    right_panel.pack(side="right", fill="both", expand=True, padx=0, pady=0)
    
    # Layout for left panel controls
    # Upload section
    ui_components["file_upload_frame"].pack(fill="x", padx=config.SPACING_SMALL, pady=config.SPACING_SMALL, anchor="n")
    
    # Process buttons section with slight margin
    ui_components["process_buttons_frame"].pack(fill="x", padx=config.SPACING_SMALL, pady=config.SPACING_SMALL, anchor="n")
    
    # Model selection section
    ui_components["model_selector_frame"].pack(fill="x", padx=config.SPACING_SMALL, pady=config.SPACING_SMALL, anchor="n")
    
    # Thresholds settings section
    ui_components["sliders_frame"].pack(fill="x", padx=config.SPACING_SMALL, pady=config.SPACING_SMALL, anchor="n")
    
    # Fast progress section (initially hidden by callbacks)
    ui_components["fast_progress_frame"].pack_forget()  # Will be packed by callbacks when needed
    
    # Layout for right panel
    # Video player container takes most of the space
    ui_components["video_player_container"].pack(fill="both", expand=True, padx=config.SPACING_SMALL, pady=config.SPACING_SMALL)
    
    # Output section at the bottom
    ui_components["output_frame"].pack(fill="x", padx=config.SPACING_SMALL, pady=config.SPACING_SMALL)
    
    # Video controls and progress frames are managed by the callbacks
    
    # Handle window close event
    root.protocol("WM_DELETE_WINDOW", lambda: on_close(root))


def on_close(root):
    """Handle window close event
    
    Args:
        root: Root Tkinter window
    """
    log_debug("Application closing...")
    
    # Clean up resources
    from .tk_ui_callbacks import _stop_all_processing_logic
    _stop_all_processing_logic()
    
    # Close window
    root.destroy()


def launch_app():
    """Launch the application with Tkinter GUI"""
    log_debug("Launching application...")
    
    # Create root window
    root = tk.Tk()
    
    # Create UI components
    ui_components = create_ui_components(root)
    
    # Create UI layout
    create_ui_layout(root, ui_components)
    
    # Set up model selector
    if not setup_model_selector(ui_components):
        root.after(2000, root.destroy)  # Close window after delay to show error
        return
    
    # Initialize callbacks
    init_callbacks(root, ui_components)
    
    # Initialize default model
    log_debug(f"--- Initializing Application --- Loading default model: {ui_components['model_var'].get()}")
    if ui_components["model_var"].get():
        # Schedule model loading in a separate thread to avoid blocking UI
        show_loading(f"Initializing with model: {ui_components['model_var'].get()}...")
        threading.Thread(
            target=lambda: [
                initial_load_model(ui_components["model_var"].get()),
                root.after(100, hide_loading_and_update_controls)
            ],
            daemon=True
        ).start()
    else:
        log_debug("No default model selected or available for initial load.")
        print("Warning: No model loaded on startup. Please select a model.")
    
    # Start main loop
    log_debug("Starting Tkinter main loop...")
    root.mainloop()
    log_debug("Application exited.")


if __name__ == "__main__":
    print("This script is intended to be launched via run_app.py")