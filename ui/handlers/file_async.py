"""
File Async Operations Module
Handles file upload processing, image processing, and related UI updates in separate threads.
"""
import os
import threading
import time
import cv2
import mimetypes

from . import shared_refs as refs
from . import loading_manager
from app.core import globals as app_globals
from app.utils.logger_setup import log_debug
from app.processing.frame_processor import process_frame_yolo
from app.processing.video_handler import format_time_display, _cleanup_processed_video_temp_file

log_debug("ui.handlers.file_async module initialized.")


def _process_uploaded_file_in_thread(file_path, stop_all_processing_logic_ref):
    """Process uploaded file (image or video) in a separate thread."""
    log_debug(f"Thread started for processing file: {file_path}")
    
    root = refs.get_root()
    ui_comps = refs.ui_components
    
    def update_image_info_labels(width, height):
        """Update image info labels in the UI."""
        ui_comps["current_frame_label"].config(text=f"Image: {width}x{height}")
        ui_comps["fps_label"].config(text="FPS: --")

    def update_video_ui_on_upload(fps, total_frames, width, height):
        """Update video-related UI elements after video upload."""
        log_debug(f"Updating video UI: FPS={fps}, Frames={total_frames}, Size={width}x{height}")
        
        app_globals.fps_global = fps
        app_globals.total_frames_global = total_frames
        app_globals.current_frame_number_global = 0
        
        # Update video metadata for compatibility
        app_globals.current_video_meta.update({
            'fps': fps,
            'total_frames': total_frames,
            'duration_seconds': total_frames / fps if fps > 0 else 0,
            'current_frame': 0
        })
        
        if ui_comps.get("progress_slider"):
            ui_comps["progress_slider"].state(['!disabled'])
        if ui_comps.get("play_pause_button"):
            ui_comps["play_pause_button"].state(['!disabled'])
        if ui_comps.get("stop_button"):
            ui_comps["stop_button"].state(['!disabled'])
        
        ui_comps["time_label"].config(text=format_time_display(0, total_frames / fps if fps > 0 else 0))
        ui_comps["current_frame_label"].config(text=f"Frame: 0 / {total_frames}")
        ui_comps["fps_label"].config(text=f"FPS: {fps:.1f}")
        
        if ui_comps.get("fast_process_button"):
            ui_comps["fast_process_button"].state(['!disabled'])
        
        if ui_comps.get("process_button"):
            ui_comps["process_button"].state(['!disabled'])
    
    try:
        # Stop any ongoing processing
        if stop_all_processing_logic_ref:
            stop_all_processing_logic_ref()
        
        # Determine file type
        mime_type, _ = mimetypes.guess_type(file_path)
        file_type = None
        
        if mime_type:
            if mime_type.startswith('image/'):
                file_type = 'image'
            elif mime_type.startswith('video/'):
                file_type = 'video'
        
        if not file_type:
            # Fallback: check file extension
            ext = os.path.splitext(file_path)[1].lower()
            if ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tiff']:
                file_type = 'image'
            elif ext in ['.mp4', '.avi', '.mov', '.mkv']:
                file_type = 'video'
        
        log_debug(f"File type determined in thread: {file_type}, mime: {mime_type}")
        
        _cleanup_processed_video_temp_file()
        app_globals.current_uploaded_file_path_global = file_path
        
        # Update uploaded_file_info for loading manager compatibility
        file_name = os.path.basename(file_path)
        app_globals.uploaded_file_info = {
            'path': file_path,
            'name': file_name,
            'type': mime_type,
            'file_type': file_type
        }
        
        if file_type == 'image':
            log_debug("Image file: reading in thread...")
            img = cv2.imread(file_path)
            if img is None:
                raise ValueError(f"Could not read image file: {file_path}")
            
            height, width = img.shape[:2]
            app_globals.current_unprocessed_image_for_display = img.copy()
            
            display_img = img.copy()
            
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
            else:
                log_debug("No model loaded. Displaying image without processing.")
                app_globals.current_processed_image_for_display = None
            
            if root and root.winfo_exists():
                def update_image_display():
                    if ui_comps.get("video_display"):
                        ui_comps["video_display"].update_frame(display_img)
                    update_image_info_labels(width, height)
                root.after(0, update_image_display)
            
            success = True
            
        elif file_type == 'video':
            log_debug("Video file: setting up video capture in thread...")
            
            with app_globals.video_access_lock:
                if app_globals.video_capture_global:
                    app_globals.video_capture_global.release()
                
                app_globals.video_capture_global = cv2.VideoCapture(file_path)
                
                if not app_globals.video_capture_global.isOpened():
                    raise ValueError(f"Could not open video file: {file_path}")
                
                fps = app_globals.video_capture_global.get(cv2.CAP_PROP_FPS)
                total_frames = int(app_globals.video_capture_global.get(cv2.CAP_PROP_FRAME_COUNT))
                width = int(app_globals.video_capture_global.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(app_globals.video_capture_global.get(cv2.CAP_PROP_FRAME_HEIGHT))
                
                log_debug(f"Video properties: FPS={fps}, Frames={total_frames}, Size={width}x{height}")
                
                # Read and display first frame
                ret, first_frame = app_globals.video_capture_global.read()
                app_globals.video_capture_global.set(cv2.CAP_PROP_POS_FRAMES, 0)
                
                if ret:
                    display_frame = first_frame.copy()
                    if app_globals.active_model_object_global:
                        processed_first_frame, _ = process_frame_yolo(
                            first_frame, app_globals.active_model_object_global, app_globals.active_class_list_global,
                            is_video_mode=True,
                            active_filter_list=app_globals.active_processed_class_filter_global,
                            current_conf_thresh=app_globals.conf_threshold_global, current_iou_thresh=app_globals.iou_threshold_global
                        )
                        display_frame = processed_first_frame
                    
                    if root and root.winfo_exists():
                        def update_video_display():
                            if ui_comps.get("video_display"):
                                ui_comps["video_display"].update_frame(display_frame)
                            update_video_ui_on_upload(fps, total_frames, width, height)
                        root.after(0, update_video_display)
                
            success = True
        else:
            raise ValueError(f"Unsupported file type: {file_path}")
        
        log_debug(f"Thread processing for {file_path} completed. Success: {success}")
        
    except Exception as e:
        log_debug(f"Error processing file {file_path} in thread: {e}", exc_info=True)
        success = False
    
    # Schedule UI updates on main thread
    if root and root.winfo_exists():
        if file_type == 'video' and success:
            log_debug(f"Thread for {file_path} completed successfully (video). UI updates already scheduled.")
            # For video, ensure controls are updated after UI updates
            root.after(100, loading_manager.hide_loading_and_update_controls)
        else:
            log_debug(f"Thread for {file_path} scheduling hide_loading_and_update_controls (non-video or error case).")
            root.after(0, loading_manager.hide_loading_and_update_controls)


def run_image_processing_in_thread(file_path):
    """Process an image file in a separate thread."""
    log_debug(f"run_image_processing_in_thread: Starting image processing for {file_path}")
    
    def process_image_task():
        """Image processing task that runs in a separate thread."""
        def update_ui_after_img_proc(processed_image, detection_count):
            """Update UI after image processing completes."""
            ui_comps = refs.ui_components
            if ui_comps.get("video_display"):
                ui_comps["video_display"].update_frame(processed_image)
            print(f"Processed image. Detected {detection_count} objects.")
        
        try:
            img = cv2.imread(file_path)
            if img is None: 
                raise ValueError(f"Could not read image file: {file_path}")

            processed_img, detected_count = process_frame_yolo(
                img, app_globals.active_model_object_global, app_globals.active_class_list_global,
                is_video_mode=False, active_filter_list=app_globals.active_processed_class_filter_global,
                current_conf_thresh=app_globals.conf_threshold_global, current_iou_thresh=app_globals.iou_threshold_global
            )
            app_globals.current_processed_image_for_display = processed_img

            root = refs.get_root()
            if root and root.winfo_exists():
                root.after(0, lambda: update_ui_after_img_proc(processed_img, detected_count))
                root.after(0, loading_manager.hide_loading_and_update_controls)
            
            log_debug(f"Image processing completed for {file_path}")
            
        except Exception as e:
            log_debug(f"Error in image processing task: {e}", exc_info=True)
            root = refs.get_root()
            if root and root.winfo_exists():
                root.after(0, loading_manager.hide_loading_and_update_controls)
    
    threading.Thread(target=process_image_task, daemon=True).start()
    log_debug("Image processing thread started.")


def reinitialize_video_capture(file_path):
    """Re-initialize video capture after a model load or other operations that might release it."""
    log_debug(f"Re-initializing video capture for: {file_path}")
    success = False
    root = refs.get_root()
    ui_comps = refs.ui_components

    try:
        with app_globals.video_access_lock:
            if app_globals.video_capture_global:
                app_globals.video_capture_global.release()
            
            app_globals.video_capture_global = cv2.VideoCapture(file_path)
            
            if not app_globals.video_capture_global.isOpened():
                raise ValueError(f"Could not re-open video file: {file_path}")
            
            fps = app_globals.video_capture_global.get(cv2.CAP_PROP_FPS)
            total_frames = int(app_globals.video_capture_global.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(app_globals.video_capture_global.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(app_globals.video_capture_global.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            app_globals.current_video_meta.update({
                'fps': fps,
                'total_frames': total_frames,
                'duration_seconds': total_frames / fps if fps > 0 else 0,
                'current_frame': 0
            })
            app_globals.current_frame_number_global = 0 # Ensure consistency with metadata
            
            # Read first frame for display
            ret, first_frame = app_globals.video_capture_global.read()
            # IMPORTANT: Reset to frame 0 after reading the first frame, so playback/processing starts from beginning
            app_globals.video_capture_global.set(cv2.CAP_PROP_POS_FRAMES, 0) 

            if ret and first_frame is not None:
                display_frame = first_frame.copy()
                if app_globals.active_model_object_global: # Model is now loaded
                    log_debug(f"Re-initializing video: Processing first frame with model {app_globals.active_model_key}")
                    processed_first_frame, _ = process_frame_yolo(
                        first_frame, app_globals.active_model_object_global, app_globals.active_class_list_global,
                        is_video_mode=True, active_filter_list=app_globals.active_processed_class_filter_global,
                        current_conf_thresh=app_globals.conf_threshold_global, current_iou_thresh=app_globals.iou_threshold_global
                    )
                    display_frame = processed_first_frame
                
                # Schedule display_frame update on main thread.
                # hide_loading_and_update_controls will handle other UI elements based on updated app_globals.current_video_meta
                if root and root.winfo_exists() and ui_comps and ui_comps.get("video_display"):
                    def update_disp_frame(d_frame):
                        if ui_comps.get("video_display"):
                             ui_comps["video_display"].update_frame(d_frame)
                    root.after(0, lambda d_f=display_frame: update_disp_frame(d_f))
            success = True
            log_debug(f"Video capture re-initialized for {file_path}. FPS: {fps}, Total Frames: {total_frames}")

    except Exception as e:
        log_debug(f"Error re-initializing video capture for {file_path}: {e}", exc_info=True)
        with app_globals.video_access_lock: # Ensure cleanup on error
            if app_globals.video_capture_global:
                app_globals.video_capture_global.release()
            app_globals.video_capture_global = None
        app_globals.current_video_meta.clear() # Clear metadata on failure
    
    return success