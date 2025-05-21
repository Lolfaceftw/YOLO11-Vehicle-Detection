"""
Tkinter UI Callbacks for the Vehicle Detection and Tracking Application
This module defines event handlers and callbacks for the UI components.
"""

import os
import io
import sys
import cv2
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import numpy as np
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


# Global references to UI components
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
    
    if loading_overlay is not None:
        loading_overlay.update_message(message)
        return
    
    try:
        loading_overlay = LoadingOverlay(root_window, message)
        root_window.update_idletasks()
    except Exception as e:
        log_debug(f"Error creating loading overlay: {e}", exc_info=True)
        messagebox.showerror("Error", f"Error creating loading overlay: {e}")
    
    # Disable interactive controls
    if ui_components:
        ui_components["file_upload_button"].config(state="disabled")
        ui_components["process_button"].config(state="disabled")
        ui_components["fast_process_button"].config(state="disabled")
        
        for button in ui_components["model_buttons"]:
            button.config(state="disabled")
        
        ui_components["iou_slider"].config(state="disabled")
        ui_components["conf_slider"].config(state="disabled")
        ui_components["play_pause_button"].config(state="disabled")
        ui_components["stop_button"].config(state="disabled")
        ui_components["progress_slider"].config(state="disabled")


def hide_loading_and_update_controls():
    """Hide loading overlay and update the state of UI controls"""
    log_debug("Hiding loading overlay and updating controls.")
    global loading_overlay, root_window # Ensure root_window is accessible for update_idletasks
    
    if loading_overlay is not None:
        loading_overlay.destroy()
        loading_overlay = None
    
    if not ui_components:
        log_debug("hide_loading_and_update_controls: ui_components is empty. Aborting.")
        return
    
    # Determine current application state
    is_fast_processing = app_globals.fast_processing_active_flag.is_set()
    model_loaded = app_globals.active_model_object_global is not None
    file_uploaded = app_globals.uploaded_file_info is not None 
    is_video_file = file_uploaded and app_globals.uploaded_file_info.get('file_type', '') == 'video'
    
    # --- Step 1: Configure states of individual interactive elements ---
    
    file_upload_button = ui_components["file_upload_button"]
    new_fub_state = "disabled" if is_fast_processing else "normal"
    if file_upload_button.cget("state") != new_fub_state:
        file_upload_button.config(state=new_fub_state)

    for button in ui_components["model_buttons"]:
        new_mb_state = "disabled" if is_fast_processing else "normal"
        if button.cget("state") != new_mb_state: # type: ignore
            button.config(state=new_mb_state)
    
    sliders_disabled_state_actual = "disabled" if (not model_loaded or is_fast_processing) else "normal"
    iou_slider_widget = ui_components["iou_slider"]
    if iou_slider_widget.cget("state") != sliders_disabled_state_actual:
        iou_slider_widget.config(state=sliders_disabled_state_actual)

    conf_slider_widget = ui_components["conf_slider"]
    if conf_slider_widget.cget("state") != sliders_disabled_state_actual:
        conf_slider_widget.config(state=sliders_disabled_state_actual)
    
    can_process_realtime = file_uploaded and model_loaded and not is_fast_processing
    process_button_widget = ui_components["process_button"]
    new_pb_state = "normal" if can_process_realtime else "disabled"
    if process_button_widget.cget("state") != new_pb_state:
        process_button_widget.config(state=new_pb_state)

    fast_process_button_widget = ui_components["fast_process_button"]
    new_fpb_state = "normal" if (can_process_realtime and is_video_file) else "disabled"
    if fast_process_button_widget.cget("state") != new_fpb_state:
        fast_process_button_widget.config(state=new_fpb_state)

    # --- Step 2: Configure video-specific controls (state and values) ---
    is_video_playback_active = app_globals.video_thread and app_globals.video_thread.is_alive()
    is_processed_video_ready = app_globals.processed_video_temp_file_path_global and os.path.exists(app_globals.processed_video_temp_file_path_global)
    should_show_video_controls_ui = is_video_file and not is_fast_processing

    log_debug(f"hide_controls: is_fast_processing={is_fast_processing}, model_loaded={model_loaded}, file_uploaded={file_uploaded}, is_video_file={is_video_file}")
    log_debug(f"hide_controls: is_video_playback_active={is_video_playback_active}, is_processed_video_ready={is_processed_video_ready}, should_show_video_controls_ui={should_show_video_controls_ui}")
    if file_uploaded:
        log_debug(f"hide_controls: uploaded_file_info={app_globals.uploaded_file_info}")
    log_debug(f"hide_controls: current_video_meta={app_globals.current_video_meta}")

    play_pause_button_widget = ui_components["play_pause_button"]
    stop_button_widget = ui_components["stop_button"]
    progress_slider_widget = ui_components["progress_slider"]
    progress_var_widget = ui_components["progress_var"]
    time_label_widget = ui_components["time_label"]

    if should_show_video_controls_ui:
        new_play_text = ""
        new_play_state = ""
        new_stop_state = ""

        if is_video_playback_active:
            new_play_text = "Pause" if not app_globals.video_paused_flag.is_set() else "Play"
            new_play_state = "normal"
            new_stop_state = "normal"
        elif is_processed_video_ready or (is_video_file and file_uploaded): 
            new_play_text = "Play"
            new_play_state = "normal"
            new_stop_state = "normal" if app_globals.video_capture_global and app_globals.video_capture_global.isOpened() else "disabled"
        else: 
            new_play_text = "Play"
            new_play_state = "disabled"
            new_stop_state = "disabled"

        if play_pause_button_widget.cget("text") != new_play_text:
            play_pause_button_widget.config(text=new_play_text)
        if play_pause_button_widget.cget("state") != new_play_state:
            play_pause_button_widget.config(state=new_play_state)
        if stop_button_widget.cget("state") != new_stop_state:
            stop_button_widget.config(state=new_stop_state)
        
        meta_fps = app_globals.current_video_meta.get('fps', 0)
        meta_total_frames = app_globals.current_video_meta.get('total_frames', 0)
        meta_duration_seconds = app_globals.current_video_meta.get('duration_seconds', 0)

        current_progress_slider_to = progress_slider_widget.cget("to")
        
        if meta_total_frames > 0:
            new_progress_slider_state = "normal"
            new_progress_slider_to_val = float(meta_total_frames)
            
            if progress_slider_widget.cget("state") != new_progress_slider_state:
                progress_slider_widget.config(state=new_progress_slider_state)
            if abs(current_progress_slider_to - new_progress_slider_to_val) > 1e-9: # Compare floats
                 progress_slider_widget.config(to=new_progress_slider_to_val)

            if not is_video_playback_active:
                current_slider_val = progress_var_widget.get()
                if not (app_globals.video_capture_global and app_globals.video_capture_global.isOpened()) or \
                   current_slider_val >= meta_total_frames:
                    if current_slider_val != 0:
                        progress_var_widget.set(0)
            
            current_frame_for_time = progress_var_widget.get()
            current_secs_for_time = current_frame_for_time / meta_fps if meta_fps > 0 else 0
            new_time_label_text = format_time_display(current_secs_for_time, meta_duration_seconds)
            if time_label_widget.cget("text") != new_time_label_text:
                time_label_widget.config(text=new_time_label_text)
        else:
            default_to_val = 100.0
            if progress_slider_widget.cget("state") != "disabled":
                progress_slider_widget.config(state="disabled")
            # Get current_progress_slider_to again as it might have been set above if meta_total_frames was >0 then became 0
            current_progress_slider_to = progress_slider_widget.cget("to")
            if abs(current_progress_slider_to - default_to_val) > 1e-9:
                 progress_slider_widget.config(to=default_to_val)
            
            if progress_var_widget.get() != 0:
                progress_var_widget.set(0)
            default_time_text = "00:00 / 00:00"
            if time_label_widget.cget("text") != default_time_text:
                time_label_widget.config(text=default_time_text)
    else: 
        # Video controls are hidden
        if play_pause_button_widget.cget("text") != "Play":
            play_pause_button_widget.config(text="Play")
        if play_pause_button_widget.cget("state") != "disabled":
            play_pause_button_widget.config(state="disabled")
        if stop_button_widget.cget("state") != "disabled":
            stop_button_widget.config(state="disabled")
        
        current_progress_slider_to = progress_slider_widget.cget("to")
        default_to_val = 100.0
        if progress_slider_widget.cget("state") != "disabled":
            progress_slider_widget.config(state="disabled")
        if abs(current_progress_slider_to - default_to_val) > 1e-9: # Compare floats for 'to'
             progress_slider_widget.config(to=default_to_val)
        if progress_var_widget.get() != 0:
            progress_var_widget.set(0)
        default_time_text = "00:00 / 00:00"
        if time_label_widget.cget("text") != default_time_text:
            time_label_widget.config(text=default_time_text)
        
    # --- Step 3: Update visibility of container frames ---
    fast_progress_frame_widget = ui_components["fast_progress_frame"]
    if is_fast_processing:
        if not fast_progress_frame_widget.winfo_ismapped():
            fast_progress_frame_widget.pack(fill="x", padx=10, pady=5)
    else:
        if fast_progress_frame_widget.winfo_ismapped():
            fast_progress_frame_widget.pack_forget()
            
    video_controls_frame_widget = ui_components["video_controls_frame"]
    progress_frame_widget = ui_components["progress_frame"]
    if should_show_video_controls_ui:
        if not video_controls_frame_widget.winfo_ismapped():
            video_controls_frame_widget.grid(row=0, column=0, sticky="ew", padx=5, pady=(5,0))
        if not progress_frame_widget.winfo_ismapped():
            progress_frame_widget.grid(row=1, column=0, sticky="ew", padx=5, pady=(0,5))
    else: 
        if video_controls_frame_widget.winfo_ismapped():
            video_controls_frame_widget.grid_remove()
        if progress_frame_widget.winfo_ismapped():
            progress_frame_widget.grid_remove()    
    
    if not should_show_video_controls_ui and not is_fast_processing:
        is_static_image_displayed = file_uploaded and app_globals.uploaded_file_info.get('file_type', '') == 'image' and app_globals.current_processed_image_for_display is not None
        if not is_static_image_displayed:
             # Assuming video_display has a cget method or similar to check current state if "clear" is expensive
             # For now, direct call if logic implies it should be cleared.
             ui_components["video_display"].clear() # Consider if clear() itself has internal checks or is lightweight
             log_debug("Cleared video_display as controls are hidden, not fast processing, and not showing a static image.")

    if root_window: 
        root_window.update_idletasks()
    log_debug("hide_loading_and_update_controls finished.")


def toggle_play_pause():
    """Toggle video playback between play and pause"""
    global root_window
    log_debug("Play/Pause button clicked.")
    
    play_pause_btn = ui_components["play_pause_button"] # Get reference once

    if not app_globals.video_capture_global and not (app_globals.processed_video_temp_file_path_global and os.path.exists(app_globals.processed_video_temp_file_path_global)):
        log_debug("No video capture available and no processed video ready.")
        if app_globals.uploaded_file_info.get('file_type') == 'video' and app_globals.uploaded_file_info.get('path'):
            log_debug("Raw video uploaded. Attempting to start its playback.")
            messagebox.showinfo("Info", "Please use 'Process Real Time' or 'Fast Process' to start video playback.")
            return
        else:
            return

    is_video_playback_active = app_globals.video_thread and app_globals.video_thread.is_alive()
    is_processed_video_ready = app_globals.processed_video_temp_file_path_global and os.path.exists(app_globals.processed_video_temp_file_path_global)
    
    if is_video_playback_active:
        if app_globals.video_paused_flag.is_set(): # Was paused, now resuming
            app_globals.video_paused_flag.clear()
            if play_pause_btn.cget("text") != "Pause":
                play_pause_btn.config(text="Pause")
            log_debug("Video playback resumed.")
        else: # Was playing, now pausing
            app_globals.video_paused_flag.set()
            if play_pause_btn.cget("text") != "Play":
                play_pause_btn.config(text="Play")
            log_debug("Video playback paused.")
    elif is_processed_video_ready:
        log_debug("Starting playback of processed video.")
        show_loading("Loading processed video...")
        if root_window:
            root_window.update_idletasks()
        try:
            app_globals.stop_video_processing_flag.clear()
            app_globals.video_paused_flag.clear()
            
            with app_globals.video_access_lock:
                app_globals.video_capture_global = cv2.VideoCapture(app_globals.processed_video_temp_file_path_global)
                if not app_globals.video_capture_global.isOpened():
                    log_debug(f"Could not open processed video file: {app_globals.processed_video_temp_file_path_global}")
                    messagebox.showerror("Error", "Could not open processed video file.")
                    # Ensure loading is hidden on error before returning
                    if root_window: root_window.after(0, hide_loading_and_update_controls)
                    return 
                
                # Safely get metadata if not already present, but prefer it from upload time
                if app_globals.current_video_meta.get('total_frames', 0) == 0 or \
                   app_globals.current_video_meta.get('fps', 0) == 0:
                    app_globals.current_video_meta['fps'] = app_globals.video_capture_global.get(cv2.CAP_PROP_FPS)
                    app_globals.current_video_meta['total_frames'] = int(app_globals.video_capture_global.get(cv2.CAP_PROP_FRAME_COUNT))
                    if app_globals.current_video_meta.get('fps', 0) > 0:
                        app_globals.current_video_meta['duration_seconds'] = app_globals.current_video_meta.get('total_frames', 0) / app_globals.current_video_meta.get('fps', 1) # Avoid div by zero
            
            if root_window: 
                root_window.update_idletasks()

            meta_total_frames = app_globals.current_video_meta.get('total_frames', 0)
            if ui_components and meta_total_frames > 0:
                progress_slider_widget = ui_components["progress_slider"]
                current_progress_slider_to = progress_slider_widget.cget("to")
                if abs(current_progress_slider_to - float(meta_total_frames)) > 1e-9:
                    progress_slider_widget.config(to=float(meta_total_frames))
            
            app_globals.video_thread = threading.Thread(
                target=video_processing_thread_func,
                kwargs={
                    'frame_update_callback': lambda frame: ui_components["video_display"].update_frame(frame) if ui_components else None,
                    'progress_update_callback': lambda frame_idx: update_progress(frame_idx),
                    'is_processed_video': True
                }, daemon=True
            )
            app_globals.video_thread.start()
            if play_pause_btn.cget("text") != "Pause":
                play_pause_btn.config(text="Pause")
        except Exception as e:
            log_debug(f"Error starting playback of processed video: {e}", exc_info=True)
            messagebox.showerror("Error", f"Error playing processed video: {e}")
            _stop_all_processing_logic()
        else:
            # This code only runs if no exception was raised
            default_to_val = 100.0
            
            # Ensure we have references to all UI widgets needed
            progress_slider_widget = ui_components.get("progress_slider")
            progress_var_widget = ui_components.get("progress_var")
            time_label_widget = ui_components.get("time_label")
            
            # Get current value before modifying - make sure progress_slider_widget exists
            current_progress_slider_to = 0
            if progress_slider_widget:
                current_progress_slider_to = progress_slider_widget.cget("to")
                if progress_slider_widget.cget("state") != "disabled":
                    progress_slider_widget.config(state="disabled")
                if abs(current_progress_slider_to - default_to_val) > 1e-9:
                    progress_slider_widget.config(to=default_to_val)
            
            # Update progress var if it exists
            if progress_var_widget and progress_var_widget.get() != 0:
                progress_var_widget.set(0)
            
            # Update time label if it exists
            default_time_text = "00:00 / 00:00"
            if time_label_widget and time_label_widget.cget("text") != default_time_text:
                time_label_widget.config(text=default_time_text)
        finally:
            # Defer this call to ensure loading screen has a chance to show and operations to start
            if root_window:
                root_window.after(100, hide_loading_and_update_controls)


def handle_model_selection_change(*args):
    """Handle model selection change"""
    log_debug("Model selection changed.")
    
    if not ui_components:
        return
    
    selected_model = ui_components["model_var"].get()
    if not selected_model:
        log_debug("No model selected.")
        return
    
    log_debug(f"Selected model: {selected_model}")
    
    # Stop any active processing
    _stop_all_processing_logic()
    
    # Show loading overlay
    show_loading(f"Loading model: {selected_model}...")
    
    # Schedule model loading in a separate thread to avoid blocking UI
    threading.Thread(
        target=lambda: [
            model_loader_load_model(selected_model),
            root_window.after(100, hide_loading_and_update_controls) if root_window else None
        ],
        daemon=True
    ).start()


def _process_uploaded_file_in_thread(file_path):
    """Worker thread target for processing uploaded file (type check, read, initial setup)."""
    global root_window, ui_components # Ensure access
    log_debug(f"Thread started for processing file: {file_path}")
    file_type = None # Initialize to ensure it's defined for the finally block log

    try:
        # Determine file type
        file_name = os.path.basename(file_path)
        _, ext = os.path.splitext(file_path.lower())
        
        if ext in ['.jpg', '.jpeg', '.png']:
            file_type = 'image'
            mime_type = f'image/{ext[1:]}'
        elif ext in ['.mp4', '.avi', '.mov', '.mkv']:
            file_type = 'video'
            mime_type = f'video/{ext[1:] if ext != ".mkv" else "x-matroska"}'
        else:
            log_debug(f"Unsupported file type in thread: {ext}")
            if root_window: # Ensure root_window is available
                root_window.after(0, lambda: messagebox.showerror("Error", f"Unsupported file type: {ext}"))
            # Still update globals to reflect no valid file, then hide loading
            app_globals.uploaded_file_info = {} 
            app_globals.current_video_meta.update({'fps': 0.0, 'total_frames': 0, 'duration_seconds': 0.0})
            # _stop_all_processing_logic() # Not strictly needed here as it's about upload state
            return # Important to return before further processing or final hide_loading if error handled

        log_debug(f"File type determined in thread: {file_type}, mime: {mime_type}")

        # Update globals (careful with shared state, but this is primary setup)
        app_globals.uploaded_file_info = {
            'path': file_path, 'name': file_name, 'type': mime_type, 'file_type': file_type
        }
        app_globals.current_video_meta.update({'fps': 0.0, 'total_frames': 0, 'duration_seconds': 0.0, 'current_frame': 0})
        app_globals.current_video_frame = None
        app_globals.current_processed_image_for_display = None
        
        # These are safe to call from thread as they don't directly interact with UI widgets
        _cleanup_processed_video_temp_file() 
        _stop_all_processing_logic() # Stop any previous playback/processing

        if file_type == 'image':
            log_debug("Image file: reading in thread...")
            try:
                img = cv2.imread(file_path) # This is the blocking call
                if img is None:
                    log_debug(f"Could not read image file in thread: {file_path}")
                    if root_window:
                        root_window.after(0, lambda: messagebox.showerror("Error", "Could not read image data."))
                    app_globals.uploaded_file_info = {} # Invalidate on error
                    return # Exit before trying to display

                app_globals.current_processed_image_for_display = img
                log_debug("Image read in thread. Scheduling UI update.")
                if root_window and ui_components.get("video_display"):
                    # Schedule the UI update back to the main thread
                    root_window.after(0, lambda bound_img=img: ui_components["video_display"].update_frame(bound_img))
            except Exception as e_img:
                log_debug(f"Error reading/processing image in thread {file_path}: {e_img}", exc_info=True)
                if root_window:
                    root_window.after(0, lambda: messagebox.showerror("Error", f"Could not display image: {e_img}"))
                app_globals.uploaded_file_info = {} # Invalidate on error
                return # Exit

        elif file_type == 'video':
            log_debug("Video file: opening and reading first frame in thread.")
            try:
                # Open the video file and get metadata
                with app_globals.video_access_lock:
                    cap = cv2.VideoCapture(file_path)
                    if not cap.isOpened():
                        log_debug(f"Could not open video file in thread: {file_path}")
                        if root_window:
                            root_window.after(0, lambda: messagebox.showerror("Error", "Could not open video file."))
                        app_globals.uploaded_file_info = {}  # Invalidate on error
                        return  # Exit before trying to display
                    
                    # Get and store video metadata
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    if fps > 0:
                        duration_seconds = total_frames / fps
                    else:
                        duration_seconds = 0
                        
                    app_globals.current_video_meta.update({
                        'fps': fps,
                        'total_frames': total_frames,
                        'duration_seconds': duration_seconds,
                        'current_frame': 0
                    })
                    
                    # Read the first frame
                    ret, first_frame = cap.read()
                    app_globals.current_video_frame = first_frame.copy() if ret else None
                    
                    # Store the video capture for later use
                    app_globals.video_capture_global = cap
                
                # If we successfully read the first frame, display it
                if ret and first_frame is not None:
                    # Check if we should process the frame with YOLO
                    if app_globals.active_model_object_global is not None:
                        processed_frame, _ = process_frame_yolo(
                            first_frame, 
                            app_globals.active_model_object_global,
                            app_globals.active_class_list_global,
                            is_video_mode=True,
                            active_filter_list=app_globals.active_processed_class_filter_global,
                            current_conf_thresh=app_globals.conf_threshold_global,
                            current_iou_thresh=app_globals.iou_threshold_global
                        )
                    else:
                        processed_frame = first_frame
                    
                    # Schedule the UI updates back to the main thread
                    if root_window:
                        # Create lists of UI update functions that will be chained
                        ui_updates = []
                        
                        # Update video display
                        if ui_components.get("video_display"):
                            ui_updates.append(lambda frame=processed_frame: ui_components["video_display"].update_frame(frame))
                        
                        # Update time label
                        if ui_components.get("time_label"):
                            time_text = format_time_display(0, duration_seconds)
                            ui_updates.append(lambda text=time_text: ui_components["time_label"].config(text=text))
                        
                        # Update progress slider
                        if ui_components.get("progress_slider") and total_frames > 0:
                            ui_updates.append(lambda frames=total_frames: ui_components["progress_slider"].config(to=frames))
                            
                        # Reset progress var
                        if ui_components.get("progress_var"):
                            ui_updates.append(lambda: ui_components["progress_var"].set(0))
                        
                        # Chain the UI updates together to ensure they happen in sequence
                        # and don't interfere with the loading display
                        def chain_updates(update_index=0):
                            if update_index < len(ui_updates):
                                ui_updates[update_index]()
                                root_window.after(10, lambda: chain_updates(update_index + 1))
                        
                        # Start the chain after a short delay to ensure loading screen is visible
                        root_window.after(100, lambda: chain_updates())
            except Exception as e_video:
                log_debug(f"Error reading/processing video in thread {file_path}: {e_video}", exc_info=True)
                if root_window:
                    root_window.after(0, lambda: messagebox.showerror("Error", f"Could not display video: {e_video}"))
                app_globals.uploaded_file_info = {}  # Invalidate on error
                # Make sure to release the capture on error
                with app_globals.video_access_lock:
                    if app_globals.video_capture_global:
                        app_globals.video_capture_global.release()
                        app_globals.video_capture_global = None
                return  # Exit
        
        log_debug(f"Thread processing for {file_path} completed.")

    except Exception as e_thread:
        log_debug(f"General error in _process_uploaded_file_in_thread for {file_path}: {e_thread}", exc_info=True)
        if root_window:
             root_window.after(0, lambda: messagebox.showerror("Error", f"Error processing file: {e_thread}"))
        app_globals.uploaded_file_info = {} # Invalidate on major error
    finally:
        # Always ensure loading is hidden and controls are updated from the main thread
        # For videos, add a delay to ensure loading overlay is visible enough for user
        if root_window:
            log_debug(f"Thread for {file_path} scheduling hide_loading_and_update_controls. File type processed: {file_type}")
            if file_type == 'video':
                # Add a delay for video files to ensure loading screen is visible
                root_window.after(500, hide_loading_and_update_controls)
            else:
                # For images and other files, hide immediately as before
                root_window.after(0, hide_loading_and_update_controls)


def handle_file_upload():
    """Handle file upload button click"""
    global root_window 
    if not ui_components: return
    if not root_window: 
        log_debug("handle_file_upload: root_window is None. Cannot show loading dialog.")
        return
    
    # Open file dialog directly without showing loading screen first
    # (modal dialogs block UI updates, so loading screens before dialogs won't render)
    file_path = filedialog.askopenfilename(
        title="Select Image or Video",
        filetypes=[
            ("Images and Videos", "*.jpg *.jpeg *.png *.mp4 *.avi *.mov *.mkv"),
            ("Images", "*.jpg *.jpeg *.png"), ("Videos", "*.mp4 *.avi *.mov *.mkv"),
            ("All files", "*.*")
        ]
    )
    
    if not file_path:
        log_debug("No file selected.")
        return

    # Update file label immediately on main thread
    file_name = os.path.basename(file_path)
    ui_components["file_upload_label"].config(text=file_name)
    
    # Show loading screen AFTER file selection
    show_loading("Processing file...") 
    
    # Force a complete UI update (more aggressive than update_idletasks)
    # This ensures the loading screen is rendered before proceeding
    root_window.update()
    
    # Define the worker thread function
    def start_processing_thread():
        thread = threading.Thread(target=_process_uploaded_file_in_thread, args=(file_path,), daemon=True)
        thread.start()
        log_debug(f"File upload: Worker thread started for {file_path}.")
    
    # Add a short delay before starting the thread to ensure the loading screen is visible
    root_window.after(200, start_processing_thread)


def on_process_button_click():
    """Handle process button click"""
    global root_window
    log_debug("Process button clicked.")
    
    if not app_globals.uploaded_file_info:
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
        if root_window:
            root_window.update_idletasks()
        try:
            img = cv2.imread(file_path) # Potentially blocking
            if img is None:
                raise ValueError(f"Could not read image file: {file_path}")
            if root_window: # Give UI a chance to update after read, before heavy processing
                root_window.update_idletasks()

            processed_img, detected_count = process_frame_yolo(
                img, app_globals.active_model_object_global, app_globals.active_class_list_global,
                is_video_mode=False, active_filter_list=app_globals.active_processed_class_filter_global,
                current_conf_thresh=app_globals.conf_threshold_global, current_iou_thresh=app_globals.iou_threshold_global
            )
            if ui_components and "video_display" in ui_components:
                ui_components["video_display"].update_frame(processed_img)
            print(f"Processed image. Detected {detected_count} vehicles.")
        except Exception as e:
            log_debug(f"Error processing image: {e}", exc_info=True)
            messagebox.showerror("Error", f"Error processing image: {e}")
        finally:
            hide_loading_and_update_controls()
            
    elif file_type == 'video':
        log_debug(f"Preparing video for real-time analysis: {file_path}")
        show_loading("Preparing real-time analysis...")
        if root_window:
            root_window.update_idletasks()
        try:
            # Potentially blocking: cv2.VideoCapture and metadata reads
            with app_globals.video_access_lock:
                app_globals.video_capture_global = cv2.VideoCapture(file_path)
                if not app_globals.video_capture_global.isOpened():
                    raise ValueError(f"Could not open video file: {file_path}")
                app_globals.current_video_meta['fps'] = app_globals.video_capture_global.get(cv2.CAP_PROP_FPS)
                app_globals.current_video_meta['total_frames'] = int(app_globals.video_capture_global.get(cv2.CAP_PROP_FRAME_COUNT))
                if app_globals.current_video_meta['fps'] > 0:
                    app_globals.current_video_meta['duration_seconds'] = app_globals.current_video_meta['total_frames'] / app_globals.current_video_meta['fps']
            
            if root_window: # UI update after video load, before thread start
                 root_window.update_idletasks()

            if ui_components and app_globals.current_video_meta['total_frames'] > 0:
                ui_components["progress_slider"].config(to=app_globals.current_video_meta['total_frames'])
            
            app_globals.stop_video_processing_flag.clear()
            app_globals.video_paused_flag.clear()
            
            app_globals.video_thread = threading.Thread(
                target=video_processing_thread_func,
                kwargs={
                    'frame_update_callback': lambda frame: ui_components["video_display"].update_frame(frame) if ui_components else None,
                    'progress_update_callback': lambda frame_idx: update_progress(frame_idx)
                }, daemon=True
            )
            app_globals.video_thread.start()
            if root_window: # Defer hiding loading screen
                root_window.after(500, hide_loading_and_update_controls)
        except Exception as e:
            log_debug(f"Error preparing video for real-time analysis: {e}", exc_info=True)
            messagebox.showerror("Error", f"Error processing video: {e}")
            _stop_all_processing_logic()
            hide_loading_and_update_controls() 


def on_fast_process_button_click():
    """Handle fast process button click"""
    global root_window
    log_debug("Fast process button clicked.")
    
    if not app_globals.uploaded_file_info:
        messagebox.showerror("Error", "Please upload a file first.")
        return
    if not app_globals.active_model_object_global:
        messagebox.showerror("Error", "No model loaded. Please select a model.")
        return
    if app_globals.uploaded_file_info.get('file_type', '') != 'video':
        messagebox.showerror("Error", "Fast processing is only available for video files.")
        return

    _stop_all_processing_logic()
    
    file_path = app_globals.uploaded_file_info.get('path', '')
    log_debug(f"Preparing for fast video processing: {file_path}")
    show_loading("Preparing fast video processing...")
    if root_window:
        root_window.update_idletasks()

    app_globals.fast_processing_active_flag.set()
    
    try:
        # Potentially blocking: cv2.VideoCapture for metadata
        with app_globals.video_access_lock:
            temp_cap = cv2.VideoCapture(file_path)
            if not temp_cap.isOpened():
                raise ValueError(f"Could not open video file: {file_path}")
            app_globals.current_video_meta['fps'] = temp_cap.get(cv2.CAP_PROP_FPS)
            app_globals.current_video_meta['total_frames'] = int(temp_cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if app_globals.current_video_meta['fps'] > 0:
                app_globals.current_video_meta['duration_seconds'] = app_globals.current_video_meta['total_frames'] / app_globals.current_video_meta['fps']
            temp_cap.release()
        
        if root_window: # UI update after video load, before thread start
            root_window.update_idletasks()

        app_globals.stop_fast_processing_flag.clear()
        if ui_components:
            ui_components["fast_progress_var"].set(0)
        
        app_globals.fast_video_processing_thread = threading.Thread(
            target=fast_video_processing_thread_func,
            kwargs={
                'video_file_path': file_path,
                'progress_callback': lambda progress: update_fast_progress(progress)
            }, daemon=True
        )
        app_globals.fast_video_processing_thread.start()
        hide_loading_and_update_controls() 
        
    except Exception as e:
        log_debug(f"Error setting up fast processing: {e}", exc_info=True)
        messagebox.showerror("Error", f"Error setting up fast processing: {e}")
        app_globals.fast_processing_active_flag.clear()
        hide_loading_and_update_controls() 


def update_fast_progress(progress):
    """Update fast progress bar"""
    if ui_components and "fast_progress_var" in ui_components:
        ui_components["fast_progress_var"].set(int(progress * 100))
        
        if progress >= 1.0:
            log_debug("Fast processing completed.")
            app_globals.fast_processing_active_flag.clear()
            hide_loading_and_update_controls()


def update_progress(frame_idx):
    """Update progress slider and time label during video playback"""
    if not ui_components:
        return
    
    # Update progress slider without triggering value changed event
    ui_components["progress_var"].set(frame_idx)
    
    # Update time label
    current_time = 0
    if app_globals.current_video_meta['fps'] > 0:
        current_time = frame_idx / app_globals.current_video_meta['fps']
    
    ui_components["time_label"].config(
        text=format_time_display(current_time, app_globals.current_video_meta['duration_seconds'])
    )


def stop_video_stream_button_click():
    """Stop video playback"""
    log_debug("Stop button clicked.")
    _stop_all_processing_logic()
    hide_loading_and_update_controls()


def _perform_seek_action():
    """Perform the actual seek operation to the selected frame"""
    global root_window
    log_debug("Performing seek action.")
    show_loading("Seeking video...") 
    if root_window:
        root_window.update_idletasks()
    try:
        target_frame = app_globals.slider_target_frame_value
        log_debug(f"Seeking to frame {target_frame}")
        
        # Potentially blocking: set, read, process_frame_yolo
        with app_globals.video_access_lock:
            if not app_globals.video_capture_global or not app_globals.video_capture_global.isOpened():
                log_debug("No valid video capture for seeking.")
                return 
            
            was_playing = not app_globals.video_paused_flag.is_set()
            if was_playing:
                app_globals.video_paused_flag.set()
                if ui_components:
                    ui_components["play_pause_button"].config(text="Play")
            
            # Force UI update before potentially slow I/O and processing
            if root_window:
                root_window.update_idletasks()

            app_globals.video_capture_global.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            ret, frame = app_globals.video_capture_global.read()
            if ret:
                app_globals.current_video_frame = frame
                
                # Force UI update before potentially slow processing
                if root_window:
                    root_window.update_idletasks()
                
                processed_frame, _ = process_frame_yolo(
                    frame, app_globals.active_model_object_global, app_globals.active_class_list_global,
                    is_video_mode=True, active_filter_list=app_globals.active_processed_class_filter_global,
                    current_conf_thresh=app_globals.conf_threshold_global, current_iou_thresh=app_globals.iou_threshold_global
                )
                if ui_components and "video_display" in ui_components:
                    ui_components["video_display"].update_frame(processed_frame)
                
                current_time = 0
                if app_globals.current_video_meta['fps'] > 0:
                    current_time = target_frame / app_globals.current_video_meta['fps']
                if ui_components and "time_label" in ui_components:
                    ui_components["time_label"].config(
                        text=format_time_display(current_time, app_globals.current_video_meta['duration_seconds'])
                    )
            else:
                log_debug(f"Failed to read frame at position {target_frame}")
                app_globals.video_capture_global.set(cv2.CAP_PROP_POS_FRAMES, 0) 
    except Exception as e:
        log_debug(f"Error during seek action: {e}", exc_info=True)
    finally:
        hide_loading_and_update_controls() 


def handle_slider_value_change(*args):
    """Handle changes to the progress slider with debouncing"""
    if not ui_components:
        return
    
    # Get slider value
    value = ui_components["progress_var"].get()
    app_globals.slider_target_frame_value = value
    
    # Cancel existing timer if any
    global root_window
    if app_globals.slider_debounce_timer:
        root_window.after_cancel(app_globals.slider_debounce_timer)
    
    # Set new timer for debounced seek
    app_globals.slider_debounce_timer = root_window.after(
        int(config.SLIDER_DEBOUNCE_INTERVAL * 1000), 
        _perform_seek_action
    )


def handle_iou_change(*args):
    """Handle changes to the IoU threshold slider"""
    if not ui_components:
        return
    value = ui_components["iou_var"].get()
    app_globals.iou_threshold_global = value
    log_debug(f"IoU threshold changed to {value}")


def handle_conf_change(*args):
    """Handle changes to the confidence threshold slider"""
    if not ui_components:
        return
    value = ui_components["conf_var"].get()
    app_globals.conf_threshold_global = value
    log_debug(f"Confidence threshold changed to {value}")


def _stop_all_processing_logic():
    """Stop all video processing and playback logic"""
    log_debug("Stopping all video processing and playback.")
    
    # Stop any active video playback
    app_globals.stop_video_processing_flag.set()
    app_globals.video_paused_flag.clear()
    
    # Stop any active fast processing
    app_globals.stop_fast_processing_flag.set()

    # Wait a small amount of time for threads to respond to flags
    time.sleep(0.1)
    
    # Close any open video capture
    with app_globals.video_access_lock:
        if app_globals.video_capture_global and app_globals.video_capture_global.isOpened():
            app_globals.video_capture_global.release()
            app_globals.video_capture_global = None


def init_callbacks(root, components):
    """Initialize callbacks with references to UI components
    
    Args:
        root: Root Tkinter window
        components: Dictionary of UI components
    """
    global ui_components, root_window
    ui_components = components
    root_window = root
    
    # Connect callbacks to UI elements
    ui_components["file_upload_button"].config(command=handle_file_upload)
    ui_components["process_button"].config(command=on_process_button_click)
    ui_components["fast_process_button"].config(command=on_fast_process_button_click)
    
    ui_components["iou_var"].trace_add("write", handle_iou_change)
    ui_components["conf_var"].trace_add("write", handle_conf_change)
    ui_components["model_var"].trace_add("write", handle_model_selection_change)
    
    ui_components["play_pause_button"].config(command=toggle_play_pause)
    ui_components["stop_button"].config(command=stop_video_stream_button_click)
    ui_components["progress_var"].trace_add("write", handle_slider_value_change)
    
    # Create stdout redirection for the output text widget
    from .tk_ui_elements import RedirectText
    sys.stdout = RedirectText(ui_components["output_text"]) 