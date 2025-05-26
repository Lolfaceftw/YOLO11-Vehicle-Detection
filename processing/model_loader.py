import torch
import os
from ultralytics import YOLO, RTDETR 
from app import config
from app.core import globals as app_globals
from app.utils.logger_setup import log_debug

log_debug("processing.model_loader module initialized.")

AVAILABLE_MODELS = {
    "YOLOv11x": {"loader": YOLO, "path": config.YOLO_MODEL_PATH, "instance": None, "class_list": {}},
    "YOLO11s-small_trained": {"loader": YOLO, "path": config.YOLO11S_SMALL_TRAINED_PATH, "instance": None, "class_list": {}},
    "RT-DETR-X": {"loader": RTDETR, "path": config.RTDETR_MODEL_PATH, "instance": None, "class_list": {}},
    "Select Custom Model": {"loader": YOLO, "path": "", "instance": None, "class_list": {}}
}

def set_custom_model_path(model_path):
    """Set the path for the custom model."""
    if "Select Custom Model" in AVAILABLE_MODELS:
        AVAILABLE_MODELS["Select Custom Model"]["path"] = model_path
        log_debug(f"Custom model path set to: {model_path}")

def get_custom_model_path():
    """Get the current custom model path."""
    if "Select Custom Model" in AVAILABLE_MODELS:
        return AVAILABLE_MODELS["Select Custom Model"]["path"]
    return ""

def is_custom_model_selected():
    """Check if a custom model is currently selected."""
    return app_globals.active_model_key == "Select Custom Model"

def _update_processed_class_filter():
    log_debug("Updating processed class filter.")
    valid_classes = []
    
    # Determine which filter indices to use based on the active model
    filter_indices = []
    if app_globals.active_model_key == "YOLO11s-small_trained":
        # Use indices for all custom classes in the trained model (0-7)
        filter_indices = list(range(8))  # 0, 1, 2, 3, 4, 5, 6, 7
        log_debug(f"Using custom class filter indices for {app_globals.active_model_key}: {filter_indices}")
    elif app_globals.active_model_key == "Select Custom Model":
        # For custom models, use all available classes by default
        if app_globals.active_class_list_global:
            filter_indices = list(app_globals.active_class_list_global.keys()) if isinstance(app_globals.active_class_list_global, dict) else list(range(len(app_globals.active_class_list_global)))
        log_debug(f"Using all class indices for custom model: {filter_indices}")
    else:
        # Use default filter indices for all other models
        filter_indices = config.YOLO_CLASS_FILTER_INDICES
    
    if filter_indices and app_globals.active_class_list_global:
        for c_idx in filter_indices:
            if isinstance(app_globals.active_class_list_global, dict):
                if c_idx in app_globals.active_class_list_global:
                    valid_classes.append(c_idx)
                else:
                    log_debug(f"Warning: Class index {c_idx} not in active model's class list (dict). It will be ignored.")
                    print(f"Warning: Class index {c_idx} not in active model's class list. It will be ignored.") # To standard console
            elif isinstance(app_globals.active_class_list_global, list): 
                 if 0 <= c_idx < len(app_globals.active_class_list_global):
                    valid_classes.append(c_idx)
                 else:
                    log_debug(f"Warning: Class index {c_idx} is out of bounds for active model's class list (list). It will be ignored.")
                    print(f"Warning: Class index {c_idx} is out of bounds for active model's class list. It will be ignored.") # To standard console
        if valid_classes:
            app_globals.active_processed_class_filter_global = valid_classes
            class_names_str = str([app_globals.active_class_list_global[i] for i in app_globals.active_processed_class_filter_global if i in app_globals.active_class_list_global])
            log_debug(f"Active model filtering for classes: {class_names_str}")
            print(f"Active model filtering for classes: {class_names_str}.") # To standard console
        else:
            app_globals.active_processed_class_filter_global = None
            log_debug("Warning: No valid class indices for active model. It will detect all classes.")
            print("Warning: No valid class indices for active model. It will detect all classes.") # To standard console
    else:
        app_globals.active_processed_class_filter_global = None
        log_debug("No class filter specified or model class list unavailable. Active model will detect all classes.")
        print("No class filter specified or model class list unavailable. Active model will detect all classes.") # To standard console

def load_model(model_key_to_load):
    log_debug(f"Attempting to load model: {model_key_to_load}")
    
    load_successful = False
    model_config = {} 

    try:
        if model_key_to_load not in AVAILABLE_MODELS:
            log_debug(f"Error: Unknown model key '{model_key_to_load}'. Cannot load.")
            print(f"Error: Unknown model key '{model_key_to_load}'. Cannot load.") # To standard console
            app_globals.active_model_object_global = None
            app_globals.active_class_list_global = {}
            return False

        model_config = AVAILABLE_MODELS[model_key_to_load]
        log_debug(f"Model config for {model_key_to_load}: {model_config['path']}")
        # print(f"Attempting to load model: {model_key_to_load} ({model_config['path']})") # To standard console

        model_path_from_config = model_config['path']
        model_identifier_for_loader = model_path_from_config # Default to the path in config

        # Validate custom model path
        if model_key_to_load == "Select Custom Model":
            if not model_path_from_config:
                log_debug("Error: Custom model selected but no .pt file path has been set.")
                print("Error: Custom model selected but no .pt file path has been set. Please browse and select a .pt file.") # To standard console
                return False
            if not os.path.exists(model_path_from_config):
                log_debug(f"Error: Custom model file not found at {model_path_from_config}.")
                print(f"Error: Custom model file not found at {model_path_from_config}. Please select a valid .pt file.") # To standard console
                return False
        
        # For pre-defined models, if not found at specified path, try to load by name (allowing Ultralytics to download)
        # Except for YOLO11s-small_trained which is explicitly local.
        elif model_key_to_load != "YOLO11s-small_trained" and not os.path.exists(model_path_from_config):
            # Extract the base filename or use a known hub identifier if different
            base_filename = os.path.basename(model_path_from_config) 
            # For RT-DETR-X, Ultralytics uses 'rtdetr-x.pt' for hub download.
            # For YOLO models, it's typically like 'yolov8x.pt'. We assume yolo11x.pt is custom or a specific file.
            # If yolo11x.pt is not standard, this won't download it unless Ultralytics recognizes the name.
            if model_key_to_load == "RT-DETR-X":
                 model_identifier_for_loader = 'rtdetr-x.pt' # Standard name for auto-download
                 log_debug(f"Model file not found at {model_path_from_config}. Attempting to load/download '{model_identifier_for_loader}' via Ultralytics.")
                 print(f"Model file {base_filename} not found locally. Attempting to download/load from Ultralytics hub as '{model_identifier_for_loader}'...")
            elif model_key_to_load == "YOLOv11x": # Assuming yolo11x.pt is a specific file name you expect
                 # If yolo11x.pt is not a standard Ultralytics model name that it can auto-download,
                 # then just using base_filename will likely only work if it's in a dir Ultralytics checks.
                 # For this case, if not at model_config['path'], it means it's an error unless yolo11x.pt is a hub model name.
                 # Sticking to previous logic for yolo11x.pt: if not at path, it is an error.
                 # However, the user wants a download if not found.
                 # The most robust way for a non-standard model is a direct download link + custom code, which is out of scope for this auto-fix.
                 # For now, we let it try to load by its base filename. If Ultralytics recognizes 'yolo11x.pt', it might work.
                 model_identifier_for_loader = base_filename 
                 log_debug(f"Model file {model_path_from_config} not found. Attempting to load/download '{model_identifier_for_loader}' via Ultralytics. This may fail if not a recognized name.")
                 print(f"Model file {base_filename} not found locally. Attempting to download/load from Ultralytics hub as '{model_identifier_for_loader}'...")
            # Else, for other potential future pre-defined models, we'd use base_filename by default.
            else:
                 model_identifier_for_loader = base_filename
                 log_debug(f"Model file not found at {model_path_from_config}. Attempting to load/download '{model_identifier_for_loader}' via Ultralytics.")
                 print(f"Model file {base_filename} not found locally. Attempting to download/load from Ultralytics hub as '{model_identifier_for_loader}'...")

        elif model_key_to_load == "YOLO11s-small_trained" and not os.path.exists(model_path_from_config):
            log_debug(f"Error: Trained model file {model_path_from_config} not found. This model cannot be auto-downloaded.")
            print(f"Error: Trained model file {model_path_from_config} not found. Please ensure it exists.")
            return False

        # Log final model identifier
        log_debug(f"Final model identifier for Ultralytics loader: '{model_identifier_for_loader}' for key '{model_key_to_load}'")
        print(f"Loading model: {model_key_to_load} using identifier: '{model_identifier_for_loader}'")

        current_attempt_device = 'cuda' if torch.cuda.is_available() else 'cpu'
        log_debug(f"{{'CUDA is available' if current_attempt_device == 'cuda' else 'CUDA not available. Using CPU'}} for {model_key_to_load}.")
        # print(f"{{'CUDA is available' if current_attempt_device == 'cuda' else 'CUDA not available. Using CPU'}} for {model_key_to_load}.") # To standard console
        
        model_loader_func = model_config['loader']
        
        # This was the old check that caused issues, now handled above with model_identifier_for_loader
        # if model_key_to_load == "RT-DETR-X" and not os.path.isabs(model_config['path']) and not os.path.exists(model_config['path']):
        #     log_debug(f"Using Ultralytics default loading for {model_key_to_load} with name '{model_config['path']}'.")
        # elif not os.path.exists(model_config['path']):
        #     if model_key_to_load != "RT-DETR-X": 
        #          print(f"Error: Model file not found at {model_config['path']}. Please ensure it exists.") # To standard console
        #          return False
        
        loaded_model = model_loader_func(model_identifier_for_loader) # Use the determined identifier
        
        try:
            loaded_model.to(current_attempt_device) 
            app_globals.device_to_use = current_attempt_device
            log_debug(f"{model_key_to_load} successfully configured for {app_globals.device_to_use}.")
            print(f"{model_key_to_load} successfully configured for {app_globals.device_to_use}.") # To standard console
        except Exception as e_device:
            log_debug(f"Error moving {model_key_to_load} to {current_attempt_device}: {e_device}. Falling back to CPU if applicable.", exc_info=True)
            print(f"Error moving {model_key_to_load} to {current_attempt_device}: {e_device}.") # To standard console
            if current_attempt_device == 'cuda':
                print(f"Falling back to CPU for {model_key_to_load}.") # To standard console
                app_globals.device_to_use = 'cpu'
                try:
                    loaded_model.to('cpu')
                    log_debug(f"{model_key_to_load} successfully configured for CPU after fallback.")
                    print(f"{model_key_to_load} successfully configured for CPU after fallback.") # To standard console
                except Exception as e_cpu_fallback:
                    log_debug(f"Error moving {model_key_to_load} to CPU during fallback: {e_cpu_fallback}. Model load failed.", exc_info=True)
                    print(f"Error moving {model_key_to_load} to CPU during fallback: {e_cpu_fallback}. Model might be unstable.") # To standard console
                    app_globals.active_model_object_global = None; app_globals.active_class_list_global = {}; model_config['instance'] = None; model_config['class_list'] = {}; return False
            else: 
                 actual_device = getattr(loaded_model.device, 'type', 'Unknown') 
                 log_debug(f"{model_key_to_load} remains on its initial device. Error was on CPU or non-CUDA device. Device: {actual_device}")
                 print(f"{model_key_to_load} remains on its initial device. Current model device: {actual_device}") # To standard console
                 app_globals.device_to_use = str(actual_device) if actual_device else 'cpu'

        app_globals.active_model_object_global = loaded_model
        app_globals.active_class_list_global = loaded_model.names if hasattr(loaded_model, 'names') else {}
        
        # Update category names for YOLO11s-small_trained model
        if model_key_to_load == "YOLO11s-small_trained":
            # Custom category names for the trained model
            app_globals.active_class_list_global = {0: 'bicycle', 1: 'bus', 2: 'car', 3: 'jeep', 4: 'motorcycle', 5: 'tricycle', 6: 'truck', 7: 'van'}
            log_debug(f"Using custom category names for {model_key_to_load}")
            print(f"Using custom category names for {model_key_to_load}: {app_globals.active_class_list_global}")
        elif model_key_to_load == "Select Custom Model":
            # For custom models, automatically detect class names from the .names attribute
            if hasattr(loaded_model, 'names') and loaded_model.names:
                app_globals.active_class_list_global = loaded_model.names
                log_debug(f"Automatically detected class names for custom model: {app_globals.active_class_list_global}")
                print(f"Custom model loaded with {len(app_globals.active_class_list_global)} classes: {list(app_globals.active_class_list_global.values())}")
            else:
                log_debug("Warning: Custom model does not have class names (.names attribute)")
                print("Warning: Custom model does not have class names available")
            
        app_globals.active_model_key = model_key_to_load 
        
        model_config['instance'] = app_globals.active_model_object_global
        model_config['class_list'] = app_globals.active_class_list_global
        
        _update_processed_class_filter()
        
        actual_device_str = str(getattr(app_globals.active_model_object_global.device, 'type', "Unknown"))
        log_debug(f"Model '{model_key_to_load}' loaded. Classes: {len(app_globals.active_class_list_global)}. Configured to run on: {actual_device_str}.")
        print(f"Model '{model_key_to_load}' loaded. Classes: {len(app_globals.active_class_list_global)}. Configured to run on: {actual_device_str}.") # To standard console
        load_successful = True
        return True

    except Exception as e:
        log_debug(f"General error loading model {model_key_to_load} ({model_config.get('path', 'N/A')}): {e}. Detection/tracking disabled.", exc_info=True)
        print(f"Error loading model {model_key_to_load} ({model_config.get('path', 'N/A')}): {e}. Detection/tracking with this model disabled.") # To standard console
        app_globals.active_model_object_global = None
        app_globals.active_class_list_global = {}
        if model_key_to_load in AVAILABLE_MODELS: 
            AVAILABLE_MODELS[model_key_to_load]['instance'] = None
            AVAILABLE_MODELS[model_key_to_load]['class_list'] = {}
        return False
    finally:
        log_debug(f"load_model finished. Load successful: {load_successful}")

def get_available_model_keys():
    return list(AVAILABLE_MODELS.keys())

def get_default_model_key():
    return config.DEFAULT_MODEL_KEY
