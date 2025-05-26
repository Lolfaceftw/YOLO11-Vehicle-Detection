"""
Model Async Operations Module
Handles model loading operations in separate threads.
"""
import threading
import cv2

from . import shared_refs as refs
from . import loading_manager
from app.core import globals as app_globals
from app.utils.logger_setup import log_debug
from app.processing.model_loader import load_model
from app.processing.frame_processor import process_frame_yolo
from . import file_async

log_debug("ui.handlers.model_async module initialized.")


def run_model_load_in_thread(selected_model_key, stop_all_processing_logic_ref):
    """Load a model in a separate thread to avoid blocking the UI."""
    log_debug(f"run_model_load_in_thread: Starting model load for {selected_model_key}")
    
    def load_model_task():
        """Model loading task that runs in a separate thread."""
        log_debug(f"Model loading task started for {selected_model_key}")
        model_load_success = False # Initialize
        video_file_to_reinitialize = None # Initialize
        root = refs.get_root() # Get root and ui_comps once
        ui_comps = refs.ui_components
        
        try:
            # Set active_model_key BEFORE attempting to load the model object.
            # This ensures the UI knows which model is intended, even if loading fails.
            app_globals.active_model_key = selected_model_key
            
            model_load_success = load_model(selected_model_key)
            
            # Determine if a video needs re-initialization regardless of model load success
            if app_globals.uploaded_file_info and app_globals.uploaded_file_info.get('file_type') == 'video':
                video_file_to_reinitialize = app_globals.uploaded_file_info.get('path')
            elif app_globals.current_uploaded_file_path_global and app_globals.current_uploaded_file_path_global.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
                video_file_to_reinitialize = app_globals.current_uploaded_file_path_global

            if video_file_to_reinitialize:
                log_debug(f"Model loading process for {selected_model_key} finished (Success: {model_load_success}). Re-initializing video: {video_file_to_reinitialize}")
                file_async.reinitialize_video_capture(video_file_to_reinitialize)
            
            if model_load_success and root and root.winfo_exists():
                # Reprocess current image if one is loaded (and not a video that was just reinitialized)
                if not video_file_to_reinitialize and (app_globals.current_uploaded_file_path_global and 
                    app_globals.current_uploaded_file_path_global.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tiff'))):
                    
                    original_image_path = app_globals.current_uploaded_file_path_global
                    img_to_reprocess = cv2.imread(original_image_path)
                    
                    if img_to_reprocess is not None:
                        log_debug(f"Re-processing image {original_image_path} with new model {selected_model_key}")
                        processed_img, detected_count = process_frame_yolo(
                            img_to_reprocess, app_globals.active_model_object_global, app_globals.active_class_list_global,
                            is_video_mode=False, active_filter_list=app_globals.active_processed_class_filter_global,
                            current_conf_thresh=app_globals.conf_threshold_global, current_iou_thresh=app_globals.iou_threshold_global
                        )
                        app_globals.current_processed_image_for_display = processed_img
                        if ui_comps and ui_comps.get("video_display"):
                             ui_comps["video_display"].update_frame(processed_img)
                        print(f"Re-processed image with {selected_model_key}. Detected {detected_count} objects.")
            elif not model_load_success:
                log_debug(f"Model loading failed for {selected_model_key}. Video re-initialization (if applicable) was still attempted.")
                
        except Exception as e:
            log_debug(f"Error in model loading task for {selected_model_key}: {e}", exc_info=True)
        finally:
            if root and root.winfo_exists():
                # Ensure UI controls are updated regardless of success/failure of model load or video re-init
                root.after(0, loading_manager.hide_loading_and_update_controls)
    
    # Stop any ongoing processing before loading new model
    if stop_all_processing_logic_ref:
        stop_all_processing_logic_ref()
    
    loading_manager.show_loading(f"Loading model: {selected_model_key}...")
    
    model_thread = threading.Thread(target=load_model_task, daemon=True)
    model_thread.start()
    log_debug(f"Model loading thread started for {selected_model_key}")