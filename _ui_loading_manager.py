# _ui_loading_manager.py
"""
Manages the loading overlay and updating UI control states.
Also includes UI update callbacks like update_progress.
"""
import tkinter as tk
from tkinter import ttk
from . import _ui_shared_refs as refs
from . import globals as app_globals
from . import config
from .logger_setup import log_debug
from .ui_custom_widgets import LoadingOverlay # Corrected import
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
        # Disable all interactive controls during loading
        controls_to_manage = [
            "file_upload_button", "process_button", "fast_process_button",
            "iou_slider", "conf_slider",
            "play_pause_button", "stop_button", "progress_slider"
        ]
        for key in controls_to_manage:
            comp = ui_comps.get(key)
            if comp:
                if isinstance(comp, (ttk.Button, ttk.Radiobutton)):
                    comp.state(['disabled'])
                elif isinstance(comp, ttk.Scale):
                    comp.config(state="disabled")
        
        model_buttons = ui_comps.get("model_buttons", [])
        for button in model_buttons:
            if button:
                button.state(['disabled'])


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
    log_debug(f"hide_loading_and_update_controls: is_fast_processing FLAG is currently {is_fast_processing}")
    model_loaded = app_globals.active_model_object_global is not None
    file_uploaded = bool(app_globals.uploaded_file_info and app_globals.uploaded_file_info.get('path'))
    is_video_file = file_uploaded and app_globals.uploaded_file_info.get('file_type', '') == 'video'

    # File Upload Button
    file_upload_btn = ui_comps.get("file_upload_button")
    if file_upload_btn:
        new_state = ['disabled'] if is_fast_processing else ['!disabled']
        file_upload_btn.state(new_state)
        log_debug(f"File Upload Button state set to: {file_upload_btn.state()}, Effective style: {file_upload_btn.cget('style')}")


    # Model Radiobuttons
    for button in ui_comps.get("model_buttons", []):
        if button:
            new_state = ['disabled'] if is_fast_processing else ['!disabled']
            button.state(new_state)
            # log_debug(f"Model Button '{button.cget('text')}' state set to: {button.state()}, Effective style: {button.cget('style')}")


    # Sliders (use .config for state)
    sliders_new_state_tk = "normal" if model_loaded and not is_fast_processing else "disabled"
    if ui_comps.get("iou_slider"): ui_comps["iou_slider"].config(state=sliders_new_state_tk)
    if ui_comps.get("conf_slider"): ui_comps["conf_slider"].config(state=sliders_new_state_tk)

    # Process Real-time Button
    process_btn = ui_comps.get("process_button")
    if process_btn:
        can_process_realtime = file_uploaded and model_loaded and not is_fast_processing
        new_state = ['!disabled'] if can_process_realtime else ['disabled']
        process_btn.state(new_state)
        log_debug(f"Process Real-time Button state set to: {process_btn.state()}, Effective style: {process_btn.cget('style')}")


    # Fast Process Video Button
    fast_process_btn = ui_comps.get("fast_process_button")
    if fast_process_btn:
        can_fast_process = file_uploaded and model_loaded and is_video_file and not is_fast_processing
        new_state = ['!disabled'] if can_fast_process else ['disabled']
        fast_process_btn.state(new_state)
        log_debug(f"Fast Process Button state set to: {fast_process_btn.state()}, Effective style: {fast_process_btn.cget('style')}")


    is_video_playback_active = app_globals.is_playing_via_after_loop
    is_processed_video_ready_for_playback = app_globals.processed_video_temp_file_path_global and \
                                           os.path.exists(app_globals.processed_video_temp_file_path_global) and \
                                           not is_video_playback_active
    
    should_show_video_controls_ui = (is_video_file or is_processed_video_ready_for_playback) and not is_fast_processing


    play_pause_btn = ui_comps.get("play_pause_button")
    stop_btn = ui_comps.get("stop_button")
    prog_slider = ui_comps.get("progress_slider")
    prog_var = ui_comps.get("progress_var")
    time_lbl = ui_comps.get("time_label")
    fps_lbl = ui_comps.get("fps_label")
    current_frame_lbl = ui_comps.get("current_frame_label")

    if play_pause_btn and stop_btn and prog_slider and prog_var and time_lbl:
        if should_show_video_controls_ui:
            play_text = "Play"
            play_btn_new_state_list = ['disabled']
            stop_btn_new_state_list = ['disabled']

            if is_video_playback_active:
                play_text = "Pause" if not app_globals.video_paused_flag.is_set() else "Play"
                play_btn_new_state_list = ['!disabled']
                stop_btn_new_state_list = ['!disabled']
            elif is_processed_video_ready_for_playback:
                play_text = "Play"
                play_btn_new_state_list = ['!disabled']
                stop_btn_new_state_list = ['!disabled']
            elif is_video_file and app_globals.video_capture_global and app_globals.video_capture_global.isOpened():
                play_text = "Play"
                play_btn_new_state_list = ['!disabled']
                stop_btn_new_state_list = ['!disabled']
            elif is_video_file: 
                play_text = "Play" 
                play_btn_new_state_list = ['!disabled'] 
                stop_btn_new_state_list = ['disabled'] 

            play_pause_btn.config(text=play_text) 
            play_pause_btn.state(play_btn_new_state_list) 
            stop_btn.state(stop_btn_new_state_list)
            log_debug(f"Play/Pause Button state: {play_pause_btn.state()}, Text: {play_text}, Style: {play_pause_btn.cget('style')}")
            log_debug(f"Stop Button state: {stop_btn.state()}, Style: {stop_btn.cget('style')}")


            meta_total_frames = app_globals.current_video_meta.get('total_frames', 0)
            meta_fps_source = app_globals.current_video_meta.get('fps', 0)
            meta_duration = app_globals.current_video_meta.get('duration_seconds', 0)
            current_frame_num = app_globals.current_video_meta.get('current_frame', 0)

            if meta_total_frames > 0:
                prog_slider.config(state="normal", to=float(meta_total_frames - 1 if meta_total_frames > 0 else 0))
                if not is_video_playback_active: 
                    if prog_var.get() != current_frame_num:
                        app_globals.is_programmatic_slider_update = True
                        try: prog_var.set(current_frame_num)
                        finally: app_globals.is_programmatic_slider_update = False
                
                actual_slider_pos = prog_var.get()
                current_secs_for_time = actual_slider_pos / meta_fps_source if meta_fps_source > 0 else 0
                time_lbl.config(text=format_time_display(current_secs_for_time, meta_duration))
                
                if is_video_playback_active:
                    if fps_lbl: fps_lbl.config(text=f"FPS: {app_globals.real_time_fps_display_value:.2f}")
                else: 
                    if fps_lbl: fps_lbl.config(text=f"FPS: {meta_fps_source:.2f}" if meta_fps_source > 0 else "FPS: --")
                
                if current_frame_lbl: current_frame_lbl.config(text=f"Frame: {actual_slider_pos} / {meta_total_frames}")

            else: 
                prog_slider.config(state="disabled", to=100.0)
                if prog_var.get() != 0: prog_var.set(0)
                time_lbl.config(text="00:00 / 00:00")
                if fps_lbl: fps_lbl.config(text="FPS: --")
                if current_frame_lbl: current_frame_lbl.config(text="Frame: -- / --")
        else: 
            play_pause_btn.config(text="Play")
            play_pause_btn.state(['disabled'])
            stop_btn.state(['disabled'])
            prog_slider.config(state="disabled", to=100.0)
            if prog_var.get() != 0: prog_var.set(0)
            time_lbl.config(text="00:00 / 00:00")
            if fps_lbl: fps_lbl.config(text="FPS: --")
            if current_frame_lbl: current_frame_lbl.config(text="Frame: -- / --")
            log_debug(f"Play/Pause Button (no video controls) state: {play_pause_btn.state()}, Style: {play_pause_btn.cget('style')}")
            log_debug(f"Stop Button (no video controls) state: {stop_btn.state()}, Style: {stop_btn.cget('style')}")


    fast_progress_frame = ui_comps.get("fast_progress_frame")
    if fast_progress_frame:
        if is_fast_processing:
            log_debug("hide_loading_and_update_controls: Fast processing IS active, ensuring progress frame is packed.")
            if not fast_progress_frame.winfo_ismapped():
                log_debug("Packing fast_progress_frame.")
                fast_progress_frame.pack(fill="x", padx=config.SPACING_SMALL, pady=config.SPACING_SMALL, anchor="n")
                if fast_progress_frame.winfo_exists():
                    fast_progress_frame.update_idletasks()
                log_debug(f"fast_progress_frame is_mapped: {fast_progress_frame.winfo_ismapped()}, width: {fast_progress_frame.winfo_width()}, height: {fast_progress_frame.winfo_height()}")

                fp_label = ui_comps.get("fast_progress_label")
                fp_bar = ui_comps.get("fast_progress_bar")

                if fp_label and fp_label.winfo_exists():
                    log_debug("Re-packing fast_progress_label.")
                    fp_label.pack_forget()
                    fp_label.pack(side="left", padx=(0, config.SPACING_MEDIUM))
                    fp_label.update_idletasks()
                
                if fp_bar and fp_bar.winfo_exists():
                    log_debug("Re-packing fast_progress_bar.")
                    fp_bar.pack_forget()
                    fp_bar.pack(side="left", expand=True, fill="x")
                    fp_bar.update_idletasks()
                    log_debug(f"fast_progress_bar (after repack) is_mapped: {fp_bar.winfo_ismapped()}, width: {fp_bar.winfo_width()}, height: {fp_bar.winfo_height()}, current_value: {fp_bar.cget('value')}, var_value: {ui_comps.get('fast_progress_var').get()}")
            
            fp_label_widget = ui_comps.get("fast_progress_label")
            if fp_label_widget and fp_label_widget.cget("text") == "Progress: 0% | --:--:-- Time Left":
                 log_debug("Fast progress label is default, ensuring it's visible and updated if processing.")
                 fp_label_widget.config(text="Progress: 0% | Calculating..." if is_fast_processing else "Progress: 0% | --:--:-- Time Left")


            if root and root.winfo_exists():
                 log_debug("Updating root idletasks at end of fast_processing block.")
                 root.update_idletasks()
        else: 
            log_debug("hide_loading_and_update_controls: Fast processing IS NOT active, ensuring progress frame is forgotten.")
            if fast_progress_frame.winfo_ismapped():
                fast_progress_frame.pack_forget()
            fp_label_widget = ui_comps.get("fast_progress_label")
            if fp_label_widget: 
                fp_label_widget.config(text="Progress: 0% | --:--:-- Time Left")


    video_controls_frame = ui_comps.get("video_controls_frame")
    progress_frame = ui_comps.get("progress_frame")
    video_info_frame = ui_comps.get("video_info_subframe")

    if video_controls_frame and progress_frame and video_info_frame:
        if should_show_video_controls_ui:
            if not video_controls_frame.winfo_ismapped():
                video_controls_frame.grid(row=0, column=0, sticky="ew", padx=2, pady=(2,0))
            if not progress_frame.winfo_ismapped():
                progress_frame.grid(row=1, column=0, sticky="ew", padx=2, pady=(0,2))
            if not video_info_frame.winfo_ismapped():
                video_info_frame.grid(row=3, column=0, sticky="ew", padx=config.SPACING_SMALL, pady=(config.SPACING_SMALL, config.SPACING_SMALL))
        else:
            if video_controls_frame.winfo_ismapped(): video_controls_frame.grid_remove()
            if progress_frame.winfo_ismapped(): progress_frame.grid_remove()
            if video_info_frame.winfo_ismapped(): video_info_frame.grid_remove()

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
        app_globals.is_programmatic_slider_update = True
        try:
            progress_var = ui_comps.get("progress_var")
            if progress_var:
                progress_var.set(frame_idx)

            current_time_secs = 0
            total_duration_secs = app_globals.current_video_meta.get('duration_seconds', 0)
            total_frames = app_globals.current_video_meta.get('total_frames', 0)
            source_fps = app_globals.current_video_meta.get('fps', 0)
            if source_fps > 0:
                current_time_secs = frame_idx / source_fps

            time_label = ui_comps.get("time_label")
            if time_label:
                time_label.config(
                    text=format_time_display(current_time_secs, total_duration_secs)
                )

            current_frame_label = ui_comps.get("current_frame_label")
            if current_frame_label:
                current_frame_label.config(text=f"Frame: {frame_idx} / {total_frames}")

            fps_label = ui_comps.get("fps_label")
            if fps_label :
                fps_label.config(text=f"FPS: {app_globals.real_time_fps_display_value:.2f}")

        except Exception as e:
            log_debug(f"Exception in update_progress do_update: {e}", exc_info=True)
        finally:
            def reset_flag():
                 app_globals.is_programmatic_slider_update = False
            root.after(5, reset_flag)

    root.after(0, do_update)

def update_fast_progress(progress_value, time_left_str="--:--:--"):
    """Update fast progress bar and label. Called from fast_video_processing_thread_func."""
    root = refs.get_root()
    ui_comps = refs.ui_components
    if not ui_comps:
        log_debug("update_fast_progress: ui_comps not available. Aborting.")
        return

    fast_progress_var = ui_comps.get("fast_progress_var")
    fast_progress_label = ui_comps.get("fast_progress_label")

    log_debug(f"update_fast_progress called with value: {progress_value*100:.1f}%, time_left: {time_left_str}")

    if fast_progress_var and root and root.winfo_exists():
        def do_update():
            current_val_int = int(progress_value * 100)
            log_debug(f"update_fast_progress (do_update): Target value: {current_val_int}%")
            
            if fast_progress_var:
                fast_progress_var.set(current_val_int)
                log_debug(f"fast_progress_var set to: {fast_progress_var.get()}")

            if fast_progress_label:
                new_label_text = f"Progress: {current_val_int}% | {time_left_str} Time Left"
                if progress_value >= 1.0 and time_left_str in ["Cancelled", "Error", "Invalid Video", "Writer Error", "Finished"]:
                    new_label_text = f"Fast Processing: {time_left_str}"
                elif progress_value >= 1.0:
                     new_label_text = "Fast Processing: Complete"
                fast_progress_label.config(text=new_label_text)
                log_debug(f"fast_progress_label text set to: \"{new_label_text}\"")


            fp_bar = ui_comps.get("fast_progress_bar")
            if fp_bar and fp_bar.winfo_exists():
                # log_debug(f"fast_progress_bar widget value before update: {fp_bar.cget('value')}, var_value: {fast_progress_var.get()}, is_mapped: {fp_bar.winfo_ismapped()}, width: {fp_bar.winfo_width()}, height: {fp_bar.winfo_height()}")
                fp_bar.update_idletasks()
                # log_debug(f"fast_progress_bar widget value after update_idletasks: {fp_bar.cget('value')}, var_value: {fast_progress_var.get()}, is_mapped: {fp_bar.winfo_ismapped()}, width: {fp_bar.winfo_width()}, height: {fp_bar.winfo_height()}")
            # else:
                # log_debug("fast_progress_bar widget not found or not existing in do_update.")


            if root and root.winfo_exists():
                # log_debug("update_fast_progress (do_update): Updating root idletasks.")
                root.update_idletasks()

            if progress_value >= 1.0:
                log_debug("Fast processing 100% (update_fast_progress). Preparing to finalize.")
                app_globals.fast_processing_active_flag.clear()
                log_debug("Fast processing 100% (update_fast_progress): Flag cleared. Updating controls.")
                hide_loading_and_update_controls()
                
                if time_left_str not in ["Cancelled", "Error", "Invalid Video", "Writer Error", "Finished"]:
                    print("Fast video processing complete. Ready for playback.")
                
                fps_label = ui_comps.get("fps_label")
                meta_fps = app_globals.current_video_meta.get('fps', 0)
                if fps_label and meta_fps > 0: 
                    fps_label.config(text=f"FPS: {meta_fps:.2f}")
        
        root.after(0, do_update)
    elif not fast_progress_var:
        log_debug("update_fast_progress: fast_progress_var is None.")
    elif not root or not root.winfo_exists():
        log_debug("update_fast_progress: root window not available.")
