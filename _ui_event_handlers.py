# _ui_event_handlers.py
"""
Contains direct event handlers for Tkinter UI elements.
"""
import os
import threading
from tkinter import filedialog, messagebox
import cv2 
import time 

from . import _ui_shared_refs as refs
from . import _ui_loading_manager as loading_manager
from . import _ui_async_logic as async_logic 
from . import globals as app_globals
from . import config
from .logger_setup import log_debug

_stop_all_processing_logic_ref = None

def init_event_handlers(stop_logic_func):
    global _stop_all_processing_logic_ref
    _stop_all_processing_logic_ref = stop_logic_func
    log_debug("Event handlers initialized.")


def handle_file_upload():
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
    if root and root.winfo_exists(): root.update() 
    
    threading.Thread(target=async_logic._process_uploaded_file_in_thread, 
                     args=(file_path, _stop_all_processing_logic_ref), 
                     daemon=True).start()
    log_debug(f"File upload: Worker thread started for {file_path}.")


def handle_model_selection_change(*args):
    """Handle model selection change."""
    selected_model_from_event = refs.ui_components["model_var"].get() 
    log_debug(f"handle_model_selection_change: Model selection changed to '{selected_model_from_event}'. Args: {args}")
    
    root = refs.get_root()
    ui_comps = refs.ui_components
        
    if not ui_comps or root is None or not root.winfo_exists():
        log_debug("Model selection: UI components or root window not available.")
        return
    
    selected_model = ui_comps["model_var"].get() 
    if not selected_model:
        log_debug("No model selected after change event.")
        return
    
    if selected_model == app_globals.active_model_key and app_globals.active_model_object_global is not None:
        log_debug(f"Model {selected_model} is already loaded and active. No action taken.")
        return

    log_debug(f"Selected model for loading: {selected_model}")
    async_logic.run_model_load_in_thread(selected_model, _stop_all_processing_logic_ref)


def on_process_button_click(): 
    """Handle process button click for real-time video processing."""
    log_debug("on_process_button_click: 'Process Real-time' button pressed.")
    # Reset any previous processing flags
    app_globals.stop_video_processing_flag.clear()
    root = refs.get_root()
    ui_comps = refs.ui_components
    
    # Prevent multiple clicks or processing when already active
    if app_globals.is_playing_via_after_loop:
        log_debug("on_process_button_click: Real-time processing already active. Ignoring click.")
        return
    
    # Reset any in-progress seek operations
    app_globals.seek_in_progress = False
    app_globals.last_seek_requested = False
    
    # Basic validation checks
    if not app_globals.uploaded_file_info.get('path'): 
        messagebox.showerror("Error", "Please upload a file first.")
        return
    if not app_globals.active_model_object_global:
        messagebox.showerror("Error", "No model loaded. Please select a model.")
        return
    
    file_type = app_globals.uploaded_file_info.get('file_type', '')
    file_path = app_globals.uploaded_file_info.get('path', '') 
    
    # Handle image processing
    if file_type == 'image':
        log_debug(f"Processing image: {file_path}")
        async_logic.run_image_processing_in_thread(file_path) 
        return
            
    # Handle video processing
    elif file_type == 'video':
        # Show loading screen immediately with more detailed message
        log_debug(f"Preparing video for real-time analysis: {file_path}")
        loading_manager.show_loading("Initializing real-time video analysis...")
        
        # Force UI update to ensure loading screen is visible
        if root and root.winfo_exists(): 
            try:
                root.update_idletasks()
                root.update()
            except Exception as e:
                log_debug(f"Error updating UI before video processing: {str(e)}")

        # Stop any existing processing to ensure clean slate
        _stop_all_processing_logic_ref() 
        
        # Reset performance tracking variables
        if hasattr(app_globals, 'heavy_frame_count'):
            app_globals.heavy_frame_count = 0
        if hasattr(app_globals, 'frame_process_counter'):
            app_globals.frame_process_counter = 0

        # Main video initialization
        try:
            # Improved video initialization with preloading
            def initialize_video_processing():
                """Initialize video file for processing with performance optimizations"""
                log_debug("initialize_video_processing: Starting video initialization")
                
                with app_globals.video_access_lock:
                    # Clean up any existing resources
                    if app_globals.video_capture_global and app_globals.video_capture_global.isOpened():
                        app_globals.video_capture_global.release()
                        log_debug("Released previous video capture")
                    
                    # Set OpenCV buffer size for better performance
                    # This increases memory usage but improves playback stability
                    buffer_size = 10 * 1024 * 1024  # 10MB buffer
                    cv2.setNumThreads(4)  # Use multiple threads for processing
                        
                    # Create optimized video capture with appropriate settings
                    log_debug(f"Opening video file with optimized settings: {file_path}")
                    app_globals.video_capture_global = cv2.VideoCapture(file_path)
                    
                    # Check if opened successfully
                    if not app_globals.video_capture_global.isOpened():
                        raise ValueError(f"Could not open video file: {file_path}")
                    
                    # Set capture properties for better performance
                    app_globals.video_capture_global.set(cv2.CAP_PROP_BUFFERSIZE, 3)  # Buffer 3 frames
                    
                    # Read and validate video metadata
                    fps = app_globals.video_capture_global.get(cv2.CAP_PROP_FPS)
                    if fps <= 0 or fps > 120:  # Sanity check on FPS
                        fps = 30.0  # Use a reasonable default
                        log_debug(f"Invalid or extreme FPS detected ({fps}), using default: 30")
                    
                    # Limit FPS for real-time processing to maintain UI responsiveness
                    target_fps = min(fps, 30.0)  # Cap at 30 FPS for UI responsiveness
                    app_globals.current_video_meta['fps'] = target_fps
                    
                    # Get video properties with safer error handling
                    try:
                        total_frames = int(app_globals.video_capture_global.get(cv2.CAP_PROP_FRAME_COUNT))
                        width = int(app_globals.video_capture_global.get(cv2.CAP_PROP_FRAME_WIDTH))
                        height = int(app_globals.video_capture_global.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        log_debug(f"Video details: {width}x{height}, {total_frames} frames @ {target_fps} FPS")
                    except Exception as e:
                        log_debug(f"Error reading video properties: {str(e)}")
                        total_frames = 1000  # Safe default
                        
                    # Update metadata with safer defaults
                    app_globals.current_video_meta['total_frames'] = max(1, total_frames)
                    app_globals.current_video_meta['duration_seconds'] = total_frames / target_fps if target_fps > 0 else 0
                    app_globals.current_video_meta['current_frame'] = 0
                    
                    # Preload first frame to verify video is readable and warm up the decoder
                    try:
                        ret, test_frame = app_globals.video_capture_global.read()
                        if not ret or test_frame is None:
                            raise ValueError("Failed to read first frame - video may be corrupted")
                        
                        # Pre-process first frame to warm up the model in a background thread
                        if app_globals.active_model_object_global:
                            from app.frame_processor import process_frame_yolo
                            import threading
                            
                            # Use a thread-safe lock for synchronization
                            warm_up_completed = threading.Event()
                            warm_up_success = [False]  # Use list as mutable container
                            
                            # Show loading message
                            loading_manager.update_message("Warming up inference model...")
                            
                            # Keep a reference to the original frame
                            app_globals.current_processed_image_for_display = test_frame.copy()
                            
                            # Function to run in background thread
                            def warm_up_model_thread():
                                try:
                                    # Process frame in background
                                    processed_frame, _ = process_frame_yolo(
                                        test_frame, 
                                        app_globals.active_model_object_global, 
                                        app_globals.active_class_list_global,
                                        persist_tracking=True, 
                                        is_video_mode=True,
                                        active_filter_list=app_globals.active_processed_class_filter_global,
                                        current_conf_thresh=app_globals.conf_threshold_global,
                                        current_iou_thresh=app_globals.iou_threshold_global
                                    )
                                    
                                    # Store result and mark as successful
                                    app_globals.current_processed_image_for_display = processed_frame
                                    warm_up_success[0] = True
                                    log_debug("First frame pre-processed to warm up model in background thread")
                                except Exception as thread_err:
                                    log_debug(f"Error in warm up thread: {thread_err}", exc_info=True)
                                finally:
                                    # Signal completion regardless of success/failure
                                    warm_up_completed.set()
                            
                            # Start the warm-up thread
                            warm_up_thread = threading.Thread(
                                target=warm_up_model_thread,
                                daemon=True
                            )
                            warm_up_thread.start()
                            
                            # Wait for warm-up with timeout and UI responsiveness
                            # Only wait briefly to keep UI responsive
                            warm_up_completed.wait(timeout=0.1)
                            
                            # If not completed in initial timeout, continue without waiting
                            if not warm_up_completed.is_set():
                                log_debug("Model warm-up continues in background")
                    except Exception as pre_err:
                        log_debug(f"Error during model warm-up: {str(pre_err)}")
                    
                    # Reset to beginning after pre-processing
                    app_globals.video_capture_global.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    
                return True
            
            # Function to start video playback after successful initialization
            def start_real_time_playback():
                """Start the real-time video processing and playback loop"""
                log_debug("start_real_time_playback: Configuring UI and starting playback")
                
                # Configure UI elements
                if ui_comps.get("progress_slider") and app_globals.current_video_meta['total_frames'] > 0:
                    ui_comps["progress_slider"].config(to=float(app_globals.current_video_meta['total_frames']-1))
                
                if ui_comps.get("progress_var"):
                    app_globals.is_programmatic_slider_update = True
                    try:
                        ui_comps["progress_var"].set(0)
                    except Exception as e:
                        log_debug(f"Error setting progress slider: {str(e)}")
                    finally:
                        app_globals.is_programmatic_slider_update = False
                
                # Set up state for playback
                app_globals.stop_video_processing_flag.clear()
                app_globals.video_paused_flag.clear()
                app_globals.is_playing_via_after_loop = True
                
                # Reset performance counters
                app_globals.real_time_fps_frames_processed = 0
                app_globals.real_time_fps_last_update_time = time.perf_counter()
                app_globals.real_time_fps_display_value = 0.0
                app_globals.prev_fps_value = 0.0
                async_logic._last_frame_display_time_ns = 0
                
                # Cancel any existing playback loop
                if app_globals.after_id_playback_loop:
                    try: 
                        root.after_cancel(app_globals.after_id_playback_loop)
                    except Exception as e:
                        log_debug(f"Error canceling previous playback: {str(e)}")
                
                # Set initial UI elements
                if ui_comps.get("play_pause_button"): 
                    ui_comps["play_pause_button"].config(text="Pause")
                    
                if ui_comps.get("time_label"):
                    ui_comps["time_label"].config(text="00:00 / " + 
                        async_logic.format_time_display(app_globals.current_video_meta.get('duration_seconds', 0), 
                                                       app_globals.current_video_meta.get('duration_seconds', 0)))
                
                if ui_comps.get("fps_label"):
                    ui_comps["fps_label"].config(text="FPS: --")
                    
                if ui_comps.get("current_frame_label"):
                    ui_comps["current_frame_label"].config(
                        text=f"Frame: 0 / {app_globals.current_video_meta.get('total_frames', '--')}")
                
                # Start the playback loop with a high priority (1ms delay)
                app_globals.after_id_playback_loop = root.after(1, 
                    lambda: async_logic._video_playback_loop(process_frames_real_time=True))
                
                # Now that everything is initialized, hide the loading overlay
                loading_manager.hide_loading_and_update_controls()
                log_debug("Real-time video playback started successfully")
            
            # Execute initialization in stages
            # Step 1: Initialize video capture and metadata
            if not initialize_video_processing():
                raise ValueError("Video initialization failed")
                
            # Step 2: Update loading message for real-time analysis
            loading_manager.update_message("Starting real-time analysis...")
                
            # If the model warm-up is still in progress, that's okay
            # It will continue in background and be used when available
            log_debug("Starting real-time analysis even if warm-up still in progress")
            
            # Display first frame immediately before starting playback
            video_display = app_globals.ui_references.get("ui_components_dict", {}).get("video_display")
            if video_display and video_display.winfo_exists() and app_globals.current_video_frame is not None:
                video_display.update_frame(app_globals.current_video_frame)
                log_debug("Displayed first frame before starting real-time playback")
            
            # Step 3: Start playback with slight delay for UI to update
            if root and root.winfo_exists():
                # Use short delay for better responsiveness
                root.after(50, start_real_time_playback)
            else:
                log_debug("Root window no longer exists, cannot start playback")
                loading_manager.hide_loading_and_update_controls()

        except Exception as e:
            # Comprehensive error handling
            error_msg = str(e)
            log_debug(f"Error preparing video for real-time analysis: {error_msg}", exc_info=True)
            
            # Ensure we clean up properly
            _stop_all_processing_logic_ref()
            
            # Make sure loading overlay is hidden before showing error message
            loading_manager.hide_loading_and_update_controls()
            
            # Let UI update before showing error dialog
            if root and root.winfo_exists():
                try:
                    root.update_idletasks()
                except Exception:
                    pass
            
            # Show user-friendly error message
            if "Failed to read first frame" in error_msg:
                messagebox.showerror("Video Error", "Could not read video data. The file may be corrupted or in an unsupported format.")
            elif "Could not open video file" in error_msg:
                messagebox.showerror("File Error", "Could not open the video file. Please check that it exists and is not in use by another program.")
            else:
                messagebox.showerror("Processing Error", f"Error processing video: {error_msg}")
            
            # Reset UI state
            if ui_comps.get("play_pause_button"): 
                ui_comps["play_pause_button"].config(text="Play")
            app_globals.is_playing_via_after_loop = False


def on_fast_process_button_click():
    """Handle fast process button click."""
    log_debug("on_fast_process_button_click: 'Fast Process Video' button pressed.")
    
    if not app_globals.uploaded_file_info.get('path'):
        messagebox.showerror("Error", "Please upload a file first.")
        return
    if not app_globals.active_model_object_global:
        messagebox.showerror("Error", "No model loaded. Please select a model.")
        return
    if app_globals.uploaded_file_info.get('file_type', '') != 'video':
        messagebox.showerror("Error", "Fast processing is only available for video files.")
        return
    
    _stop_all_processing_logic_ref()

    file_path = app_globals.uploaded_file_info.get('path')
    log_debug(f"Preparing for fast video processing: {file_path}")
    async_logic.run_fast_video_processing_in_thread(file_path, _stop_all_processing_logic_ref)


def toggle_play_pause():
    """Toggle video playback between play and pause. Can also initiate playback."""
    log_debug("toggle_play_pause: 'Play/Pause' button pressed.")
    root = refs.get_root()
    ui_comps = refs.ui_components
        
    play_pause_btn = ui_comps.get("play_pause_button")

    if app_globals.is_playing_via_after_loop:
        if app_globals.video_paused_flag.is_set(): # Resuming
            app_globals.video_paused_flag.clear()
            if play_pause_btn: play_pause_btn.config(text="Pause")
            log_debug("Video playback resumed (root.after loop).")
            
            target_fps = app_globals.current_video_meta.get('fps', 30)
            target_fps = target_fps if target_fps > 0 else 30
            target_frame_duration_ns = int((1.0 / target_fps) * 1_000_000_000)
            current_frame_at_resume = app_globals.current_video_meta.get('current_frame', 0)
            # Re-anchor _last_frame_display_time_ns for the current frame, as if it's just about to be displayed
            async_logic._last_frame_display_time_ns = time.perf_counter_ns() - target_frame_duration_ns 
            
            app_globals.real_time_fps_last_update_time = time.perf_counter()
            app_globals.real_time_fps_frames_processed = 0
            log_debug(f"Resumed. FPS timers reset. Last display time re-anchored for frame {current_frame_at_resume}.")
        else: # Pausing
            app_globals.video_paused_flag.set()
            if play_pause_btn: play_pause_btn.config(text="Play")
            log_debug("Video playback paused (root.after loop).")
        return

    is_processed_video_ready_path = app_globals.processed_video_temp_file_path_global
    if is_processed_video_ready_path and os.path.exists(is_processed_video_ready_path):
        log_debug(f"Attempting to start playback of processed video: {is_processed_video_ready_path}")
        loading_manager.show_loading("Loading processed video...")
        if root and root.winfo_exists(): root.update_idletasks()
        
        video_path_to_play = is_processed_video_ready_path 

        try:
            # _stop_all_processing_logic_ref() # DO NOT CALL here when starting NEW processed video
            app_globals.stop_video_processing_flag.clear() 
            app_globals.video_paused_flag.clear()
            
            cap = None
            for attempt in range(3): # Increased retries slightly
                with app_globals.video_access_lock:
                    if app_globals.video_capture_global and app_globals.video_capture_global.isOpened():
                        app_globals.video_capture_global.release() 
                    
                    log_debug(f"Opening processed video file for playback (attempt {attempt+1}): {video_path_to_play}")
                    cap = cv2.VideoCapture(video_path_to_play)
                    if cap.isOpened():
                        app_globals.video_capture_global = cap
                        log_debug(f"Successfully opened processed video on attempt {attempt+1}")
                        break 
                    else:
                        log_debug(f"Failed to open processed video on attempt {attempt+1}. Path: {video_path_to_play}")
                        if attempt < 2: # If not the last attempt
                            time.sleep(0.3 * (attempt + 1)) # Slightly increasing delay
            
            if not app_globals.video_capture_global or not app_globals.video_capture_global.isOpened():
                messagebox.showerror("Error", f"Could not open processed video file after retries: {video_path_to_play}")
                if root and root.winfo_exists(): root.after(0, loading_manager.hide_loading_and_update_controls)
                return

            with app_globals.video_access_lock: 
                app_globals.current_video_meta['fps'] = app_globals.video_capture_global.get(cv2.CAP_PROP_FPS)
                app_globals.current_video_meta['total_frames'] = int(app_globals.video_capture_global.get(cv2.CAP_PROP_FRAME_COUNT))
                app_globals.current_video_meta['duration_seconds'] = \
                    app_globals.current_video_meta['total_frames'] / app_globals.current_video_meta['fps'] if app_globals.current_video_meta['fps'] > 0 else 0
                app_globals.current_video_meta['current_frame'] = 0 
                if ui_comps.get("progress_var"): 
                    app_globals.is_programmatic_slider_update = True
                    try: ui_comps["progress_var"].set(0)
                    finally: app_globals.is_programmatic_slider_update = False

            if ui_comps.get("progress_slider") and app_globals.current_video_meta['total_frames'] > 0:
                 ui_comps["progress_slider"].config(to=float(app_globals.current_video_meta['total_frames']-1))
            
            app_globals.is_playing_via_after_loop = True
            app_globals.real_time_fps_frames_processed = 0
            app_globals.real_time_fps_last_update_time = time.perf_counter()
            app_globals.real_time_fps_display_value = 0.0
            async_logic._last_frame_display_time_ns = 0 

            if app_globals.after_id_playback_loop: 
                try: root.after_cancel(app_globals.after_id_playback_loop)
                except: pass
            app_globals.after_id_playback_loop = root.after(10, lambda: async_logic._video_playback_loop(process_frames_real_time=False)) 

            if play_pause_btn: play_pause_btn.config(text="Pause")
            log_debug("Processed video playback (root.after loop) initiated.")
        except Exception as e:
            log_debug(f"Error during toggle_play_pause for processed video: {e}", exc_info=True)
            messagebox.showerror("Error", f"Error playing processed video: {e}")
            _stop_all_processing_logic_ref() 
        finally:
            if root and root.winfo_exists():
                 root.after(100, loading_manager.hide_loading_and_update_controls)
        return

    if app_globals.uploaded_file_info.get('file_type') == 'video' and \
       app_globals.uploaded_file_info.get('path') and \
       not (app_globals.video_capture_global and app_globals.video_capture_global.isOpened()):
        log_debug("Raw video uploaded. Play click implies starting real-time processing.")
        on_process_button_click() 
        return

    log_debug("Toggle_play_pause: No specific action taken (e.g. no video ready).")
    if root and root.winfo_exists():
        loading_manager.hide_loading_and_update_controls()


def stop_video_stream_button_click():
    """Stop video playback or any ongoing video-related processing."""
    log_debug("stop_video_stream_button_click: 'Stop' button pressed.")
    ui_comps = refs.ui_components
    
    # Cancel any pending seek operations
    app_globals.seek_in_progress = False
    app_globals.last_seek_requested = False
    
    # Show loading indicator briefly for better feedback
    root = refs.get_root()
    if root and root.winfo_exists():
        loading_manager.show_loading("Stopping video playback...")
        # Force an update to show loading screen
        root.update()
    
    # Stop all processing
    _stop_all_processing_logic_ref() 
    
    # Reset UI elements
    if ui_comps.get("video_display"): 
        ui_comps["video_display"].clear()
        
    if ui_comps.get("play_pause_button"):
        ui_comps["play_pause_button"].config(text="Play")
        
    if ui_comps.get("progress_var"):
        app_globals.is_programmatic_slider_update = True
        try:
            ui_comps["progress_var"].set(0)
        except Exception:
            pass
        finally:
            app_globals.is_programmatic_slider_update = False
            
    if ui_comps.get("time_label"):
        ui_comps["time_label"].config(text="00:00 / 00:00")
        
    if ui_comps.get("current_frame_label"):
        ui_comps["current_frame_label"].config(text="Frame: 0 / 0")
        
    # Hide loading screen after cleanup is complete
    loading_manager.hide_loading_and_update_controls()
    app_globals.current_video_frame = None
    app_globals.current_video_meta['current_frame'] = 0
    if ui_comps.get("progress_var"): 
        app_globals.is_programmatic_slider_update = True
        try: ui_comps["progress_var"].set(0)
        finally: app_globals.is_programmatic_slider_update = False
            
    if ui_comps.get("time_label"):
         ui_comps["time_label"].config(text=async_logic.format_time_display(0, app_globals.current_video_meta.get('duration_seconds',0)))
    
    app_globals.real_time_fps_display_value = 0.0
    if ui_comps.get("fps_label"): ui_comps["fps_label"].config(text="FPS: --")
    if ui_comps.get("current_frame_label"): ui_comps["current_frame_label"].config(text="Frame: 0 / {}".format(app_globals.current_video_meta.get('total_frames', '--')))


    loading_manager.hide_loading_and_update_controls()


def handle_slider_value_change(*args): 
    """Handle changes to the progress slider variable (typically from dragging). Uses debouncing."""
    log_debug(f"handle_slider_value_change (trace on var) triggered. Programmatic update flag: {app_globals.is_programmatic_slider_update}. Args: {args}")
    root = refs.get_root()
    ui_comps = refs.ui_components
    
    if app_globals.is_programmatic_slider_update: 
        log_debug("Slider change is programmatic. No seek action from trace.")
        return 

    # Check if another seek operation is in progress to prevent conflicts
    if getattr(app_globals, 'seek_in_progress', False):
        log_debug("Slider change ignored: Another seek operation is already in progress.")
        return

    log_debug("Slider change from var trace (likely drag). Proceeding with debounced seek logic.")
    if not ui_comps or root is None or not root.winfo_exists():
        log_debug("Slider var trace: UI components or root window not available.")
        return
    
    progress_slider_widget = ui_comps.get("progress_slider")
    if not progress_slider_widget or \
       not (app_globals.video_capture_global and app_globals.video_capture_global.isOpened()) or \
       progress_slider_widget.cget("state") == "disabled":
        log_debug("Slider var trace: Video not ready or slider disabled.")
        return

    try:
        # Get the target frame value and store it
        value = ui_comps["progress_var"].get() 
        app_globals.slider_target_frame_value = value
        
        # Set seek target frame for real-time processing to detect
        with getattr(app_globals, 'seek_lock', threading.Lock()):
            app_globals.seek_target_frame = int(value)
            app_globals.last_seek_requested = True
            app_globals.seek_start_time = time.perf_counter()
            
        log_debug(f"Slider var trace: target_frame_value set to: {value}")
    except Exception as e: 
        log_debug(f"Error getting slider value from var trace: {str(e)}", exc_info=True)
        return

    # Update UI to reflect the target position
    current_time_secs = 0
    fps = app_globals.current_video_meta.get('fps', 0)
    if fps > 0: current_time_secs = app_globals.slider_target_frame_value / fps
    
    if ui_comps.get("time_label"):
        ui_comps["time_label"].config(
            text=async_logic.format_time_display(current_time_secs, app_globals.current_video_meta.get('duration_seconds', 0))
        )
    if ui_comps.get("current_frame_label"):
        ui_comps["current_frame_label"].config(text=f"Frame: {app_globals.slider_target_frame_value} / {app_globals.current_video_meta.get('total_frames', '--')}")

    # Cancel any existing debounce timer
    if app_globals.slider_debounce_timer:
        try: root.after_cancel(app_globals.slider_debounce_timer)
        except Exception: pass 
    
    # Create a new debounce timer with improved seek handling
    try:
        log_debug(f"Setting new debounce timer for seek to {app_globals.slider_target_frame_value} (from var trace).")
        
        # Execute seek when timer expires
        def execute_debounced_seek():
            # Flag seek as in progress
            app_globals.seek_in_progress = True
            
            try:
                # Launch seek thread
                threading.Thread(target=_perform_optimized_seek, daemon=True).start()
            except Exception as e:
                log_debug(f"Error starting seek thread: {str(e)}")
                app_globals.seek_in_progress = False
        
        # Schedule the debounced seek
        app_globals.slider_debounce_timer = root.after(
            int(config.SLIDER_DEBOUNCE_INTERVAL * 1000), 
            execute_debounced_seek
        )
    except Exception as e: 
        log_debug(f"Error setting debounce timer from var trace: {str(e)}")

def handle_slider_click_release(event):
    """Handle LMB release on the progress slider for immediate seek (teleport)."""
    log_debug(f"handle_slider_click_release (LMB Release) triggered. Event X: {event.x}")
    root = refs.get_root()
    ui_comps = refs.ui_components

    if app_globals.is_programmatic_slider_update:
        log_debug("Slider click release was flagged as programmatic. Ignoring.")
        return

    # Check if another seek operation is already in progress
    if getattr(app_globals, 'seek_in_progress', False):
        log_debug("Slider click release ignored: Another seek operation is already in progress.")
        return

    if not ui_comps or root is None or not root.winfo_exists():
        log_debug("Slider click release: UI components or root window not available.")
        return

    progress_slider_widget = ui_comps.get("progress_slider")
    if not progress_slider_widget or \
       not (app_globals.video_capture_global and app_globals.video_capture_global.isOpened()) or \
       progress_slider_widget.cget("state") == "disabled":
        log_debug("Slider click release: Video not ready or slider disabled.")
        return

    # Cancel any pending debounce timer
    if app_globals.slider_debounce_timer:
        try:
            root.after_cancel(app_globals.slider_debounce_timer)
            log_debug("Cancelled existing debounce timer due to click release.")
        except Exception: pass
        app_globals.slider_debounce_timer = None 

    try:
        # Calculate the target frame based on click position
        slider_width = progress_slider_widget.winfo_width()
        if slider_width <= 0: 
            log_debug("Slider width is zero, cannot calculate click position.")
            return

        click_x = event.x
        click_x = max(0, min(click_x, slider_width))
        
        proportion = click_x / slider_width
        
        total_frames = app_globals.current_video_meta.get('total_frames', 0)
        if total_frames <= 0:
            log_debug("Total frames is zero, cannot calculate target frame for click.")
            return
            
        target_frame = int(proportion * (total_frames -1)) 
        target_frame = max(0, min(target_frame, total_frames - 1)) 

        app_globals.slider_target_frame_value = target_frame
        
        # Set global seek target frame for video processing loop to detect
        with getattr(app_globals, 'seek_lock', threading.Lock()):
            app_globals.seek_target_frame = target_frame
            app_globals.last_seek_requested = True
            app_globals.seek_start_time = time.perf_counter()
            
        log_debug(f"Slider click release: Set target_frame: {target_frame}, proportion {proportion:.3f}")
        
        # Update UI elements programmatically
        log_debug(f"Setting is_programmatic_slider_update=True before progress_var.set for click")
        app_globals.is_programmatic_slider_update = True
        try:
            if ui_comps.get("progress_var"):
                ui_comps["progress_var"].set(target_frame)
        finally:
            root.after_idle(lambda: setattr(app_globals, 'is_programmatic_slider_update', False))
            log_debug(f"Scheduled is_programmatic_slider_update=False after progress_var.set for click")
        
        # Perform immediate seek with improved handling
        log_debug(f"Initiating immediate seek to frame {target_frame}")
        app_globals.seek_in_progress = True
        threading.Thread(target=_perform_optimized_seek, daemon=True).start()
    except Exception as e:
        log_debug(f"Error during slider click release handling: {e}", exc_info=True)
        app_globals.seek_in_progress = False


def handle_iou_change(*args): 
    """Handle changes to the IoU threshold slider."""
    log_debug(f"handle_iou_change: IoU slider changed. Args: {args}")
    ui_comps = refs.ui_components
    if not ui_comps: return
    try:
        value = ui_comps["iou_var"].get()
        app_globals.iou_threshold_global = value
        if ui_comps.get("iou_value_label"): ui_comps["iou_value_label"].config(text=f"{value:.2f}")
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
                    if ui_comps.get("video_display"): ui_comps["video_display"].update_frame(processed_img)
                    print(f"Re-processed image with new IoU. Detected {detected_count} objects.")
    except Exception: 
        log_debug("Error in handle_iou_change.", exc_info=True)


def _perform_optimized_seek():
    """
    Perform video seek operation with improved stability and performance.
    This function handles seeking in both normal and real-time playback modes.
    """
    seek_start_time = time.perf_counter()
    log_debug("_perform_optimized_seek: Starting optimized seek operation")
    
    try:
        # First check if we still have valid video and target
        target_frame = app_globals.slider_target_frame_value
        if target_frame is None or not app_globals.video_capture_global or not app_globals.video_capture_global.isOpened():
            log_debug("_perform_optimized_seek: Invalid state - missing video or target frame")
            app_globals.seek_in_progress = False
            return
        
        # Get UI components for updates
        ui_comps = refs.ui_components
        if not ui_comps:
            log_debug("_perform_optimized_seek: UI components not available")
            app_globals.seek_in_progress = False
            return
        
        # Check if real-time processing is active
        is_real_time = getattr(app_globals, 'is_playing_via_after_loop', False)
        
        # Pause video playback temporarily during seek to prevent conflicts
        was_paused = app_globals.video_paused_flag.is_set()
        app_globals.video_paused_flag.set()
        
        # Acquire video lock to perform seek
        with app_globals.video_access_lock:
            log_debug(f"_perform_optimized_seek: Locked video for seek to frame {target_frame}")
            
            # Store current position (in case seek fails, we can go back)
            current_pos = int(app_globals.video_capture_global.get(cv2.CAP_PROP_POS_FRAMES))
            
            # For large seeks, it's often faster to close and reopen the video
            # than to seek, especially for compressed formats like H.264
            seek_distance = abs(target_frame - current_pos)
            file_path = app_globals.uploaded_file_info.get('path', '')
            
            # If seeking far forward, it's faster to reopen the file
            if seek_distance > 300 and file_path and os.path.exists(file_path):
                log_debug(f"_perform_optimized_seek: Using reopen strategy for large seek distance: {seek_distance}")
                
                # Release current capture
                app_globals.video_capture_global.release()
                
                # Open fresh capture
                app_globals.video_capture_global = cv2.VideoCapture(file_path)
                if not app_globals.video_capture_global.isOpened():
                    raise ValueError(f"Could not reopen video file for seeking: {file_path}")
                
                # Seek directly to target frame
                seek_success = app_globals.video_capture_global.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            else:
                # Normal seek for shorter distances
                seek_success = app_globals.video_capture_global.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            
            if not seek_success:
                log_debug(f"_perform_optimized_seek: Seek failed, reverting to position {current_pos}")
                # Try to restore position if seek failed
                app_globals.video_capture_global.set(cv2.CAP_PROP_POS_FRAMES, current_pos)
                app_globals.seek_in_progress = False
                # Restore pause state
                if not was_paused:
                    app_globals.video_paused_flag.clear()
                return
            
            # Read the frame at the new position
            ret, frame = app_globals.video_capture_global.read()
            
            if not ret:
                log_debug("_perform_optimized_seek: Failed to read frame after seek")
                # Try to restore position if frame read failed
                app_globals.video_capture_global.set(cv2.CAP_PROP_POS_FRAMES, current_pos)
                app_globals.seek_in_progress = False
                # Restore pause state
                if not was_paused:
                    app_globals.video_paused_flag.clear()
                return
            
            # Update metadata with new position
            actual_pos = int(app_globals.video_capture_global.get(cv2.CAP_PROP_POS_FRAMES)) - 1
            app_globals.current_video_meta['current_frame'] = actual_pos
            seek_time = time.perf_counter() - seek_start_time
            log_debug(f"_perform_optimized_seek: Seek success, now at frame {actual_pos}, took {seek_time:.3f}s")
            
            # Flag that seek was completed for video processing loop to detect
            app_globals.last_seek_requested = False
            
            # Process frame if video display exists
            if ui_comps.get("video_display"):
                # If in real-time mode, process frame with model
                if is_real_time and app_globals.active_model_object_global:
                    try:
                        from app.frame_processor import process_frame_yolo
                        frame, _ = process_frame_yolo(
                            frame, app_globals.active_model_object_global, app_globals.active_class_list_global,
                            persist_tracking=True, is_video_mode=True,
                            active_filter_list=app_globals.active_processed_class_filter_global,
                            current_conf_thresh=app_globals.conf_threshold_global,
                            current_iou_thresh=app_globals.iou_threshold_global
                        )
                        log_debug("_perform_optimized_seek: Processed seek frame with model")
                    except Exception as e:
                        log_debug(f"_perform_optimized_seek: Error processing frame after seek: {e}")
                
                # Store the frame (needed for both normal and real-time modes)
                app_globals.current_processed_image_for_display = frame
                
                # Update video display on UI thread
                root = refs.get_root()
                if root and root.winfo_exists():
                    def update_ui_after_seek():
                        try:
                            if ui_comps.get("video_display") and ui_comps["video_display"].winfo_exists():
                                ui_comps["video_display"].update_frame(frame)
                            
                            # Update time display
                            fps = app_globals.current_video_meta.get('fps', 0)
                            if fps > 0 and ui_comps.get("time_label"):
                                current_time = actual_pos / fps
                                ui_comps["time_label"].config(text=async_logic.format_time_display(
                                    current_time, app_globals.current_video_meta.get('duration_seconds', 0)
                                ))
                            
                            # Update frame counter
                            if ui_comps.get("current_frame_label"):
                                ui_comps["current_frame_label"].config(
                                    text=f"Frame: {actual_pos} / {app_globals.current_video_meta.get('total_frames', '--')}"
                                )
                            
                            # Restore pause state
                            if not was_paused:
                                app_globals.video_paused_flag.clear()
                                
                            # Force a UI update to refresh playback state
                            if root and root.winfo_exists():
                                try:
                                    root.update_idletasks()
                                except Exception:
                                    pass
                            
                            # Finally mark seek operation as complete
                            app_globals.seek_in_progress = False
                            log_debug("_perform_optimized_seek: Seek completed successfully")
                        except Exception as e:
                            log_debug(f"_perform_optimized_seek: Error in UI update after seek: {e}")
                            # Restore pause state on error
                            if not was_paused:
                                app_globals.video_paused_flag.clear()
                            app_globals.seek_in_progress = False
                    
                    # Schedule UI update with higher priority
                    root.after(1, update_ui_after_seek)
                    return
    
    except Exception as e:
        log_debug(f"_perform_optimized_seek: Unexpected error during seek: {e}")
        # Restore pause state on error
        if 'was_paused' in locals() and not was_paused:
            app_globals.video_paused_flag.clear()
    
    # Mark seek as complete if we reached this point (error case)
    app_globals.seek_in_progress = False


def handle_conf_change(*args): 
    """Handle changes to the confidence threshold slider."""
    log_debug(f"handle_conf_change: Confidence slider changed. Args: {args}")
    ui_comps = refs.ui_components
    if not ui_comps: return
    try:
        value = ui_comps["conf_var"].get()
        app_globals.conf_threshold_global = value
        if ui_comps.get("conf_value_label"): ui_comps["conf_value_label"].config(text=f"{value:.2f}")
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
                    if ui_comps.get("video_display"): ui_comps["video_display"].update_frame(processed_img)
                    print(f"Re-processed image with new Conf. Detected {detected_count} objects.")
    except Exception: 
        log_debug("Error in handle_conf_change.", exc_info=True)
