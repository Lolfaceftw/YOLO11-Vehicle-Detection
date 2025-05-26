"""
Model Async Operations Module
Handles model loading operations in separate threads.
"""
import threading
import cv2

from . import _ui_shared_refs as refs
from . import _ui_loading_manager as loading_manager
from . import globals as app_globals
from .logger_setup import log_debug
from .model_loader import load_model
from .frame_processor import process_frame_yolo


def run_model_load_in_thread(selected_model_key, stop_all_processing_logic_ref):
    """Load a model in a separate thread to avoid blocking the UI."""
    log_debug(f"run_model_load_in_thread: Starting model load for {selected_model_key}")
    
    def load_model_task():
        """Model loading task that runs in a separate thread."""
        log_debug(f"Model loading task started for {selected_model_key}")
        
        try:
            success = load_model(selected_model_key)
            
            root = refs.get_root()
            ui_comps = refs.ui_components
            
            if success and root and root.winfo_exists():
                # Reprocess current image if one is loaded
                if (app_globals.current_uploaded_file_path_global and 
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
                        if ui_comps.get("video_display"):
                             ui_comps["video_display"].update_frame(processed_img)
                        print(f"Re-processed image with {selected_model_key}. Detected {detected_count} objects.")
                
                root.after(0, loading_manager.hide_loading_and_update_controls)
            else:
                root = refs.get_root()
                if root and root.winfo_exists():
                    root.after(0, loading_manager.hide_loading_and_update_controls)
                log_debug(f"Model loading failed for {selected_model_key}")
                
        except Exception as e:
            log_debug(f"Error in model loading task for {selected_model_key}: {e}", exc_info=True)
            root = refs.get_root()
            if root and root.winfo_exists():
                root.after(0, loading_manager.hide_loading_and_update_controls)
    
    # Stop any ongoing processing before loading new model
    if stop_all_processing_logic_ref:
        stop_all_processing_logic_ref()
    
    loading_manager.show_loading(f"Loading model: {selected_model_key}...")
    
    model_thread = threading.Thread(target=load_model_task, daemon=True)
    model_thread.start()
    log_debug(f"Model loading thread started for {selected_model_key}")