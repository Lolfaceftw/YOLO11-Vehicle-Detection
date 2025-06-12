"""
Core package initialization.
Contains main application logic, global states, and model/video processing.
"""
from app.utils.logger_setup import log_debug
log_debug("core package initialized.")

from app import config # Corrected import

# Import main application entry points
from .main_app import launch_app

# Import global states and core utilities
from .globals import (
    active_model_key, active_model_object_global, active_class_list_global, active_processed_class_filter_global,
    iou_threshold_global, conf_threshold_global, device_to_use,
    video_thread, stop_video_processing_flag, video_paused_flag, current_video_frame,
    video_capture_global, video_access_lock, is_playing_via_after_loop, after_id_playback_loop,
    current_video_meta, uploaded_file_info, current_uploaded_file_path_global,
    current_processed_image_for_display, current_unprocessed_image_for_display,
    fps_global, total_frames_global, current_frame_number_global
)

__all__ = [
    'launch_app',
    'config',
    # Globals (selectively exposed or managed internally)
    'active_model_key', 'active_model_object_global', 'active_class_list_global', 'active_processed_class_filter_global',
    'iou_threshold_global', 'conf_threshold_global', 'device_to_use',
    'video_thread', 'stop_video_processing_flag', 'video_paused_flag', 'current_video_frame',
    'video_capture_global', 'video_access_lock', 'is_playing_via_after_loop', 'after_id_playback_loop',
    'current_video_meta', 'uploaded_file_info', 'current_uploaded_file_path_global',
    'current_processed_image_for_display', 'current_unprocessed_image_for_display',
    'fps_global', 'total_frames_global', 'current_frame_number_global'
]