# _ui_loading_manager.py
"""
Manages the loading overlay and updating UI control states.
Also includes UI update callbacks like update_progress.
"""
import tkinter as tk
from tkinter import ttk
import time 
from . import _ui_shared_refs as refs
from . import globals as app_globals
from . import config
from .logger_setup import log_debug
from .ui_custom_widgets import LoadingOverlay 
from .video_handler import format_time_display
import os

def show_loading(message="Loading..."):
    log_debug(f"show_loading: START - {message}")
    root = refs.get_root()
    if root is None: root = app_globals.ui_references.get("root") 
    if root is None: log_debug("show_loading: root_window is None. Aborting."); return

    root.update_idletasks() 
    try:
        # Use the integrated overlay
        log_debug(f"show_loading: Showing integrated overlay with message: {message}")
        LoadingOverlay.show(root, message)
        log_debug(f"show_loading: Integrated overlay shown successfully")
    except Exception as e: 
        log_debug(f"show_loading: Error showing loading overlay: {e}", exc_info=True)
        print(f"Loading: {message} (Overlay Error: {e})")

    ui_comps = app_globals.ui_references.get("ui_components_dict", {})
    if ui_comps:
        controls_to_disable = [
            "file_upload_button", "process_button", "fast_process_button",
            "iou_slider", "conf_slider", "play_pause_button", "stop_button",
            "progress_slider"
        ]
        for key in controls_to_disable:
            comp = ui_comps.get(key)
            if comp and hasattr(comp, 'state'):
                try:
                    if isinstance(comp, (ttk.Button, ttk.Radiobutton)): comp.state(['disabled'])
                    elif isinstance(comp, ttk.Scale): comp.config(state="disabled")
                except tk.TclError: log_debug(f"show_loading: TclError disabling {key}, possibly already destroyed.")
        
        for button in ui_comps.get("model_buttons", []): 
            if button and hasattr(button, 'state'): 
                try: button.state(['disabled'])
                except tk.TclError: log_debug(f"show_loading: TclError disabling model button, possibly already destroyed.")
    log_debug(f"show_loading: END")

def update_message(message):
    """
    Updates the message in the loading overlay.
    
    Args:
        message (str): The new message to display
    """
    log_debug(f"update_message: START - {message}")
    try:
        # Call the LoadingOverlay's static method to update the message
        LoadingOverlay.update(message)
        log_debug(f"update_message: Message updated successfully to: {message}")
    except Exception as e:
        log_debug(f"update_message: Error updating loading message: {e}", exc_info=True)
        print(f"Update message: {message} (Error: {e})")
    log_debug(f"update_message: END")


def hide_loading_and_update_controls():
    func_id = f"HLC_{time.monotonic_ns()}" 
    log_debug(f"{func_id}: START. Root geo: {app_globals.ui_references.get('root').geometry() if app_globals.ui_references.get('root') else 'N/A'}")
    t_start_func = time.perf_counter()
    root = app_globals.ui_references.get("root") 
    ui_comps = app_globals.ui_references.get("ui_components_dict", {})
    
    # Hide the integrated loading overlay
    try:
        log_debug(f"{func_id}: Hiding integrated loading overlay")
        LoadingOverlay.hide()  # Use the static hide method
    except Exception as e:
        log_debug(f"{func_id}: Error hiding loading overlay: {str(e)}")
        # If hide fails, try to restore window state
        if root and root.winfo_exists():
            root.resizable(True, True)
            root.config(cursor="")  # Reset cursor to default

    if not ui_comps or not app_globals.ui_references: log_debug(f"{func_id}: ui_comps or ui_references not available."); return
    if root is None or not root.winfo_exists(): log_debug(f"{func_id}: root_window not available."); return

    app_frame = app_globals.ui_references.get("app_frame")
    left_panel = app_globals.ui_references.get("left_panel")
    right_panel = app_globals.ui_references.get("right_panel")

    if not all([app_frame, left_panel, right_panel]): log_debug(f"{func_id}: Core panel refs missing."); return

    file_uploaded = bool(app_globals.uploaded_file_info and app_globals.uploaded_file_info.get('path'))
    is_fast_processing = app_globals.fast_processing_active_flag.is_set()
    model_loaded = app_globals.active_model_object_global is not None
    uploaded_file_type = app_globals.uploaded_file_info.get('file_type', '') if file_uploaded else ''
    is_video_file = uploaded_file_type == 'video'
    
    log_debug(f"{func_id}: States: file_uploaded={file_uploaded}, file_type='{uploaded_file_type}', is_fast_processing={is_fast_processing}, model_loaded={model_loaded}")
    
    video_player_container = ui_comps.get("video_player_container")
    video_display_widget = ui_comps.get("video_display")
    
    file_upload_frame = ui_comps.get("file_upload_frame")
    model_selector_frame = ui_comps.get("model_selector_frame")
    process_buttons_frame = ui_comps.get("process_buttons_frame")
    sliders_frame = ui_comps.get("sliders_frame")

    # --- Manage visibility of left panel sections ---
    # Start by forgetting all to ensure a clean slate for conditional packing
    for frame_key, frame_widget in [("file_upload_frame", file_upload_frame), 
                                    ("model_selector_frame", model_selector_frame),
                                    ("process_buttons_frame", process_buttons_frame),
                                    ("sliders_frame", sliders_frame)]:
        if frame_widget and frame_widget.winfo_ismapped() and frame_widget.winfo_manager() == 'pack':
            log_debug(f"{func_id}: Pre-emptively forgetting {frame_key} (current size: {frame_widget.winfo_width()}x{frame_widget.winfo_height()})")
            frame_widget.pack_forget()
    root.update_idletasks() # Process forgets before repacking
    log_debug(f"{func_id}: All left panel section frames ensured forgotten. Left panel size after forgets: {left_panel.winfo_width()}x{left_panel.winfo_height()}")


    # Conditionally pack frames
    last_packed_widget = None
    if file_upload_frame and not is_fast_processing:
        log_debug(f"{func_id}: Packing file_upload_frame.")
        file_upload_frame.pack(fill="x", pady=(0, config.SPACING_MEDIUM), anchor="n")
        last_packed_widget = file_upload_frame
    
    if model_selector_frame:
        if model_loaded and not is_fast_processing and file_uploaded:
            log_debug(f"{func_id}: Packing model_selector_frame. (File uploaded)")
            model_selector_frame.pack(fill="x", pady=(0, config.SPACING_MEDIUM), anchor="n", after=last_packed_widget)
            last_packed_widget = model_selector_frame
            log_debug(f"{func_id}: Packing radiobuttons within model_selector_frame.")
            for rb_idx, rb in enumerate(ui_comps.get("model_buttons", [])): 
                if not rb.winfo_ismapped(): 
                    rb.pack(anchor="w", padx=config.SPACING_MEDIUM, pady=config.SPACING_SMALL)
        # Ensure it's forgotten if conditions not met (especially at launch)
        elif model_selector_frame.winfo_ismapped():
            log_debug(f"{func_id}: Conditions not met for model_selector_frame, forgetting. model_loaded={model_loaded}, is_fast_processing={is_fast_processing}, file_uploaded={file_uploaded}")
            model_selector_frame.pack_forget()


    show_processing_controls = file_uploaded and model_loaded and not is_fast_processing
    if process_buttons_frame and show_processing_controls:
        log_debug(f"{func_id}: Packing process_buttons_frame.")
        process_buttons_frame.pack(fill="x", pady=(0, config.SPACING_MEDIUM), anchor="n", after=last_packed_widget)
        last_packed_widget = process_buttons_frame
    
    if sliders_frame and show_processing_controls:
        log_debug(f"{func_id}: Packing sliders_frame.")
        sliders_frame.pack(fill="x", pady=(0, config.SPACING_MEDIUM), anchor="n", after=last_packed_widget)
        last_packed_widget = sliders_frame # Though not strictly needed as it's the last one here
    
    root.update_idletasks() 
    log_debug(f"{func_id}: Left panel items packed/forgotten. Left panel new size: {left_panel.winfo_width()}x{left_panel.winfo_height()}. Root geo: {root.geometry()}")

    # --- Manage two-panel layout and right panel content ---
    if file_uploaded:
        if not right_panel.winfo_ismapped(): 
            log_debug(f"{func_id}: File uploaded: Switching to two-panel layout.")
            
            if video_display_widget: 
                log_debug(f"{func_id}: Unbinding Configure from video_display_widget.")
                video_display_widget.unbind("<Configure>") 
                video_display_widget._initial_configure_done = False

            left_panel.grid_configure(column=0, row=1, columnspan=1, sticky="nswe", padx=(0, config.SPACING_MEDIUM))
            app_frame.columnconfigure(0, weight=1, minsize=280, uniform="left_group") 
            # Give right panel a defined initial minsize and a moderate weight
            app_frame.columnconfigure(1, weight=2, minsize=int(config.DEFAULT_VIDEO_WIDTH * 0.7), uniform="right_group") 
            right_panel.grid(row=1, column=1, sticky="nswe")
            log_debug(f"{func_id}: Panels gridded for two-panel. app_frame col1 weight=2.")
            
            # Use fixed size of 1305 x 805 as requested
            target_w, target_h = 1305, 805
            screen_w, screen_h = root.winfo_screenwidth(), root.winfo_screenheight()
            
            # Ensure we don't exceed screen limits (with margin) if screen is smaller than target
            target_w = min(target_w, int(screen_w * 0.95))
            target_h = min(target_h, int(screen_h * 0.95))

            current_w, current_h = root.winfo_width(), root.winfo_height()
            
            # Always set to exact target size (1305x805) when file is uploaded
            # Ensure we're not expanding beyond screen bounds
            new_w = min(target_w, screen_w - 50)
            new_h = min(target_h, screen_h - 80)
            log_debug(f"{func_id}: Resizing window from {current_w}x{current_h} to exact target {new_w}x{new_h}")
            root.geometry(f"{new_w}x{new_h}")
            root.minsize(new_w, new_h)  # Set minimum window size to match target
            # Force a redraw to ensure window size takes effect immediately
            root.update()
            
            log_debug(f"{func_id}: Set window minsize to {new_w}x{new_h} and calling root.update() for structural geometry. Pre-update geo: {root.geometry()}")
            t_before_update = time.perf_counter()
            root.update() 
            t_after_update = time.perf_counter()
            log_debug(f"{func_id}: root.update() for structural geometry completed in {(t_after_update - t_before_update)*1000:.2f} ms. Post-update geo: {root.geometry()}")
            log_debug(f"{func_id}: Right panel size after root.update(): {right_panel.winfo_width()}x{right_panel.winfo_height()}. Left panel: {left_panel.winfo_width()}x{left_panel.winfo_height()}")

            def _setup_video_player_content_final_deferred():
                func_id_def = f"{func_id}_deferred"
                log_debug(f"{func_id_def}: START. Root geo: {root.geometry()}")
                t_deferred_start = time.perf_counter()
                if not root.winfo_exists(): return
                
                # Ensure first frame is displayed in deferred setup
                if app_globals.current_processed_image_for_display is not None and video_display_widget and video_display_widget.winfo_exists():
                    video_display_widget.update_frame(app_globals.current_processed_image_for_display)
                    log_debug(f"{func_id_def}: Displayed first frame in deferred setup")

                if video_player_container:
                    # Configure video_player_container with an explicit size BEFORE gridding it,
                    # to prevent it from influencing parent's size request initially.
                    # It should later expand due to sticky="nsew" in its grid config.
                    # Use more conservative size limits to prevent overflow and resize bugginess
                    right_panel_w = right_panel.winfo_width() or config.DEFAULT_VIDEO_WIDTH
                    right_panel_h = right_panel.winfo_height() or config.DEFAULT_VIDEO_HEIGHT
                    
                    # Hard cap the maximum size to avoid display issues
                    max_width = min(config.DEFAULT_VIDEO_WIDTH * 1.5, 1280)
                    max_height = min(config.DEFAULT_VIDEO_HEIGHT * 1.5, 720)
                    
                    # More cautious sizing of the video container
                    initial_vpc_w = min(max(100, int(right_panel_w * 0.85)), max_width)
                    initial_vpc_h = min(max(100, int(right_panel_h * 0.65)), max_height)
                    log_debug(f"{func_id_def}: Configuring video_player_container with WxH: {initial_vpc_w}x{initial_vpc_h}")
                    video_player_container.config(width=initial_vpc_w, height=initial_vpc_h)
                    
                    if not video_player_container.winfo_ismapped():
                        log_debug(f"{func_id_def}: Gridding video_player_container (sticky='nsew') into right_panel ({right_panel.winfo_width()}x{right_panel.winfo_height()}).")
                        video_player_container.grid(row=0, column=0, sticky="nsew", padx=config.SPACING_SMALL, pady=config.SPACING_SMALL)
                    
                    # Add metrics frame for additional video stats
                    metrics_frame = ui_comps.get("metrics_frame")
                    if metrics_frame is None:
                        # Create metrics frame if it doesn't exist
                        import tkinter as tk
                        metrics_frame = tk.Frame(right_panel, bg=config.COLOR_BACKGROUND)
                        ui_comps["metrics_frame"] = metrics_frame
                        
                        # Create detection count label if it doesn't exist
                        detection_count_label = ttk.Label(metrics_frame, text="Detections: 0")
                        detection_count_label.pack(side=tk.LEFT, padx=(config.SPACING_SMALL, config.SPACING_MEDIUM))
                        ui_comps["detection_count_label"] = detection_count_label
                        
                        # Create performance label if it doesn't exist
                        performance_label = ttk.Label(metrics_frame, text="Performance: --")
                        performance_label.pack(side=tk.LEFT, padx=(config.SPACING_SMALL, config.SPACING_MEDIUM))
                        ui_comps["performance_label"] = performance_label
                    
                    # Grid metrics frame below video container
                    if not metrics_frame.winfo_ismapped():
                        metrics_frame.grid(row=1, column=0, sticky="ew", padx=config.SPACING_SMALL, pady=(0, config.SPACING_SMALL))
                    
                    root.update_idletasks() 
                    log_debug(f"{func_id_def}: video_player_container actual size after grid & update: {video_player_container.winfo_width()}x{video_player_container.winfo_height()}")
                else:
                    log_debug(f"{func_id_def}: video_player_container is None."); return

                if video_display_widget: 
                    # Get container dimensions but apply stricter size constraints
                    container_w = video_player_container.winfo_width() if video_player_container.winfo_width() > 1 else config.DEFAULT_VIDEO_WIDTH
                    container_h = video_player_container.winfo_height() if video_player_container.winfo_height() > 1 else config.DEFAULT_VIDEO_HEIGHT
                        
                    # Set target width/height with hard maximum limits to prevent runaway growth
                    max_display_width = min(config.DEFAULT_VIDEO_WIDTH * 1.5, 1024)
                    max_display_height = min(config.DEFAULT_VIDEO_HEIGHT * 1.5, 768)
                        
                    video_display_widget.target_width = min(container_w, max_display_width)
                    video_display_widget.target_height = min(container_h, max_display_height)
                    log_debug(f"{func_id_def}: Set video_display_widget target to container size: {video_display_widget.target_width}x{video_display_widget.target_height}")

                    if uploaded_file_type == 'image' and app_globals.current_processed_image_for_display is not None:
                        video_display_widget.update_frame(app_globals.current_processed_image_for_display)
                    elif uploaded_file_type == 'video' and app_globals.current_processed_image_for_display is not None:
                        video_display_widget.update_frame(app_globals.current_processed_image_for_display)
                    
                        # Ensure we're not triggering a cascade of resize events
                        try:
                            video_display_widget.force_initial_resize_and_rebind(prevent_recursive=True) 
                        except Exception as e:
                            log_debug(f"{func_id_def}: Error during video_display_widget resize: {str(e)}")
                else: log_debug(f"{func_id_def}: video_display_widget is None.")

                t_deferred_end = time.perf_counter()
                log_debug(f"{func_id_def}: END. Total time: {(t_deferred_end - t_deferred_start)*1000:.2f} ms.")
                if root and root.winfo_exists(): root.update_idletasks()

            if root and root.winfo_exists():
                # Use a longer delay to ensure window is stable before setting up video content
                root.after(250, _setup_video_player_content_final_deferred)
                log_debug(f"{func_id}: Scheduled _setup_video_player_content_final_deferred.")

        elif right_panel.winfo_ismapped(): 
            log_debug(f"{func_id}: File uploaded: Right panel already mapped. Updating content directly.")
            if video_display_widget:
                 log_debug(f"{func_id}: video_display_widget current target size: {video_display_widget.target_width}x{video_display_widget.target_height}, actual size: {video_display_widget.winfo_width()}x{video_display_widget.winfo_height()}")
            if uploaded_file_type == 'image' and app_globals.current_processed_image_for_display is not None:
                if video_display_widget: video_display_widget.update_frame(app_globals.current_processed_image_for_display)
            elif uploaded_file_type == 'video' and app_globals.current_processed_image_for_display is not None:
                if video_display_widget: 
                    video_display_widget.update_frame(app_globals.current_processed_image_for_display)
                    log_debug(f"{func_id}: Displayed first video frame in already mapped panel")
            root.update_idletasks() 

    else: # No file uploaded
        if right_panel.winfo_ismapped() or left_panel.grid_info().get("columnspan") != 2:
            log_debug(f"{func_id}: No file uploaded: Ensuring single-panel (left) centered layout.")
            # First clear any video content to prevent memory issues
            if video_display_widget: video_display_widget.clear()
                
            # Hide right panel elements
            if video_player_container and video_player_container.winfo_ismapped(): 
                video_player_container.grid_remove()
                    
            # Remove right panel completely
            right_panel.grid_remove()
                
            # Reconfigure left panel to span both columns
            left_panel.grid_configure(column=0, row=1, columnspan=2, sticky="nsew", padx=0)
            app_frame.columnconfigure(0, weight=1, minsize=300, uniform="left_group") 
            app_frame.columnconfigure(1, weight=0, minsize=0, uniform="right_group") 
                
            # Always reset the minimum size to a fixed smaller value when switching to single panel
            initial_min_w, initial_min_h = 450, 350  # Conservative minimum size for single panel view
            root.minsize(initial_min_w, initial_min_h)
            log_debug(f"{func_id}: Reset window minsize to {initial_min_w}x{initial_min_h} for single panel view")
                
            # Process layout changes
            root.update_idletasks()
                
            # Always return window to a fixed size when switching to single panel
            current_w, current_h = root.winfo_width(), root.winfo_height()
            # Use a fixed size for single panel that's appropriately sized
            new_w, new_h = 600, 500
            log_debug(f"{func_id}: Resizing window from {current_w}x{current_h} to fixed single panel size {new_w}x{new_h}")
            root.geometry(f"{new_w}x{new_h}")
            root.update_idletasks()  # Process the resize immediately

    # --- Standard control state updates (enabling/disabling) ---
    file_upload_btn = ui_comps.get("file_upload_button")
    if file_upload_btn: file_upload_btn.state(['disabled'] if is_fast_processing else ['!disabled'])
    for button in ui_comps.get("model_buttons", []): 
        if button: button.state(['disabled'] if is_fast_processing or not model_loaded else ['!disabled'])
    sliders_new_state_tk = "normal" if model_loaded and not is_fast_processing and file_uploaded else "disabled"
    if ui_comps.get("iou_slider"): ui_comps["iou_slider"].config(state=sliders_new_state_tk)
    if ui_comps.get("conf_slider"): ui_comps["conf_slider"].config(state=sliders_new_state_tk)
    process_btn = ui_comps.get("process_button")
    if process_btn:
        can_process_realtime = file_uploaded and model_loaded and not is_fast_processing
        process_btn.state(['!disabled'] if can_process_realtime else ['disabled'])
    fast_process_btn = ui_comps.get("fast_process_button")
    if fast_process_btn:
        can_fast_process = file_uploaded and model_loaded and is_video_file and not is_fast_processing
        fast_process_btn.state(['!disabled'] if can_fast_process else ['disabled'])
    is_video_playback_active = app_globals.is_playing_via_after_loop
    is_processed_video_ready_for_playback = app_globals.processed_video_temp_file_path_global and \
                                           os.path.exists(app_globals.processed_video_temp_file_path_global) and \
                                           not is_video_playback_active
    should_show_video_controls_ui = file_uploaded and (is_video_file or is_processed_video_ready_for_playback) and not is_fast_processing
    play_pause_btn = ui_comps.get("play_pause_button")
    stop_btn = ui_comps.get("stop_button")
    prog_slider = ui_comps.get("progress_slider")
    prog_var = ui_comps.get("progress_var")
    time_lbl = ui_comps.get("time_label")
    video_controls_frame = ui_comps.get("video_controls_frame")
    progress_frame_ui = ui_comps.get("progress_frame") 
    video_info_frame = ui_comps.get("video_info_frame") 
    if all([play_pause_btn, stop_btn, prog_slider, prog_var, time_lbl, 
            video_controls_frame, progress_frame_ui, video_info_frame]):
        if should_show_video_controls_ui:
            if not video_controls_frame.winfo_ismapped(): video_controls_frame.grid()
            if not progress_frame_ui.winfo_ismapped(): progress_frame_ui.grid()
            if not video_info_frame.winfo_ismapped(): video_info_frame.grid()
            play_text = "Play"; play_btn_new_state_list = ['disabled']; stop_btn_new_state_list = ['disabled']
            if is_video_playback_active:
                play_text = "Pause" if not app_globals.video_paused_flag.is_set() else "Play"
                play_btn_new_state_list = ['!disabled']; stop_btn_new_state_list = ['!disabled']
            elif is_processed_video_ready_for_playback:
                play_text = "Play"; play_btn_new_state_list = ['!disabled']; stop_btn_new_state_list = ['!disabled']
            elif is_video_file and app_globals.video_capture_global and app_globals.video_capture_global.isOpened():
                play_text = "Play"; play_btn_new_state_list = ['!disabled']; stop_btn_new_state_list = ['!disabled']
            elif is_video_file: 
                play_text = "Play"; play_btn_new_state_list = ['!disabled']; stop_btn_new_state_list = ['disabled']
            if uploaded_file_type == 'image': 
                play_btn_new_state_list = ['disabled']; stop_btn_new_state_list = ['disabled']
                play_text = "Play" 
            play_pause_btn.config(text=play_text); play_pause_btn.state(play_btn_new_state_list)
            stop_btn.state(stop_btn_new_state_list)
            meta_total_frames = app_globals.current_video_meta.get('total_frames', 0)
            meta_fps_source = app_globals.current_video_meta.get('fps', 0)
            meta_duration = app_globals.current_video_meta.get('duration_seconds', 0)
            current_frame_num_meta = app_globals.current_video_meta.get('current_frame', 0)
            if uploaded_file_type == 'video' and meta_total_frames > 0 :
                prog_slider.config(state="normal", to=float(max(0, meta_total_frames - 1)))
                if not is_video_playback_active: 
                    if prog_var.get() != current_frame_num_meta:
                        app_globals.is_programmatic_slider_update = True
                        try: prog_var.set(current_frame_num_meta)
                        finally: app_globals.is_programmatic_slider_update = False
                actual_slider_pos = int(prog_var.get()) 
                current_secs_for_time = actual_slider_pos / meta_fps_source if meta_fps_source > 0 else 0
                time_lbl.config(text=format_time_display(current_secs_for_time, meta_duration))
                if ui_comps.get("fps_label"): ui_comps["fps_label"].config(text=f"FPS: {app_globals.real_time_fps_display_value:.2f}" if is_video_playback_active else (f'{meta_fps_source:.2f}' if meta_fps_source > 0 else '--'))
                if ui_comps.get("current_frame_label"): ui_comps["current_frame_label"].config(text=f"Frame: {actual_slider_pos} / {meta_total_frames}")
            elif uploaded_file_type == 'image': 
                 prog_slider.config(state="disabled", to=100.0); prog_var.set(0)
                 time_lbl.config(text="--:-- / --:--")
            else: 
                prog_slider.config(state="disabled", to=100.0); prog_var.set(0)
                time_lbl.config(text="00:00 / 00:00")
                if ui_comps.get("fps_label"): ui_comps["fps_label"].config(text="FPS: --")
                if ui_comps.get("current_frame_label"): ui_comps["current_frame_label"].config(text="Frame: -- / --")
        else: 
            if video_controls_frame.winfo_ismapped(): video_controls_frame.grid_remove()
            if progress_frame_ui.winfo_ismapped(): progress_frame_ui.grid_remove()
            if video_info_frame.winfo_ismapped(): video_info_frame.grid_remove() 
            if not file_uploaded and video_display_widget: 
                 video_display_widget.clear()

    fast_progress_frame = ui_comps.get("fast_progress_frame")
    if fast_progress_frame:
        if is_fast_processing:
            if not fast_progress_frame.winfo_ismapped():
                current_after_fp = sliders_frame if sliders_frame and sliders_frame.winfo_ismapped() else \
                                  (process_buttons_frame if process_buttons_frame and process_buttons_frame.winfo_ismapped() else \
                                   (model_selector_frame if model_selector_frame and model_selector_frame.winfo_ismapped() else \
                                    (file_upload_frame if file_upload_frame and file_upload_frame.winfo_ismapped() else None)))
                fast_progress_frame.pack(fill="x", padx=config.SPACING_SMALL, pady=config.SPACING_SMALL, anchor="n", after=current_after_fp)
            fp_label_widget = ui_comps.get("fast_progress_label")
            if fp_label_widget and fp_label_widget.cget("text") == "Progress: 0% | --:--:-- Time Left": 
                 fp_label_widget.config(text="Progress: 0% | Calculating...")
        else:
            if fast_progress_frame.winfo_ismapped():
                fast_progress_frame.pack_forget()
            fp_label_widget = ui_comps.get("fast_progress_label") 
            if fp_label_widget: fp_label_widget.config(text="Progress: 0% | --:--:-- Time Left")
    
    log_debug(f"{func_id}: Final component sizes: FileUp: {file_upload_frame.winfo_width() if file_upload_frame else 'N/A'}x{file_upload_frame.winfo_height() if file_upload_frame and file_upload_frame.winfo_ismapped() else 'N/M'}, ModelSel: {model_selector_frame.winfo_width() if model_selector_frame else 'N/A'}x{model_selector_frame.winfo_height() if model_selector_frame and model_selector_frame.winfo_ismapped() else 'N/M'}")
    if video_player_container and video_player_container.winfo_ismapped():
        log_debug(f"{func_id}: VideoPlayerContainer is mapped. Size: {video_player_container.winfo_width()}x{video_player_container.winfo_height()}")
        if video_display_widget and video_display_widget.winfo_ismapped():
            log_debug(f"{func_id}: VideoDisplayWidget is mapped. Target: {video_display_widget.target_width}x{video_display_widget.target_height}, Actual: {video_display_widget.winfo_width()}x{video_display_widget.winfo_height()}")
        else:
            log_debug(f"{func_id}: VideoDisplayWidget is NOT mapped or does not exist.")
    else:
        log_debug(f"{func_id}: VideoPlayerContainer is NOT mapped or does not exist.")


    t_before_final_update = time.perf_counter()
    if root and root.winfo_exists(): root.update_idletasks()
    t_after_final_update = time.perf_counter()
    log_debug(f"{func_id}: Final root.update_idletasks() took {(t_after_final_update - t_before_final_update)*1000:.2f} ms. Current geo: {root.geometry()}")
    t_end_func = time.perf_counter()
    log_debug(f"{func_id}: hide_loading_and_update_controls finished in {(t_end_func - t_start_func)*1000:.2f} ms.")


def update_progress(frame_idx):
    root = app_globals.ui_references.get("root")
    ui_comps = app_globals.ui_references.get("ui_components_dict", {})
    if not ui_comps or not root or not root.winfo_exists(): return
    def do_update():
        app_globals.is_programmatic_slider_update = True
        try:
            progress_var = ui_comps.get("progress_var"); current_frame_label = ui_comps.get("current_frame_label")
            time_label = ui_comps.get("time_label"); fps_label = ui_comps.get("fps_label")
            detection_count_label = ui_comps.get("detection_count_label")
            performance_label = ui_comps.get("performance_label")
            
            safe_frame_idx = int(frame_idx)

            if progress_var: progress_var.set(safe_frame_idx)
            
            current_time_secs = 0.0
            total_duration_secs = app_globals.current_video_meta.get('duration_seconds', 0.0)
            total_frames = app_globals.current_video_meta.get('total_frames', 0)
            source_fps = app_globals.current_video_meta.get('fps', 0.0)

            if source_fps > 0: current_time_secs = safe_frame_idx / source_fps
            
            # Always update critical UI elements
            if time_label: time_label.config(text=format_time_display(current_time_secs, total_duration_secs))
            if current_frame_label: current_frame_label.config(text=f"Frame: {safe_frame_idx} / {total_frames}")
            
            # Ensure FPS is always displayed, even if real_time_fps_display_value is 0
            if fps_label:
                fps_value = app_globals.real_time_fps_display_value
                if fps_value <= 0 and source_fps > 0:
                    fps_value = source_fps  # Fallback to source FPS if real-time value not available
                fps_label.config(text=f"FPS: {fps_value:.1f}")
            
            # Display detection count if available
            if detection_count_label and hasattr(app_globals, 'last_detection_count'):
                detection_count_label.config(text=f"Detections: {app_globals.last_detection_count}")
                
            # Update performance label based on processing load if available
            if performance_label and hasattr(app_globals, 'last_processing_load'):
                load = app_globals.last_processing_load
                if load > 0.9:
                    performance_label.config(text="Performance: Poor", foreground="red")
                elif load > 0.7:
                    performance_label.config(text="Performance: Fair", foreground="orange")
                elif load > 0.5:
                    performance_label.config(text="Performance: Good", foreground="black")
                else:
                    performance_label.config(text="Performance: Excellent", foreground="green")
                fps_value = app_globals.real_time_fps_display_value
                if fps_value <= 0 and source_fps > 0:
                    fps_value = source_fps  # Fallback to source FPS if real-time value not available
                fps_label.config(text=f"FPS: {fps_value:.1f}")
            
            # Display detection count if available
            if detection_count_label and hasattr(app_globals, 'last_detection_count'):
                detection_count_label.config(text=f"Detections: {app_globals.last_detection_count}")

        except Exception as e: log_debug(f"Exception in update_progress do_update: {e}", exc_info=True)
        finally:
            def reset_flag(): app_globals.is_programmatic_slider_update = False
            if root and root.winfo_exists(): root.after(5, reset_flag) 
    if root and root.winfo_exists(): root.after(0, do_update)


def update_fast_progress(progress_value, time_left_str="--:--:--"):
    # Don't update if we're not actually in fast processing mode
    if not app_globals.fast_processing_active_flag.is_set():
        log_debug(f"update_fast_progress: Ignoring call as fast_processing_active_flag is not set")
        return
        
    root = app_globals.ui_references.get("root")
    ui_comps = app_globals.ui_references.get("ui_components_dict", {})
    if not ui_comps: log_debug("update_fast_progress: ui_comps not available."); return
    
    fast_progress_var = ui_comps.get("fast_progress_var")
    fast_progress_label = ui_comps.get("fast_progress_label")
    fps_label = ui_comps.get("fps_label")
    current_frame_label = ui_comps.get("current_frame_label")
    log_debug(f"update_fast_progress called with value: {progress_value*100:.1f}%, time_left: {time_left_str}")

    if fast_progress_var and root and root.winfo_exists():
        def do_update():
            current_val_int = int(progress_value * 100)
            if fast_progress_var: fast_progress_var.set(current_val_int)
            
            if fast_progress_label:
                new_label_text = f"Progress: {current_val_int}% | {time_left_str} Time Left"
                if progress_value >= 1.0: 
                    if time_left_str in ["Cancelled", "Error", "Invalid Video", "Writer Error", "Finished"]:
                        new_label_text = f"Fast Processing: {time_left_str}"
                    else: 
                        new_label_text = "Fast Processing: Complete"
                fast_progress_label.config(text=new_label_text)
            
            fp_bar = ui_comps.get("fast_progress_bar")
            if fp_bar and fp_bar.winfo_exists(): fp_bar.update_idletasks() 

            if root and root.winfo_exists(): root.update_idletasks() 

            if progress_value >= 1.0: 
                app_globals.fast_processing_active_flag.clear()
                hide_loading_and_update_controls() 
                
                if time_left_str not in ["Cancelled", "Error", "Invalid Video", "Writer Error", "Finished"]:
                    # Only print once at completion
                    log_debug("Fast video processing complete. Ready for playback.")
                    print("Fast video processing complete. Ready for playback.")
                
                if time_left_str not in ["Cancelled", "Error", "Invalid Video", "Writer Error"]:
                    # Update all relevant UI elements with final values
                    fps_label_widget = ui_comps.get("fps_label")
                    current_frame_label = ui_comps.get("current_frame_label")
                    detection_count_label = ui_comps.get("detection_count_label")
                    
                    meta_fps = app_globals.current_video_meta.get('fps', 0)
                    total_frames = app_globals.current_video_meta.get('total_frames', 0)
                    
                    if fps_label_widget and meta_fps > 0:
                        fps_label_widget.config(text=f"FPS: {meta_fps:.1f}")
                    
                    if current_frame_label:
                        current_frame_label.config(text=f"Frame: {total_frames} / {total_frames}")
                        
                    if detection_count_label:
                        last_count = getattr(app_globals, 'last_detection_count', 0)
                        detection_count_label.config(text=f"Detections: {last_count}")

        if root and root.winfo_exists(): root.after(0, do_update)
    elif not fast_progress_var: log_debug("update_fast_progress: fast_progress_var is None.")
    elif not root or not root.winfo_exists(): log_debug("update_fast_progress: root window not available.")
