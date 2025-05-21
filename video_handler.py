import cv2
import os
import tempfile
import threading
import time
from . import globals as app_globals
from .logger_setup import log_debug
from .frame_processor import process_frame_yolo

def format_time_display(current_seconds, total_seconds):
    def to_mm_ss(seconds):
        seconds = max(0, float(seconds)) 
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
            print(f"Cleaned up temporary processed video: {app_globals.processed_video_temp_file_path_global}")
        except OSError as e_unlink:
            log_debug(f"Error deleting temp file {app_globals.processed_video_temp_file_path_global}: {e_unlink}", exc_info=True)
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
    
    playback_start_abs_time = time.perf_counter()
    # Initialize current_frame_index based on where the video capture is starting.
    # This is crucial if playback begins after a seek.
    with app_globals.video_access_lock:
        if app_globals.video_capture_global and app_globals.video_capture_global.isOpened():
            current_frame_index = int(app_globals.video_capture_global.get(cv2.CAP_PROP_POS_FRAMES))
        else:
            log_debug("Video capture not available at thread start. Exiting.")
            return
            
    app_globals.current_video_meta['current_frame'] = current_frame_index
    log_debug(f"Initial frame index for playback loop: {current_frame_index}")

    try:
        target_fps = app_globals.current_video_meta.get('fps', 30)
        if target_fps <= 0: target_fps = 30 
        target_frame_duration = 1.0 / target_fps
        log_debug(f"Playback: Target FPS: {target_fps}, Target Frame Duration: {target_frame_duration:.4f}s")

        while not app_globals.stop_video_processing_flag.is_set():
            if app_globals.video_paused_flag.is_set():
                time.sleep(0.05) 
                # When resuming, adjust playback_start_abs_time to keep accumulated time correct
                # for the current_frame_index.
                playback_start_abs_time = time.perf_counter() - (current_frame_index * target_frame_duration)
                continue
            
            # Store the time at the beginning of this frame's processing cycle    
            this_frame_ideal_start_time = playback_start_abs_time + (current_frame_index * target_frame_duration)

            frame_read_start_time = time.perf_counter()
            actual_cv2_frame_pos = -1 # For debugging
            with app_globals.video_access_lock:
                if app_globals.video_capture_global is None or not app_globals.video_capture_global.isOpened():
                    log_debug("Video capture is None or closed during loop. Exiting thread.")
                    break
                
                # It's generally better to rely on our incremented current_frame_index for logic,
                # but get actual position for verification or if a seek happened externally (not typical here).
                actual_cv2_frame_pos = int(app_globals.video_capture_global.get(cv2.CAP_PROP_POS_FRAMES))
                
                # If current_frame_index has diverged significantly from actual_cv2_frame_pos
                # (e.g., due to an external seek not updating our index), resync.
                # This should ideally be handled by the seek logic itself by updating current_frame_index.
                if abs(current_frame_index - actual_cv2_frame_pos) > 1 and actual_cv2_frame_pos >=0 : # Resync if off by more than 1 frame
                    log_debug(f"Resyncing frame index. Loop index: {current_frame_index}, OpenCV POS_FRAMES: {actual_cv2_frame_pos}")
                    current_frame_index = actual_cv2_frame_pos
                    # Also readjust playback_start_abs_time to match this new frame index anchor
                    playback_start_abs_time = time.perf_counter() - (current_frame_index * target_frame_duration)
                    this_frame_ideal_start_time = playback_start_abs_time + (current_frame_index * target_frame_duration)


                ret, frame = app_globals.video_capture_global.read()
            
            if not ret:
                log_debug(f"End of video reached or read error at frame index {current_frame_index}.")
                break
                
            app_globals.current_video_frame = frame.copy() 
            app_globals.current_video_meta['current_frame'] = current_frame_index # Update global for UI
            
            output_frame = frame
            if not is_processed_video and app_globals.active_model_object_global is not None:
                output_frame, _ = process_frame_yolo(
                    frame, app_globals.active_model_object_global, app_globals.active_class_list_global,
                    persist_tracking=True, is_video_mode=True,
                    active_filter_list=app_globals.active_processed_class_filter_global,
                    current_conf_thresh=app_globals.conf_threshold_global,
                    current_iou_thresh=app_globals.iou_threshold_global
                )
            
            if frame_update_callback:
                frame_update_callback(output_frame)
            
            if progress_update_callback:
                progress_update_callback(current_frame_index) 
            
            # Calculate how much time this frame's processing and display scheduling took
            time_spent_for_frame = time.perf_counter() - this_frame_ideal_start_time
            
            # Calculate sleep duration to hit the next frame's ideal start time
            sleep_duration = target_frame_duration - time_spent_for_frame
            
            if sleep_duration > 0.001: # Avoid very small sleeps that might be less than OS timer resolution
                time.sleep(sleep_duration)
            # If sleep_duration is negative or very small, we're lagging; proceed immediately.

            current_frame_index += 1 # Increment for the next frame

    except Exception as e:
        log_debug(f"Error in video processing thread: {e}", exc_info=True)
    finally:
        log_debug(f"Video processing thread ending. Last processed frame index: {current_frame_index-1}")


def fast_video_processing_thread_func(video_file_path, progress_callback=None):
    """Thread function for batch processing a video and saving it to a temporary file. """
    log_debug(f"Fast video processing thread started for {video_file_path}")
    
    try:
        cap = cv2.VideoCapture(video_file_path)
        if not cap.isOpened():
            log_debug(f"Error: Cannot open video file {video_file_path}")
            if progress_callback: progress_callback(1.0) 
            return
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        log_debug(f"Video properties: {fps} FPS, {total_frames} frames, {width}x{height}")
        
        if fps <= 0 or total_frames <= 0 or width <= 0 or height <= 0:
            log_debug("Invalid video properties. Cannot process.")
            if progress_callback: progress_callback(1.0)
            return
        
        temp_output_path = None
        try:
            fd, temp_output_path = tempfile.mkstemp(suffix='.mp4')
            os.close(fd) 
        except Exception as e:
            log_debug(f"Error creating temp file: {e}", exc_info=True)
            if progress_callback: progress_callback(1.0)
            return
        
        log_debug(f"Temporary output file: {temp_output_path}")
        
        fourcc = cv2.VideoWriter_fourcc(*'mp4v') 
        out = cv2.VideoWriter(temp_output_path, fourcc, fps, (width, height))
        
        if not out.isOpened():
            log_debug("Failed to create video writer.")
            if progress_callback: progress_callback(1.0)
            if temp_output_path and os.path.exists(temp_output_path): os.unlink(temp_output_path) 
            return
            
        frame_count = 0
        last_progress_update_time = time.time()
        
        while not app_globals.stop_fast_processing_flag.is_set():
            ret, frame = cap.read()
            if not ret: break
                
            processed_frame = frame
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
            
            out.write(processed_frame)
            
            frame_count += 1
            current_time = time.time()
            if (current_time - last_progress_update_time >= 0.25 or frame_count == total_frames) and progress_callback: 
                progress = frame_count / total_frames if total_frames > 0 else 0
                progress_callback(progress)
                last_progress_update_time = current_time
        
        cap.release()
        out.release()
        
        if not app_globals.stop_fast_processing_flag.is_set():
            log_debug(f"Fast processing complete. Processed video saved to {temp_output_path}")
            app_globals.processed_video_temp_file_path_global = temp_output_path
        else:
            log_debug("Fast processing stopped by user.")
            if temp_output_path and os.path.exists(temp_output_path): os.unlink(temp_output_path) 
            app_globals.processed_video_temp_file_path_global = None 
        
        if progress_callback: progress_callback(1.0) 
            
    except Exception as e:
        log_debug(f"Error in fast video processing thread: {e}", exc_info=True)
        if progress_callback: progress_callback(1.0)
    finally:
        app_globals.fast_processing_active_flag.clear() 
        log_debug("Fast video processing thread ending.")
