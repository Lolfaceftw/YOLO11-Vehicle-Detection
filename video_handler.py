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

def format_seconds_to_hhmmss(seconds):
    """Formats seconds into HH:MM:SS string."""
    seconds = max(0, int(seconds))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

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


def fast_video_processing_thread_func(video_file_path, progress_callback=None):
    """Thread function for batch processing a video and saving it to a temporary file. """
    log_debug(f"Fast video processing thread STARTS for {video_file_path}")

    temp_output_path_local = None
    success = False
    start_processing_time = time.time()
    frames_processed_since_last_rate_calc = 0
    time_of_last_rate_calc = start_processing_time
    processing_fps_estimate = 0

    try:
        cap = cv2.VideoCapture(video_file_path)
        if not cap.isOpened():
            log_debug(f"Error: Cannot open video file {video_file_path}")
            if progress_callback: progress_callback(1.0, "Error") # Signal completion with error
            return

        source_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        log_debug(f"Video properties: {source_fps} FPS, {total_frames} frames, {width}x{height}")

        if source_fps <= 0 or total_frames <= 0 or width <= 0 or height <= 0:
            log_debug("Invalid video properties. Cannot process.")
            if progress_callback: progress_callback(1.0, "Invalid Video") # Signal completion with error
            return

        fd, temp_output_path_local = tempfile.mkstemp(suffix='.mp4')
        os.close(fd)

        log_debug(f"Temporary output file: {temp_output_path_local}")

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(temp_output_path_local, fourcc, source_fps, (width, height))

        if not out.isOpened():
            log_debug("Failed to create video writer.")
            if temp_output_path_local and os.path.exists(temp_output_path_local): os.unlink(temp_output_path_local)
            if progress_callback: progress_callback(1.0, "Writer Error") # Signal completion with error
            return

        frame_count = 0
        last_progress_update_time = time.time()

        while not app_globals.stop_fast_processing_flag.is_set():
            ret, frame = cap.read()
            if not ret:
                log_debug(f"Fast process: End of input video at frame {frame_count}.")
                break

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
            frames_processed_since_last_rate_calc +=1
            current_time = time.time()

            if (current_time - last_progress_update_time >= 0.25 or frame_count == total_frames) and progress_callback:
                progress = frame_count / total_frames if total_frames > 0 else 0
                
                # Calculate processing FPS and estimated time remaining
                time_since_last_rate_calc = current_time - time_of_last_rate_calc
                if time_since_last_rate_calc > 0.5 : # Update rate every 0.5s
                    processing_fps_estimate = frames_processed_since_last_rate_calc / time_since_last_rate_calc
                    frames_processed_since_last_rate_calc = 0
                    time_of_last_rate_calc = current_time

                time_left_str = "--:--:--"
                if processing_fps_estimate > 0:
                    frames_remaining = total_frames - frame_count
                    seconds_left = frames_remaining / processing_fps_estimate
                    time_left_str = format_seconds_to_hhmmss(seconds_left)
                
                log_debug(f"Fast process: Calling progress_callback with {progress*100:.1f}% ({frame_count}/{total_frames}), Time Left: {time_left_str}")
                progress_callback(progress, time_left_str)
                last_progress_update_time = current_time

        cap.release()
        out.release()
        log_debug(f"Fast process: VideoWriter released for {temp_output_path_local}")

        time.sleep(0.1)

        if not app_globals.stop_fast_processing_flag.is_set():
            log_debug(f"Fast processing successfully completed. Processed video saved to {temp_output_path_local}")
            app_globals.processed_video_temp_file_path_global = temp_output_path_local
            success = True
            if progress_callback: progress_callback(1.0, "00:00:00") # Final update
        else:
            log_debug("Fast processing was stopped by user flag.")
            if temp_output_path_local and os.path.exists(temp_output_path_local): os.unlink(temp_output_path_local)
            app_globals.processed_video_temp_file_path_global = None
            if progress_callback: progress_callback(1.0, "Cancelled") # Final update

    except Exception as e:
        log_debug(f"Error in fast video processing thread: {e}", exc_info=True)
        if temp_output_path_local and os.path.exists(temp_output_path_local):
            try: os.unlink(temp_output_path_local)
            except OSError: pass
        app_globals.processed_video_temp_file_path_global = None
        if progress_callback: progress_callback(1.0, "Error") # Signal completion with error
    finally:
        log_debug(f"Fast process thread finally block. Success: {success}, Stop flag: {app_globals.stop_fast_processing_flag.is_set()}")
        # Ensure final callback if not already done by success/stopped/error paths
        # if progress_callback and not (success or app_globals.stop_fast_processing_flag.is_set()):
        #     progress_callback(1.0, "Finished")
        log_debug("Fast video processing thread FINISHED.")
