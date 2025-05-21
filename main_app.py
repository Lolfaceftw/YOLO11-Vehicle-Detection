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
from .logger_setup import log_debug, setup_logging as app_setup_logging 
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

    # video_player_container now takes the full space allocated to it in the right panel
    ui_components_dict["video_player_container"].grid(row=0, column=0, sticky="nsew")
    

def on_close(root_win):
    """Handle window close event. """
    log_debug("Application closing...")
    
    from .tk_ui_callbacks import _stop_all_processing_logic 
    _stop_all_processing_logic()
    
    if root_win and root_win.winfo_exists():
        root_win.destroy()
    log_debug("Root window destroyed.")


def launch_app():
    """Launch the application with Tkinter GUI"""
    log_debug("Launching application...")
    
    root = tk.Tk()
    root.title("Vehicle Detection and Tracking")
    root.geometry("900x700") 
    root.minsize(700, 500) 
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
    
    log_debug("Starting Tkinter main loop...")
    root.mainloop()
    log_debug("Application exited main loop.")


if __name__ == "__main__": 
    print("main_app.py executed directly. For proper execution, use run_app.py.")
    if not config.IS_DEBUG_MODE: 
        print("Debug mode not enabled via run_app.py. Basic logging might be limited.")
    launch_app()
