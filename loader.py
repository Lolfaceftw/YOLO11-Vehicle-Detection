import torch
import os
from ultralytics import YOLO, RTDETR # RTDETR might need specific import if not general
from . import config, globals as app_globals
from .logger_setup import log_debug

AVAILABLE_MODELS = {
    "YOLOv11x": {"loader": YOLO, "path": config.YOLO_MODEL_PATH, "instance": None, "class_list": {}},
    "RT-DETR-X": {"loader": RTDETR, "path": config.RTDETR_MODEL_PATH, "instance": None, "class_list": {}}
}

def _update_processed_class_filter():
    log_debug("Updating processed class filter.")
    valid_classes = []
    if config.YOLO_CLASS_FILTER_INDICES and app_globals.active_class_list_global:
        for c_idx in config.YOLO_CLASS_FILTER_INDICES:
            # Ensure active_class_list_global is a dict (standard for model.names)
            if isinstance(app_globals.active_class_list_global, dict):
                if c_idx in app_globals.active_class_list_global:
                    valid_classes.append(c_idx)
                else:
                    log_debug(f"Warning: Class index {c_idx} not in active model's class list (dict). It will be ignored.")
                    if app_globals.main_output_area_widget:
                        with app_globals.main_output_area_widget:
                            print(f"Warning: Class index {c_idx} not in active model's class list. It will be ignored.")
            elif isinstance(app_globals.active_class_list_global, list): # Less common, but handle
                 if 0 <= c_idx < len(app_globals.active_class_list_global):
                    valid_classes.append(c_idx)
                 else:
                    log_debug(f"Warning: Class index {c_idx} is out of bounds for active model's class list (list). It will be ignored.")
                    if app_globals.main_output_area_widget:
                        with app_globals.main_output_area_widget:
                             print(f"Warning: Class index {c_idx} is out of bounds for active model's class list. It will be ignored.")
        if valid_classes:
            app_globals.active_processed_class_filter_global = valid_classes
            class_names_str = str([app_globals.active_class_list_global[i] for i in app_globals.active_processed_class_filter_global if i in app_globals.active_class_list_global])
            log_debug(f"Active model filtering for classes: {class_names_str}")
            if app_globals.main_output_area_widget:
                with app_globals.main_output_area_widget:
                    print(f"Active model filtering for classes: {class_names_str}.")
        else:
            app_globals.active_processed_class_filter_global = None
            log_debug("Warning: No valid class indices for active model. It will detect all classes.")
            if app_globals.main_output_area_widget:
                with app_globals.main_output_area_widget:
                    print("Warning: No valid class indices for active model. It will detect all classes.")
    else:
        app_globals.active_processed_class_filter_global = None
        log_debug("No class filter specified or model class list unavailable. Active model will detect all classes.")
        if app_globals.main_output_area_widget:
            with app_globals.main_output_area_widget:
                print("No class filter specified or model class list unavailable. Active model will detect all classes.")

def load_model(model_key_to_load):
    log_debug(f"Attempting to load model: {model_key_to_load}")
    
    # Caller (e.g., in ui_callbacks) should handle show_loading/hide_loading
    
    load_successful = False
    model_config = {} # Initialize to prevent UnboundLocalError in except block

    try:
        if model_key_to_load not in AVAILABLE_MODELS:
            log_debug(f"Error: Unknown model key '{model_key_to_load}'. Cannot load.")
            if app_globals.main_output_area_widget:
                with app_globals.main_output_area_widget: print(f"Error: Unknown model key '{model_key_to_load}'. Cannot load.")
            app_globals.active_model_object_global = None
            app_globals.active_class_list_global = {}
            return False

        model_config = AVAILABLE_MODELS[model_key_to_load]
        log_debug(f"Model config for {model_key_to_load}: {model_config['path']}")
        if app_globals.main_output_area_widget:
            with app_globals.main_output_area_widget: print(f"Attempting to load model: {model_key_to_load} ({model_config['path']})")

        if not os.path.exists(model_config['path']) and model_key_to_load == "YOLOv11x": # Specific check for local model
             log_debug(f"Error: Model file not found at {model_config['path']}. Please ensure it exists.")
             if app_globals.main_output_area_widget:
                 with app_globals.main_output_area_widget: print(f"Error: Model file not found at {model_config['path']}. Please ensure it exists.")
             return False


        current_attempt_device = 'cuda' if torch.cuda.is_available() else 'cpu'
        log_debug(f"{'CUDA is available' if current_attempt_device == 'cuda' else 'CUDA not available. Using CPU'} for {model_key_to_load}.")
        if app_globals.main_output_area_widget:
            with app_globals.main_output_area_widget: print(f"{'CUDA is available' if current_attempt_device == 'cuda' else 'CUDA not available. Using CPU'} for {model_key_to_load}.")
        
        model_loader_func = model_config['loader']
        loaded_model = model_loader_func(model_config['path'])
        
        try:
            loaded_model.to(current_attempt_device) 
            app_globals.device_to_use = current_attempt_device
            log_debug(f"{model_key_to_load} successfully configured for {app_globals.device_to_use}.")
            if app_globals.main_output_area_widget:
                with app_globals.main_output_area_widget: print(f"{model_key_to_load} successfully configured for {app_globals.device_to_use}.")
        except Exception as e_device:
            log_debug(f"Error moving {model_key_to_load} to {current_attempt_device}: {e_device}. Falling back to CPU if applicable.", exc_info=True)
            if app_globals.main_output_area_widget:
                with app_globals.main_output_area_widget: print(f"Error moving {model_key_to_load} to {current_attempt_device}: {e_device}.")
            if current_attempt_device == 'cuda':
                if app_globals.main_output_area_widget:
                    with app_globals.main_output_area_widget: print(f"Falling back to CPU for {model_key_to_load}.")
                app_globals.device_to_use = 'cpu'
                try:
                    loaded_model.to('cpu')
                    log_debug(f"{model_key_to_load} successfully configured for CPU after fallback.")
                    if app_globals.main_output_area_widget:
                        with app_globals.main_output_area_widget: print(f"{model_key_to_load} successfully configured for CPU after fallback.")
                except Exception as e_cpu_fallback:
                    log_debug(f"Error moving {model_key_to_load} to CPU during fallback: {e_cpu_fallback}. Model load failed.", exc_info=True)
                    if app_globals.main_output_area_widget:
                        with app_globals.main_output_area_widget: print(f"Error moving {model_key_to_load} to CPU during fallback: {e_cpu_fallback}. Model might be unstable.")
                    app_globals.active_model_object_global = None; app_globals.active_class_list_global = {}; model_config['instance'] = None; model_config['class_list'] = {}; return False
            else: # Error occurred on CPU or non-CUDA device initially
                 actual_device = getattr(loaded_model, 'device', 'Unknown')
                 log_debug(f"{model_key_to_load} remains on its initial device. Error was on CPU or non-CUDA device. Device: {actual_device}")
                 if app_globals.main_output_area_widget:
                     with app_globals.main_output_area_widget: print(f"{model_key_to_load} remains on its initial device. Current model device: {actual_device}")
                 app_globals.device_to_use = str(actual_device) if actual_device else 'cpu'


        app_globals.active_model_object_global = loaded_model
        app_globals.active_class_list_global = loaded_model.names if hasattr(loaded_model, 'names') else {}
        app_globals.active_model_key = model_key_to_load # Update active model key in globals
        
        model_config['instance'] = app_globals.active_model_object_global
        model_config['class_list'] = app_globals.active_class_list_global
        
        _update_processed_class_filter()
        
        actual_device_str = str(getattr(app_globals.active_model_object_global, 'device', "Unknown"))
        log_debug(f"Model '{model_key_to_load}' loaded. Classes: {len(app_globals.active_class_list_global)}. Configured to run on: {actual_device_str}.")
        if app_globals.main_output_area_widget:
            with app_globals.main_output_area_widget: print(f"Model '{model_key_to_load}' loaded. Classes: {len(app_globals.active_class_list_global)}. Configured to run on: {actual_device_str}.")
        load_successful = True
        return True

    except Exception as e:
        log_debug(f"General error loading model {model_key_to_load} ({model_config.get('path', 'N/A')}): {e}. Detection/tracking disabled.", exc_info=True)
        if app_globals.main_output_area_widget:
            with app_globals.main_output_area_widget: print(f"Error loading model {model_key_to_load} ({model_config.get('path', 'N/A')}): {e}. Detection/tracking with this model disabled.")
        app_globals.active_model_object_global = None
        app_globals.active_class_list_global = {}
        if model_key_to_load in AVAILABLE_MODELS: # Ensure key exists before trying to modify
            AVAILABLE_MODELS[model_key_to_load]['instance'] = None
            AVAILABLE_MODELS[model_key_to_load]['class_list'] = {}
        return False
    finally:
        log_debug(f"load_model finished. Load successful: {load_successful}")
        # Caller handles hide_loading_and_update_controls

def get_available_model_keys():
    return list(AVAILABLE_MODELS.keys())

def get_default_model_key():
    return config.DEFAULT_MODEL_KEY