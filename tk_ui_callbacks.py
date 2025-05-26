# tk_ui_callbacks.py (Refactored)
"""
Main module for Tkinter UI Callbacks initialization and core utilities.
Connects UI elements to their respective handlers from helper modules.
"""
import sys
import time 
import tkinter as tk 
from . import _ui_shared_refs as refs
from . import _ui_event_handlers as event_handlers
from . import _ui_loading_manager as loading_manager 
from . import _ui_seek_optimizer as seek_optimizer
from . import globals as app_globals
from .logger_setup import log_debug
from .video_handler import _cleanup_processed_video_temp_file

def _stop_all_processing_logic():
    """Stop all video processing, playback, and fast processing logic. Also releases video capture."""
    log_debug("Stopping all video processing and playback logic.")
    root = refs.get_root() 
    
    app_globals.stop_video_processing_flag.set() 

    if app_globals.is_playing_via_after_loop and app_globals.after_id_playback_loop: 
        if root and root.winfo_exists():
            try:
                root.after_cancel(app_globals.after_id_playback_loop)
                log_debug(f"Cancelled root.after playback loop with ID: {app_globals.after_id_playback_loop}")
            except tk.TclError:
                log_debug(f"Error cancelling root.after playback loop ID: {app_globals.after_id_playback_loop} (already cancelled or window gone).")
        app_globals.after_id_playback_loop = None
    app_globals.is_playing_via_after_loop = False 

    if app_globals.video_thread and app_globals.video_thread.is_alive(): 
        log_debug("Stopping legacy video_thread (if any)...")
        app_globals.video_thread.join(timeout=0.5) 
        if app_globals.video_thread.is_alive():
            log_debug("Legacy video_thread did not join in time.")
        app_globals.video_thread = None
    
    app_globals.video_paused_flag.clear() 

    if app_globals.fast_video_processing_thread and app_globals.fast_video_processing_thread.is_alive():
        app_globals.stop_fast_processing_flag.set()
        log_debug("Waiting for fast processing thread to join...")
        app_globals.fast_video_processing_thread.join(timeout=1.0) 
        if app_globals.fast_video_processing_thread.is_alive():
            log_debug("Fast processing thread did not join in time.")
        app_globals.fast_video_processing_thread = None
    app_globals.stop_fast_processing_flag.clear() 
    app_globals.fast_processing_active_flag.clear() 
    
    with app_globals.video_access_lock:
        if app_globals.video_capture_global and app_globals.video_capture_global.isOpened():
            log_debug("Releasing video capture object.")
            app_globals.video_capture_global.release()
        app_globals.video_capture_global = None 
    
    if app_globals.slider_debounce_timer and root and root.winfo_exists():
        try:
            root.after_cancel(app_globals.slider_debounce_timer)
        except tk.TclError: pass 
        app_globals.slider_debounce_timer = None

    # Cancel all seek operations
    seek_optimizer.cancel_all_seeks()

    _cleanup_processed_video_temp_file()
    app_globals.stop_video_processing_flag.clear() 
    log_debug("All processing logic stopped and resources potentially released.")


def init_callbacks(root_win, components_dict):
    """Initialize callbacks with references to UI components.
    
    Args:
        root_win: Root Tkinter window
        components_dict: Dictionary of UI components
    """
    refs.init_shared_refs(components_dict, root_win)
    event_handlers.init_event_handlers(_stop_all_processing_logic) 

    components_dict["file_upload_button"].config(command=event_handlers.handle_file_upload)
    components_dict["custom_model_button"].config(command=event_handlers.handle_custom_model_upload)
    components_dict["process_button"].config(command=event_handlers.on_process_button_click)
    components_dict["fast_process_button"].config(command=event_handlers.on_fast_process_button_click)
    
    components_dict["iou_var"].trace_add("write", event_handlers.handle_iou_change)
    components_dict["conf_var"].trace_add("write", event_handlers.handle_conf_change)
    components_dict["model_var"].trace_add("write", event_handlers.handle_model_selection_change)
    
    components_dict["play_pause_button"].config(command=event_handlers.toggle_play_pause)
    components_dict["stop_button"].config(command=event_handlers.stop_video_stream_button_click)
    
    components_dict["progress_var"].trace_add("write", event_handlers.handle_slider_value_change)
    progress_slider_widget = components_dict.get("progress_slider")
    if progress_slider_widget:
        progress_slider_widget.bind("<Button-1>", event_handlers.handle_slider_click_press)
        progress_slider_widget.bind("<ButtonRelease-1>", event_handlers.handle_slider_click_release)
    
    # Removed stdout/stderr redirection as console output box is removed
    # sys.stdout = RedirectText(components_dict["output_text"])
    # sys.stderr = RedirectText(components_dict["output_text"]) 

    log_debug("Tkinter callbacks initialized.")
