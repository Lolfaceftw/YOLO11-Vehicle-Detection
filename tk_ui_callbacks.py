"""
Tkinter UI Callbacks for the Vehicle Detection and Tracking Application
This module defines event handlers and callbacks for the UI components.
"""

import os
import io # Not used directly, but cv2.imdecode might use similar concepts
import sys
import cv2
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import numpy as np # Not used directly, but cv2 uses numpy arrays
import time
from PIL import Image, ImageTk

from . import globals as app_globals
from . import config
from .logger_setup import log_debug
from .model_loader import load_model as model_loader_load_model
from .frame_processor import process_frame_yolo
from .video_handler import (
    video_processing_thread_func, 
    fast_video_processing_thread_func,
    _cleanup_processed_video_temp_file,
    format_time_display
)
from .tk_ui_elements import LoadingOverlay


# Global references to UI components dictionary and root window
ui_components = {}
loading_overlay = None
root_window = None


def show_loading(message="Loading..."):
    """Show loading overlay with the given message"""
    log_debug(f"Showing loading overlay: {message}")
    global loading_overlay, root_window

    if root_window is None:
        log_debug("show_loading: root_window is None. Aborting.")
        return
    
    root_window.update_idletasks()

    if loading_overlay is not None and loading_overlay.winfo_exists():
        loading_overlay.update_message(message)
        loading_overlay.lift() 
        return
    
    try:
        if loading_overlay is None or not loading_overlay.winfo_exists():
            loading_overlay = LoadingOverlay(root_window, message)
        else: 
            loading_overlay.update_message(message)
            loading_overlay.lift()

        root_window.update_idletasks() 
    except Exception as e:
        log_debug(f"Error creating/updating loading overlay: {e}", exc_info=True)
        if app_globals.main_output_area_widget: 
             print(f"Loading: {message} (Overlay Error: {e})")
        else: 
             sys.stderr.write(f"Loading: {message} (Overlay Error: {e})\n")
    
    if ui_components:
        controls_to_disable = [
            "file_upload_button", "process_button", "fast_process_button",
            "iou_slider", "conf_slider",
            "play_pause_button", "stop_button", "progress_slider"
        ]
        for key in controls_to_disable:
            if key in ui_components and ui_components[key]:
                ui_components[key].config(state="disabled")
        
        if "model_buttons" in ui_components:
            for button in ui_components["model_buttons"]:
                if button: button.config(state="disabled")


def hide_loading_and_update_controls():
    """Hide loading overlay and update the state of UI controls"""
    log_debug("Hiding loading overlay and updating controls.")
    global loading_overlay, root_window
    
    if loading_overlay is not None and loading_overlay.winfo_exists():
        loading_overlay.destroy()
    loading_overlay = None 
    
    if not ui_components:
        log_debug("hide_loading_and_update_controls: ui_components is empty. Aborting.")
        return
    if root_window is None or not root_window.winfo_exists():
        log_debug("hide_loading_and_update_controls: root_window is not available. Aborting.")
        return

    is_fast_processing = app_globals.fast_processing_active_flag.is_set()
    model_loaded = app_globals.active_model_object_global is not None
    file_uploaded = bool(app_globals.uploaded_file_info and app_globals.uploaded_file_info.get('path'))
    is_video_file = file_uploaded and app_globals.uploaded_file_info.get('file_type', '') == 'video'
    
    ui_components["file_upload_button"].config(state="disabled" if is_fast_processing else "normal")

    for button in ui_components.get("model_buttons", []):
        button.config(state="disabled" if is_fast_processing else "normal")
    
    sliders_state = "normal" if model_loaded and not is_fast_processing else "disabled"
    ui_components["iou_slider"].config(state=sliders_state)
    ui_components["conf_slider"].config(state=sliders_state)
    
    can_process_realtime = file_uploaded and model_loaded and not is_fast_processing
    ui_components["process_button"].config(state="normal" if can_process_realtime else "disabled")
    ui_components["fast_process_button"].config(state="normal" if (can_process_realtime and is_video_file) else "disabled")

    is_video_playback_active = app_globals.video_thread and app_globals.video_thread.is_alive()
    
    is_processed_video_ready_for_playback = app_globals.processed_video_temp_file_path_global and \
                                           os.path.exists(app_globals.processed_video_temp_file_path_global) and \
                                           not is_video_playback_active 

    should_show_video_controls_ui = (is_video_file or is_processed_video_ready_for_playback) and not is_fast_processing

    play_pause_btn = ui_components["play_pause_button"]
    stop_btn = ui_components["stop_button"]
    prog_slider = ui_components["progress_slider"]
    prog_var = ui_components["progress_var"]
    time_lbl = ui_components["time_label"]

    if should_show_video_controls_ui:
        play_text = "Play"
        play_state = "disabled"
        stop_state = "disabled"

        if is_video_playback_active:
            play_text = "Pause" if not app_globals.video_paused_flag.is_set() else "Play"
            play_state = "normal"
            stop_state = "normal"
        elif is_processed_video_ready_for_playback or \
             (is_video_file and app_globals.video_capture_global and app_globals.video_capture_global.isOpened()):
            play_text = "Play"
            play_state = "normal"
            stop_state = "normal" 
        elif is_video_file and not (app_globals.video_capture_global and app_globals.video_capture_global.isOpened()):
            play_text = "Play"
            play_state = "normal" 
            stop_state = "disabled"


        play_pause_btn.config(text=play_text, state=play_state)
        stop_btn.config(state=stop_state)
        
        meta_total_frames = app_globals.current_video_meta.get('total_frames', 0)
        meta_fps = app_globals.current_video_meta.get('fps', 0)
        meta_duration = app_globals.current_video_meta.get('duration_seconds', 0)

        if meta_total_frames > 0:
            prog_slider.config(state="normal", to=float(meta_total_frames -1 if meta_total_frames > 0 else 0)) 
            if not is_video_playback_active:
                current_slider_val = prog_var.get()
                is_cap_closed_or_none = not (app_globals.video_capture_global and app_globals.video_capture_global.isOpened())
                
                if is_cap_closed_or_none or current_slider_val >= meta_total_frames -1 :
                     if current_slider_val != 0 : prog_var.set(0) 
            
            current_frame_for_time = prog_var.get()
            current_secs_for_time = current_frame_for_time / meta_fps if meta_fps > 0 else 0
            time_lbl.config(text=format_time_display(current_secs_for_time, meta_duration))
        else:
            prog_slider.config(state="disabled", to=100.0) 
            if prog_var.get() != 0: prog_var.set(0)
            time_lbl.config(text="00:00 / 00:00")
    else: 
        play_pause_btn.config(text="Play", state="disabled")
        stop_btn.config(state="disabled")
        prog_slider.config(state="disabled", to=100.0)
        if prog_var.get() != 0: prog_var.set(0)
        time_lbl.config(text="00:00 / 00:00")
        
    fast_progress_frame = ui_components["fast_progress_frame"]
    if is_fast_processing:
        if not fast_progress_frame.winfo_ismapped():
            fast_progress_frame.pack(fill="x", padx=config.SPACING_SMALL, pady=config.SPACING_SMALL, anchor="n")
    else:
        if fast_progress_frame.winfo_ismapped():
            fast_progress_frame.pack_forget()
            
    video_controls_frame = ui_components["video_controls_frame"]
    progress_frame = ui_components["progress_frame"]

    if should_show_video_controls_ui:
        if not video_controls_frame.winfo_ismapped():
            video_controls_frame.grid(row=0, column=0, sticky="ew", padx=2, pady=(2,0))
        if not progress_frame.winfo_ismapped():
            progress_frame.grid(row=1, column=0, sticky="ew", padx=2, pady=(0,2))
    else: 
        if video_controls_frame.winfo_ismapped(): video_controls_frame.grid_remove()
        if progress_frame.winfo_ismapped(): progress_frame.grid_remove()
    
    if not should_show_video_controls_ui and not is_fast_processing:
        is_static_image_type = file_uploaded and app_globals.uploaded_file_info.get('file_type', '') == 'image'
        is_static_image_processed = app_globals.current_processed_image_for_display is not None
        
        if not (is_static_image_type and is_static_image_processed):
             ui_components["video_display"].clear()
             log_debug("Cleared video_display as controls are hidden, not fast processing, and not showing a processed static image.")

    if root_window and root_window.winfo_exists(): 
        root_window.update_idletasks()
    log_debug("hide_loading_and_update_controls finished.")


def toggle_play_pause():
    """Toggle video playback between play and pause. Can also initiate playback of processed video."""
    global root_window
    log_debug("Play/Pause button clicked.")
    
    play_pause_btn = ui_components["play_pause_button"]

    if app_globals.video_thread and app_globals.video_thread.is_alive():
        if app_globals.video_paused_flag.is_set(): 
            app_globals.video_paused_flag.clear()
            play_pause_btn.config(text="Pause")
            log_debug("Video playback resumed.")
        else: 
            app_globals.video_paused_flag.set()
            play_pause_btn.config(text="Play")
            log_debug("Video playback paused.")
        return 

    is_processed_video_ready = app_globals.processed_video_temp_file_path_global and \
                               os.path.exists(app_globals.processed_video_temp_file_path_global)
    if is_processed_video_ready:
        log_debug("Starting playback of processed video.")
        show_loading("Loading processed video...")
        if root_window and root_window.winfo_exists(): root_window.update_idletasks()
        
        try:
            app_globals.stop_video_processing_flag.clear()
            app_globals.video_paused_flag.clear()
            
            video_path_to_play = app_globals.processed_video_temp_file_path_global
            
            with app_globals.video_access_lock:
                app_globals.video_capture_global = cv2.VideoCapture(video_path_to_play)
                if not app_globals.video_capture_global.isOpened():
                    log_debug(f"Could not open processed video file: {video_path_to_play}")
                    messagebox.showerror("Error", f"Could not open processed video file: {video_path_to_play}")
                    if root_window and root_window.winfo_exists(): root_window.after(0, hide_loading_and_update_controls)
                    return
                
                app_globals.current_video_meta['fps'] = app_globals.video_capture_global.get(cv2.CAP_PROP_FPS)
                app_globals.current_video_meta['total_frames'] = int(app_globals.video_capture_global.get(cv2.CAP_PROP_FRAME_COUNT))
                if app_globals.current_video_meta['fps'] > 0:
                    app_globals.current_video_meta['duration_seconds'] = \
                        app_globals.current_video_meta['total_frames'] / app_globals.current_video_meta['fps']
                else: 
                    app_globals.current_video_meta['duration_seconds'] = 0
                app_globals.current_video_meta['current_frame'] = 0
                ui_components["progress_var"].set(0)


            if ui_components["progress_slider"] and app_globals.current_video_meta['total_frames'] > 0:
                 ui_components["progress_slider"].config(to=float(app_globals.current_video_meta['total_frames']-1))
            
            app_globals.video_thread = threading.Thread(
                target=video_processing_thread_func,
                kwargs={
                    'frame_update_callback': lambda frame: ui_components["video_display"].update_frame(frame) if ui_components.get("video_display") else None,
                    'progress_update_callback': lambda frame_idx: update_progress(frame_idx) if ui_components else None,
                    'is_processed_video': True 
                }, daemon=True
            )
            app_globals.video_thread.start()
            play_pause_btn.config(text="Pause")
            log_debug("Processed video playback thread started.")

        except Exception as e:
            log_debug(f"Error starting playback of processed video: {e}", exc_info=True)
            messagebox.showerror("Error", f"Error playing processed video: {e}")
            _stop_all_processing_logic() 
        finally:
            if root_window and root_window.winfo_exists():
                 root_window.after(100, hide_loading_and_update_controls)
        return

    if app_globals.uploaded_file_info.get('file_type') == 'video' and \
       app_globals.uploaded_file_info.get('path') and \
       not (app_globals.video_capture_global and app_globals.video_capture_global.isOpened()):
        log_debug("Raw video uploaded. Play click implies starting real-time processing.")
        on_process_button_click() 
        return

    log_debug("Toggle_play_pause: No specific action taken (e.g., no video loaded or unexpected state).")
    if root_window and root_window.winfo_exists():
        hide_loading_and_update_controls()


def handle_model_selection_change(*args):
    """Handle model selection change"""
    log_debug("Model selection changed.")
    
    if not ui_components or root_window is None or not root_window.winfo_exists():
        log_debug("Model selection: UI components or root window not available.")
        return
    
    selected_model = ui_components["model_var"].get()
    if not selected_model:
        log_debug("No model selected.")
        return
    
    if selected_model == app_globals.active_model_key and app_globals.active_model_object_global is not None:
        log_debug(f"Model {selected_model} is already loaded and active.")
        print(f"Model {selected_model} is already active.")
        return

    log_debug(f"Selected model: {selected_model}")
    
    _stop_all_processing_logic() 
    
    show_loading(f"Loading model: {selected_model}...")
    
    def load_model_task():
        model_loader_load_model(selected_model)
        if root_window and root_window.winfo_exists():
             root_window.after(0, hide_loading_and_update_controls) 
        if app_globals.uploaded_file_info.get('file_type') == 'image' and \
           app_globals.current_processed_image_for_display is not None and \
           app_globals.active_model_object_global is not None: 
            try:
                original_image_path = app_globals.uploaded_file_info.get('path')
                if original_image_path and os.path.exists(original_image_path):
                    img_to_reprocess = cv2.imread(original_image_path)
                    if img_to_reprocess is not None:
                        log_debug(f"Re-processing image {original_image_path} with new model {selected_model}")
                        processed_img, detected_count = process_frame_yolo(
                            img_to_reprocess, app_globals.active_model_object_global, app_globals.active_class_list_global,
                            is_video_mode=False, active_filter_list=app_globals.active_processed_class_filter_global,
                            current_conf_thresh=app_globals.conf_threshold_global, current_iou_thresh=app_globals.iou_threshold_global
                        )
                        app_globals.current_processed_image_for_display = processed_img 
                        if ui_components.get("video_display"):
                             ui_components["video_display"].update_frame(processed_img)
                        print(f"Re-processed image with {selected_model}. Detected {detected_count} objects.")
                    else:
                        log_debug(f"Failed to re-read image for re-processing: {original_image_path}")
                else:
                    log_debug("Original image path not found for re-processing.")
            except Exception as e_reprocess:
                log_debug(f"Error re-processing image with new model: {e_reprocess}", exc_info=True)
                print(f"Error re-processing image: {e_reprocess}")


    threading.Thread(target=load_model_task, daemon=True).start()


def _process_uploaded_file_in_thread(file_path):
    """Worker thread for processing uploaded file (type check, read, initial setup)."""
    global root_window, ui_components
    log_debug(f"Thread started for processing file: {file_path}")
    file_type = None 
    success = False

    try:
        file_name = os.path.basename(file_path)
        _, ext = os.path.splitext(file_path.lower())
        
        mime_type = "" 
        if ext in ['.jpg', '.jpeg', '.png']:
            file_type = 'image'
            mime_type = f'image/{ext[1:]}'
        elif ext in ['.mp4', '.avi', '.mov', '.mkv']:
            file_type = 'video'
            mime_type = f'video/{ext[1:] if ext != ".mkv" else "x-matroska"}'
        else:
            log_debug(f"Unsupported file type in thread: {ext}")
            if root_window and root_window.winfo_exists():
                root_window.after(0, lambda: messagebox.showerror("Error", f"Unsupported file type: {ext}"))
            app_globals.uploaded_file_info = {}
            app_globals.current_video_meta.update({'fps': 0.0, 'total_frames': 0, 'duration_seconds': 0.0, 'current_frame': 0})
            app_globals.current_processed_image_for_display = None
            return 

        log_debug(f"File type determined in thread: {file_type}, mime: {mime_type}")

        app_globals.uploaded_file_info = {
            'path': file_path, 'name': file_name, 'type': mime_type, 'file_type': file_type
        }
        app_globals.current_video_meta.update({'fps': 0.0, 'total_frames': 0, 'duration_seconds': 0.0, 'current_frame': 0})
        app_globals.current_video_frame = None 
        app_globals.current_processed_image_for_display = None 

        _cleanup_processed_video_temp_file() 
        _stop_all_processing_logic() 

        if file_type == 'image':
            log_debug("Image file: reading in thread...")
            img = cv2.imread(file_path)
            if img is None:
                log_debug(f"Could not read image file in thread: {file_path}")
                if root_window and root_window.winfo_exists():
                    root_window.after(0, lambda: messagebox.showerror("Error", "Could not read image data."))
                app_globals.uploaded_file_info = {} 
                return

            app_globals.current_processed_image_for_display = img.copy() 
            
            display_img = img
            if app_globals.active_model_object_global:
                log_debug("Model loaded, processing uploaded image immediately.")
                processed_img, detected_count = process_frame_yolo(
                    img, app_globals.active_model_object_global, app_globals.active_class_list_global,
                    is_video_mode=False, active_filter_list=app_globals.active_processed_class_filter_global,
                    current_conf_thresh=app_globals.conf_threshold_global, current_iou_thresh=app_globals.iou_threshold_global
                )
                app_globals.current_processed_image_for_display = processed_img 
                display_img = processed_img
                if root_window and root_window.winfo_exists():
                    root_window.after(0, lambda count=detected_count: print(f"Processed uploaded image. Detected {count} objects."))
            
            if root_window and root_window.winfo_exists() and ui_components.get("video_display"):
                root_window.after(0, lambda bound_img=display_img: ui_components["video_display"].update_frame(bound_img))
            success = True

        elif file_type == 'video':
            log_debug("Video file: opening and reading first frame in thread.")
            with app_globals.video_access_lock: 
                if app_globals.video_capture_global and app_globals.video_capture_global.isOpened():
                    app_globals.video_capture_global.release()
                
                cap = cv2.VideoCapture(file_path)
                if not cap.isOpened():
                    log_debug(f"Could not open video file in thread: {file_path}")
                    if root_window and root_window.winfo_exists():
                        root_window.after(0, lambda: messagebox.showerror("Error", "Could not open video file."))
                    app_globals.uploaded_file_info = {}
                    return
                
                app_globals.video_capture_global = cap 
                
                fps = cap.get(cv2.CAP_PROP_FPS)
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                duration_seconds = total_frames / fps if fps > 0 else 0
                
                app_globals.current_video_meta.update({
                    'fps': fps, 'total_frames': total_frames, 'duration_seconds': duration_seconds, 'current_frame': 0
                })
                
                ret, first_frame = cap.read()
                app_globals.current_video_frame = first_frame.copy() if ret else None 
            
            if ret and first_frame is not None:
                display_frame = first_frame
                if app_globals.active_model_object_global:
                    processed_first_frame, _ = process_frame_yolo(
                        first_frame, app_globals.active_model_object_global, app_globals.active_class_list_global,
                        is_video_mode=True, 
                        active_filter_list=app_globals.active_processed_class_filter_global,
                        current_conf_thresh=app_globals.conf_threshold_global, current_iou_thresh=app_globals.iou_threshold_global
                    )
                    display_frame = processed_first_frame

                if root_window and root_window.winfo_exists():
                    def update_video_ui_on_upload():
                        if ui_components.get("video_display"):
                            ui_components["video_display"].update_frame(display_frame)
                        if ui_components.get("time_label"):
                            ui_components["time_label"].config(text=format_time_display(0, duration_seconds))
                        if ui_components.get("progress_slider") and total_frames > 0:
                            ui_components["progress_slider"].config(to=float(total_frames -1 if total_frames > 0 else 0))
                        if ui_components.get("progress_var"):
                            app_globals.is_programmatic_slider_update = True
                            try:
                                ui_components["progress_var"].set(0)
                            finally:
                                app_globals.is_programmatic_slider_update = False
                        hide_loading_and_update_controls()

                    root_window.after(0, update_video_ui_on_upload)
                success = True
            else: 
                log_debug(f"Failed to read first frame of video: {file_path}")
                if root_window and root_window.winfo_exists():
                     root_window.after(0, lambda: messagebox.showerror("Error", "Could not read first frame of video."))
                with app_globals.video_access_lock:
                    if app_globals.video_capture_global:
                        app_globals.video_capture_global.release()
                        app_globals.video_capture_global = None
                app_globals.uploaded_file_info = {}
        
        log_debug(f"Thread processing for {file_path} completed. Success: {success}")

    except Exception as e_thread:
        log_debug(f"General error in _process_uploaded_file_in_thread for {file_path}: {e_thread}", exc_info=True)
        if root_window and root_window.winfo_exists():
             root_window.after(0, lambda bound_e=e_thread: messagebox.showerror("Error", f"Error processing file: {bound_e}"))
        app_globals.uploaded_file_info = {} 
    finally:
        if not (file_type == 'video' and success):
            if root_window and root_window.winfo_exists():
                log_debug(f"Thread for {file_path} scheduling hide_loading_and_update_controls (non-video or error case).")
                root_window.after(100, hide_loading_and_update_controls)


def handle_file_upload():
    """Handle file upload button click"""
    global root_window 
    if not ui_components or root_window is None or not root_window.winfo_exists():
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
        log_debug("No file selected.")
        return

    file_name = os.path.basename(file_path)
    ui_components["file_upload_label"].config(text=file_name if len(file_name) < 50 else file_name[:47]+"...")
    
    show_loading("Processing uploaded file...") 
    if root_window and root_window.winfo_exists(): root_window.update() 
    
    threading.Thread(target=_process_uploaded_file_in_thread, args=(file_path,), daemon=True).start()
    log_debug(f"File upload: Worker thread started for {file_path}.")


def on_process_button_click():
    """Handle process button click (for images and real-time video)"""
    global root_window
    log_debug("Process button clicked.")
    
    if not app_globals.uploaded_file_info.get('path'): 
        messagebox.showerror("Error", "Please upload a file first.")
        return
    if not app_globals.active_model_object_global:
        messagebox.showerror("Error", "No model loaded. Please select a model.")
        return
    
    _stop_all_processing_logic() 
    
    file_type = app_globals.uploaded_file_info.get('file_type', '')
    file_path = app_globals.uploaded_file_info.get('path', '') 
    
    if file_type == 'image':
        log_debug(f"Processing image: {file_path}")
        show_loading("Processing image...")
        if root_window and root_window.winfo_exists(): root_window.update_idletasks()
        
        def process_image_task():
            try:
                img = cv2.imread(file_path)
                if img is None:
                    raise ValueError(f"Could not read image file: {file_path}")

                processed_img, detected_count = process_frame_yolo(
                    img, app_globals.active_model_object_global, app_globals.active_class_list_global,
                    is_video_mode=False, active_filter_list=app_globals.active_processed_class_filter_global,
                    current_conf_thresh=app_globals.conf_threshold_global, current_iou_thresh=app_globals.iou_threshold_global
                )
                app_globals.current_processed_image_for_display = processed_img 

                if root_window and root_window.winfo_exists():
                    def update_ui_after_image_processing():
                        if ui_components.get("video_display"):
                            ui_components["video_display"].update_frame(processed_img)
                        print(f"Processed image. Detected {detected_count} objects.")
                        hide_loading_and_update_controls()
                    root_window.after(0, update_ui_after_image_processing)
            except Exception as e:
                log_debug(f"Error processing image: {e}", exc_info=True)
                if root_window and root_window.winfo_exists():
                    root_window.after(0, lambda bound_e=e: messagebox.showerror("Error", f"Error processing image: {bound_e}"))
                    root_window.after(0, hide_loading_and_update_controls) 
        
        threading.Thread(target=process_image_task, daemon=True).start()
            
    elif file_type == 'video':
        log_debug(f"Preparing video for real-time analysis: {file_path}")
        show_loading("Preparing real-time analysis...")
        if root_window and root_window.winfo_exists(): root_window.update_idletasks()

        def process_video_task():
            try:
                with app_globals.video_access_lock:
                    if app_globals.video_capture_global and app_globals.video_capture_global.isOpened():
                        app_globals.video_capture_global.release()

                    app_globals.video_capture_global = cv2.VideoCapture(file_path)
                    if not app_globals.video_capture_global.isOpened():
                        raise ValueError(f"Could not open video file: {file_path}")
                    
                    app_globals.current_video_meta['fps'] = app_globals.video_capture_global.get(cv2.CAP_PROP_FPS)
                    app_globals.current_video_meta['total_frames'] = int(app_globals.video_capture_global.get(cv2.CAP_PROP_FRAME_COUNT))
                    if app_globals.current_video_meta['fps'] > 0:
                        app_globals.current_video_meta['duration_seconds'] = \
                            app_globals.current_video_meta['total_frames'] / app_globals.current_video_meta['fps']
                    else:
                        app_globals.current_video_meta['duration_seconds'] = 0
                    app_globals.current_video_meta['current_frame'] = 0
                    if ui_components.get("progress_var"): 
                        app_globals.is_programmatic_slider_update = True
                        try:
                            ui_components["progress_var"].set(0)
                        finally:
                            app_globals.is_programmatic_slider_update = False


                if root_window and root_window.winfo_exists():
                    def setup_video_ui_and_start_thread():
                        if ui_components.get("progress_slider") and app_globals.current_video_meta['total_frames'] > 0:
                            ui_components["progress_slider"].config(to=float(app_globals.current_video_meta['total_frames']-1))
                        
                        app_globals.stop_video_processing_flag.clear()
                        app_globals.video_paused_flag.clear()
                        
                        app_globals.video_thread = threading.Thread(
                            target=video_processing_thread_func,
                            kwargs={
                                'frame_update_callback': lambda frame: ui_components["video_display"].update_frame(frame) if ui_components.get("video_display") else None,
                                'progress_update_callback': lambda frame_idx: update_progress(frame_idx) if ui_components else None,
                                'is_processed_video': False 
                            }, daemon=True
                        )
                        app_globals.video_thread.start()
                        ui_components["play_pause_button"].config(text="Pause")
                        hide_loading_and_update_controls() 
                    
                    root_window.after(0, setup_video_ui_and_start_thread)

            except Exception as e:
                log_debug(f"Error preparing video for real-time analysis: {e}", exc_info=True)
                if root_window and root_window.winfo_exists():
                    root_window.after(0, lambda bound_e=e: messagebox.showerror("Error", f"Error processing video: {bound_e}"))
                    root_window.after(0, _stop_all_processing_logic) 
                    root_window.after(0, hide_loading_and_update_controls)
        
        threading.Thread(target=process_video_task, daemon=True).start()


def on_fast_process_button_click():
    """Handle fast process button click"""
    global root_window
    log_debug("Fast process button clicked.")
    
    if not app_globals.uploaded_file_info.get('path'):
        messagebox.showerror("Error", "Please upload a file first.")
        return
    if not app_globals.active_model_object_global:
        messagebox.showerror("Error", "No model loaded. Please select a model.")
        return
    if app_globals.uploaded_file_info.get('file_type', '') != 'video':
        messagebox.showerror("Error", "Fast processing is only available for video files.")
        return

    _stop_all_processing_logic() 
    
    file_path = app_globals.uploaded_file_info.get('path')
    log_debug(f"Preparing for fast video processing: {file_path}")
    
    app_globals.fast_processing_active_flag.set() 
    hide_loading_and_update_controls() 

    def fast_process_task():
        try:
            if app_globals.current_video_meta.get('total_frames', 0) == 0:
                temp_cap = cv2.VideoCapture(file_path)
                if temp_cap.isOpened():
                    app_globals.current_video_meta['fps'] = temp_cap.get(cv2.CAP_PROP_FPS)
                    app_globals.current_video_meta['total_frames'] = int(temp_cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    if app_globals.current_video_meta['fps'] > 0:
                        app_globals.current_video_meta['duration_seconds'] = \
                            app_globals.current_video_meta['total_frames'] / app_globals.current_video_meta['fps']
                    temp_cap.release()
                else:
                    raise ValueError(f"Fast Process: Could not open video file for metadata: {file_path}")
            
            app_globals.stop_fast_processing_flag.clear()
            if ui_components.get("fast_progress_var"):
                ui_components["fast_progress_var"].set(0) 
            
            app_globals.fast_video_processing_thread = threading.Thread(
                target=fast_video_processing_thread_func,
                kwargs={
                    'video_file_path': file_path,
                    'progress_callback': lambda progress: update_fast_progress(progress) if ui_components else None
                }, daemon=True
            )
            app_globals.fast_video_processing_thread.start()
            
        except Exception as e:
            log_debug(f"Error setting up fast processing: {e}", exc_info=True)
            if root_window and root_window.winfo_exists():
                root_window.after(0, lambda bound_e=e: messagebox.showerror("Error", f"Error setting up fast processing: {bound_e}"))
            app_globals.fast_processing_active_flag.clear() 
            if root_window and root_window.winfo_exists():
                root_window.after(0, hide_loading_and_update_controls) 

    threading.Thread(target=fast_process_task, daemon=True).start()


def update_fast_progress(progress_value): 
    """Update fast progress bar. Called from fast_video_processing_thread_func."""
    if ui_components.get("fast_progress_var") and root_window and root_window.winfo_exists():
        def do_update():
            ui_components["fast_progress_var"].set(int(progress_value * 100))
            
            if progress_value >= 1.0:
                log_debug("Fast processing completed (reported by progress callback).")
                app_globals.fast_processing_active_flag.clear()
                print("Fast video processing complete. Ready for playback.")
                hide_loading_and_update_controls() 
        
        root_window.after(0, do_update)


def update_progress(frame_idx):
    """Update progress slider and time label during video playback. Called from video_processing_thread_func."""
    if not ui_components or not root_window or not root_window.winfo_exists():
        return
    
    def do_update():
        log_debug(f"update_progress: Setting is_programmatic_slider_update = True. Frame: {frame_idx}")
        app_globals.is_programmatic_slider_update = True 
        try:
            if ui_components.get("progress_var"):
                log_debug(f"update_progress: Setting progress_var to {frame_idx}")
                ui_components["progress_var"].set(frame_idx)
            
            current_time_secs = 0
            total_duration_secs = app_globals.current_video_meta.get('duration_seconds', 0)
            fps = app_globals.current_video_meta.get('fps', 0)
            if fps > 0:
                current_time_secs = frame_idx / fps
            
            if ui_components.get("time_label"):
                ui_components["time_label"].config(
                    text=format_time_display(current_time_secs, total_duration_secs)
                )
        except Exception as e:
            log_debug(f"Exception in update_progress do_update: {e}", exc_info=True)
        finally:
            log_debug(f"update_progress: Resetting is_programmatic_slider_update = False. Frame: {frame_idx}")
            app_globals.is_programmatic_slider_update = False 

    root_window.after(0, do_update) 


def stop_video_stream_button_click():
    """Stop video playback or any ongoing video-related processing."""
    log_debug("Stop button clicked.")
    _stop_all_processing_logic() 
    
    if ui_components.get("video_display"):
        ui_components["video_display"].clear()
    app_globals.current_video_frame = None
    app_globals.current_video_meta['current_frame'] = 0
    if ui_components.get("progress_var"): 
        app_globals.is_programmatic_slider_update = True
        try:
            ui_components["progress_var"].set(0)
        finally:
            app_globals.is_programmatic_slider_update = False
            
    if ui_components.get("time_label"):
         ui_components["time_label"].config(text=format_time_display(0, app_globals.current_video_meta.get('duration_seconds',0)))

    hide_loading_and_update_controls() 


def _perform_seek_action():
    """Perform the actual seek operation to the selected frame. Called by debounced timer."""
    global root_window
    if not root_window or not root_window.winfo_exists() or not ui_components:
        log_debug("Seek action: Root window or UI components not available.")
        return

    log_debug(f"Performing seek action to frame: {app_globals.slider_target_frame_value}")
    show_loading("Seeking video...") 
    if root_window and root_window.winfo_exists(): root_window.update_idletasks()

    def seek_task():
        try:
            target_frame = int(app_globals.slider_target_frame_value)
            
            with app_globals.video_access_lock:
                if not app_globals.video_capture_global or not app_globals.video_capture_global.isOpened():
                    log_debug("No valid video capture for seeking.")
                    if root_window and root_window.winfo_exists(): root_window.after(0, hide_loading_and_update_controls)
                    return 
                
                was_playing = not app_globals.video_paused_flag.is_set() and \
                              (app_globals.video_thread and app_globals.video_thread.is_alive())
                
                if was_playing: 
                    app_globals.video_paused_flag.set()
                    if root_window and root_window.winfo_exists() and ui_components.get("play_pause_button"):
                        root_window.after(0, lambda: ui_components["play_pause_button"].config(text="Play"))
                
                app_globals.video_capture_global.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                ret, frame = app_globals.video_capture_global.read()
                
                if ret and frame is not None:
                    app_globals.current_video_frame = frame.copy() 
                    app_globals.current_video_meta['current_frame'] = target_frame

                    is_playing_processed_video = app_globals.processed_video_temp_file_path_global and \
                                                 os.path.exists(app_globals.processed_video_temp_file_path_global) and \
                                                 app_globals.video_capture_global.get(cv2.CAP_PROP_POS_FRAMES) >= 0 

                    output_frame_on_seek = frame
                    if not is_playing_processed_video and app_globals.active_model_object_global:
                        output_frame_on_seek, _ = process_frame_yolo(
                            frame, app_globals.active_model_object_global, app_globals.active_class_list_global,
                            is_video_mode=True, active_filter_list=app_globals.active_processed_class_filter_global,
                            current_conf_thresh=app_globals.conf_threshold_global, current_iou_thresh=app_globals.iou_threshold_global
                        )
                    
                    if root_window and root_window.winfo_exists():
                        def update_ui_after_seek():
                            if ui_components.get("video_display"):
                                ui_components["video_display"].update_frame(output_frame_on_seek)
                            
                            current_time_secs = 0
                            fps = app_globals.current_video_meta.get('fps', 0)
                            if fps > 0:
                                current_time_secs = target_frame / fps
                            if ui_components.get("time_label"):
                                ui_components["time_label"].config(
                                    text=format_time_display(current_time_secs, app_globals.current_video_meta.get('duration_seconds', 0))
                                )
                            if ui_components.get("progress_var"):
                                app_globals.is_programmatic_slider_update = True # Ensure this set is also flagged
                                try:
                                    ui_components["progress_var"].set(target_frame)
                                finally:
                                    app_globals.is_programmatic_slider_update = False
                            
                            hide_loading_and_update_controls()
                        root_window.after(0, update_ui_after_seek)
                else:
                    log_debug(f"Failed to read frame at position {target_frame}")
                    if root_window and root_window.winfo_exists():
                        root_window.after(0, lambda: messagebox.showinfo("Seek Info", "Could not seek to selected frame. End of video or read error."))
                        root_window.after(0, hide_loading_and_update_controls)
        except Exception as e:
            log_debug(f"Error during seek task: {e}", exc_info=True)
            if root_window and root_window.winfo_exists():
                root_window.after(0, lambda bound_e=e: messagebox.showerror("Seek Error", f"Error during seek: {bound_e}"))
                root_window.after(0, hide_loading_and_update_controls)
        
    threading.Thread(target=seek_task, daemon=True).start()


def handle_slider_value_change(*args): 
    """Handle changes to the progress slider with debouncing."""
    log_debug(f"handle_slider_value_change triggered. Programmatic update flag: {app_globals.is_programmatic_slider_update}")
    
    if app_globals.is_programmatic_slider_update: 
        log_debug("Slider change is programmatic. Updating time label only and returning.")
        try:
            # This path is taken when update_progress calls progress_var.set()
            # The time label is already updated within update_progress's do_update.
            # So, nothing strictly needs to be done here, but we log and return.
            # value = ui_components["progress_var"].get() # Already set
            # log_debug(f"Programmatic slider update to value: {value}")
            pass # Time label is handled by update_progress
        except Exception as e_slider_prog_update:
            log_debug(f"Error in programmatic slider update path (should be minimal): {e_slider_prog_update}")
        return 

    log_debug("Slider change is USER-INITIATED. Proceeding with seek logic.")
    if not ui_components or not root_window or not root_window.winfo_exists():
        log_debug("User-initiated slider change: UI components or root window not available.")
        return
    
    if not (app_globals.video_capture_global and app_globals.video_capture_global.isOpened()) or \
       ui_components["progress_slider"].cget("state") == "disabled":
        log_debug("User-initiated slider change: Video not ready or slider disabled.")
        # Update time label based on current slider value if it's just a disabled drag
        try:
            value = ui_components["progress_var"].get()
            current_time_secs = 0
            fps = app_globals.current_video_meta.get('fps', 0)
            if fps > 0: current_time_secs = value / fps
            if ui_components.get("time_label"):
                ui_components["time_label"].config(
                    text=format_time_display(current_time_secs, app_globals.current_video_meta.get('duration_seconds', 0))
                )
        except Exception as e_slider_val_disabled:
            log_debug(f"Minor error updating time label for disabled user slider action: {e_slider_val_disabled}")
        return

    try:
        value = ui_components["progress_var"].get() 
        app_globals.slider_target_frame_value = value
        log_debug(f"User-initiated slider target_frame_value set to: {value}")
    except tk.TclError: 
        log_debug("TclError getting slider value for user seek, possibly during shutdown.")
        return

    current_time_secs = 0
    fps = app_globals.current_video_meta.get('fps', 0)
    if fps > 0: current_time_secs = app_globals.slider_target_frame_value / fps
    
    if ui_components.get("time_label"):
        ui_components["time_label"].config(
            text=format_time_display(current_time_secs, app_globals.current_video_meta.get('duration_seconds', 0))
        )
    
    if app_globals.slider_debounce_timer:
        try:
            root_window.after_cancel(app_globals.slider_debounce_timer)
            log_debug("Cancelled existing debounce timer.")
        except tk.TclError: pass
    
    try:
        log_debug(f"Setting new debounce timer for seek to {app_globals.slider_target_frame_value}.")
        app_globals.slider_debounce_timer = root_window.after(
            int(config.SLIDER_DEBOUNCE_INTERVAL * 1000), 
            _perform_seek_action
        )
    except tk.TclError: 
        log_debug("TclError setting debounce timer for user seek, possibly during shutdown.")


def handle_iou_change(*args): 
    """Handle changes to the IoU threshold slider."""
    if not ui_components: return
    try:
        value = ui_components["iou_var"].get()
        app_globals.iou_threshold_global = value
        ui_components["iou_value_label"].config(text=f"{value:.2f}")
        log_debug(f"IoU threshold changed to {value}")

        if app_globals.uploaded_file_info.get('file_type') == 'image' and \
           app_globals.current_processed_image_for_display is not None and \
           app_globals.active_model_object_global is not None:
            original_image_path = app_globals.uploaded_file_info.get('path')
            if original_image_path and os.path.exists(original_image_path):
                img_to_reprocess = cv2.imread(original_image_path)
                if img_to_reprocess is not None:
                    processed_img, detected_count = process_frame_yolo(
                        img_to_reprocess, app_globals.active_model_object_global, app_globals.active_class_list_global,
                        is_video_mode=False, active_filter_list=app_globals.active_processed_class_filter_global,
                        current_conf_thresh=app_globals.conf_threshold_global, 
                        current_iou_thresh=app_globals.iou_threshold_global  
                    )
                    app_globals.current_processed_image_for_display = processed_img 
                    if ui_components.get("video_display"):
                        ui_components["video_display"].update_frame(processed_img)
                    print(f"Re-processed image with new IoU. Detected {detected_count} objects.")
    except tk.TclError:
        log_debug("TclError in handle_iou_change, possibly during shutdown.")


def handle_conf_change(*args): 
    """Handle changes to the confidence threshold slider."""
    if not ui_components: return
    try:
        value = ui_components["conf_var"].get()
        app_globals.conf_threshold_global = value
        ui_components["conf_value_label"].config(text=f"{value:.2f}")
        log_debug(f"Confidence threshold changed to {value}")

        if app_globals.uploaded_file_info.get('file_type') == 'image' and \
           app_globals.current_processed_image_for_display is not None and \
           app_globals.active_model_object_global is not None:
            original_image_path = app_globals.uploaded_file_info.get('path')
            if original_image_path and os.path.exists(original_image_path):
                img_to_reprocess = cv2.imread(original_image_path)
                if img_to_reprocess is not None:
                    processed_img, detected_count = process_frame_yolo(
                        img_to_reprocess, app_globals.active_model_object_global, app_globals.active_class_list_global,
                        is_video_mode=False, active_filter_list=app_globals.active_processed_class_filter_global,
                        current_conf_thresh=app_globals.conf_threshold_global, 
                        current_iou_thresh=app_globals.iou_threshold_global  
                    )
                    app_globals.current_processed_image_for_display = processed_img
                    if ui_components.get("video_display"):
                        ui_components["video_display"].update_frame(processed_img)
                    print(f"Re-processed image with new Conf. Detected {detected_count} objects.")
    except tk.TclError:
        log_debug("TclError in handle_conf_change, possibly during shutdown.")


def _stop_all_processing_logic():
    """Stop all video processing, playback, and fast processing logic. Also releases video capture."""
    log_debug("Stopping all video processing and playback logic.")
    
    if app_globals.fast_video_processing_thread and app_globals.fast_video_processing_thread.is_alive():
        app_globals.stop_fast_processing_flag.set()
        log_debug("Waiting for fast processing thread to join...")
        app_globals.fast_video_processing_thread.join(timeout=2.0) 
        if app_globals.fast_video_processing_thread.is_alive():
            log_debug("Fast processing thread did not join in time.")
        app_globals.fast_video_processing_thread = None
    app_globals.stop_fast_processing_flag.clear() 
    app_globals.fast_processing_active_flag.clear() 

    if app_globals.video_thread and app_globals.video_thread.is_alive():
        app_globals.stop_video_processing_flag.set()
        app_globals.video_paused_flag.clear() 
        log_debug("Waiting for real-time video thread to join...")
        app_globals.video_thread.join(timeout=2.0)
        if app_globals.video_thread.is_alive():
            log_debug("Real-time video thread did not join in time.")
        app_globals.video_thread = None
    app_globals.stop_video_processing_flag.clear()
    app_globals.video_paused_flag.clear() 
    
    with app_globals.video_access_lock:
        if app_globals.video_capture_global and app_globals.video_capture_global.isOpened():
            log_debug("Releasing video capture object.")
            app_globals.video_capture_global.release()
        app_globals.video_capture_global = None 
    
    if app_globals.slider_debounce_timer and root_window and root_window.winfo_exists():
        try:
            root_window.after_cancel(app_globals.slider_debounce_timer)
        except tk.TclError: pass 
        app_globals.slider_debounce_timer = None

    _cleanup_processed_video_temp_file()

    log_debug("All processing logic stopped and resources potentially released.")


def init_callbacks(root, components_dict):
    """Initialize callbacks with references to UI components.
    
    Args:
        root: Root Tkinter window
        components_dict: Dictionary of UI components
    """
    global ui_components, root_window
    ui_components = components_dict
    root_window = root
    
    ui_components["file_upload_button"].config(command=handle_file_upload)
    ui_components["process_button"].config(command=on_process_button_click)
    ui_components["fast_process_button"].config(command=on_fast_process_button_click)
    
    ui_components["iou_var"].trace_add("write", handle_iou_change)
    ui_components["conf_var"].trace_add("write", handle_conf_change)
    
    ui_components["model_var"].trace_add("write", handle_model_selection_change)
    
    ui_components["play_pause_button"].config(command=toggle_play_pause)
    ui_components["stop_button"].config(command=stop_video_stream_button_click)
    
    ui_components["progress_var"].trace_add("write", handle_slider_value_change)
    
    from .tk_ui_elements import RedirectText 
    sys.stdout = RedirectText(ui_components["output_text"])
    sys.stderr = RedirectText(ui_components["output_text"]) 

    log_debug("Tkinter callbacks initialized and stdout/stderr redirected.")
