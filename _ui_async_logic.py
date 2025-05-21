# app/_ui_async_logic.py
"""
Handles asynchronous operations and the main video playback loop.
"""
import os
import cv2
import threading
import time 
from tkinter import messagebox 

from . import _ui_shared_refs as refs
from . import _ui_loading_manager as loading_manager 
from . import globals as app_globals
from .logger_setup import log_debug
from .frame_processor import process_frame_yolo
from .video_handler import format_time_display, _cleanup_processed_video_temp_file, \
                           fast_video_processing_thread_func 
from .model_loader import load_model as model_loader_load_model


_last_frame_display_time_ns = 0 # Module-level global

def _video_playback_loop(process_frames_real_time: bool):
    """
    Main video playback loop, driven by root.after().
    Handles both real-time processed playback and pre-processed video playback.
    """
    global _last_frame_display_time_ns 
    root = app_globals.ui_references.get("root") # Get root from global references
    ui_comps = app_globals.ui_references.get("ui_components_dict", {})


    if app_globals.stop_video_processing_flag.is_set() or not app_globals.is_playing_via_after_loop:
        log_debug("Stopping video playback loop (flag set or mode changed).")
        app_globals.is_playing_via_after_loop = False 
        app_globals.real_time_fps_display_value = 0.0 
        if ui_comps.get("fps_label"): ui_comps["fps_label"].config(text="FPS: --")
        return

    if app_globals.video_paused_flag.is_set():
        if root and root.winfo_exists(): # Ensure root is valid before calling 'after'
            app_globals.after_id_playback_loop = root.after(50, lambda: _video_playback_loop(process_frames_real_time))
        return

    frame_read_success = False
    raw_frame = None 
    output_frame = None 
    current_frame_pos_from_cv = -1

    with app_globals.video_access_lock:
        if app_globals.video_capture_global and app_globals.video_capture_global.isOpened():
            current_frame_pos_from_cv = int(app_globals.video_capture_global.get(cv2.CAP_PROP_POS_FRAMES))
            # Ensure OpenCV's internal pointer matches our metadata if there's a discrepancy (e.g., after a seek)
            if abs(current_frame_pos_from_cv - app_globals.current_video_meta['current_frame']) > 1 : # If more than 1 frame off
                 log_debug(f"Playback loop: Discrepancy detected. OpenCV pos: {current_frame_pos_from_cv}, Meta pos: {app_globals.current_video_meta['current_frame']}. Setting OpenCV to meta.")
                 app_globals.video_capture_global.set(cv2.CAP_PROP_POS_FRAMES, app_globals.current_video_meta['current_frame'])
                 current_frame_pos_from_cv = app_globals.current_video_meta['current_frame']


            frame_read_success, raw_frame = app_globals.video_capture_global.read()
            if frame_read_success:
                 app_globals.current_video_frame = raw_frame.copy() 
                 # Update meta current_frame based on what was actually read
                 app_globals.current_video_meta['current_frame'] = int(app_globals.video_capture_global.get(cv2.CAP_PROP_POS_FRAMES)) -1 # POS_FRAMES is next frame
                 if app_globals.current_video_meta['current_frame'] < 0: app_globals.current_video_meta['current_frame'] = 0 # Correction for start
                 output_frame = raw_frame 
            else: # Read failed
                 app_globals.current_video_meta['current_frame'] = app_globals.current_video_meta.get('total_frames', 0)


    if not frame_read_success:
        log_debug(f"Video playback: End of video or read error at effective frame {app_globals.current_video_meta['current_frame']}.")
        app_globals.stop_video_processing_flag.set() 
        app_globals.is_playing_via_after_loop = False
        app_globals.real_time_fps_display_value = 0.0 
        if ui_comps.get("fps_label"): ui_comps["fps_label"].config(text="FPS: --")
        if ui_comps.get("play_pause_button"): ui_comps["play_pause_button"].config(text="Play")
        # Update progress to show the end
        if root and root.winfo_exists(): 
            root.after(0, lambda: loading_manager.update_progress(app_globals.current_video_meta.get('total_frames', 0) -1 if app_globals.current_video_meta.get('total_frames', 0) > 0 else 0 ))
            root.after(10, loading_manager.hide_loading_and_update_controls) # Delay slightly for progress update
        return

    app_globals.real_time_fps_frames_processed += 1
    current_time_fps_calc = time.perf_counter()
    time_delta_fps = current_time_fps_calc - app_globals.real_time_fps_last_update_time
    if time_delta_fps >= 0.5: 
        if time_delta_fps > 0 : 
            app_globals.real_time_fps_display_value = app_globals.real_time_fps_frames_processed / time_delta_fps
        else: 
            app_globals.real_time_fps_display_value = 999 # Avoid division by zero if time hasn't passed
        app_globals.real_time_fps_frames_processed = 0
        app_globals.real_time_fps_last_update_time = current_time_fps_calc

    if process_frames_real_time and app_globals.active_model_object_global and output_frame is not None:
        try:
            output_frame, _ = process_frame_yolo(
                output_frame, app_globals.active_model_object_global, app_globals.active_class_list_global,
                persist_tracking=True, is_video_mode=True,
                active_filter_list=app_globals.active_processed_class_filter_global,
                current_conf_thresh=app_globals.conf_threshold_global,
                current_iou_thresh=app_globals.iou_threshold_global
            )
        except Exception as e_process:
            log_debug(f"Error during real-time frame processing in playback loop: {e_process}", exc_info=True)
            
    # from ._ui_loading_manager import update_progress # Already imported at top level
    if ui_comps.get("video_display") and output_frame is not None:
        ui_comps["video_display"].update_frame(output_frame) 
    
    # Schedule update_progress on the main thread
    if root and root.winfo_exists():
        root.after(0, lambda cf=app_globals.current_video_meta['current_frame']: loading_manager.update_progress(cf))


    target_fps = app_globals.current_video_meta.get('fps', 30)
    if target_fps <= 0: target_fps = 30 # Default to 30 if FPS is invalid
    target_frame_duration_ns = int((1 / target_fps) * 1_000_000_000) 

    current_time_ns = time.perf_counter_ns()
    if _last_frame_display_time_ns == 0: # First frame logic
        _last_frame_display_time_ns = current_time_ns - target_frame_duration_ns # Ensure first frame isn't delayed

    next_ideal_display_time_ns = _last_frame_display_time_ns + target_frame_duration_ns
    
    delay_ns = next_ideal_display_time_ns - current_time_ns
    delay_ms = max(1, int(delay_ns / 1_000_000)) # Ensure at least 1ms delay

    _last_frame_display_time_ns = next_ideal_display_time_ns # Update for next iteration
    
    if root and root.winfo_exists():
        app_globals.after_id_playback_loop = root.after(delay_ms, lambda: _video_playback_loop(process_frames_real_time))


def _process_uploaded_file_in_thread(file_path, stop_processing_logic_func):
    log_debug(f"Thread started for processing file: {file_path}")
    root = app_globals.ui_references.get("root")
    # ui_comps = app_globals.ui_references.get("ui_components_dict", {}) # Not needed directly in thread
    file_type = None 
    success = False
    # processed_image_for_main_thread = None # This will be stored in app_globals.current_processed_image_for_display
    detected_objects_count = 0

    try:
        file_name = os.path.basename(file_path)
        _, ext = os.path.splitext(file_path.lower())
        
        mime_type = "" 
        if ext in ['.jpg', '.jpeg', '.png']:
            file_type = 'image'; mime_type = f'image/{ext[1:]}'
        elif ext in ['.mp4', '.avi', '.mov', '.mkv']:
            file_type = 'video'; mime_type = f'video/{ext[1:] if ext != ".mkv" else "x-matroska"}'
        else:
            log_debug(f"Unsupported file type in thread: {ext}")
            if root and root.winfo_exists(): root.after(0, lambda: messagebox.showerror("Error", f"Unsupported file type: {ext}"))
            app_globals.uploaded_file_info = {}; app_globals.current_video_meta.update({'fps': 0.0, 'total_frames': 0, 'duration_seconds': 0.0, 'current_frame': 0})
            app_globals.current_processed_image_for_display = None; return 

        log_debug(f"File type determined in thread: {file_type}, mime: {mime_type}")
        app_globals.uploaded_file_info = {'path': file_path, 'name': file_name, 'type': mime_type, 'file_type': file_type}
        app_globals.current_video_meta.update({'fps': 0.0, 'total_frames': 0, 'duration_seconds': 0.0, 'current_frame': 0})
        app_globals.current_video_frame = None; app_globals.current_processed_image_for_display = None 
        
        _cleanup_processed_video_temp_file()
        if callable(stop_processing_logic_func): stop_processing_logic_func() 

        if file_type == 'image':
            log_debug("Image file: reading in thread...")
            img = cv2.imread(file_path)
            if img is None:
                log_debug(f"Could not read image file in thread: {file_path}")
                if root and root.winfo_exists(): root.after(0, lambda: messagebox.showerror("Error", "Could not read image data."))
                app_globals.uploaded_file_info = {}; return

            if app_globals.active_model_object_global:
                log_debug("Model loaded, processing uploaded image immediately in thread.")
                processed_img, detected_objects_count = process_frame_yolo(
                    img, app_globals.active_model_object_global, app_globals.active_class_list_global,
                    is_video_mode=False, # Corrected: was missing is_video_mode
                    active_filter_list=app_globals.active_processed_class_filter_global,
                    current_conf_thresh=app_globals.conf_threshold_global, 
                    current_iou_thresh=app_globals.iou_threshold_global
                )
                app_globals.current_processed_image_for_display = processed_img 
            else:
                app_globals.current_processed_image_for_display = img.copy()
            success = True

        elif file_type == 'video':
            log_debug("Video file: opening and reading first frame in thread.")
            with app_globals.video_access_lock: 
                if app_globals.video_capture_global and app_globals.video_capture_global.isOpened(): app_globals.video_capture_global.release()
                cap = cv2.VideoCapture(file_path)
                if not cap.isOpened():
                    log_debug(f"Could not open video file in thread: {file_path}"); success = False
                    if root and root.winfo_exists(): root.after(0, lambda: messagebox.showerror("Error", "Could not open video file."))
                    app_globals.uploaded_file_info = {}; return
                app_globals.video_capture_global = cap 
                fps = cap.get(cv2.CAP_PROP_FPS); total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                duration_seconds = total_frames / fps if fps > 0 else 0
                app_globals.current_video_meta.update({'fps': fps, 'total_frames': total_frames, 'duration_seconds': duration_seconds, 'current_frame': 0})
                ret, first_frame = cap.read()
                app_globals.current_video_frame = first_frame.copy() if ret else None 
            
            if ret and first_frame is not None:
                display_frame_for_video = first_frame
                if app_globals.active_model_object_global: 
                    processed_first_frame, _ = process_frame_yolo(first_frame, app_globals.active_model_object_global, app_globals.active_class_list_global, True, True, app_globals.active_processed_class_filter_global, app_globals.conf_threshold_global, app_globals.iou_threshold_global)
                    display_frame_for_video = processed_first_frame
                app_globals.current_processed_image_for_display = display_frame_for_video
                success = True
            else: 
                log_debug(f"Failed to read first frame of video: {file_path}"); success = False
                if root and root.winfo_exists(): root.after(0, lambda: messagebox.showerror("Error", "Could not read first frame of video."))
                with app_globals.video_access_lock:
                    if app_globals.video_capture_global: app_globals.video_capture_global.release(); app_globals.video_capture_global = None
                app_globals.uploaded_file_info = {}
        
        log_debug(f"Thread processing for {file_path} completed. Success: {success}")

    except Exception as e_thread:
        log_debug(f"General error in _process_uploaded_file_in_thread for {file_path}: {e_thread}", exc_info=True)
        success = False
        if root and root.winfo_exists():
             root.after(0, lambda bound_e=e_thread: messagebox.showerror("Error", f"Error processing file: {bound_e}"))
        app_globals.uploaded_file_info = {} 
    finally:
        if root and root.winfo_exists():
            log_debug(f"Thread for {file_path} scheduling final hide_loading_and_update_controls. Success: {success}")
            # hide_loading_and_update_controls will use app_globals.current_processed_image_for_display
            root.after(0, loading_manager.hide_loading_and_update_controls)
            if file_type == 'image' and success and detected_objects_count > 0: # Only print if objects were detected
                 root.after(10, lambda c=detected_objects_count: print(f"Processed uploaded image. Detected {c} objects."))


def _perform_seek_action_in_thread():
    root = app_globals.ui_references.get("root")
    ui_comps = app_globals.ui_references.get("ui_components_dict", {})
    
    if root and root.winfo_exists(): root.after(0, lambda: loading_manager.show_loading("Seeking video...")); root.after(0, root.update_idletasks) 
    log_debug(f"Seek thread: Performing seek to frame: {app_globals.slider_target_frame_value}")
    try:
        target_frame = int(app_globals.slider_target_frame_value)
        with app_globals.video_access_lock:
            if not app_globals.video_capture_global or not app_globals.video_capture_global.isOpened():
                log_debug("Seek thread: No valid video capture."); 
                if root and root.winfo_exists(): root.after(0, loading_manager.hide_loading_and_update_controls); return 
            
            was_playing_before_seek = app_globals.is_playing_via_after_loop and not app_globals.video_paused_flag.is_set()
            if was_playing_before_seek: # If it was playing, pause it for the seek
                app_globals.video_paused_flag.set() 
                if root and root.winfo_exists() and ui_comps.get("play_pause_button"): 
                    root.after(0, lambda: ui_comps["play_pause_button"].config(text="Play")) # Update button text
            
            app_globals.video_capture_global.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            ret, frame = app_globals.video_capture_global.read()
            
            if ret and frame is not None:
                app_globals.current_video_frame = frame.copy()
                # After setting position, CAP_PROP_POS_FRAMES points to the *next* frame. So current is target_frame.
                app_globals.current_video_meta['current_frame'] = target_frame 
                
                global _last_frame_display_time_ns 
                target_fps_meta = app_globals.current_video_meta.get('fps', 30); target_fps_meta = target_fps_meta if target_fps_meta > 0 else 30
                _last_frame_display_time_ns = time.perf_counter_ns() - int((1.0 / target_fps_meta) * 1_000_000_000) # Reset for smooth resume
                
                app_globals.real_time_fps_last_update_time = time.perf_counter(); app_globals.real_time_fps_frames_processed = 0; app_globals.real_time_fps_display_value = 0.0
                
                # Determine if we are in real-time processing mode (not playing a pre-processed temp file)
                is_real_time_mode = not (app_globals.processed_video_temp_file_path_global and os.path.exists(app_globals.processed_video_temp_file_path_global))
                                             
                output_frame_on_seek = frame.copy() # Use a copy for processing
                if is_real_time_mode and app_globals.active_model_object_global : 
                    output_frame_on_seek, _ = process_frame_yolo(
                        output_frame_on_seek, app_globals.active_model_object_global, app_globals.active_class_list_global,
                        persist_tracking=True, is_video_mode=True, 
                        active_filter_list=app_globals.active_processed_class_filter_global,
                        current_conf_thresh=app_globals.conf_threshold_global, current_iou_thresh=app_globals.iou_threshold_global
                    )
                
                app_globals.current_processed_image_for_display = output_frame_on_seek # Store for hide_loading

                if root and root.winfo_exists():
                    # The actual display update will now be handled by hide_loading_and_update_controls
                    root.after(0, loading_manager.hide_loading_and_update_controls)
                    # If it was playing, unpause it after seek and UI update
                    if was_playing_before_seek:
                        root.after(10, lambda: app_globals.video_paused_flag.clear()) # Small delay for UI to settle
            else:
                log_debug(f"Seek thread: Failed to read frame at position {target_frame}")
                if root and root.winfo_exists():
                    root.after(0, lambda: messagebox.showinfo("Seek Info", "Could not seek to selected frame. End of video or read error."))
                    root.after(0, loading_manager.hide_loading_and_update_controls)
    except Exception as e:
        log_debug(f"Error during seek task (thread): {e}", exc_info=True)
        if root and root.winfo_exists():
            root.after(0, lambda bound_e=e: messagebox.showerror("Seek Error", f"Error during seek: {bound_e}"))
            root.after(0, loading_manager.hide_loading_and_update_controls)


def run_model_load_in_thread(selected_model_key, stop_processing_logic_func):
    root = app_globals.ui_references.get("root")
    ui_comps = app_globals.ui_references.get("ui_components_dict", {})
    def load_model_task():
        model_loader_load_model(selected_model_key) 
        if root and root.winfo_exists(): root.after(0, loading_manager.hide_loading_and_update_controls)
        
        # If an image is already loaded, reprocess it with the new model
        if app_globals.uploaded_file_info.get('file_type') == 'image' and \
           app_globals.uploaded_file_info.get('path') and \
           app_globals.active_model_object_global is not None:
            try:
                original_image_path = app_globals.uploaded_file_info.get('path')
                img_to_reprocess = cv2.imread(original_image_path)
                if img_to_reprocess is not None:
                    log_debug(f"Re-processing image {original_image_path} with new model {selected_model_key}")
                    processed_img, detected_count = process_frame_yolo(
                        img_to_reprocess, app_globals.active_model_object_global, app_globals.active_class_list_global,
                        is_video_mode=False, active_filter_list=app_globals.active_processed_class_filter_global,
                        current_conf_thresh=app_globals.conf_threshold_global, current_iou_thresh=app_globals.iou_threshold_global
                    )
                    app_globals.current_processed_image_for_display = processed_img # Update global
                    # UI update will be handled by the hide_loading_and_update_controls call above
                    if root and root.winfo_exists(): # For the print message
                        root.after(10, lambda c=detected_count: print(f"Re-processed image with {selected_model_key}. Detected {c} objects."))
            except Exception as e_reprocess: 
                log_debug(f"Error re-processing image with new model: {e_reprocess}", exc_info=True)
                if root and root.winfo_exists(): root.after(0, lambda: print(f"Error re-processing image: {e_reprocess}"))

    if callable(stop_processing_logic_func): stop_processing_logic_func()
    loading_manager.show_loading(f"Loading model: {selected_model_key}...")
    threading.Thread(target=load_model_task, daemon=True).start()


def run_image_processing_in_thread(file_path):
    """Processes an image in a thread. Assumes model is loaded."""
    root = app_globals.ui_references.get("root")
    # ui_comps = app_globals.ui_references.get("ui_components_dict", {})
    loading_manager.show_loading("Processing image...")
    if root and root.winfo_exists(): root.update_idletasks()

    def process_image_task():
        try:
            img = cv2.imread(file_path)
            if img is None: raise ValueError(f"Could not read image file: {file_path}")

            processed_img, detected_count = process_frame_yolo(
                img, app_globals.active_model_object_global, app_globals.active_class_list_global,
                is_video_mode=False, active_filter_list=app_globals.active_processed_class_filter_global,
                current_conf_thresh=app_globals.conf_threshold_global, current_iou_thresh=app_globals.iou_threshold_global
            )
            app_globals.current_processed_image_for_display = processed_img # Key step

            if root and root.winfo_exists():
                # hide_loading_and_update_controls will now pick up current_processed_image_for_display
                root.after(0, loading_manager.hide_loading_and_update_controls) 
                root.after(10, lambda c=detected_count: print(f"Processed image. Detected {c} objects."))
        except Exception as e:
            log_debug(f"Error processing image (thread): {e}", exc_info=True)
            app_globals.current_processed_image_for_display = None # Clear on error
            if root and root.winfo_exists():
                root.after(0, lambda bound_e=e: messagebox.showerror("Error", f"Error processing image: {bound_e}"))
                root.after(0, loading_manager.hide_loading_and_update_controls) # Still update UI
    threading.Thread(target=process_image_task, daemon=True).start()


def run_fast_video_processing_in_thread(file_path, stop_processing_logic_func):
    root = app_globals.ui_references.get("root")
    ui_comps = app_globals.ui_references.get("ui_components_dict", {})
    from ._ui_loading_manager import update_fast_progress 

    if callable(stop_processing_logic_func): stop_processing_logic_func() 
    app_globals.fast_processing_active_flag.set()
    log_debug("run_fast_video_processing_in_thread: fast_processing_active_flag SET.")
    
    if root and root.winfo_exists(): 
        root.after(0, loading_manager.hide_loading_and_update_controls) # This will show the progress bar frame

    def fast_process_task():
        try:
            if root and root.winfo_exists() and ui_comps.get("fps_label"): 
                root.after(0, lambda: ui_comps["fps_label"].config(text="FPS: Processing..."))

            temp_cap_check = cv2.VideoCapture(file_path)
            if temp_cap_check.isOpened():
                app_globals.current_video_meta['fps'] = temp_cap_check.get(cv2.CAP_PROP_FPS)
                app_globals.current_video_meta['total_frames'] = int(temp_cap_check.get(cv2.CAP_PROP_FRAME_COUNT))
                app_globals.current_video_meta['duration_seconds'] = \
                    app_globals.current_video_meta['total_frames'] / app_globals.current_video_meta['fps'] if app_globals.current_video_meta['fps'] > 0 else 0
                temp_cap_check.release()
            else: 
                raise ValueError(f"Fast Process: Could not open video for metadata: {file_path}")
            
            app_globals.stop_fast_processing_flag.clear()
            if ui_comps.get("fast_progress_var"): 
                root.after(0, lambda: ui_comps["fast_progress_var"].set(0))
            if ui_comps.get("fast_progress_label"): 
                 root.after(0, lambda: ui_comps["fast_progress_label"].config(text="Progress: 0% | Calculating..."))

            
            app_globals.fast_video_processing_thread = threading.Thread(
                target=fast_video_processing_thread_func, 
                kwargs={
                    'video_file_path': file_path,
                    'progress_callback': lambda p, t: update_fast_progress(p, t) if ui_comps else None
                }, daemon=True)
            app_globals.fast_video_processing_thread.start()
        except Exception as e:
            log_debug(f"Error setting up fast processing (thread): {e}", exc_info=True)
            if root and root.winfo_exists():
                root.after(0, lambda: messagebox.showerror("Error", f"Error setting up fast processing: {e}"))
            app_globals.fast_processing_active_flag.clear() 
            if root and root.winfo_exists():
                root.after(0, loading_manager.hide_loading_and_update_controls)
    
    threading.Thread(target=fast_process_task, daemon=True).start()
