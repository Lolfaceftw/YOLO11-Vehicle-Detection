import io
import numpy as np
import cv2
import os
import threading
from IPython.display import clear_output, display
import ipywidgets as widgets # For type hinting if needed, and display()

from . import globals as app_globals
from . import config
from .logger_setup import log_debug
from .model_loader import load_model as model_loader_load_model # Renamed to avoid conflict
from .frame_processor import process_frame_yolo
from .video_handler import (
    video_processing_thread_func, 
    fast_video_processing_thread_func,
    _cleanup_processed_video_temp_file,
    format_time_display
)
from .ui_elements import (
    interactive_controls_general,
    file_uploader, model_selector_radio, # Specific controls for direct manipulation
    iou_slider, conf_slider,
    play_pause_button, stop_button, progress_slider, time_label,
    video_display_widget, progress_slider_hbox, video_controls,
    fast_progress_bar
)


def show_loading(message="Loading..."):
    log_debug(f"Showing loading overlay: {message}")
    if app_globals.ui_stack_widget is None:
        log_debug("show_loading: ui_stack_widget is None. Aborting.")
        return
    
    # Enhanced logging for diagnostics
    children_tuple = app_globals.ui_stack_widget.children
    num_children = len(children_tuple) if children_tuple is not None else 0
    log_debug(f"show_loading: ui_stack_widget type: {type(app_globals.ui_stack_widget)}")
    log_debug(f"show_loading: ui_stack_widget children tuple: {children_tuple}")
    log_debug(f"show_loading: Number of children: {num_children}")
    if num_children > 0:
        log_debug(f"show_loading: Child 0 type: {type(children_tuple[0]) if children_tuple[0] else 'None'}")
    if num_children > 1:
        log_debug(f"show_loading: Child 1 type: {type(children_tuple[1]) if children_tuple[1] else 'None'}")


    from .ui_elements import loading_message_label as ui_loading_message_label
    ui_loading_message_label.value = message
    
    if num_children > 1: # Ensure there are at least two children
        app_globals.ui_stack_widget.selected_index = 1 # Show loading overlay (index 1)
    else:
        log_debug(f"show_loading: Not enough children in ui_stack_widget to set selected_index to 1. Has {num_children} children.")
        # Fallback or error indication if necessary, for now, just log.
        # This might mean the main content or loading overlay itself is not correctly added.
        if app_globals.main_output_area_widget: # Print to UI if possible
            with app_globals.main_output_area_widget:
                print(f"DEBUG: show_loading cannot switch to loading overlay (index 1). Stack has {num_children} children.")
                print(f"DEBUG: Stack children are: {children_tuple}")

    for control in interactive_controls_general:
        control.disabled = True
    
    play_pause_button.disabled = True 
    stop_button.disabled = True
    progress_slider.disabled = True
    
    # Keep video player UI visible even during loading
    video_display_widget.layout.visibility = 'visible'
    progress_slider_hbox.layout.visibility = 'visible'
    video_controls.layout.visibility = 'visible'
    fast_progress_bar.visible = False


def hide_loading_and_update_controls():
    log_debug("Hiding loading overlay and updating controls.")

    if app_globals.ui_stack_widget is None: return

    # Before changing selected_index, ensure children are present
    children_tuple = app_globals.ui_stack_widget.children
    num_children = len(children_tuple) if children_tuple is not None else 0
    if num_children > 0: # Ensure there's at least the main content pane
        app_globals.ui_stack_widget.selected_index = 0 # Show main content (index 0)
    else:
        log_debug(f"hide_loading_and_update_controls: Not enough children in ui_stack_widget to set selected_index to 0. Has {num_children} children.")
        if app_globals.main_output_area_widget:
             with app_globals.main_output_area_widget:
                print(f"DEBUG: hide_loading cannot switch to main content (index 0). Stack has {num_children} children.")
                print(f"DEBUG: Stack children are: {children_tuple}")
        # If stack is truly empty, further UI updates might fail or be meaningless.
    
    is_fast_processing = app_globals.fast_processing_active_flag.is_set()
    fast_progress_bar.visible = is_fast_processing 
    log_debug(f"is_fast_processing: {is_fast_processing}, fast_progress_bar.visible: {fast_progress_bar.visible}")

    file_uploader.disabled = is_fast_processing
    model_selector_radio.disabled = is_fast_processing

    sliders_disabled_state = app_globals.active_model_object_global is None or is_fast_processing
    iou_slider.disabled = sliders_disabled_state
    conf_slider.disabled = sliders_disabled_state
    log_debug(f"Sliders disabled: {sliders_disabled_state}")

    can_process_realtime = app_globals.uploaded_file_info and app_globals.active_model_object_global and not is_fast_processing
    from .ui_elements import process_button as ui_process_button 
    ui_process_button.disabled = not can_process_realtime
    
    is_video_file = app_globals.uploaded_file_info.get('type', '').startswith('video/')
    from .ui_elements import fast_process_button as ui_fast_process_button 
    ui_fast_process_button.disabled = not (can_process_realtime and is_video_file)
    log_debug(f"can_process_realtime: {can_process_realtime}, process_button.disabled: {ui_process_button.disabled}")
    log_debug(f"is_video_file: {is_video_file}, fast_process_button.disabled: {ui_fast_process_button.disabled}")

    is_video_playback_active = app_globals.video_thread and app_globals.video_thread.is_alive()
    is_processed_video_ready = app_globals.processed_video_temp_file_path_global and os.path.exists(app_globals.processed_video_temp_file_path_global)
    
    is_video_capture_available_for_playback = False
    with app_globals.video_access_lock:
        if app_globals.video_capture_global and app_globals.video_capture_global.isOpened():
            is_video_capture_available_for_playback = True
            
    # Force the video player UI to always be visible
    should_show_video_player_ui = True
    
    video_display_widget.layout.visibility = 'visible' if should_show_video_player_ui else 'hidden'
    progress_slider_hbox.layout.visibility = 'visible' if should_show_video_player_ui else 'hidden'
    video_controls.layout.visibility = 'visible' if should_show_video_player_ui else 'hidden'
    log_debug(f"Video player UI visibility: {video_display_widget.layout.visibility}")

    if should_show_video_player_ui:
        if is_video_playback_active: 
            log_debug("Video player UI: Playback active. Controls managed by video thread.")
            if not app_globals.video_paused_flag.is_set():
                play_pause_button.description = "Pause"
                play_pause_button.icon = 'pause'
            else:
                play_pause_button.description = "Play"
                play_pause_button.icon = 'play'
            play_pause_button.disabled = False
            stop_button.disabled = False
            progress_slider.disabled = False if app_globals.current_video_meta.get('total_frames', 0) > 0 else True

        elif is_processed_video_ready: 
            log_debug("Video player UI: Processed video ready, playback not active. Setting controls.")
            play_pause_button.disabled = False
            play_pause_button.description = "Play"
            play_pause_button.icon = 'play'
            stop_button.disabled = False 
            
            if app_globals.current_video_meta.get('total_frames', 0) == 0:
                temp_cap = cv2.VideoCapture(app_globals.processed_video_temp_file_path_global)
                if temp_cap.isOpened():
                    app_globals.current_video_meta['fps'] = temp_cap.get(cv2.CAP_PROP_FPS)
                    app_globals.current_video_meta['total_frames'] = int(temp_cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    if app_globals.current_video_meta['fps'] > 0:
                         app_globals.current_video_meta['duration_seconds'] = app_globals.current_video_meta['total_frames'] / app_globals.current_video_meta['fps']
                    temp_cap.release()
            
            if app_globals.current_video_meta.get('total_frames', 0) > 0:
                progress_slider.disabled = False
                progress_slider.max = app_globals.current_video_meta['total_frames']
                progress_slider.value = 0 
                time_label.value = format_time_display(0, app_globals.current_video_meta['duration_seconds'])
            else: 
                progress_slider.disabled = True
                progress_slider.value = 0
                if progress_slider.max == 0 : progress_slider.max = 100 
                time_label.value = "00:00 / 00:00"
    else: 
        log_debug("Video player UI: No playback active/ready or fast processing ongoing. Disabling/resetting controls.")
        play_pause_button.disabled = True
        stop_button.disabled = True
        progress_slider.disabled = True
        play_pause_button.description = "Play"
        play_pause_button.icon = 'play'
        progress_slider.value = 0
        if progress_slider.max == 0 : progress_slider.max = 100
        time_label.value = "00:00 / 00:00"
        if not is_fast_processing: 
             video_display_widget.value = b'' 
             log_debug("Cleared video_display_widget.value as player is hidden and not fast processing.")


def _render_paused_frame_if_active(process_live=True):
    log_debug(f"_render_paused_frame_if_active called. process_live: {process_live}")

    if app_globals.video_paused_flag.is_set() and app_globals.current_video_frame is not None:
        is_still_valid_capture = False
        with app_globals.video_access_lock:
            if app_globals.video_capture_global and app_globals.video_capture_global.isOpened():
                is_still_valid_capture = True
        
        if is_still_valid_capture:
            log_debug("Rendering paused frame.")
            output_frame = app_globals.current_video_frame
            if process_live: 
                log_debug("Processing paused frame live.")
                output_frame, _ = process_frame_yolo(
                    app_globals.current_video_frame, app_globals.active_model_object_global, app_globals.active_class_list_global,
                    is_video_mode=True, active_filter_list=app_globals.active_processed_class_filter_global,
                    current_conf_thresh=app_globals.conf_threshold_global, current_iou_thresh=app_globals.iou_threshold_global)
            
            _, encoded_image = cv2.imencode('.jpeg', output_frame)
            if encoded_image is not None and len(encoded_image) > 0:
                video_display_widget.value = encoded_image.tobytes()
            else:
                video_display_widget.value = b'' 
                log_debug("Warning: Encoded image for paused frame was None or empty.")
        else:
            log_debug("_render_paused_frame_if_active: Video capture not valid.")
    else:
        log_debug("_render_paused_frame_if_active: Not paused or no current frame.")


def handle_iou_change(change):
    app_globals.iou_threshold_global = change['new']
    log_debug(f"IoU threshold changed to: {app_globals.iou_threshold_global}")
    is_realtime_playback = app_globals.video_thread and app_globals.video_thread.is_alive() and \
                           not (app_globals.processed_video_temp_file_path_global and \
                                os.path.exists(app_globals.processed_video_temp_file_path_global))
    _render_paused_frame_if_active(process_live=is_realtime_playback)

def handle_conf_change(change):
    app_globals.conf_threshold_global = change['new']
    log_debug(f"Confidence threshold changed to: {app_globals.conf_threshold_global}")
    is_realtime_playback = app_globals.video_thread and app_globals.video_thread.is_alive() and \
                           not (app_globals.processed_video_temp_file_path_global and \
                                os.path.exists(app_globals.processed_video_temp_file_path_global))
    _render_paused_frame_if_active(process_live=is_realtime_playback)


def _stop_all_processing_logic():
    log_debug("Attempting to stop all processing...")
    if app_globals.main_output_area_widget:
        with app_globals.main_output_area_widget: print("Attempting to stop all processing...")
    show_loading("Stopping all operations...") 

    if app_globals.slider_debounce_timer and app_globals.slider_debounce_timer.is_alive():
        app_globals.slider_debounce_timer.cancel()
        app_globals.slider_debounce_timer = None 
        log_debug("Slider debounce timer cancelled.")
    
    if app_globals.fast_video_processing_thread and app_globals.fast_video_processing_thread.is_alive():
        log_debug("Stopping fast video processing thread...")
        if app_globals.main_output_area_widget:
            with app_globals.main_output_area_widget: print("Stopping fast video processing thread...")
        app_globals.stop_fast_processing_flag.set()
        app_globals.fast_video_processing_thread.join(timeout=5) 
        if app_globals.fast_video_processing_thread.is_alive():
            log_debug("Warning: Fast video processing thread did not terminate in time.")
            if app_globals.main_output_area_widget:
                with app_globals.main_output_area_widget: print("Warning: Fast video processing thread did not terminate in time.")
        else: log_debug("Fast video processing thread joined.")
        app_globals.fast_video_processing_thread = None
    app_globals.stop_fast_processing_flag.clear() 
    app_globals.fast_processing_active_flag.clear() 

    if app_globals.video_thread and app_globals.video_thread.is_alive():
        log_debug("Stopping real-time video playback thread...")
        if app_globals.main_output_area_widget:
            with app_globals.main_output_area_widget: print("Stopping real-time video playback thread...")
        app_globals.stop_video_processing_flag.set()
        app_globals.video_thread.join(timeout=3) 
        if app_globals.video_thread.is_alive():
            log_debug("Warning: Real-time video thread did not terminate in time.")
            if app_globals.main_output_area_widget:
                with app_globals.main_output_area_widget: print("Warning: Real-time video thread did not terminate in time.")
        else: log_debug("Real-time video thread joined.")
        app_globals.video_thread = None
    app_globals.stop_video_processing_flag.clear()

    with app_globals.video_access_lock:
        if app_globals.video_capture_global:
            app_globals.video_capture_global.release()
            app_globals.video_capture_global = None
            log_debug("Global video capture released and set to None.")
    
    _cleanup_processed_video_temp_file() 

    video_display_widget.value = b'' 
    app_globals.current_video_frame = None
    app_globals.current_video_meta.update({'fps': 0.0, 'total_frames': 0, 'duration_seconds': 0.0})
    log_debug("Video display and metadata reset.")
    
    fast_progress_bar.value = 0
    fast_progress_bar.bar_style = 'info'
    fast_progress_bar.description = 'Fast Progress:'
    log_debug("Fast progress bar reset.")

    if app_globals.main_output_area_widget:
        with app_globals.main_output_area_widget: print("All processing stopped and UI reset.")
    log_debug("Calling hide_loading_and_update_controls from _stop_all_processing_logic.")
    hide_loading_and_update_controls() 


def handle_model_selection_change(change):
    log_debug(f"handle_model_selection_change called. New model key: {change['new']}")

    new_model_key = change['new']
    if app_globals.active_model_key == new_model_key and app_globals.active_model_object_global is not None:
        log_debug(f"Model {new_model_key} is already active. No change.")
        if app_globals.main_output_area_widget:
            with app_globals.main_output_area_widget: print(f"Model {new_model_key} is already active.")
        return
        
    _stop_all_processing_logic() 
    if app_globals.processed_image_display_area_widget:
        app_globals.processed_image_display_area_widget.clear_output(wait=False)
    
    if app_globals.main_output_area_widget: clear_output(wait=True) 
    
    show_loading(f"Loading model: {new_model_key}...") 
    load_success = model_loader_load_model(new_model_key) 
    
    if load_success:
        log_debug(f"Successfully switched to and loaded {app_globals.active_model_key}.")
        if app_globals.main_output_area_widget:
            with app_globals.main_output_area_widget: print(f"Successfully switched to and loaded {app_globals.active_model_key}.")
    else:
        log_debug(f"Failed to load {new_model_key}. Processing disabled for this model.")
        if app_globals.main_output_area_widget:
            with app_globals.main_output_area_widget: print(f"Failed to load {new_model_key}. Processing disabled for this model.")
    
    hide_loading_and_update_controls() 


def handle_upload_change(change):
    log_debug("handle_upload_change called.")
    
    _stop_all_processing_logic() 
    if app_globals.processed_image_display_area_widget:
        app_globals.processed_image_display_area_widget.clear_output(wait=False)

    try:
        if file_uploader.value: 
            app_globals.uploaded_file_info = file_uploader.value[0] 
            log_debug(f"File '{app_globals.uploaded_file_info['name']}' uploaded. Type: {app_globals.uploaded_file_info['type']}.")
            if app_globals.main_output_area_widget:
                with app_globals.main_output_area_widget:
                    clear_output(wait=True)
                    print(f"File '{app_globals.uploaded_file_info['name']}' uploaded. Type: {app_globals.uploaded_file_info['type']}. Ready.")
                    if not app_globals.active_model_object_global:
                        log_debug("Warning: No model is currently loaded during file upload.")
                        print("Warning: No model is currently loaded. Processing will not work.")
        else:
            app_globals.uploaded_file_info = {} 
            log_debug("No file uploaded or selection cleared.")
            if app_globals.main_output_area_widget:
                with app_globals.main_output_area_widget:
                    clear_output(wait=True)
                    print("No file uploaded or selection cleared.")
    finally:
        log_debug("Calling hide_loading_and_update_controls from handle_upload_change finally.")
        hide_loading_and_update_controls() 


def on_process_button_click(b): 
    log_debug("on_process_button_click (Real-time/Image) called.")
    
    _stop_all_processing_logic() 
    try:
        if app_globals.main_output_area_widget: clear_output(wait=True)
        if not app_globals.uploaded_file_info: 
            log_debug("Process button: No file uploaded.")
            if app_globals.main_output_area_widget: print("No file uploaded.")
            hide_loading_and_update_controls(); return 
        if not app_globals.active_model_object_global: 
            log_debug(f"Process button: Model '{app_globals.active_model_key}' not loaded.")
            if app_globals.main_output_area_widget: print(f"Error: Model '{app_globals.active_model_key}' not loaded.")
            hide_loading_and_update_controls(); return 
        
        log_debug(f"Processing '{app_globals.uploaded_file_info['name']}' with {app_globals.active_model_key}...")
        if app_globals.main_output_area_widget: print(f"Processing '{app_globals.uploaded_file_info['name']}' with {app_globals.active_model_key}...")
    
        if app_globals.processed_image_display_area_widget: app_globals.processed_image_display_area_widget.clear_output(wait=False)
        video_display_widget.value = b'' 
        
        file_content = app_globals.uploaded_file_info['content'] 
        file_type = app_globals.uploaded_file_info['type'] 
        log_debug(f"File type for processing: {file_type}")

        if file_type.startswith('image/'):
            log_debug("Processing as image.")
            try:
                image_stream = io.BytesIO(file_content)
                image_array = np.frombuffer(image_stream.read(), dtype=np.uint8)
                frame = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
                if frame is None: 
                    log_debug("Error: Could not decode image.")
                    raise ValueError("Could not decode image.")

                processed_frame, _ = process_frame_yolo(frame, app_globals.active_model_object_global, app_globals.active_class_list_global,
                                                           is_video_mode=False, active_filter_list=app_globals.active_processed_class_filter_global,
                                                           current_conf_thresh=app_globals.conf_threshold_global, current_iou_thresh=app_globals.iou_threshold_global)
                
                _, encoded_processed_frame = cv2.imencode('.jpeg', processed_frame)
                if encoded_processed_frame is not None and len(encoded_processed_frame) > 0:
                    if app_globals.processed_image_display_area_widget:
                        with app_globals.processed_image_display_area_widget:
                            clear_output(wait=True); display(widgets.Image(value=encoded_processed_frame.tobytes(), format='jpeg'))
                    log_debug("Processed image displayed.")
                else:
                    log_debug("Error: Could not encode processed image.")
                    if app_globals.processed_image_display_area_widget:
                        with app_globals.processed_image_display_area_widget:
                            clear_output(wait=True); print("Error: Could not encode processed image.")
                if app_globals.main_output_area_widget:
                    with app_globals.main_output_area_widget: print("Image processing complete.")
            except Exception as e:
                log_debug(f"Error processing image: {e}", exc_info=True)
                if app_globals.main_output_area_widget:
                    with app_globals.main_output_area_widget: print(f"Error processing image: {e}")
            finally: 
                hide_loading_and_update_controls()


        elif file_type.startswith('video/'):
            log_debug("Processing as real-time video.")
            if app_globals.main_output_area_widget:
                with app_globals.main_output_area_widget: print(f"Starting real-time video processing for {app_globals.uploaded_file_info['name']}...")
            
            hide_loading_and_update_controls() 
            app_globals.video_thread = threading.Thread(target=video_processing_thread_func, 
                                                        args=(file_content, video_display_widget, True), 
                                                        name="RealTimeVideoThread")
            app_globals.video_thread.daemon = True
            app_globals.video_thread.start()
            log_debug("Real-time video processing thread started.")
        else:
            log_debug(f"Unsupported file type: {file_type}.")
            if app_globals.main_output_area_widget:
                with app_globals.main_output_area_widget: print(f"Unsupported file type: {file_type}.")
            hide_loading_and_update_controls() 
    except Exception as e: 
        log_debug(f"Unexpected error in on_process_button_click: {e}", exc_info=True)
        if app_globals.main_output_area_widget:
            with app_globals.main_output_area_widget: print(f"An unexpected error occurred: {e}")
        hide_loading_and_update_controls()


def on_fast_process_button_click(b):
    log_debug("on_fast_process_button_click called.")
    
    _stop_all_processing_logic() 
    try:
        fast_progress_bar.value = 0
        fast_progress_bar.bar_style = 'info'
        fast_progress_bar.description = 'Fast Progress:'
        
        app_globals.fast_processing_active_flag.set() 
        log_debug("fast_processing_active_flag set. Calling hide_loading_and_update_controls to show progress bar.")
        hide_loading_and_update_controls() 

        if app_globals.main_output_area_widget: clear_output(wait=True)
        if not app_globals.uploaded_file_info or not app_globals.uploaded_file_info.get('type', '').startswith('video/'):
            log_debug("Fast process: No video file uploaded.")
            if app_globals.main_output_area_widget: print("No video file uploaded for fast processing.")
            app_globals.fast_processing_active_flag.clear() 
            hide_loading_and_update_controls(); return
        if not app_globals.active_model_object_global:
            log_debug(f"Fast process: Model '{app_globals.active_model_key}' not loaded.")
            if app_globals.main_output_area_widget: print(f"Error: Model '{app_globals.active_model_key}' not loaded.")
            app_globals.fast_processing_active_flag.clear() 
            hide_loading_and_update_controls(); return
        
        log_debug(f"Initiating fast video processing for {app_globals.uploaded_file_info['name']}...")
        if app_globals.main_output_area_widget:
            with app_globals.main_output_area_widget: print(f"Initiating fast video processing for {app_globals.uploaded_file_info['name']}...")
        if app_globals.processed_image_display_area_widget: app_globals.processed_image_display_area_widget.clear_output(wait=False)
        video_display_widget.value = b'' 
        
        file_content = app_globals.uploaded_file_info['content']
        app_globals.fast_video_processing_thread = threading.Thread(target=fast_video_processing_thread_func, 
                                                                    args=(file_content,), 
                                                                    name="FastProcessVideoThread")
        app_globals.fast_video_processing_thread.daemon = True
        app_globals.fast_video_processing_thread.start()
        log_debug("Fast video processing thread started.")
    except Exception as e:
        log_debug(f"Error initiating fast process: {e}", exc_info=True)
        if app_globals.main_output_area_widget:
            with app_globals.main_output_area_widget: print(f"Error initiating fast process: {e}")
        app_globals.fast_processing_active_flag.clear() 
        hide_loading_and_update_controls() 


def toggle_play_pause(b):
    log_debug("toggle_play_pause called.")
    
    is_video_active_for_playback = False
    with app_globals.video_access_lock: 
        if app_globals.video_capture_global and app_globals.video_capture_global.isOpened():
            is_video_active_for_playback = True
    log_debug(f"toggle_play_pause: is_video_active_for_playback={is_video_active_for_playback}")

    if is_video_active_for_playback: 
        if app_globals.video_paused_flag.is_set():
            app_globals.video_paused_flag.clear(); b.description = "Pause"; b.icon = 'pause'
            log_debug("Video Resumed")
            if app_globals.main_output_area_widget:
                with app_globals.main_output_area_widget: print("Video Resumed")
        else:
            app_globals.video_paused_flag.set(); b.description = "Play"; b.icon = 'play'
            log_debug("Video Paused")
            if app_globals.main_output_area_widget:
                with app_globals.main_output_area_widget: print("Video Paused")
            is_playing_preprocessed = bool(app_globals.processed_video_temp_file_path_global and \
                                           os.path.exists(app_globals.processed_video_temp_file_path_global) and \
                                           app_globals.video_capture_global.get(cv2.CAP_PROP_POS_FRAMES) >= 0) 
            _render_paused_frame_if_active(process_live=not is_playing_preprocessed)
    elif app_globals.processed_video_temp_file_path_global and \
         os.path.exists(app_globals.processed_video_temp_file_path_global) and \
         not (app_globals.video_thread and app_globals.video_thread.is_alive()):
        
        log_debug(f"Starting playback of pre-processed video: {app_globals.processed_video_temp_file_path_global}")
        if app_globals.main_output_area_widget:
            with app_globals.main_output_area_widget: print(f"Starting playback of pre-processed video: {app_globals.processed_video_temp_file_path_global}")
        
        hide_loading_and_update_controls() 
        app_globals.video_thread = threading.Thread(target=video_processing_thread_func, 
                                                    args=(app_globals.processed_video_temp_file_path_global, video_display_widget, False), 
                                                    name="PreprocessedVideoPlaybackThread")
        app_globals.video_thread.daemon = True
        app_globals.video_thread.start()
        log_debug("Pre-processed video playback thread started.")
    else: 
        b.description = "Play"; b.icon = 'play' 
        app_globals.video_paused_flag.clear() 
        log_debug("No active video or pre-processed video to play/pause. UI updated.")
        if app_globals.main_output_area_widget:
            with app_globals.main_output_area_widget: print("No active video or pre-processed video to play/pause.")
        hide_loading_and_update_controls() 


def stop_video_stream_button_click(b):
    log_debug("stop_video_stream_button_click called.")
    show_loading("Stopping video stream...") 

    if app_globals.video_thread and app_globals.video_thread.is_alive():
        log_debug("Stopping active video thread.")
        app_globals.stop_video_processing_flag.set() 
    else: 
        log_debug("No active video thread to stop. Resetting UI for playback part.")
        with app_globals.video_access_lock:
            if app_globals.video_capture_global:
                app_globals.video_capture_global.release()
                app_globals.video_capture_global = None
        app_globals.current_video_meta.update({'fps': 0.0, 'total_frames': 0, 'duration_seconds': 0.0})
        video_display_widget.value = b'' 
        hide_loading_and_update_controls() 
    
    if app_globals.main_output_area_widget:
        with app_globals.main_output_area_widget: print("Video playback stopped by user.")


def _perform_seek_action():
    log_debug(f"_perform_seek_action called. Target frame: {app_globals.slider_target_frame_value}")

    with app_globals.video_access_lock: 
        log_debug("Acquired video_access_lock for seek.")
        if not (app_globals.video_capture_global and \
                app_globals.video_capture_global.isOpened() and \
                app_globals.current_video_meta.get('fps', 0) > 0):
            log_debug("Seek action: Video capture not ready or no FPS. Returning.")
            return
        
        try:
            target_frame = app_globals.slider_target_frame_value
            log_debug(f"Setting video position to frame: {target_frame}")
            app_globals.video_capture_global.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            
            current_seconds = target_frame / app_globals.current_video_meta['fps']
            time_label.value = format_time_display(current_seconds, app_globals.current_video_meta['duration_seconds'])
            progress_slider.value = target_frame 

            if app_globals.video_paused_flag.is_set(): 
                log_debug("Video is paused, reading frame after seek.")
                ret, frame = app_globals.video_capture_global.read() 
                if ret:
                    app_globals.current_video_frame = frame.copy() 
                    output_frame_on_seek = app_globals.current_video_frame
                    
                    is_playing_preprocessed = bool(app_globals.processed_video_temp_file_path_global and \
                                                   os.path.exists(app_globals.processed_video_temp_file_path_global))
                    log_debug(f"Seek on paused frame: is_playing_preprocessed={is_playing_preprocessed}")

                    if not is_playing_preprocessed: 
                        log_debug("Processing frame after seek (real-time playback).")
                        output_frame_on_seek, _ = process_frame_yolo(
                            app_globals.current_video_frame, app_globals.active_model_object_global, 
                            app_globals.active_class_list_global, is_video_mode=True, 
                            active_filter_list=app_globals.active_processed_class_filter_global,
                            current_conf_thresh=app_globals.conf_threshold_global, 
                            current_iou_thresh=app_globals.iou_threshold_global)
                    
                    _, encoded_image = cv2.imencode('.jpeg', output_frame_on_seek)
                    if encoded_image is not None and len(encoded_image) > 0:
                        video_display_widget.value = encoded_image.tobytes()
                    else:
                        video_display_widget.value = b'' 
                        log_debug("Warning: Encoded image for seeked frame was None or empty.")
                else: 
                    if app_globals.current_video_meta.get('total_frames', 0) > 0:
                        progress_slider.value = progress_slider.max 
                    time_label.value = format_time_display(app_globals.current_video_meta.get('duration_seconds',0), 
                                                           app_globals.current_video_meta.get('duration_seconds',0))
                    video_display_widget.value = b'' 
                    log_debug("Error reading frame after seek or end of video reached.")
                    if app_globals.main_output_area_widget:
                        with app_globals.main_output_area_widget: print("Error reading frame after seek or end of video reached.")
        except Exception as e:
            log_debug(f"Error during seek operation: {e}", exc_info=True)
            if app_globals.main_output_area_widget:
                with app_globals.main_output_area_widget: print(f"Error during seek operation: {e}")
    log_debug("Released video_access_lock after seek.")


def handle_slider_value_change(change):
    new_value = change['new']
    if progress_slider.disabled: 
        return

    app_globals.slider_target_frame_value = new_value 
    
    if app_globals.slider_debounce_timer and app_globals.slider_debounce_timer.is_alive():
        app_globals.slider_debounce_timer.cancel() 
    
    app_globals.slider_debounce_timer = threading.Timer(config.SLIDER_DEBOUNCE_INTERVAL, _perform_seek_action)
    app_globals.slider_debounce_timer.daemon = True 
    app_globals.slider_debounce_timer.start()
    log_debug(f"Slider value changed to {new_value}, debounce timer started/reset.")