"""
Main Application Module for Vehicle Detection and Tracking
This module initializes and launches the application.
"""
import os
import sys

# Path setup for direct execution
if __name__ == "__main__" and (__package__ is None or __package__ == ''):
    current_script_path = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(current_script_path))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

import tkinter as tk
from tkinter import ttk, messagebox
import threading

from app import config
from app import globals as app_globals
from app.logger_setup import log_debug, setup_logging as initialize_logging
from app.model_loader import (
    load_model as initial_load_model,
    get_available_model_keys,
    get_default_model_key,
)
from app.tk_ui_elements import create_ui_components
from app._ui_loading_manager import show_loading, hide_loading_and_update_controls
from app.tk_ui_callbacks import init_callbacks

def _initial_pack_for_sizing(widget, widget_name_for_log="widget"):
    if widget and not widget.winfo_ismapped():
        log_debug(f"launch_app: Temporarily packing '{widget_name_for_log}' (current req: {widget.winfo_reqwidth()}x{widget.winfo_reqheight()}) for sizing.")
        widget.pack(fill="x", pady=(0, config.SPACING_MEDIUM), anchor="n")
        widget.winfo_toplevel().update_idletasks()
        log_debug(f"launch_app: After pack and update_idletasks, '{widget_name_for_log}' actual size: {widget.winfo_width()}x{widget.winfo_height()}")

def _initial_unpack_for_sizing(widget, widget_name_for_log="widget"):
    if widget and widget.winfo_ismapped():
        log_debug(f"launch_app: Unpacking '{widget_name_for_log}' after sizing.")
        widget.pack_forget()

def setup_model_selector(ui_components_dict):
    log_debug("setup_model_selector: START")
    model_keys = get_available_model_keys()
    default_model = get_default_model_key()

    if not model_keys:
        log_debug("setup_model_selector: CRITICAL - No models defined in AVAILABLE_MODELS.")
        sys.stderr.write("CRITICAL ERROR: No models configured.\n")
        return False

    model_selector_frame = ui_components_dict["model_selector_frame"]
    model_var = ui_components_dict["model_var"]

    for widget_in_frame in model_selector_frame.winfo_children():
        widget_in_frame.destroy() 
    ui_components_dict["model_buttons"] = []
    log_debug(f"setup_model_selector: Cleared existing children from {model_selector_frame.winfo_name()}.")

    for i, model_key in enumerate(model_keys):
        rb = ttk.Radiobutton(model_selector_frame, text=model_key, variable=model_var, value=model_key)
        ui_components_dict["model_buttons"].append(rb)
        log_debug(f"setup_model_selector: Created radiobutton for {model_key}, NOT PACKED.")

    if default_model in model_keys: model_var.set(default_model)
    elif model_keys: model_var.set(model_keys[0]); log_debug(f"Default model '{default_model}' not found. Using {model_keys[0]}")
    else: model_var.set(""); log_debug("Warning: No models available for selector.")
    log_debug("setup_model_selector: END")
    return True

def place_ui_components_in_layout(left_panel_ref, right_panel_ref, ui_components_dict, is_two_panel_layout=False):
    log_debug(f"place_ui_components_in_layout: START. is_two_panel_layout hint: {is_two_panel_layout}")
    log_debug(f"place_ui_components_in_layout: END")


def on_close(root_win, from_exception=False):
    log_debug(f"on_close called. From exception: {from_exception}")
    if hasattr(on_close, 'stopping') and on_close.stopping: log_debug("on_close: Already stopping."); return
    on_close.stopping = True
    from app.tk_ui_callbacks import _stop_all_processing_logic
    _stop_all_processing_logic()
    if root_win and root_win.winfo_exists(): log_debug("Destroying root window."); root_win.destroy()
    else: log_debug("Root window does not exist or already destroyed.")
    log_debug("Application cleanup finished."); delattr(on_close, 'stopping')
    if from_exception: sys.exit(0)

def launch_app():
    log_debug("launch_app: START")
    root = tk.Tk()
    root.title("Vehicle Detection and Tracking")
    root.configure(background=config.COLOR_BACKGROUND)
    log_debug(f"launch_app: Root window created. Initial reported geometry (pre-update): {root.geometry()}")

    app_frame = ttk.Frame(root, style="TFrame", padding=config.SPACING_MEDIUM)
    app_frame.pack(fill="both", expand=True)
    log_debug(f"launch_app: app_frame created and packed. App_frame actual size (before content): {app_frame.winfo_width()}x{app_frame.winfo_height()}")

    app_frame.columnconfigure(0, weight=1, minsize=300, uniform="left_group")
    app_frame.columnconfigure(1, weight=0, minsize=0, uniform="right_group") 
    app_frame.rowconfigure(0, weight=0) 
    app_frame.rowconfigure(1, weight=1) 
    log_debug(f"launch_app: app_frame columns configured (col1 weight=0 initially).")

    title_frame_main = ttk.Frame(app_frame, style="Card.TFrame")
    title_frame_main.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, config.SPACING_MEDIUM))
    title_label_main = ttk.Label(title_frame_main, text="Vehicle Detection and Tracking", style="Title.TLabel", font=config.FONT_TITLE)
    title_label_main.pack(padx=config.SPACING_LARGE, pady=config.SPACING_MEDIUM)
    root.update_idletasks() 
    log_debug(f"launch_app: Title frame gridded. Title_frame actual size: {title_frame_main.winfo_width()}x{title_frame_main.winfo_height()}")

    left_panel_main = ttk.Frame(app_frame, style="TFrame")
    left_panel_main.grid(row=1, column=0, columnspan=2, sticky="nsew") 
    root.update_idletasks() # Allow left_panel_main to get an initial size
    log_debug(f"launch_app: left_panel_main gridded (span 2). Left_panel actual size: {left_panel_main.winfo_width()}x{left_panel_main.winfo_height()}")

    right_panel_main = ttk.Frame(app_frame, style="TFrame")
    right_panel_main.grid_remove() 
    log_debug(f"launch_app: right_panel_main created and grid_removed.")

    app_globals.ui_references = {
        "root": root, "app_frame": app_frame, "left_panel": left_panel_main,
        "right_panel": right_panel_main, "title_frame": title_frame_main
    }
    log_debug("launch_app: ui_references populated.")

    ui_components_dict = create_ui_components(root, left_panel_main, right_panel_main)
    app_globals.ui_references["ui_components_dict"] = ui_components_dict
    log_debug("launch_app: ui_components_dict created and stored.")

    # Ensure all potentially visible frames are explicitly forgotten before first hide_loading call
    for frame_key in ["file_upload_frame", "model_selector_frame", "process_buttons_frame", "sliders_frame", "video_player_container"]:
        frame_widget = ui_components_dict.get(frame_key)
        if frame_widget:
            if frame_widget.winfo_manager() == 'pack': frame_widget.pack_forget()
            elif frame_widget.winfo_manager() == 'grid': frame_widget.grid_remove()
            log_debug(f"launch_app: Ensured '{frame_key}' is initially hidden (manager: {frame_widget.winfo_manager()}).")
    
    root.update_idletasks() 
    log_debug(f"launch_app: All component frames ensured hidden. Root geo: {root.geometry()}")

    place_ui_components_in_layout(left_panel_main, right_panel_main, ui_components_dict, is_two_panel_layout=False)
    root.protocol("WM_DELETE_WINDOW", lambda: on_close(root))

    if not setup_model_selector(ui_components_dict):
        log_debug("Model selector setup failed."); root.after(100, lambda: on_close(root)); root.mainloop(); return
    init_callbacks(root, ui_components_dict)

    log_debug("launch_app: --- Calculating Initial Window Size (Post UI component creation) ---")
    
    file_upload_frame_for_sizing = ui_components_dict.get("file_upload_frame")
    _initial_pack_for_sizing(file_upload_frame_for_sizing, "file_upload_frame")
    
    root.update_idletasks() 
    log_debug(f"launch_app: Root geometry after update_idletasks and temp packing 'file_upload_frame': {root.geometry()}")

    title_h = title_frame_main.winfo_reqheight()
    # Use app_frame's column 0 configured minsize as a base for left_w_req
    left_w_req = app_frame.grid_bbox(column=0, row=1)[2] if app_frame.grid_bbox(column=0, row=1) else 350 # Fallback to a fixed sensible width
    left_h_req = file_upload_frame_for_sizing.winfo_reqheight() if file_upload_frame_for_sizing and file_upload_frame_for_sizing.winfo_ismapped() else 80 
    
    log_debug(f"launch_app: Measured initial req sizes: TitleH={title_h}, LeftW_from_app_frame_col0={left_w_req}, LeftH_from_fileupload={left_h_req}")
    _initial_unpack_for_sizing(file_upload_frame_for_sizing, "file_upload_frame")
    # Ensure model_selector_frame is also forgotten here, as it should NOT contribute to initial minimal size
    _initial_unpack_for_sizing(ui_components_dict.get("model_selector_frame"), "model_selector_frame")
    root.update_idletasks()

    try:
        padding_list = app_frame.cget("padding")
        app_frame_padx = int(padding_list[0]) + int(padding_list[2]) if len(padding_list) == 4 else int(padding_list[0]) * 2
        app_frame_pady = int(padding_list[1]) + int(padding_list[3]) if len(padding_list) == 4 else int(padding_list[1]) * 2
    except:
        app_frame_padx = app_frame_pady = config.SPACING_MEDIUM * 2

    # Fixed estimates for target_two_panel_size
    fixed_left_panel_w_est = 380 
    fixed_left_panel_h_est = 450 # Approximate height for all left controls
    default_right_panel_w_est = config.DEFAULT_VIDEO_WIDTH + (config.SPACING_MEDIUM * 2) 
    default_right_panel_h_est = config.DEFAULT_VIDEO_HEIGHT + (config.SPACING_LARGE * 3) # video + controls
    log_debug(f"launch_app: Using fixed estimates for target_two_panel_size: Left W/H={fixed_left_panel_w_est}/{fixed_left_panel_h_est}, Right W/H={default_right_panel_w_est}/{default_right_panel_h_est}")
    
    two_panel_w = fixed_left_panel_w_est + config.SPACING_MEDIUM + default_right_panel_w_est + app_frame_padx + 40
    two_panel_h = title_h + config.SPACING_MEDIUM + max(fixed_left_panel_h_est, default_right_panel_h_est) + app_frame_pady + 60
    log_debug(f"launch_app: Calculated target_two_panel_size: {two_panel_w}x{two_panel_h}")
    
    # Initial single panel size:
    single_panel_w = left_w_req + app_frame_padx + 40 
    single_panel_h = title_h + config.SPACING_MEDIUM + left_h_req + (config.SPACING_MEDIUM * 3) + app_frame_pady + 60 # Increased buffer slightly
    log_debug(f"launch_app: Calculated single_panel_size (initial minimal): {single_panel_w}x{single_panel_h}")
    
    root.geometry(f"{single_panel_w}x{single_panel_h}")
    log_debug(f"launch_app: Set initial root geometry to: {single_panel_w}x{single_panel_h}")
    
    root.minsize(single_panel_w, single_panel_h)
    log_debug(f"launch_app: Set root minsize to: {single_panel_w}x{single_panel_h}")
    
    app_globals.ui_references['target_two_panel_size'] = (two_panel_w, two_panel_h)

    hide_loading_and_update_controls() 
    log_debug("launch_app: Called initial hide_loading_and_update_controls.")

    default_model_to_load = ui_components_dict['model_var'].get()
    if default_model_to_load:
        log_debug(f"launch_app: Loading default model: {default_model_to_load}")
        show_loading(f"Initializing with model: {default_model_to_load}...")
        def initial_model_load_task():
            initial_load_model(default_model_to_load)
            if root.winfo_exists(): 
                 root.after(0, hide_loading_and_update_controls) 
        threading.Thread(target=initial_model_load_task, daemon=True).start()
    else:
        log_debug("launch_app: No default model selected. UI should be in initial state.")
        if root.winfo_exists(): root.after(10, root.update_idletasks)

    log_debug("launch_app: Starting Tkinter main loop...")
    try:
        root.mainloop()
    except KeyboardInterrupt:
        log_debug("KeyboardInterrupt caught in main_app. Cleaning up...")
        on_close(root, from_exception=True)
    finally:
        log_debug("launch_app: Application exited main loop.")

if __name__ == "__main__":
    print("main_app.py executed directly. For proper execution, including command-line argument handling (like --debug), please use run_app.py from the project root directory.")
    
    if 'config' not in sys.modules:
        from app import config as main_config
    else:
        main_config = sys.modules['app.config']

    if "--debug" in sys.argv:
        print("main_app.py direct run: --debug flag detected. Enabling debug mode in config.")
        main_config.IS_DEBUG_MODE = True
        
    initialize_logging() 

    if main_config.IS_DEBUG_MODE:
        log_debug("main_app.py direct run: Debug mode is ON.")
    else:
        log_debug("main_app.py direct run: Debug mode is OFF.") 

    launch_app()
