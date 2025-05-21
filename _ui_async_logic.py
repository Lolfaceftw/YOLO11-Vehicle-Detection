# _ui_async_logic.py
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


_last_frame_display_time_ns = 0 

def _video_playback_loop(process_frames_real_time: bool):
    """
    Main video playback loop, driven by root.after().
    Handles both real-time processed playback and pre-processed video playback.
    """
    global _last_frame_display_time_ns
    root = refs.get_root()
    ui_comps = refs.ui_components

    if app_globals.stop_video_processing_flag.is_set() or not app_globals.is_playing_via_after_loop:
        log_debug("Stopping video playback loop (flag set or mode changed).")
        app_globals.is_playing_via_after_loop = False 
        return

    if app_globals.video_paused_flag.is_set():
        app_globals.after_id_playback_loop = root.after(50, lambda: _video_playback_loop(process_frames_real_time))
        return

    frame_read_success = False
    raw_frame = None 
    output_frame = None 
    current_frame_pos_from_cv = -1

    with app_globals.video_access_lock:
        if app_globals.video_capture_global and app_globals.video_capture_global.isOpened():
            current_frame_pos_from_cv = int(app_globals.video_capture_global.get(cv2.CAP_PROP_POS_FRAMES))
            frame_read_success, raw_frame = app_globals.video_capture_global.read()
            if frame_read_success:
                 app_globals.current_video_frame = raw_frame.copy() 
                 app_globals.current_video_meta['current_frame'] = current_frame_pos_from_cv
                 output_frame = raw_frame 

    if not frame_read_success:
        log_debug(f"Video playback: End of video or read error at frame {current_frame_pos_from_cv}.")
        app_globals.stop_video_processing_flag.set() 
        app_globals.is_playing_via_after_loop = False
        if ui_comps.get("play_pause_button"): ui_comps["play_pause_button"].config(text="Play")
        loading_manager.hide_loading_and_update_controls()
        return

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
            
    from ._ui_loading_manager import update_progress 
    if ui_comps.get("video_display") and output_frame is not None:
        ui_comps["video_display"].update_frame(output_frame) 
    update_progress(current_frame_pos_from_cv) # This will also update the new current_frame_label

    target_fps = app_globals.current_video_meta.get('fps', 30)
    if target_fps <= 0: target_fps = 30
    target_frame_duration_ns = int((1 / target_fps) * 1_000_000_000) 

    current_time_ns = time.perf_counter_ns()
    time_since_last_frame_ns = current_time_ns - _last_frame_display_time_ns
    
    delay_ns = target_frame_duration_ns - time_since_last_frame_ns
    delay_ms = max(1, int(delay_ns / 1_000_000)) 

    _last_frame_display_time_ns = current_time_ns + delay_ns # Predict next ideal display time
    
    app_globals.after_id_playback_loop = root.after(delay_ms, lambda: _video_playback_loop(process_frames_real_time))


def _process_uploaded_file_in_thread(file_path, stop_processing_logic_func):
    """Worker thread for processing uploaded file (type check, read, initial setup)."""
    log_debug(f"Thread started for processing file: {file_path}")
    root = refs.get_root()
    ui_comps = refs.ui_components
    file_type = None 
    success = False

    try:
        file_name = os.path.basename(file_path)
        _, ext = os.path.splitext(file_path.lower())
        
        mime_type = "" 
        if ext in ['.jpg', '.jpeg', '.png']:
            file_type = 'image'
            mime_type = f'image/{ext[1:]}'
        elif ext in ['.mp4', '.avi', '.mov', '.mkv']:
            file_type = 'video'
            mime_type = f'video/{ext[1:] if ext != ".mkv" else "x-matroska"}'
        else:
            log_debug(f"Unsupported file type in thread: {ext}")
            if root and root.winfo_exists():
                root.after(0, lambda: messagebox.showerror("Error", f"Unsupported file type: {ext}"))
            app_globals.uploaded_file_info = {}
            app_globals.current_video_meta.update({'fps': 0.0, 'total_frames': 0, 'duration_seconds': 0.0, 'current_frame': 0})
            app_globals.current_processed_image_for_display = None
            return 

        log_debug(f"File type determined in thread: {file_type}, mime: {mime_type}")

        app_globals.uploaded_file_info = {
            'path': file_path, 'name': file_name, 'type': mime_type, 'file_type': file_type
        }
        app_globals.current_video_meta.update({'fps': 0.0, 'total_frames': 0, 'duration_seconds': 0.0, 'current_frame': 0})
        app_globals.current_video_frame = None 
        app_globals.current_processed_image_for_display = None 

        _cleanup_processed_video_temp_file() 
        stop_processing_logic_func() 

        if file_type == 'image':
            log_debug("Image file: reading in thread...")
            img = cv2.imread(file_path)
            if img is None:
                log_debug(f"Could not read image file in thread: {file_path}")
                if root and root.winfo_exists():
                    root.after(0, lambda: messagebox.showerror("Error", "Could not read image data."))
                app_globals.uploaded_file_info = {} 
                return

            app_globals.current_processed_image_for_display = img.copy() 
            
            display_img = img
            if app_globals.active_model_object_global:
                log_debug("Model loaded, processing uploaded image immediately.")
                processed_img, detected_count = process_frame_yolo(
                    img, app_globals.active_model_object_global, app_globals.active_class_list_global,
                    is_video_mode=False, active_filter_list=app_globals.active_processed_class_filter_global,
                    current_conf_thresh=app_globals.conf_threshold_global, current_iou_thresh=app_globals.iou_threshold_global
                )
                app_globals.current_processed_image_for_display = processed_img 
                display_img = processed_img
                if root and root.winfo_exists():
                    root.after(0, lambda count=detected_count: print(f"Processed uploaded image. Detected {count} objects."))
            
            if root and root.winfo_exists() and ui_comps.get("video_display"):
                root.after(0, lambda bound_img=display_img: ui_comps["video_display"].update_frame(bound_img))
            # Update FPS and Frame labels for image (FPS not applicable, Total Frames = 1)
            if root and root.winfo_exists():
                def update_image_info_labels():
                    if ui_comps.get("fps_label"): ui_comps["fps_label"].config(text="FPS: N/A")
                    if ui_comps.get("current_frame_label"): ui_comps["current_frame_label"].config(text="Frame: 1 / 1")
                root.after(0, update_image_info_labels)
            success = True

        elif file_type == 'video':
            log_debug("Video file: opening and reading first frame in thread.")
            with app_globals.video_access_lock: 
                if app_globals.video_capture_global and app_globals.video_capture_global.isOpened():
                    app_globals.video_capture_global.release()
                
                cap = cv2.VideoCapture(file_path)
                if not cap.isOpened():
                    log_debug(f"Could not open video file in thread: {file_path}")
                    if root and root.winfo_exists():
                        root.after(0, lambda: messagebox.showerror("Error", "Could not open video file."))
                    app_globals.uploaded_file_info = {}
                    return
                
                app_globals.video_capture_global = cap 
                
                fps = cap.get(cv2.CAP_PROP_FPS)
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                duration_seconds = total_frames / fps if fps > 0 else 0
                
                app_globals.current_video_meta.update({
                    'fps': fps, 'total_frames': total_frames, 'duration_seconds': duration_seconds, 'current_frame': 0
                })
                
                ret, first_frame = cap.read()
                app_globals.current_video_frame = first_frame.copy() if ret else None 
            
            if ret and first_frame is not None:
                display_frame = first_frame
                if app_globals.active_model_object_global: 
                    processed_first_frame, _ = process_frame_yolo(
                        first_frame, app_globals.active_model_object_global, app_globals.active_class_list_global,
                        is_video_mode=True, 
                        active_filter_list=app_globals.active_processed_class_filter_global,
                        current_conf_thresh=app_globals.conf_threshold_global, current_iou_thresh=app_globals.iou_threshold_global
                    )
                    display_frame = processed_first_frame

                if root and root.winfo_exists():
                    from ._ui_loading_manager import update_progress 
                    def update_video_ui_on_upload():
                        if ui_comps.get("video_display"):
                            ui_comps["video_display"].update_frame(display_frame)
                        if ui_comps.get("time_label"):
                            ui_comps["time_label"].config(text=format_time_display(0, duration_seconds))
                        if ui_comps.get("progress_slider") and total_frames > 0:
                            ui_comps["progress_slider"].config(to=float(total_frames -1 if total_frames > 0 else 0))
                        if ui_comps.get("progress_var"):
                            app_globals.is_programmatic_slider_update = True
                            try:
                                ui_comps["progress_var"].set(0)
                            finally:
                                app_globals.is_programmatic_slider_update = False
                        # Update new labels
                        if ui_comps.get("fps_label"): ui_comps["fps_label"].config(text=f"FPS: {fps:.2f}")
                        if ui_comps.get("current_frame_label"): ui_comps["current_frame_label"].config(text=f"Frame: 0 / {total_frames}")
                        
                        loading_manager.hide_loading_and_update_controls()

                    root.after(0, update_video_ui_on_upload)
                success = True
            else: 
                log_debug(f"Failed to read first frame of video: {file_path}")
                if root and root.winfo_exists():
                     root.after(0, lambda: messagebox.showerror("Error", "Could not read first frame of video."))
                with app_globals.video_access_lock:
                    if app_globals.video_capture_global:
                        app_globals.video_capture_global.release()
                        app_globals.video_capture_global = None
                app_globals.uploaded_file_info = {}
        
        log_debug(f"Thread processing for {file_path} completed. Success: {success}")

    except Exception as e_thread:
        log_debug(f"General error in _process_uploaded_file_in_thread for {file_path}: {e_thread}", exc_info=True)
        if root and root.winfo_exists():
             root.after(0, lambda bound_e=e_thread: messagebox.showerror("Error", f"Error processing file: {bound_e}"))
        app_globals.uploaded_file_info = {} 
    finally:
        if not (file_type == 'video' and success): 
            if root and root.winfo_exists():
                log_debug(f"Thread for {file_path} scheduling hide_loading_and_update_controls (non-video or error case).")
                root.after(100, loading_manager.hide_loading_and_update_controls)

def _perform_seek_action_in_thread():
    """Perform the actual seek operation to the selected frame. Runs in a thread."""
    root = refs.get_root()
    ui_comps = refs.ui_components
    
    if root and root.winfo_exists():
        root.after(0, lambda: loading_manager.show_loading("Seeking video..."))
        root.after(0, root.update_idletasks) 

    log_debug(f"Seek thread: Performing seek to frame: {app_globals.slider_target_frame_value}")

    try:
        target_frame = int(app_globals.slider_target_frame_value)
        
        with app_globals.video_access_lock:
            if not app_globals.video_capture_global or not app_globals.video_capture_global.isOpened():
                log_debug("Seek thread: No valid video capture for seeking.")
                if root and root.winfo_exists():
                    root.after(0, loading_manager.hide_loading_and_update_controls)
                return 
            
            was_playing = app_globals.is_playing_via_after_loop and not app_globals.video_paused_flag.is_set()

            if was_playing:
                app_globals.video_paused_flag.set() 
                if root and root.winfo_exists() and ui_comps.get("play_pause_button"):
                    root.after(0, lambda: ui_comps["play_pause_button"].config(text="Play"))
            
            app_globals.video_capture_global.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            ret, frame = app_globals.video_capture_global.read()
            
            if ret and frame is not None:
                app_globals.current_video_frame = frame.copy() 
                app_globals.current_video_meta['current_frame'] = target_frame 

                global _last_frame_display_time_ns 
                target_fps = app_globals.current_video_meta.get('fps', 30)
                if target_fps <= 0: target_fps = 30
                target_frame_duration_ns = int((1.0 / target_fps) * 1_000_000_000)
                _last_frame_display_time_ns = time.perf_counter_ns() - (target_frame * target_frame_duration_ns)


                is_real_time_mode = not (app_globals.processed_video_temp_file_path_global and \
                                         os.path.exists(app_globals.processed_video_temp_file_path_global))
                                             
                output_frame_on_seek = frame
                if is_real_time_mode and app_globals.active_model_object_global : 
                    output_frame_on_seek, _ = process_frame_yolo(
                        frame, app_globals.active_model_object_global, app_globals.active_class_list_global,
                        is_video_mode=True, active_filter_list=app_globals.active_processed_class_filter_global,
                        current_conf_thresh=app_globals.conf_threshold_global, current_iou_thresh=app_globals.iou_threshold_global
                    )
                
                if root and root.winfo_exists():
                    from ._ui_loading_manager import update_progress # Moved here
                    def update_ui_after_seek_from_thread():
                        if ui_comps.get("video_display"):
                            ui_comps["video_display"].update_frame(output_frame_on_seek)
                        
                        # Update progress (which also updates frame label)
                        update_progress(target_frame)
                        
                        loading_manager.hide_loading_and_update_controls()
                    root.after(0, update_ui_after_seek_from_thread)
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
    """Loads a model in a separate thread and updates UI."""
    root = refs.get_root()
    ui_comps = refs.ui_components

    def load_model_task():
        model_loader_load_model(selected_model_key) 
        if root and root.winfo_exists():
             root.after(0, loading_manager.hide_loading_and_update_controls)
        
        if app_globals.uploaded_file_info.get('file_type') == 'image' and \
           app_globals.current_processed_image_for_display is not None and \
           app_globals.active_model_object_global is not None:
            try:
                original_image_path = app_globals.uploaded_file_info.get('path')
                if original_image_path and os.path.exists(original_image_path):
                    img_to_reprocess = cv2.imread(original_image_path)
                    if img_to_reprocess is not None:
                        log_debug(f"Re-processing image {original_image_path} with new model {selected_model_key}")
                        processed_img, detected_count = process_frame_yolo(
                            img_to_reprocess, app_globals.active_model_object_global, app_globals.active_class_list_global,
                            is_video_mode=False, active_filter_list=app_globals.active_processed_class_filter_global,
                            current_conf_thresh=app_globals.conf_threshold_global, current_iou_thresh=app_globals.iou_threshold_global
                        )
                        app_globals.current_processed_image_for_display = processed_img 
                        if ui_comps.get("video_display"):
                             ui_comps["video_display"].update_frame(processed_img)
                        print(f"Re-processed image with {selected_model_key}. Detected {detected_count} objects.")
            except Exception as e_reprocess:
                log_debug(f"Error re-processing image with new model: {e_reprocess}", exc_info=True)
                print(f"Error re-processing image: {e_reprocess}")

    stop_processing_logic_func()
    loading_manager.show_loading(f"Loading model: {selected_model_key}...")
    threading.Thread(target=load_model_task, daemon=True).start()


def run_image_processing_in_thread(file_path):
    """Processes an image in a thread."""
    root = refs.get_root()
    ui_comps = refs.ui_components
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
            app_globals.current_processed_image_for_display = processed_img

            if root and root.winfo_exists():
                def update_ui_after_img_proc():
                    if ui_comps.get("video_display"): ui_comps["video_display"].update_frame(processed_img)
                    print(f"Processed image. Detected {detected_count} objects.")
                    # Update info labels for image
                    if ui_comps.get("fps_label"): ui_comps["fps_label"].config(text="FPS: N/A")
                    if ui_comps.get("current_frame_label"): ui_comps["current_frame_label"].config(text="Frame: 1 / 1")
                    loading_manager.hide_loading_and_update_controls()
                root.after(0, update_ui_after_img_proc)
        except Exception as e:
            log_debug(f"Error processing image (thread): {e}", exc_info=True)
            if root and root.winfo_exists():
                root.after(0, lambda: messagebox.showerror("Error", f"Error processing image: {e}"))
                root.after(0, loading_manager.hide_loading_and_update_controls)
    threading.Thread(target=process_image_task, daemon=True).start()


def run_fast_video_processing_in_thread(file_path, stop_processing_logic_func):
    """Prepares and starts fast video processing in a thread."""
    root = refs.get_root()
    ui_comps = refs.ui_components
    from ._ui_loading_manager import update_fast_progress 

    app_globals.fast_processing_active_flag.set() 
    loading_manager.hide_loading_and_update_controls() 

    def fast_process_task():
        try:
            if app_globals.current_video_meta.get('total_frames', 0) == 0: # Or if path changed
                temp_cap = cv2.VideoCapture(file_path)
                if temp_cap.isOpened():
                    app_globals.current_video_meta['fps'] = temp_cap.get(cv2.CAP_PROP_FPS)
                    app_globals.current_video_meta['total_frames'] = int(temp_cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    app_globals.current_video_meta['duration_seconds'] = \
                        app_globals.current_video_meta['total_frames'] / app_globals.current_video_meta['fps'] if app_globals.current_video_meta['fps'] > 0 else 0
                    temp_cap.release()
                     # Update FPS label after fast processing metadata is known
                    if root and root.winfo_exists() and ui_comps.get("fps_label"):
                        root.after(0, lambda: ui_comps["fps_label"].config(text=f"FPS: {app_globals.current_video_meta['fps']:.2f}"))
                else: raise ValueError(f"Fast Process: Could not open video for metadata: {file_path}")
            
            app_globals.stop_fast_processing_flag.clear()
            if ui_comps.get("fast_progress_var"): ui_comps["fast_progress_var"].set(0)
            
            app_globals.fast_video_processing_thread = threading.Thread(
                target=fast_video_processing_thread_func, 
                kwargs={
                    'video_file_path': file_path,
                    'progress_callback': lambda progress: update_fast_progress(progress) if ui_comps else None
                }, daemon=True)
            app_globals.fast_video_processing_thread.start()
        except Exception as e:
            log_debug(f"Error setting up fast processing (thread): {e}", exc_info=True)
            if root and root.winfo_exists():
                root.after(0, lambda: messagebox.showerror("Error", f"Error setting up fast processing: {e}"))
            app_globals.fast_processing_active_flag.clear()
            if root and root.winfo_exists():
                root.after(0, loading_manager.hide_loading_and_update_controls)
    
    stop_processing_logic_func() 
    threading.Thread(target=fast_process_task, daemon=True).start()
