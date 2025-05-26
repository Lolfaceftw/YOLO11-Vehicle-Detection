"""
File Handlers Module
Handles file upload operations and custom model file selection.
"""
import os
import threading
from tkinter import filedialog, messagebox

from . import _ui_shared_refs as refs
from . import _ui_loading_manager as loading_manager
from . import _ui_file_async as file_async
from . import globals as app_globals
from .logger_setup import log_debug
from .model_loader import set_custom_model_path, get_custom_model_path
from . import _ui_model_async as model_async


def handle_file_upload(stop_all_processing_logic_ref):
    """Handle file upload button click."""
    log_debug("handle_file_upload: 'Upload File' button pressed.")
    root = refs.get_root()
    ui_comps = refs.ui_components
    if not ui_comps or root is None or not root.winfo_exists():
        log_debug("handle_file_upload: UI components or root window not available.")
        return
    
    file_path = filedialog.askopenfilename(
        title="Select Image or Video",
        filetypes=[
            ("Media files", "*.jpg *.jpeg *.png *.mp4 *.avi *.mov *.mkv"),
            ("Images", "*.jpg *.jpeg *.png"), 
            ("Videos", "*.mp4 *.avi *.mov *.mkv"),
            ("All files", "*.*")
        ]
    )
    
    if not file_path:
        log_debug("handle_file_upload: No file selected.")
        return

    file_name = os.path.basename(file_path)
    log_debug(f"handle_file_upload: File selected: {file_path}")
    if ui_comps.get("file_upload_label"):
        ui_comps["file_upload_label"].config(text=file_name if len(file_name) < 50 else file_name[:47]+"...")
    
    loading_manager.show_loading("Processing uploaded file...") 
    if root and root.winfo_exists(): 
        root.update() 
    
    threading.Thread(target=file_async._process_uploaded_file_in_thread, 
                     args=(file_path, stop_all_processing_logic_ref), 
                     daemon=True).start()
    log_debug(f"File upload: Worker thread started for {file_path}.")


def handle_custom_model_upload(stop_all_processing_logic_ref):
    """Handle custom model file selection."""
    log_debug("handle_custom_model_upload: 'Browse .pt File' button pressed.")
    root = refs.get_root()
    ui_comps = refs.ui_components
    if not ui_comps or root is None or not root.winfo_exists():
        log_debug("handle_custom_model_upload: UI components or root window not available.")
        return
    
    file_path = filedialog.askopenfilename(
        title="Select Custom YOLO Model (.pt file)",
        filetypes=[
            ("PyTorch Model files", "*.pt"),
            ("All files", "*.*")
        ]
    )
    
    if not file_path:
        log_debug("handle_custom_model_upload: No model file selected.")
        return

    file_name = os.path.basename(file_path)
    log_debug(f"handle_custom_model_upload: Model file selected: {file_path}")
    
    # Update the custom model path in the model loader
    set_custom_model_path(file_path)
    
    # Update the UI label
    if ui_comps.get("custom_model_label"):
        display_name = file_name if len(file_name) < 35 else file_name[:32]+"..."
        ui_comps["custom_model_label"].config(text=display_name)
    
    # If "Select Custom Model" is currently selected, reload the model
    if ui_comps.get("model_var") and ui_comps["model_var"].get() == "Select Custom Model":
        log_debug("Custom model selected and 'Select Custom Model' is active. Reloading model...")
        model_async.run_model_load_in_thread("Select Custom Model", stop_all_processing_logic_ref)
    
    log_debug(f"Custom model file set: {file_path}")