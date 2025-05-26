# _ui_event_handlers.py
"""
Contains direct event handlers for Tkinter UI elements.
"""
import os
import threading
from tkinter import filedialog, messagebox
import cv2 
import time 

from . import _ui_shared_refs as refs
from . import _ui_loading_manager as loading_manager
from . import _ui_async_logic as async_logic 
from . import globals as app_globals
from . import config
from .logger_setup import log_debug
from .model_loader import set_custom_model_path
from .frame_processor import process_frame_yolo

_stop_all_processing_logic_ref = None

def init_event_handlers(stop_logic_func):
    global _stop_all_processing_logic_ref
    _stop_all_processing_logic_ref = stop_logic_func
    log_debug("Event handlers initialized.")


def handle_file_upload():
    """Handle file upload button click."""
    log_debug("handle_file_upload: 'Upload File' button pressed.")
    root = refs.get_root()
    ui_comps = refs.ui_components
    if not ui_comps or root is None or not root.winfo_exists():
        log_debug("handle_file_upload: UI components or root window not available.")
        return
    
    file_path = filedialog.askopenfilename(
        title="Select Image or Video",
        filetypes=[
            ("Media files", "*.jpg *.jpeg *.png *.mp4 *.avi *.mov *.mkv"),
            ("Images", "*.jpg *.jpeg *.png"), 
            ("Videos", "*.mp4 *.avi *.mov *.mkv"),
            ("All files", "*.*")
        ]
    )
    
    if not file_path:
        log_debug("handle_file_upload: No file selected.")
        return

    file_name = os.path.basename(file_path)
    log_debug(f"handle_file_upload: File selected: {file_path}")
    if ui_comps.get("file_upload_label"):
        ui_comps["file_upload_label"].config(text=file_name if len(file_name) < 50 else file_name[:47]+"...")
    
    loading_manager.show_loading("Processing uploaded file...") 
    if root and root.winfo_exists(): root.update() 
    
    threading.Thread(target=async_logic._process_uploaded_file_in_thread, 
                     args=(file_path, _stop_all_processing_logic_ref), 
                     daemon=True).start()
    log_debug(f"File upload: Worker thread started for {file_path}.")


def handle_custom_model_upload():
    """Handle custom model file selection."""
    log_debug("handle_custom_model_upload: 'Browse .pt File' button pressed.")
    root = refs.get_root()
    ui_comps = refs.ui_components
    if not ui_comps or root is None or not root.winfo_exists():
        log_debug("handle_custom_model_upload: UI components or root window not available.")
        return
    
    file_path = filedialog.askopenfilename(
        title="Select Custom YOLO Model (.pt file)",
        filetypes=[
            ("PyTorch Model files", "*.pt"),
            ("All files", "*.*")
        ]
    )
    
    if not file_path:
        log_debug("handle_custom_model_upload: No model file selected.")
        return

    file_name = os.path.basename(file_path)
    log_debug(f"handle_custom_model_upload: Model file selected: {file_path}")
    
    # Update the custom model path in the model loader
    set_custom_model_path(file_path)
    
    # Update the UI label
    if ui_comps.get("custom_model_label"):
        display_name = file_name if len(file_name) < 35 else file_name[:32]+"..."
        ui_comps["custom_model_label"].config(text=display_name)
    
    # If "Select Custom Model" is currently selected, reload the model
    if ui_comps.get("model_var") and ui_comps["model_var"].get() == "Select Custom Model":
        log_debug("Custom model selected and 'Select Custom Model' is active. Reloading model...")
        async_logic.run_model_load_in_thread("Select Custom Model", _stop_all_processing_logic_ref)
    
    log_debug(f"Custom model file set: {file_path}")


def handle_model_selection_change(*args):
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
        from .model_loader import get_custom_model_path
        custom_path = get_custom_model_path()
        if not custom_path or not os.path.exists(custom_path):
            log_debug("Custom model selected but no valid .pt file has been chosen.")
            messagebox.showwarning("Custom Model", "Please select a valid .pt model file using the 'Browse .pt File' button.")
            return
    
    if selected_model == app_globals.active_model_key and app_globals.active_model_object_global is not None:
        log_debug(f"Model {selected_model} is already loaded and active. No action taken.")
        return

    log_debug(f"Selected model for loading: {selected_model}")
    async_logic.run_model_load_in_thread(selected_model, _stop_all_processing_logic_ref)


def on_process_button_click(): 
    """Handle process button click for real-time video processing."""
    log_debug("on_process_button_click: 'Process Real-time' button pressed.")
    root = refs.get_root()
    ui_comps = refs.ui_components
    
    if not app_globals.uploaded_file_info.get('path'): 
        messagebox.showerror("Error", "Please upload a file first.")
        return
    if not app_globals.active_model_object_global:
        messagebox.showerror("Error", "No model loaded. Please select a model.")
        return
    
    file_type = app_globals.uploaded_file_info.get('file_type', '')
    file_path = app_globals.uploaded_file_info.get('path', '') 
    
    if file_type == 'image':
        log_debug(f"Processing image: {file_path}")
        async_logic.run_image_processing_in_thread(file_path) 
            
    elif file_type == 'video':
        log_debug(f"Preparing video for real-time analysis using root.after() loop: {file_path}")
        loading_manager.show_loading("Preparing real-time analysis...")
        if root and root.winfo_exists(): root.update_idletasks()

        _stop_all_processing_logic_ref() 

        try:
            with app_globals.video_access_lock:
                if app_globals.video_capture_global and app_globals.video_capture_global.isOpened():
                    app_globals.video_capture_global.release()
                app_globals.video_capture_global = cv2.VideoCapture(file_path)
                if not app_globals.video_capture_global.isOpened():
                    raise ValueError(f"Could not open video file: {file_path}")
                
                app_globals.current_video_meta['fps'] = app_globals.video_capture_global.get(cv2.CAP_PROP_FPS)
                app_globals.current_video_meta['total_frames'] = int(app_globals.video_capture_global.get(cv2.CAP_PROP_FRAME_COUNT))
                app_globals.current_video_meta['duration_seconds'] = \
                    app_globals.current_video_meta['total_frames'] / app_globals.current_video_meta['fps'] if app_globals.current_video_meta['fps'] > 0 else 0
                app_globals.current_video_meta['current_frame'] = 0 
                if ui_comps.get("progress_var"):
                    app_globals.is_programmatic_slider_update = True
                    try: ui_comps["progress_var"].set(0)
                    finally: app_globals.is_programmatic_slider_update = False
            
            if ui_comps.get("progress_slider") and app_globals.current_video_meta['total_frames'] > 0:
                ui_comps["progress_slider"].config(to=float(app_globals.current_video_meta['total_frames']-1))
            
            app_globals.stop_video_processing_flag.clear()
            app_globals.video_paused_flag.clear()
            app_globals.is_playing_via_after_loop = True 
            
            app_globals.real_time_fps_frames_processed = 0
            app_globals.real_time_fps_last_update_time = time.perf_counter()
            app_globals.real_time_fps_display_value = 0.0
            async_logic._last_frame_display_time_ns = 0 

            if app_globals.after_id_playback_loop: 
                try: root.after_cancel(app_globals.after_id_playback_loop)
                except: pass
            app_globals.after_id_playback_loop = root.after(10, lambda: async_logic._video_playback_loop(process_frames_real_time=True))

            if ui_comps.get("play_pause_button"): ui_comps["play_pause_button"].config(text="Pause")
            loading_manager.hide_loading_and_update_controls()
            log_debug("Real-time video playback (root.after loop) initiated.")

        except Exception as e:
            log_debug(f"Error preparing video for real-time analysis: {e}", exc_info=True)
            messagebox.showerror("Error", f"Error processing video: {e}")
            _stop_all_processing_logic_ref() 
            loading_manager.hide_loading_and_update_controls()


def on_fast_process_button_click():
    """Handle fast process button click."""
    log_debug("on_fast_process_button_click: 'Fast Process Video' button pressed.")
    
    if not app_globals.uploaded_file_info.get('path'):
        messagebox.showerror("Error", "Please upload a file first.")
        return
    if not app_globals.active_model_object_global:
        messagebox.showerror("Error", "No model loaded. Please select a model.")
        return
    if app_globals.uploaded_file_info.get('file_type', '') != 'video':
        messagebox.showerror("Error", "Fast processing is only available for video files.")
        return
    
    _stop_all_processing_logic_ref()

    file_path = app_globals.uploaded_file_info.get('path')
    log_debug(f"Preparing for fast video processing: {file_path}")
    async_logic.run_fast_video_processing_in_thread(file_path, _stop_all_processing_logic_ref)


def toggle_play_pause():
    """Toggle video playback between play and pause. Can also initiate playback."""
    log_debug("toggle_play_pause: 'Play/Pause' button pressed.")
    root = refs.get_root()
    ui_comps = refs.ui_components
        
    play_pause_btn = ui_comps.get("play_pause_button")

    if app_globals.is_playing_via_after_loop:
        if app_globals.video_paused_flag.is_set(): # Resuming
            app_globals.video_paused_flag.clear()
            if play_pause_btn: play_pause_btn.config(text="Pause")
            log_debug("Video playback resumed (root.after loop).")
            
            target_fps = app_globals.current_video_meta.get('fps', 30)
            target_fps = target_fps if target_fps > 0 else 30
            target_frame_duration_ns = int((1.0 / target_fps) * 1_000_000_000)
            current_frame_at_resume = app_globals.current_video_meta.get('current_frame', 0)
            # Re-anchor _last_frame_display_time_ns for the current frame, as if it's just about to be displayed
            async_logic._last_frame_display_time_ns = time.perf_counter_ns() - target_frame_duration_ns 
            
            app_globals.real_time_fps_last_update_time = time.perf_counter()
            app_globals.real_time_fps_frames_processed = 0
            log_debug(f"Resumed. FPS timers reset. Last display time re-anchored for frame {current_frame_at_resume}.")
        else: # Pausing
            app_globals.video_paused_flag.set()
            if play_pause_btn: play_pause_btn.config(text="Play")
            log_debug("Video playback paused (root.after loop).")
        return

    is_processed_video_ready_path = app_globals.processed_video_temp_file_path_global
    if is_processed_video_ready_path and os.path.exists(is_processed_video_ready_path):
        log_debug(f"Attempting to start playback of processed video: {is_processed_video_ready_path}")
        loading_manager.show_loading("Loading processed video...")
        if root and root.winfo_exists(): root.update_idletasks()
        
        video_path_to_play = is_processed_video_ready_path 

        try:
            # _stop_all_processing_logic_ref() # DO NOT CALL here when starting NEW processed video
            app_globals.stop_video_processing_flag.clear() 
            app_globals.video_paused_flag.clear()
            
            cap = None
            for attempt in range(3): # Increased retries slightly
                with app_globals.video_access_lock:
                    if app_globals.video_capture_global and app_globals.video_capture_global.isOpened():
                        app_globals.video_capture_global.release() 
                    
                    log_debug(f"Opening processed video file for playback (attempt {attempt+1}): {video_path_to_play}")
                    cap = cv2.VideoCapture(video_path_to_play)
                    if cap.isOpened():
                        app_globals.video_capture_global = cap
                        log_debug(f"Successfully opened processed video on attempt {attempt+1}")
                        break 
                    else:
                        log_debug(f"Failed to open processed video on attempt {attempt+1}. Path: {video_path_to_play}")
                        if attempt < 2: # If not the last attempt
                            time.sleep(0.3 * (attempt + 1)) # Slightly increasing delay
            
            if not app_globals.video_capture_global or not app_globals.video_capture_global.isOpened():
                messagebox.showerror("Error", f"Could not open processed video file after retries: {video_path_to_play}")
                if root and root.winfo_exists(): root.after(0, loading_manager.hide_loading_and_update_controls)
                return

            with app_globals.video_access_lock: 
                app_globals.current_video_meta['fps'] = app_globals.video_capture_global.get(cv2.CAP_PROP_FPS)
                app_globals.current_video_meta['total_frames'] = int(app_globals.video_capture_global.get(cv2.CAP_PROP_FRAME_COUNT))
                app_globals.current_video_meta['duration_seconds'] = \
                    app_globals.current_video_meta['total_frames'] / app_globals.current_video_meta['fps'] if app_globals.current_video_meta['fps'] > 0 else 0
                app_globals.current_video_meta['current_frame'] = 0 
                if ui_comps.get("progress_var"): 
                    app_globals.is_programmatic_slider_update = True
                    try: ui_comps["progress_var"].set(0)
                    finally: app_globals.is_programmatic_slider_update = False

            if ui_comps.get("progress_slider") and app_globals.current_video_meta['total_frames'] > 0:
                 ui_comps["progress_slider"].config(to=float(app_globals.current_video_meta['total_frames']-1))
            
            app_globals.is_playing_via_after_loop = True
            app_globals.real_time_fps_frames_processed = 0
            app_globals.real_time_fps_last_update_time = time.perf_counter()
            app_globals.real_time_fps_display_value = 0.0
            async_logic._last_frame_display_time_ns = 0 

            if app_globals.after_id_playback_loop: 
                try: root.after_cancel(app_globals.after_id_playback_loop)
                except: pass
            app_globals.after_id_playback_loop = root.after(10, lambda: async_logic._video_playback_loop(process_frames_real_time=False)) 

            if play_pause_btn: play_pause_btn.config(text="Pause")
            log_debug("Processed video playback (root.after loop) initiated.")
        except Exception as e:
            log_debug(f"Error during toggle_play_pause for processed video: {e}", exc_info=True)
            messagebox.showerror("Error", f"Error playing processed video: {e}")
            _stop_all_processing_logic_ref() 
        finally:
            if root and root.winfo_exists():
                 root.after(100, loading_manager.hide_loading_and_update_controls)
        return

    if app_globals.uploaded_file_info.get('file_type') == 'video' and \
       app_globals.uploaded_file_info.get('path') and \
       not (app_globals.video_capture_global and app_globals.video_capture_global.isOpened()):
        log_debug("Raw video uploaded. Play click implies starting real-time processing.")
        on_process_button_click() 
        return

    log_debug("Toggle_play_pause: No specific action taken (e.g. no video ready).")
    if root and root.winfo_exists():
        loading_manager.hide_loading_and_update_controls()


def stop_video_stream_button_click():
    """Stop video playback or any ongoing video-related processing."""
    log_debug("stop_video_stream_button_click: 'Stop' button pressed.")
    ui_comps = refs.ui_components
    
    # Inform user that this will clear the video selection
    messagebox.showinfo("Video Selection", "Stopping process will clear the current video selection.")
    
    _stop_all_processing_logic_ref() 
    
    # Clear the video selection
    app_globals.uploaded_file_info = {}
    if ui_comps.get("file_upload_label"): 
        ui_comps["file_upload_label"].config(text="No file selected")
    
    if ui_comps.get("video_display"): ui_comps["video_display"].clear()
    app_globals.current_video_frame = None
    app_globals.current_video_meta['current_frame'] = 0
    if ui_comps.get("progress_var"): 
        app_globals.is_programmatic_slider_update = True
        try: ui_comps["progress_var"].set(0)
        finally: app_globals.is_programmatic_slider_update = False
            
    if ui_comps.get("time_label"):
         ui_comps["time_label"].config(text=async_logic.format_time_display(0, app_globals.current_video_meta.get('duration_seconds',0)))
    
    app_globals.real_time_fps_display_value = 0.0
    if ui_comps.get("fps_label"): ui_comps["fps_label"].config(text="FPS: --")
    if ui_comps.get("current_frame_label"): ui_comps["current_frame_label"].config(text="Frame: 0 / {}".format(app_globals.current_video_meta.get('total_frames', '--')))


    loading_manager.hide_loading_and_update_controls()


def handle_slider_value_change(*args): 
    """Handle changes to the progress slider variable (typically from dragging). Uses debouncing."""
    log_debug(f"handle_slider_value_change (trace on var) triggered. Programmatic update flag: {app_globals.is_programmatic_slider_update}. Args: {args}")
    root = refs.get_root()
    ui_comps = refs.ui_components
    
    if app_globals.is_programmatic_slider_update: 
        log_debug("Slider change is programmatic. No seek action from trace.")
        return 

    log_debug("Slider change from var trace (likely drag). Proceeding with debounced seek logic.")
    if not ui_comps or root is None or not root.winfo_exists():
        log_debug("Slider var trace: UI components or root window not available.")
        return
    
    progress_slider_widget = ui_comps.get("progress_slider")
    if not progress_slider_widget or \
       not (app_globals.video_capture_global and app_globals.video_capture_global.isOpened()) or \
       progress_slider_widget.cget("state") == "disabled":
        log_debug("Slider var trace: Video not ready or slider disabled.")
        return

    try:
        value = ui_comps["progress_var"].get() 
        app_globals.slider_target_frame_value = value
        log_debug(f"Slider var trace: target_frame_value set to: {value}")
    except Exception: 
        log_debug("Error getting slider value from var trace.", exc_info=True)
        return

    current_time_secs = 0
    fps = app_globals.current_video_meta.get('fps', 0)
    if fps > 0: current_time_secs = app_globals.slider_target_frame_value / fps
    
    if ui_comps.get("time_label"):
        ui_comps["time_label"].config(
            text=async_logic.format_time_display(current_time_secs, app_globals.current_video_meta.get('duration_seconds', 0))
        )
    if ui_comps.get("current_frame_label"):
        ui_comps["current_frame_label"].config(text=f"Frame: {app_globals.slider_target_frame_value} / {app_globals.current_video_meta.get('total_frames', '--')}")

    
    if app_globals.slider_debounce_timer:
        try: root.after_cancel(app_globals.slider_debounce_timer)
        except Exception: pass 
    
    try:
        log_debug(f"Setting new debounce timer for seek to {app_globals.slider_target_frame_value} (from var trace).")
        app_globals.slider_debounce_timer = root.after(
            int(config.SLIDER_DEBOUNCE_INTERVAL * 1000), 
            lambda: threading.Thread(target=async_logic._perform_seek_action_in_thread, daemon=True).start()
        )
    except Exception: 
        log_debug("Error setting debounce timer from var trace.", exc_info=True)

def handle_slider_click_release(event):
    """Handle LMB release on the progress slider for immediate seek (teleport)."""
    log_debug(f"handle_slider_click_release (LMB Release) triggered. Event X: {event.x}")
    root = refs.get_root()
    ui_comps = refs.ui_components

    if app_globals.is_programmatic_slider_update:
        log_debug("Slider click release was flagged as programmatic. Ignoring.")
        return

    if not ui_comps or root is None or not root.winfo_exists():
        log_debug("Slider click release: UI components or root window not available.")
        return

    progress_slider_widget = ui_comps.get("progress_slider")
    if not progress_slider_widget or \
       not (app_globals.video_capture_global and app_globals.video_capture_global.isOpened()) or \
       progress_slider_widget.cget("state") == "disabled":
        log_debug("Slider click release: Video not ready or slider disabled.")
        return

    if app_globals.slider_debounce_timer:
        try:
            root.after_cancel(app_globals.slider_debounce_timer)
            log_debug("Cancelled existing debounce timer due to click release.")
        except Exception: pass
        app_globals.slider_debounce_timer = None 

    try:
        slider_width = progress_slider_widget.winfo_width()
        if slider_width <= 0: 
            log_debug("Slider width is zero, cannot calculate click position.")
            return

        click_x = event.x
        click_x = max(0, min(click_x, slider_width))
        
        proportion = click_x / slider_width
        
        total_frames = app_globals.current_video_meta.get('total_frames', 0)
        if total_frames <= 0:
            log_debug("Total frames is zero, cannot calculate target frame for click.")
            return
            
        target_frame = int(proportion * (total_frames -1)) 
        target_frame = max(0, min(target_frame, total_frames - 1)) 

        app_globals.slider_target_frame_value = target_frame
        log_debug(f"Slider click release: Calculated target_frame: {target_frame} from proportion {proportion:.3f}")
        
        log_debug(f"Setting is_programmatic_slider_update=True before progress_var.set for click")
        app_globals.is_programmatic_slider_update = True
        try:
            if ui_comps.get("progress_var"):
                ui_comps["progress_var"].set(target_frame)
        finally:
            root.after_idle(lambda: setattr(app_globals, 'is_programmatic_slider_update', False))
            log_debug(f"Scheduled is_programmatic_slider_update=False after progress_var.set for click")
            
        log_debug(f"Initiating immediate seek thread for click to frame {target_frame}")
        threading.Thread(target=async_logic._perform_seek_action_in_thread, daemon=True).start()
    except Exception as e:
        log_debug(f"Error during slider click release handling: {e}", exc_info=True)


def handle_iou_change(*args): 
    """Handle changes to the IoU threshold slider."""
    log_debug(f"handle_iou_change: IoU slider changed. Args: {args}")
    ui_comps = refs.ui_components
    if not ui_comps: return
    try:
        value = ui_comps["iou_var"].get()
        app_globals.iou_threshold_global = value
        if ui_comps.get("iou_value_label"): ui_comps["iou_value_label"].config(text=f"{value:.2f}")
        log_debug(f"IoU threshold changed to {value}")

        if app_globals.uploaded_file_info.get('file_type') == 'image' and \
           app_globals.current_processed_image_for_display is not None and \
           app_globals.active_model_object_global is not None:
            original_image_path = app_globals.uploaded_file_info.get('path')
            if original_image_path and os.path.exists(original_image_path):
                img_to_reprocess = cv2.imread(original_image_path)
                if img_to_reprocess is not None:
                    processed_img, detected_count = process_frame_yolo(
                        img_to_reprocess, app_globals.active_model_object_global, app_globals.active_class_list_global,
                        is_video_mode=False, active_filter_list=app_globals.active_processed_class_filter_global,
                        current_conf_thresh=app_globals.conf_threshold_global, 
                        current_iou_thresh=app_globals.iou_threshold_global  
                    )
                    app_globals.current_processed_image_for_display = processed_img 
                    if ui_comps.get("video_display"): ui_comps["video_display"].update_frame(processed_img)
                    print(f"Re-processed image with new IoU. Detected {detected_count} objects.")
    except Exception: 
        log_debug("Error in handle_iou_change.", exc_info=True)


def handle_conf_change(*args): 
    """Handle changes to the confidence threshold slider."""
    log_debug(f"handle_conf_change: Confidence slider changed. Args: {args}")
    ui_comps = refs.ui_components
    if not ui_comps: return
    try:
        value = ui_comps["conf_var"].get()
        app_globals.conf_threshold_global = value
        if ui_comps.get("conf_value_label"): ui_comps["conf_value_label"].config(text=f"{value:.2f}")
        log_debug(f"Confidence threshold changed to {value}")

        if app_globals.uploaded_file_info.get('file_type') == 'image' and \
           app_globals.current_processed_image_for_display is not None and \
           app_globals.active_model_object_global is not None:
            original_image_path = app_globals.uploaded_file_info.get('path')
            if original_image_path and os.path.exists(original_image_path):
                img_to_reprocess = cv2.imread(original_image_path)
                if img_to_reprocess is not None:
                    processed_img, detected_count = process_frame_yolo(
                        img_to_reprocess, app_globals.active_model_object_global, app_globals.active_class_list_global,
                        is_video_mode=False, active_filter_list=app_globals.active_processed_class_filter_global,
                        current_conf_thresh=app_globals.conf_threshold_global, 
                        current_iou_thresh=app_globals.iou_threshold_global  
                    )
                    app_globals.current_processed_image_for_display = processed_img
                    if ui_comps.get("video_display"): ui_comps["video_display"].update_frame(processed_img)
                    print(f"Re-processed image with new Conf. Detected {detected_count} objects.")
    except Exception: 
        log_debug("Error in handle_conf_change.", exc_info=True)
