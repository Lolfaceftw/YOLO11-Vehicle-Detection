"""
Control Handlers Module
Handles UI control interactions including process buttons, video controls, and sliders.
"""
import time
import cv2
from tkinter import messagebox

from . import _ui_shared_refs as refs
from . import _ui_loading_manager as loading_manager
from . import _ui_file_async as file_async
from . import _ui_video_async as video_async
from . import _ui_seek_optimizer as seek_optimizer
from . import globals as app_globals
from .logger_setup import log_debug
from .video_handler import format_time_display


def on_process_button_click():
    """Handle process button click for real-time processing."""
    log_debug("on_process_button_click: 'Process Real-time' button pressed.")
    
    root = refs.get_root()
    ui_comps = refs.ui_components
    
    if not ui_comps or root is None or not root.winfo_exists():
        log_debug("Process button: UI components or root window not available.")
        return
    
    if not app_globals.active_model_object_global:
        log_debug("Process button: No model loaded.")
        messagebox.showwarning("No Model", "Please select and load a model before processing.")
        return
    
    if not app_globals.current_uploaded_file_path_global and not app_globals.uploaded_file_info.get('path'):
        log_debug("Process button: No file uploaded.")
        messagebox.showwarning("No File", "Please upload a file before processing.")
        return
    
    file_path = app_globals.current_uploaded_file_path_global or app_globals.uploaded_file_info.get('path')
    
    # Check if it's an image file
    if file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tiff')):
        log_debug("Process button: Processing image file.")
        loading_manager.show_loading("Processing image...")
        file_async.run_image_processing_in_thread(file_path)
        return
    
    # Handle video file
    if not file_path.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
        log_debug("Process button: Unsupported file type.")
        messagebox.showerror("Unsupported File", "Please upload a supported image or video file.")
        return
    
    log_debug("Process button: Starting real-time video processing.")
    
    # Reset video processing flags
    app_globals.stop_video_processing_flag.clear()
    app_globals.video_paused_flag.clear()
    
    try:
        with app_globals.video_access_lock:
            if app_globals.video_capture_global is None or not app_globals.video_capture_global.isOpened():
                log_debug("Process button: Video capture not available.")
                messagebox.showerror("Video Error", "Video file is not properly loaded.")
                return
            
            # Reset to beginning
            app_globals.video_capture_global.set(cv2.CAP_PROP_POS_FRAMES, 0)
            app_globals.current_frame_number_global = 0
        
        # Update UI buttons
        ui_comps["play_pause_button"].config(text="Pause")
        ui_comps["process_button"].state(['disabled'])
        ui_comps["fast_process_button"].state(['disabled'])
        
        # Start video playback loop
        app_globals.is_playing_via_after_loop = True
        video_async._video_playback_loop()
        
        log_debug("Real-time video processing started.")
        
    except Exception as e:
        log_debug(f"Error starting real-time processing: {e}", exc_info=True)
        messagebox.showerror("Processing Error", f"Failed to start real-time processing: {str(e)}")


def on_fast_process_button_click(stop_all_processing_logic_ref):
    """Handle fast process button click."""
    log_debug("on_fast_process_button_click: 'Fast Process Video' button pressed.")
    
    if not app_globals.active_model_object_global:
        log_debug("Fast process button: No model loaded.")
        messagebox.showwarning("No Model", "Please select and load a model before processing.")
        return
    
    if not app_globals.current_uploaded_file_path_global and not app_globals.uploaded_file_info.get('path'):
        log_debug("Fast process button: No file uploaded.")
        messagebox.showwarning("No File", "Please upload a video file before processing.")
        return
    
    uploaded_file_path = app_globals.current_uploaded_file_path_global or app_globals.uploaded_file_info.get('path')
    loading_manager.show_loading("Starting fast video processing...")
    video_async.run_fast_video_processing_in_thread(uploaded_file_path, stop_all_processing_logic_ref)


def toggle_play_pause():
    """Toggle between play and pause for video playback."""
    log_debug("toggle_play_pause: Play/Pause button pressed.")
    
    root = refs.get_root()
    ui_comps = refs.ui_components
    
    if not ui_comps or root is None or not root.winfo_exists():
        log_debug("Play/Pause: UI components or root window not available.")
        return
    
    play_pause_btn = ui_comps.get("play_pause_button")
    if not play_pause_btn:
        log_debug("Play/Pause: Button not found.")
        return
    
    current_text = play_pause_btn.cget("text")
    
    if current_text == "Play":
        log_debug("Starting video playback.")
        
        if not app_globals.video_capture_global or not app_globals.video_capture_global.isOpened():
            log_debug("Play: Video capture not available.")
            messagebox.showerror("Video Error", "No video loaded or video capture failed.")
            return
        
        app_globals.video_paused_flag.clear()
        app_globals.stop_video_processing_flag.clear()
        
        if not app_globals.is_playing_via_after_loop:
            app_globals.is_playing_via_after_loop = True
            video_async._video_playback_loop()
        
        play_pause_btn.config(text="Pause")
        if ui_comps.get("process_button"):
            ui_comps["process_button"].state(['disabled'])
        
    elif current_text == "Pause":
        log_debug("Pausing video playback.")
        app_globals.video_paused_flag.set()
        play_pause_btn.config(text="Play")
        if ui_comps.get("process_button"):
            ui_comps["process_button"].state(['!disabled'])


def stop_video_stream_button_click(stop_all_processing_logic_ref):
    """Handle stop button click to stop video processing."""
    log_debug("stop_video_stream_button_click: Stop button pressed.")
    
    root = refs.get_root()
    ui_comps = refs.ui_components
    
    if not ui_comps or root is None or not root.winfo_exists():
        log_debug("Stop button: UI components or root window not available.")
        return
    
    # Stop all processing
    if stop_all_processing_logic_ref:
        stop_all_processing_logic_ref()
    
    # Cancel any pending seek operations
    seek_optimizer.cancel_all_seeks()
    
    # Reset UI state
    if ui_comps.get("play_pause_button"):
        ui_comps["play_pause_button"].config(text="Play")
    
    if ui_comps.get("process_button"):
        ui_comps["process_button"].state(['!disabled'])
    
    # Reset video to beginning if video is loaded
    if app_globals.video_capture_global and app_globals.video_capture_global.isOpened():
        with app_globals.video_access_lock:
            app_globals.video_capture_global.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, first_frame = app_globals.video_capture_global.read()
            app_globals.video_capture_global.set(cv2.CAP_PROP_POS_FRAMES, 0)
            
            if ret and ui_comps.get("video_display"):
                ui_comps["video_display"].update_frame(first_frame)
        
        app_globals.current_frame_number_global = 0
        app_globals.current_video_meta['current_frame'] = 0
        ui_comps["progress_var"].set(0)
        
        current_time_sec = 0
        total_time_sec = app_globals.current_video_meta.get('duration_seconds', 0)
        ui_comps["time_label"].config(text=format_time_display(current_time_sec, total_time_sec))
        ui_comps["current_frame_label"].config(text=f"Frame: 0 / {app_globals.current_video_meta.get('total_frames', 0)}")
    
    log_debug("Video stream stopped and UI reset.")


def handle_slider_value_change(*args):
    """Handle progress slider value changes with optimized seeking."""
    ui_comps = refs.ui_components
    
    if not ui_comps or not ui_comps.get("progress_var"):
        return
    
    # Skip if this is a programmatic update to prevent feedback loops
    if app_globals.is_programmatic_slider_update:
        return
    
    if app_globals.is_playing_via_after_loop:
        return
    
    if not app_globals.video_capture_global or not app_globals.video_capture_global.isOpened():
        return
    
    total_frames = app_globals.current_video_meta.get('total_frames', 0)
    if total_frames <= 0:
        return
    
    # Get target frame directly from slider (slider now uses frame numbers)
    target_frame = ui_comps["progress_var"].get()
    target_frame = max(0, min(target_frame, total_frames - 1))
    
    # Determine if real-time processing is active
    is_real_time = ui_comps.get("play_pause_button") and ui_comps["play_pause_button"].cget("text") == "Pause"
    
    # Use optimized seek system with debouncing
    seek_optimizer.request_seek(target_frame, is_real_time_mode=is_real_time, force_immediate=False)


def _execute_slider_seek():
    """Legacy function - now handled by optimized seek system."""
    # This function is kept for compatibility but functionality moved to handle_slider_value_change
    pass


def handle_slider_click_press(event):
    """Handle slider click press event to calculate exact position from click coordinates."""
    ui_comps = refs.ui_components
    
    if not ui_comps or not ui_comps.get("progress_var") or not ui_comps.get("progress_slider"):
        return
    
    if not app_globals.video_capture_global or not app_globals.video_capture_global.isOpened():
        return
    
    total_frames = app_globals.current_video_meta.get('total_frames', 0)
    if total_frames <= 0:
        return
    
    slider = ui_comps["progress_slider"]
    
    # Calculate the relative position of the click (0.0 to 1.0)
    slider_width = slider.winfo_width()
    click_x = event.x
    
    # Account for slider padding/margins - Tkinter Scale has some internal padding
    # Typically about 8-10 pixels on each side for the Scale widget
    padding = 10
    effective_width = max(1, slider_width - 2 * padding)
    adjusted_x = max(0, click_x - padding)
    
    relative_pos = max(0.0, min(1.0, adjusted_x / effective_width))
    
    # Convert to frame number
    target_frame = int(relative_pos * (total_frames - 1))
    target_frame = max(0, min(target_frame, total_frames - 1))
    
    progress_percentage = (target_frame / total_frames) * 100 if total_frames > 0 else 0
    log_debug(f"Slider click press: Click at x={click_x}, width={slider_width}, relative_pos={relative_pos:.3f}, target_frame={target_frame} ({progress_percentage:.1f}%)")
    
    # Set the slider value directly to override Tkinter's default behavior
    app_globals.is_programmatic_slider_update = True
    try:
        ui_comps["progress_var"].set(target_frame)
    finally:
        app_globals.is_programmatic_slider_update = False
    
    # Trigger immediate seek
    is_real_time = ui_comps.get("play_pause_button") and ui_comps["play_pause_button"].cget("text") == "Pause"
    seek_optimizer.request_seek(target_frame, is_real_time_mode=is_real_time, force_immediate=True)


def handle_slider_click_release(event):
    """Handle slider click release event with optimized seeking."""
    log_debug("handle_slider_click_release: Slider clicked/released.")
    
    ui_comps = refs.ui_components
    
    if not ui_comps or not ui_comps.get("progress_var"):
        log_debug("Slider click: UI components not available.")
        return
    
    if not app_globals.video_capture_global or not app_globals.video_capture_global.isOpened():
        log_debug("Slider click: No video loaded.")
        return
    
    total_frames = app_globals.current_video_meta.get('total_frames', 0)
    if total_frames <= 0:
        log_debug("Slider click: Invalid total frames.")
        return
    
    target_frame = ui_comps["progress_var"].get()
    target_frame = max(0, min(target_frame, total_frames - 1))
    
    # Check if we're already at the target frame to avoid duplicate seeks
    current_frame = app_globals.current_frame_number_global
    if abs(current_frame - target_frame) <= 1:  # Allow 1 frame tolerance
        log_debug(f"Slider click release: Already at target frame {target_frame}, skipping duplicate seek")
        return
    
    progress_percentage = (target_frame / total_frames) * 100 if total_frames > 0 else 0
    log_debug(f"Slider click seek: Moving to frame {target_frame} ({progress_percentage:.1f}%)")
    
    is_real_time = ui_comps.get("play_pause_button") and ui_comps["play_pause_button"].cget("text") == "Pause"
    
    # Use optimized seek system with immediate execution for click events
    seek_optimizer.request_seek(target_frame, is_real_time_mode=is_real_time, force_immediate=True)