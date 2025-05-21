import cv2
import os
import tempfile
import threading
import time
from . import globals as app_globals
from .logger_setup import log_debug
from .frame_processor import process_frame_yolo
# To break circular dependency, ui_callbacks will be imported where its functions are called
# This is a common pattern for threaded UI updates in ipywidgets.
# from .ui_callbacks import hide_loading_and_update_controls # Example, import specifically

def format_time_display(current_seconds, total_seconds):
    def to_mm_ss(seconds):
        seconds = max(0, float(seconds)) # Ensure non-negative
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
    return f"{to_mm_ss(current_seconds)} / {to_mm_ss(total_seconds)}"

def _cleanup_processed_video_temp_file():
    log_debug(f"Attempting to cleanup temp file: {app_globals.processed_video_temp_file_path_global}")
    if app_globals.processed_video_temp_file_path_global and os.path.exists(app_globals.processed_video_temp_file_path_global):
        try:
            os.unlink(app_globals.processed_video_temp_file_path_global)
            log_debug(f"Successfully deleted temp file: {app_globals.processed_video_temp_file_path_global}")
            if app_globals.main_output_area_widget:
                with app_globals.main_output_area_widget:
                    print(f"Cleaned up temporary processed video: {app_globals.processed_video_temp_file_path_global}")
        except OSError as e_unlink:
            log_debug(f"Error deleting temp file {app_globals.processed_video_temp_file_path_global}: {e_unlink}", exc_info=True)
            if app_globals.main_output_area_widget:
                with app_globals.main_output_area_widget:
                    print(f"Warning: Could not delete temporary processed video {app_globals.processed_video_temp_file_path_global}: {e_unlink}")
    app_globals.processed_video_temp_file_path_global = None


def video_processing_thread_func(frame_update_callback=None, progress_update_callback=None, is_processed_video=False):
    """Thread function for processing video frames.
    
    Args:
        frame_update_callback: Function to call with processed frame for display
        progress_update_callback: Function to call with current frame index for progress updates
        is_processed_video: Whether processing a pre-processed video (True) or raw video (False)
    """
    log_debug(f"Video processing thread started. is_processed_video={is_processed_video}")
    
    # Frame processing loop
    try:
        frame_count = 0
        
        # Main processing loop
        while not app_globals.stop_video_processing_flag.is_set():
            # Check if paused
            if app_globals.video_paused_flag.is_set():
                time.sleep(0.05)
                continue
                
            with app_globals.video_access_lock:
                if app_globals.video_capture_global is None or not app_globals.video_capture_global.isOpened():
                    log_debug("Video capture is None or closed. Exiting thread.")
                    break
                
                # Read frame
                ret, frame = app_globals.video_capture_global.read()
            
            # Check if end of video
            if not ret:
                log_debug("End of video reached.")
                break
                
            # Store current frame for seeking
            app_globals.current_video_frame = frame.copy()
            
            # Process frame if needed
            if not is_processed_video and app_globals.active_model_object_global is not None:
                processed_frame, _ = process_frame_yolo(
                    frame, 
                    app_globals.active_model_object_global,
                    app_globals.active_class_list_global,
                    persist_tracking=True, 
                    is_video_mode=True,
                    active_filter_list=app_globals.active_processed_class_filter_global,
                    current_conf_thresh=app_globals.conf_threshold_global,
                    current_iou_thresh=app_globals.iou_threshold_global
                )
            else:
                processed_frame = frame
            
            # Update display
            if frame_update_callback:
                frame_update_callback(processed_frame)
            
            # Update progress
            frame_count += 1
            if progress_update_callback:
                progress_update_callback(frame_count)
            
            # Maintain playback rate by sleeping if needed
            target_fps = app_globals.current_video_meta.get('fps', 30)
            if target_fps <= 0:
                target_fps = 30  # Default to 30 FPS if unknown
            
            sleep_time = 1.0 / target_fps
            time.sleep(max(0, sleep_time - 0.025))  # Subtract processing overhead
    
    except Exception as e:
        log_debug(f"Error in video processing thread: {e}", exc_info=True)
    finally:
        log_debug("Video processing thread ending.")


def fast_video_processing_thread_func(video_file_path, progress_callback=None):
    """Thread function for batch processing a video and saving it to a temporary file.
    
    Args:
        video_file_path: Path to the source video file
        progress_callback: Callback to update progress (0.0 to 1.0)
    """
    log_debug(f"Fast video processing thread started for {video_file_path}")
    
    try:
        # Create capture
        cap = cv2.VideoCapture(video_file_path)
        if not cap.isOpened():
            log_debug(f"Error: Cannot open video file {video_file_path}")
            if progress_callback:
                progress_callback(1.0)  # Signal completion even on error
            return
        
        # Get video properties
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        log_debug(f"Video properties: {fps} FPS, {total_frames} frames, {width}x{height}")
        
        if fps <= 0 or total_frames <= 0 or width <= 0 or height <= 0:
            log_debug("Invalid video properties. Cannot process.")
            if progress_callback:
                progress_callback(1.0)
            return
        
        # Create temporary output file
        temp_output_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
                temp_output_path = temp_file.name
        except Exception as e:
            log_debug(f"Error creating temp file: {e}", exc_info=True)
            if progress_callback:
                progress_callback(1.0)
            return
        
        log_debug(f"Temporary output file: {temp_output_path}")
        
        # Initialize video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # or 'avc1' or other codec
        out = cv2.VideoWriter(temp_output_path, fourcc, fps, (width, height))
        
        if not out.isOpened():
            log_debug("Failed to create video writer.")
            if progress_callback:
                progress_callback(1.0)
            return
            
        # Process each frame
        frame_count = 0
        last_progress_update = time.time()
        
        while not app_globals.stop_fast_processing_flag.is_set():
            ret, frame = cap.read()
            if not ret:
                break
                
            # Process frame
            if app_globals.active_model_object_global is not None:
                processed_frame, _ = process_frame_yolo(
                    frame, 
                    app_globals.active_model_object_global,
                    app_globals.active_class_list_global,
                    persist_tracking=True, 
                    is_video_mode=True,
                    active_filter_list=app_globals.active_processed_class_filter_global,
                    current_conf_thresh=app_globals.conf_threshold_global,
                    current_iou_thresh=app_globals.iou_threshold_global
                )
            else:
                processed_frame = frame
            
            # Write frame to output
            out.write(processed_frame)
            
            # Update progress every 0.5 seconds to avoid UI freezing
            frame_count += 1
            current_time = time.time()
            if current_time - last_progress_update >= 0.5 and progress_callback:
                progress = frame_count / total_frames if total_frames > 0 else 0
                progress_callback(progress)
                last_progress_update = current_time
        
        # Release resources
        cap.release()
        out.release()
        
        # Store path for later use if not stopped
        if not app_globals.stop_fast_processing_flag.is_set():
            log_debug(f"Fast processing complete. Processed video saved to {temp_output_path}")
            app_globals.processed_video_temp_file_path_global = temp_output_path
        else:
            log_debug("Fast processing stopped by user.")
            _cleanup_processed_video_temp_file()
        
        # Final progress update
        if progress_callback:
            progress_callback(1.0)
            
    except Exception as e:
        log_debug(f"Error in fast video processing thread: {e}", exc_info=True)
        if progress_callback:
            progress_callback(1.0)
    finally:
        app_globals.fast_processing_active_flag.clear()
        log_debug("Fast video processing thread ending.")