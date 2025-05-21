# _ui_loading_manager.py
"""
Manages the loading overlay and updating UI control states.
Also includes UI update callbacks like update_progress.
"""
import tkinter as tk 
from . import _ui_shared_refs as refs
from . import globals as app_globals
from . import config
from .logger_setup import log_debug
from .tk_ui_elements import LoadingOverlay 
from .video_handler import format_time_display 
import os 

def show_loading(message="Loading..."):
    """Show loading overlay with the given message."""
    log_debug(f"Showing loading overlay: {message}")
    root = refs.get_root()
    if root is None:
        log_debug("show_loading: root_window is None. Aborting.")
        return

    root.update_idletasks()
    current_overlay = refs.get_loading_overlay_ref()

    if current_overlay is not None and current_overlay.winfo_exists():
        current_overlay.update_message(message)
        current_overlay.lift()
        return

    try:
        if current_overlay is None or not current_overlay.winfo_exists():
            new_overlay = LoadingOverlay(root, message)
            refs.set_loading_overlay_ref(new_overlay)
        else:
            current_overlay.update_message(message)
            current_overlay.lift()
        root.update_idletasks()
    except Exception as e:
        log_debug(f"Error creating/updating loading overlay: {e}", exc_info=True)
        print(f"Loading: {message} (Overlay Error: {e})")

    ui_comps = refs.ui_components 
    if ui_comps:
        controls_to_disable = [
            "file_upload_button", "process_button", "fast_process_button",
            "iou_slider", "conf_slider",
            "play_pause_button", "stop_button", "progress_slider"
        ]
        for key in controls_to_disable:
            comp = ui_comps.get(key)
            if comp:
                comp.config(state="disabled")
        
        model_buttons = ui_comps.get("model_buttons", [])
        for button in model_buttons:
            if button:
                button.config(state="disabled")

def hide_loading_and_update_controls():
    """Hide loading overlay and update the state of UI controls."""
    log_debug("Hiding loading overlay and updating controls.")
    root = refs.get_root()
    ui_comps = refs.ui_components
    current_overlay = refs.get_loading_overlay_ref()

    if current_overlay is not None and current_overlay.winfo_exists():
        current_overlay.destroy()
    refs.set_loading_overlay_ref(None)

    if not ui_comps:
        log_debug("hide_loading_and_update_controls: ui_components is empty. Aborting.")
        return
    if root is None or not root.winfo_exists():
        log_debug("hide_loading_and_update_controls: root_window is not available. Aborting.")
        return

    is_fast_processing = app_globals.fast_processing_active_flag.is_set()
    model_loaded = app_globals.active_model_object_global is not None
    file_uploaded = bool(app_globals.uploaded_file_info and app_globals.uploaded_file_info.get('path'))
    is_video_file = file_uploaded and app_globals.uploaded_file_info.get('file_type', '') == 'video'

    if ui_comps.get("file_upload_button"):
        ui_comps["file_upload_button"].config(state="disabled" if is_fast_processing else "normal")

    for button in ui_comps.get("model_buttons", []):
        if button: button.config(state="disabled" if is_fast_processing else "normal")

    sliders_state = "normal" if model_loaded and not is_fast_processing else "disabled"
    if ui_comps.get("iou_slider"): ui_comps["iou_slider"].config(state=sliders_state)
    if ui_comps.get("conf_slider"): ui_comps["conf_slider"].config(state=sliders_state)

    can_process_realtime = file_uploaded and model_loaded and not is_fast_processing
    if ui_comps.get("process_button"):
        ui_comps["process_button"].config(state="normal" if can_process_realtime else "disabled")
    if ui_comps.get("fast_process_button"):
        ui_comps["fast_process_button"].config(state="normal" if (can_process_realtime and is_video_file) else "disabled")

    # Corrected flag name here
    is_video_playback_active = app_globals.is_playing_via_after_loop or \
                               (app_globals.video_thread and app_globals.video_thread.is_alive()) # Keep video_thread check for legacy/other uses
                               
    is_processed_video_ready_for_playback = app_globals.processed_video_temp_file_path_global and \
                                           os.path.exists(app_globals.processed_video_temp_file_path_global) and \
                                           not is_video_playback_active # Not already playing something else
    should_show_video_controls_ui = (is_video_file or is_processed_video_ready_for_playback) and not is_fast_processing

    play_pause_btn = ui_comps.get("play_pause_button")
    stop_btn = ui_comps.get("stop_button")
    prog_slider = ui_comps.get("progress_slider")
    prog_var = ui_comps.get("progress_var")
    time_lbl = ui_comps.get("time_label")

    if play_pause_btn and stop_btn and prog_slider and prog_var and time_lbl:
        if should_show_video_controls_ui:
            play_text = "Play"; play_state = "disabled"; stop_state = "disabled"
            if is_video_playback_active:
                play_text = "Pause" if not app_globals.video_paused_flag.is_set() else "Play"
                play_state = "normal"; stop_state = "normal"
            elif is_processed_video_ready_for_playback or \
                 (is_video_file and app_globals.video_capture_global and app_globals.video_capture_global.isOpened()):
                play_text = "Play"; play_state = "normal"; stop_state = "normal"
            elif is_video_file and not (app_globals.video_capture_global and app_globals.video_capture_global.isOpened()):
                play_text = "Play"; play_state = "normal"; stop_state = "disabled"

            play_pause_btn.config(text=play_text, state=play_state)
            stop_btn.config(state=stop_state)

            meta_total_frames = app_globals.current_video_meta.get('total_frames', 0)
            meta_fps = app_globals.current_video_meta.get('fps', 0)
            meta_duration = app_globals.current_video_meta.get('duration_seconds', 0)

            if meta_total_frames > 0:
                prog_slider.config(state="normal", to=float(meta_total_frames - 1 if meta_total_frames > 0 else 0))
                if not is_video_playback_active:
                    current_slider_val = prog_var.get()
                    is_cap_closed_or_none = not (app_globals.video_capture_global and app_globals.video_capture_global.isOpened())
                    if is_cap_closed_or_none or current_slider_val >= meta_total_frames - 1:
                        if current_slider_val != 0: prog_var.set(0)
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

    fast_progress_frame = ui_comps.get("fast_progress_frame")
    if fast_progress_frame:
        if is_fast_processing:
            if not fast_progress_frame.winfo_ismapped():
                fast_progress_frame.pack(fill="x", padx=config.SPACING_SMALL, pady=config.SPACING_SMALL, anchor="n")
        else:
            if fast_progress_frame.winfo_ismapped():
                fast_progress_frame.pack_forget()

    video_controls_frame = ui_comps.get("video_controls_frame")
    progress_frame = ui_comps.get("progress_frame")
    if video_controls_frame and progress_frame:
        if should_show_video_controls_ui:
            if not video_controls_frame.winfo_ismapped():
                video_controls_frame.grid(row=0, column=0, sticky="ew", padx=2, pady=(2,0))
            if not progress_frame.winfo_ismapped():
                progress_frame.grid(row=1, column=0, sticky="ew", padx=2, pady=(0,2))
        else:
            if video_controls_frame.winfo_ismapped(): video_controls_frame.grid_remove()
            if progress_frame.winfo_ismapped(): progress_frame.grid_remove()
    
    video_display = ui_comps.get("video_display")
    if video_display and not should_show_video_controls_ui and not is_fast_processing:
        is_static_image_type = file_uploaded and app_globals.uploaded_file_info.get('file_type', '') == 'image'
        is_static_image_processed = app_globals.current_processed_image_for_display is not None
        if not (is_static_image_type and is_static_image_processed):
            video_display.clear()
            log_debug("Cleared video_display as controls are hidden, not fast processing, and not showing a processed static image.")

    if root and root.winfo_exists():
        root.update_idletasks()
    log_debug("hide_loading_and_update_controls finished.")

def update_progress(frame_idx):
    """Update progress slider and time label during video playback."""
    root = refs.get_root()
    ui_comps = refs.ui_components
    if not ui_comps or not root or not root.winfo_exists():
        return
    
    def do_update():
        log_debug(f"update_progress: Setting is_programmatic_slider_update = True. Frame: {frame_idx}")
        app_globals.is_programmatic_slider_update = True 
        try:
            progress_var = ui_comps.get("progress_var")
            if progress_var:
                log_debug(f"update_progress: Setting progress_var to {frame_idx}")
                progress_var.set(frame_idx)
            
            current_time_secs = 0
            total_duration_secs = app_globals.current_video_meta.get('duration_seconds', 0)
            fps = app_globals.current_video_meta.get('fps', 0)
            if fps > 0:
                current_time_secs = frame_idx / fps
            
            time_label = ui_comps.get("time_label")
            if time_label:
                time_label.config(
                    text=format_time_display(current_time_secs, total_duration_secs)
                )
        except Exception as e:
            log_debug(f"Exception in update_progress do_update: {e}", exc_info=True)
        finally:
            def reset_flag():
                 app_globals.is_programmatic_slider_update = False
                 log_debug(f"update_progress: Reset is_programmatic_slider_update = False (deferred). Frame: {frame_idx}")
            root.after(5, reset_flag) 

    root.after(0, do_update) 

def update_fast_progress(progress_value): 
    """Update fast progress bar. Called from fast_video_processing_thread_func."""
    root = refs.get_root()
    ui_comps = refs.ui_components
    fast_progress_var = ui_comps.get("fast_progress_var")
    if fast_progress_var and root and root.winfo_exists():
        def do_update():
            fast_progress_var.set(int(progress_value * 100))
            
            if progress_value >= 1.0:
                log_debug("Fast processing completed (reported by progress callback).")
                app_globals.fast_processing_active_flag.clear()
                print("Fast video processing complete. Ready for playback.")
                hide_loading_and_update_controls() 
        
        root.after(0, do_update)
