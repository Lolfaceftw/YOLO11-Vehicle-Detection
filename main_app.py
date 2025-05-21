"""
Main Application Module for Vehicle Detection and Tracking
This module initializes and launches the application.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
import threading

from . import config
from . import globals as app_globals
from .logger_setup import log_debug 
from .model_loader import (
    load_model as initial_load_model,
    get_available_model_keys,
    get_default_model_key,
)
from .tk_ui_elements import create_ui_components
from ._ui_loading_manager import show_loading, hide_loading_and_update_controls
from .tk_ui_callbacks import init_callbacks


def setup_model_selector(ui_components_dict):
    """Set up the model selector with available models """
    log_debug("Setting up model selector...")

    model_keys = get_available_model_keys()
    default_model = get_default_model_key()

    if not model_keys:
        log_debug("CRITICAL: No models defined in AVAILABLE_MODELS.")
        sys.stderr.write("CRITICAL ERROR: No models configured. Application cannot start.\n")
        return False

    model_selector_frame = ui_components_dict["model_selector_frame"]
    model_var = ui_components_dict["model_var"]

    for widget in model_selector_frame.winfo_children():
        if isinstance(widget, ttk.Radiobutton):
            widget.destroy()
    ui_components_dict["model_buttons"] = []

    for i, model_key in enumerate(model_keys):
        rb = ttk.Radiobutton(
            model_selector_frame,
            text=model_key,
            variable=model_var,
            value=model_key
        )
        rb.pack(anchor="w", padx=config.SPACING_MEDIUM, pady=config.SPACING_SMALL)
        ui_components_dict["model_buttons"].append(rb)

    if default_model in model_keys:
        model_var.set(default_model)
    elif model_keys:
        model_var.set(model_keys[0])
        log_debug(f"Default model key '{default_model}' not found. Using first available: {model_keys[0]}")
    else:
        model_var.set("")
        log_debug("Warning: No models available to set for model selector.")

    return True


def place_ui_components_in_layout(left_panel_ref, right_panel_ref, ui_components_dict):
    """Places the already created UI components into their respective parent panels."""
    log_debug("Placing UI components into layout...")

    ui_components_dict["file_upload_frame"].pack(fill="x", pady=(0, config.SPACING_MEDIUM), anchor="n")
    ui_components_dict["process_buttons_frame"].pack(fill="x", pady=(0, config.SPACING_MEDIUM), anchor="n")
    ui_components_dict["model_selector_frame"].pack(fill="x", pady=(0, config.SPACING_MEDIUM), anchor="n")
    ui_components_dict["sliders_frame"].pack(fill="x", pady=(0, config.SPACING_MEDIUM), anchor="n")

    right_panel_ref.rowconfigure(0, weight=1)
    right_panel_ref.columnconfigure(0, weight=1)

    ui_components_dict["video_player_container"].grid(row=0, column=0, sticky="nsew")


def on_close(root_win, from_exception=False):
    """Handle window close event or program interruption. """
    log_debug(f"on_close called. From exception: {from_exception}")

    if hasattr(on_close, 'stopping') and on_close.stopping:
        log_debug("on_close: Already stopping, returning.")
        return
    on_close.stopping = True

    from .tk_ui_callbacks import _stop_all_processing_logic
    _stop_all_processing_logic()

    if root_win and root_win.winfo_exists():
        log_debug("Destroying root window.")
        root_win.destroy()
    else:
        log_debug("Root window does not exist or already destroyed.")

    log_debug("Application cleanup finished.")
    delattr(on_close, 'stopping')

    if from_exception:
        sys.exit(0)


def launch_app():
    """Launch the application with Tkinter GUI"""
    log_debug("Launching application...")

    root = tk.Tk()
    root.title("Vehicle Detection and Tracking")
    root.configure(background=config.COLOR_BACKGROUND)

    app_frame = ttk.Frame(root, style="TFrame", padding=config.SPACING_MEDIUM)
    app_frame.pack(fill="both", expand=True)

    app_frame.columnconfigure(0, weight=1, minsize=280)
    app_frame.columnconfigure(1, weight=3)
    app_frame.rowconfigure(0, weight=0)
    app_frame.rowconfigure(1, weight=1)

    title_frame_main = ttk.Frame(app_frame, style="Card.TFrame")
    title_frame_main.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, config.SPACING_MEDIUM))

    title_label_main = ttk.Label(
        title_frame_main,
        text="Vehicle Detection and Tracking",
        style="Title.TLabel",
        font=config.FONT_TITLE
    )
    title_label_main.pack(padx=config.SPACING_LARGE, pady=config.SPACING_MEDIUM)

    left_panel_main = ttk.Frame(app_frame, style="TFrame")
    left_panel_main.grid(row=1, column=0, sticky="nswe", padx=(0, config.SPACING_MEDIUM))

    right_panel_main = ttk.Frame(app_frame, style="TFrame")
    right_panel_main.grid(row=1, column=1, sticky="nswe")

    ui_components_dict = create_ui_components(root, left_panel_main, right_panel_main)

    place_ui_components_in_layout(left_panel_main, right_panel_main, ui_components_dict)

    root.protocol("WM_DELETE_WINDOW", lambda: on_close(root))

    if not setup_model_selector(ui_components_dict):
        log_debug("Model selector setup failed. Closing application.")
        root.after(100, lambda: on_close(root))
        root.mainloop()
        return

    init_callbacks(root, ui_components_dict)

    root.update_idletasks() 

    title_req_height = title_frame_main.winfo_reqheight()
    left_req_width = left_panel_main.winfo_reqwidth()
    left_req_height = left_panel_main.winfo_reqheight()
    right_req_width = right_panel_main.winfo_reqwidth()
    right_req_height = right_panel_main.winfo_reqheight()
    
    # Consider the fast_progress_frame if it's part of the initial layout calculation needs
    # However, it's usually hidden initially. For now, we assume its space is accounted for
    # by the left_panel_main's general requested size or managed dynamically.
    # If it were always visible, you might add its reqheight to left_req_height.

    grid_content_width = left_req_width + config.SPACING_MEDIUM + right_req_width
    grid_content_height = title_req_height + config.SPACING_MEDIUM + max(left_req_height, right_req_height)

    final_width = grid_content_width + (2 * config.SPACING_MEDIUM)
    final_height = grid_content_height + (2 * config.SPACING_MEDIUM)

    final_width += 20
    final_height += 40 # Added a bit more height buffer

    log_debug(f"Calculated required window size: {final_width}x{final_height}")
    root.geometry(f"{final_width}x{final_height}")
    
    # Set a reasonable absolute minimum size
    min_width = max(700, left_req_width + right_req_width // 2 + (2 * config.SPACING_MEDIUM) + 20) 
    min_height = max(500, title_req_height + left_req_height // 2 + (2 * config.SPACING_MEDIUM) + 40)
    root.minsize(min_width, min_height)
    log_debug(f"Set root minsize to: {min_width}x{min_height}")


    log_debug(f"--- Initializing Application --- Loading default model: {ui_components_dict['model_var'].get()}")
    default_model_to_load = ui_components_dict['model_var'].get()
    if default_model_to_load:
        show_loading(f"Initializing with model: {default_model_to_load}...")

        def initial_model_load_task():
            initial_load_model(default_model_to_load)
            if root.winfo_exists():
                 root.after(0, hide_loading_and_update_controls)

        threading.Thread(target=initial_model_load_task, daemon=True).start()
    else:
        log_debug("No default model selected or available for initial load.")
        print("Warning: No model loaded on startup. Please select a model from the UI.")
        if root.winfo_exists():
            root.after(0, hide_loading_and_update_controls)
    
    # One final update before mainloop to ensure all initial styling and geometry is applied
    root.update_idletasks()
    log_debug("Starting Tkinter main loop...")
    try:
        root.mainloop()
    except KeyboardInterrupt:
        log_debug("KeyboardInterrupt caught in main_app. Cleaning up...")
        on_close(root, from_exception=True)
    finally:
        log_debug("Application exited main loop.")


if __name__ == "__main__":
    print("main_app.py executed directly. For proper execution, use run_app.py.")
    if not config.IS_DEBUG_MODE:
        print("Debug mode not enabled via run_app.py. Basic logging might be limited.")
    launch_app()
