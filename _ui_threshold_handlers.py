"""
Threshold Handlers Module
Handles IoU and confidence threshold slider changes and image reprocessing.
"""
import cv2

from . import _ui_shared_refs as refs
from . import globals as app_globals
from .logger_setup import log_debug
from .frame_processor import process_frame_yolo


def handle_iou_change(*args):
    """Handle IoU threshold slider changes."""
    log_debug(f"handle_iou_change: IoU slider changed. Args: {args}")
    
    ui_comps = refs.ui_components
    if not ui_comps or not ui_comps.get("iou_var"):
        log_debug("IoU change: UI components not available.")
        return
    
    try:
        new_iou_value = ui_comps["iou_var"].get()
        app_globals.iou_threshold_global = new_iou_value
        
        log_debug(f"IoU threshold changed to {new_iou_value}")
        
        # Update display label
        if ui_comps.get("iou_value_label"):
            ui_comps["iou_value_label"].config(text=f"{new_iou_value:.2f}")
        
        # Reprocess current image if available
        if (app_globals.current_uploaded_file_path_global and 
            app_globals.current_uploaded_file_path_global.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tiff')) and
            app_globals.active_model_object_global):
            
            original_image_path = app_globals.current_uploaded_file_path_global
            img_to_reprocess = cv2.imread(original_image_path)
            
            if img_to_reprocess is not None:
                processed_img, detected_count = process_frame_yolo(
                    img_to_reprocess, app_globals.active_model_object_global, app_globals.active_class_list_global,
                    is_video_mode=False, active_filter_list=app_globals.active_processed_class_filter_global,
                    current_conf_thresh=app_globals.conf_threshold_global, 
                    current_iou_thresh=app_globals.iou_threshold_global  
                )
                app_globals.current_processed_image_for_display = processed_img 
                if ui_comps.get("video_display"): 
                    ui_comps["video_display"].update_frame(processed_img)
                print(f"Re-processed image with new IoU. Detected {detected_count} objects.")
        
    except Exception as e:
        log_debug(f"Error in handle_iou_change: {e}", exc_info=True)


def handle_conf_change(*args):
    """Handle confidence threshold slider changes."""
    log_debug(f"handle_conf_change: Conf slider changed. Args: {args}")
    
    ui_comps = refs.ui_components
    if not ui_comps or not ui_comps.get("conf_var"):
        log_debug("Conf change: UI components not available.")
        return
    
    try:
        new_conf_value = ui_comps["conf_var"].get()
        app_globals.conf_threshold_global = new_conf_value
        
        log_debug(f"Confidence threshold changed to {new_conf_value}")
        
        # Update display label
        if ui_comps.get("conf_value_label"):
            ui_comps["conf_value_label"].config(text=f"{new_conf_value:.2f}")
        
        # Reprocess current image if available
        if (app_globals.current_uploaded_file_path_global and 
            app_globals.current_uploaded_file_path_global.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp', '.tiff')) and
            app_globals.active_model_object_global):
            
            original_image_path = app_globals.current_uploaded_file_path_global
            img_to_reprocess = cv2.imread(original_image_path)
            
            if img_to_reprocess is not None:
                processed_img, detected_count = process_frame_yolo(
                    img_to_reprocess, app_globals.active_model_object_global, app_globals.active_class_list_global,
                    is_video_mode=False, active_filter_list=app_globals.active_processed_class_filter_global,
                    current_conf_thresh=app_globals.conf_threshold_global, 
                    current_iou_thresh=app_globals.iou_threshold_global  
                )
                app_globals.current_processed_image_for_display = processed_img
                if ui_comps.get("video_display"): 
                    ui_comps["video_display"].update_frame(processed_img)
                print(f"Re-processed image with new Conf. Detected {detected_count} objects.")
        
    except Exception as e:
        log_debug(f"Error in handle_conf_change: {e}", exc_info=True)


def update_threshold_displays():
    """Update threshold display labels with current values."""
    ui_comps = refs.ui_components
    if not ui_comps:
        return
    
    if ui_comps.get("iou_value_label"):
        ui_comps["iou_value_label"].config(text=f"{app_globals.iou_threshold_global:.2f}")
    
    if ui_comps.get("conf_value_label"):
        ui_comps["conf_value_label"].config(text=f"{app_globals.conf_threshold_global:.2f}")


def get_current_thresholds():
    """Get current IoU and confidence threshold values."""
    return {
        'iou': app_globals.iou_threshold_global,
        'conf': app_globals.conf_threshold_global
    }