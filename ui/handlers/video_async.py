"""
Video Async Operations Module
Handles video playback, seeking, and fast processing operations in separate threads.
"""
import threading
import time
import cv2
import tkinter as tk

from . import shared_refs as refs
from . import loading_manager
from app.core import globals as app_globals
from app.utils.logger_setup import log_debug
from app.processing.frame_processor import process_frame_yolo
from app.processing.video_handler import format_time_display, fast_video_processing_thread_func

log_debug("ui.handlers.video_async module initialized.")

def _video_playback_loop():
    """Main video playback loop running in root.after() calls."""
    root = refs.get_root()
    ui_comps = refs.ui_components
    
    # Primary check: If playback is not supposed to be active, exit immediately.
    if not app_globals.is_playing_via_after_loop:
        log_debug("Video playback loop: is_playing_via_after_loop is False. Terminating loop.")
        app_globals.after_id_playback_loop = None # Ensure no dangling ID
        return

    if not ui_comps or root is None or not root.winfo_exists():
        log_debug("Video playback loop: UI components or root window not available. Stopping loop.")
        app_globals.is_playing_via_after_loop = False
        app_globals.after_id_playback_loop = None
        return
    
    if app_globals.stop_video_processing_flag.is_set():
        log_debug("Video playback loop: Stop flag detected. Ending playback loop.")
        app_globals.is_playing_via_after_loop = False 
        app_globals.after_id_playback_loop = None
        return
    
    if app_globals.video_paused_flag.is_set():
        if root.winfo_exists() and app_globals.is_playing_via_after_loop: # Continue polling if paused but meant to be playing
            app_globals.after_id_playback_loop = root.after(50, _video_playback_loop)
        else:
            # If not supposed to be playing, ensure no reschedule
            app_globals.after_id_playback_loop = None
        return
    
    with app_globals.video_access_lock:
        if app_globals.video_capture_global is None or not app_globals.video_capture_global.isOpened():
            app_globals.is_playing_via_after_loop = False 
            app_globals.after_id_playback_loop = None
            return
        
        ret, frame = app_globals.video_capture_global.read()
        if not ret:
            app_globals.is_playing_via_after_loop = False 
            app_globals.after_id_playback_loop = None
            return
        
        app_globals.current_frame_number_global = int(app_globals.video_capture_global.get(cv2.CAP_PROP_POS_FRAMES))
        app_globals.current_video_meta['current_frame'] = app_globals.current_frame_number_global
        
        output_frame = frame.copy()
        
        # Process frame with YOLO if model is available
        if app_globals.active_model_object_global:
            try:
                output_frame, _ = process_frame_yolo(
                    output_frame, app_globals.active_model_object_global, app_globals.active_class_list_global,
                    persist_tracking=True, is_video_mode=True,
                    active_filter_list=app_globals.active_processed_class_filter_global,
                    current_conf_thresh=app_globals.conf_threshold_global,
                    current_iou_thresh=app_globals.iou_threshold_global
                )
            except Exception as e_process:
                log_debug(f"Frame processing error: {e_process}")
                output_frame = frame
        
        # Update UI
        if ui_comps.get("video_display"):
            ui_comps["video_display"].update_frame(output_frame)
        
        # Update progress and time using video metadata
        total_frames = app_globals.current_video_meta.get('total_frames', 0)
        fps = app_globals.current_video_meta.get('fps', 30.0)
        
        # Update slider with programmatic flag to prevent feedback loops
        # Use frame numbers directly since slider is configured with frame range
        app_globals.is_programmatic_slider_update = True
        try:
            ui_comps["progress_var"].set(app_globals.current_frame_number_global)
        finally:
            app_globals.is_programmatic_slider_update = False
        
        current_time_sec = app_globals.current_frame_number_global / fps if fps > 0 else 0
        total_time_sec = app_globals.current_video_meta.get('duration_seconds', 0)
        ui_comps["time_label"].config(text=format_time_display(current_time_sec, total_time_sec))
        
        ui_comps["current_frame_label"].config(text=f"Frame: {app_globals.current_frame_number_global} / {total_frames}")
        ui_comps["fps_label"].config(text=f"FPS: {fps:.1f}")
    
    if root.winfo_exists():
        fps = app_globals.current_video_meta.get('fps', 30.0)
        delay_ms = max(1, int(1000 / fps)) if fps > 0 else 33
        # Only reschedule if still intended to be playing
        if app_globals.is_playing_via_after_loop:
            app_globals.after_id_playback_loop = root.after(delay_ms, _video_playback_loop)
        else:
            log_debug("Video playback loop: Playback no longer active at rescheduling point. Not rescheduling.")
            app_globals.after_id_playback_loop = None


def _perform_seek_action_in_thread(target_frame_number, is_real_time_mode=False):
    """
    Legacy seek function - now delegates to optimized seek system.
    Maintained for backward compatibility.
    """
    log_debug(f"_perform_seek_action_in_thread (legacy): Delegating to optimized seek system for frame {target_frame_number}")
    
    # Import here to avoid circular imports
    from . import seek_optimizer
    
    # Delegate to the optimized seek system
    seek_optimizer.request_seek(target_frame_number, is_real_time_mode, force_immediate=True)


def run_fast_video_processing_in_thread(uploaded_video_path, stop_all_processing_logic_ref):
    """Start fast video processing in a separate thread."""
    log_debug(f"run_fast_video_processing_in_thread: Starting fast processing for {uploaded_video_path}")
    
    if app_globals.fast_processing_active_flag.is_set():
        log_debug("Fast processing already active. Ignoring new request.")
        return
    
    # Cancel any pending seek operations before starting fast processing
    from . import seek_optimizer
    seek_optimizer.cancel_all_seeks()
    
    def fast_process_task():
        """Fast processing task that runs in a separate thread."""
        log_debug("Fast processing task started.")
        root = refs.get_root() # Get root early for UI updates
        
        try:
            app_globals.fast_processing_active_flag.set()
            app_globals.stop_fast_processing_flag.clear()

            # Immediately switch to the fast processing progress UI
            if root and root.winfo_exists():
                log_debug("Scheduling show_fast_processing_progress_ui from fast_process_task.")
                root.after(0, loading_manager.show_fast_processing_progress_ui)
            else:
                log_debug("fast_process_task: Root window not available for initial UI update.")
            
            # Give UI a moment to update before heavy processing starts
            # This helps ensure the "Starting..." overlay is hidden and progress UI appears quickly.
            time.sleep(0.1)

            success = fast_video_processing_thread_func(
                uploaded_video_path,
                progress_callback=loading_manager.update_fast_progress
            )
            
            log_debug(f"Fast processing completed. Success: {success}")
            
        except Exception as e:
            log_debug(f"Error in fast processing task: {e}", exc_info=True)
        finally:
            app_globals.fast_processing_active_flag.clear()
            root = refs.get_root()
            if root and root.winfo_exists():
                root.after(0, loading_manager.hide_loading_and_update_controls)
            log_debug("Fast processing task finished.")
    
    app_globals.fast_video_processing_thread = threading.Thread(target=fast_process_task, daemon=True)
    app_globals.fast_video_processing_thread.start()
    log_debug("Fast processing thread started.")