# tk_ui_elements.py

"""
Tkinter UI Elements for the Vehicle Detection and Tracking Application
This module defines all the UI components used in the application.
Refactored for better modularity.
"""

import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageTk
import cv2
import numpy as np
import os
from . import config # Assuming config.py is in the same directory or package

# --- Theme Setup ---
def setup_material_theme(style_instance=None):
    """Set up a Material Design theme for ttk widgets"""
    style = style_instance if style_instance else ttk.Style()
    try:
        style.theme_use('clam')
    except tk.TclError:
        print("Warning: 'clam' theme not available, using default.")
        pass

    # General widget configurations
    style.configure(".", font=config.FONT_BODY, background=config.COLOR_BACKGROUND)
    style.configure("TFrame", background=config.COLOR_BACKGROUND)
    style.configure("Card.TFrame", background=config.COLOR_SURFACE, relief="solid", borderwidth=1)
    style.map("Card.TFrame", bordercolor=[('active', config.COLOR_PRIMARY_LIGHT), ('!active', config.COLOR_BACKGROUND_LIGHT)])

    # Label styles
    style.configure("TLabel", font=config.FONT_BODY, background=config.COLOR_BACKGROUND, foreground=config.COLOR_TEXT_PRIMARY)
    style.configure("Card.TLabel", font=config.FONT_BODY, background=config.COLOR_SURFACE, foreground=config.COLOR_TEXT_PRIMARY)
    style.configure("Title.TLabel", font=config.FONT_TITLE, background=config.COLOR_SURFACE, foreground=config.COLOR_TEXT_PRIMARY)
    style.configure("Subtitle.TLabel", font=config.FONT_SUBTITLE, background=config.COLOR_SURFACE, foreground=config.COLOR_TEXT_SECONDARY)
    style.configure("Caption.TLabel", font=config.FONT_CAPTION, foreground=config.COLOR_TEXT_SECONDARY)
    style.configure("Info.TLabel", font=config.FONT_CAPTION, background=config.COLOR_BACKGROUND, foreground=config.COLOR_TEXT_SECONDARY)

    # Labelframe styles
    style.configure("TLabelframe", background=config.COLOR_SURFACE, relief="solid", borderwidth=1, padding=config.SPACING_MEDIUM)
    style.map("TLabelframe", bordercolor=[('active', config.COLOR_PRIMARY_LIGHT), ('!active', config.COLOR_BACKGROUND_LIGHT)])
    style.configure("TLabelframe.Label", font=config.FONT_SUBTITLE, background=config.COLOR_SURFACE, foreground=config.COLOR_TEXT_PRIMARY, padding=(0,0,0,config.SPACING_SMALL))

    # Button styles
    button_padding = (config.SPACING_MEDIUM, config.SPACING_SMALL)
    style.configure("TButton", font=config.FONT_BUTTON, padding=button_padding, relief="raised", borderwidth=1, focusthickness=1)
    style.map("TButton",
              background=[('active', config.COLOR_BACKGROUND_LIGHT), ('disabled', '#E0E0E0'), ('!disabled', config.COLOR_SURFACE)],
              foreground=[('disabled', config.COLOR_TEXT_SECONDARY), ('!disabled', config.COLOR_TEXT_PRIMARY)],
              relief=[('pressed', 'sunken'), ('!pressed', 'raised')])

    style.configure("Primary.TButton", font=config.FONT_BUTTON, padding=button_padding, background=config.COLOR_PRIMARY, foreground=config.COLOR_PRIMARY_TEXT, relief="raised", borderwidth=1)
    style.map("Primary.TButton",
              background=[('active', config.COLOR_PRIMARY_DARK), ('disabled', '#B0BEC5'), ('!disabled', config.COLOR_PRIMARY)],
              foreground=[('disabled', config.COLOR_TEXT_PRIMARY), ('!disabled', config.COLOR_PRIMARY_TEXT)],
              relief=[('pressed', 'sunken'), ('!pressed', 'raised')])

    style.configure("Secondary.TButton", font=config.FONT_BUTTON, padding=button_padding, background=config.COLOR_SECONDARY, foreground=config.COLOR_TEXT_PRIMARY, relief="raised", borderwidth=1)
    style.map("Secondary.TButton",
              background=[('active', config.COLOR_SECONDARY_DARK), ('disabled', '#A5D6A7'), ('!disabled', config.COLOR_SECONDARY)],
              foreground=[('disabled', config.COLOR_TEXT_PRIMARY), ('!disabled', config.COLOR_TEXT_PRIMARY)],
              relief=[('pressed', 'sunken'), ('!pressed', 'raised')])

    # Other widget styles
    style.configure("TRadiobutton", font=config.FONT_BODY, background=config.COLOR_SURFACE, foreground=config.COLOR_TEXT_PRIMARY, indicatorrelief="flat", indicatormargin=config.SPACING_SMALL, padding=(config.SPACING_SMALL, config.SPACING_SMALL))
    style.map("TRadiobutton", background=[('active', config.COLOR_BACKGROUND_LIGHT)], indicatorbackground=[('selected', config.COLOR_PRIMARY), ('!selected', config.COLOR_SURFACE)], indicatorforeground=[('selected', config.COLOR_PRIMARY_TEXT), ('!selected', config.COLOR_TEXT_PRIMARY)])
    style.configure("TScale", troughcolor=config.COLOR_BACKGROUND_LIGHT, background=config.COLOR_SURFACE, sliderrelief="raised", sliderthickness=18, borderwidth=1)
    style.map("TScale", background=[('active', config.COLOR_PRIMARY_LIGHT), ('disabled', config.COLOR_BACKGROUND_LIGHT)], troughcolor=[('disabled', config.COLOR_BACKGROUND_LIGHT)])
    style.configure("TProgressbar", troughcolor=config.COLOR_BACKGROUND_LIGHT, background=config.COLOR_SECONDARY, thickness=config.SPACING_MEDIUM)

    # Overlay styles
    style.configure("Overlay.TFrame", background=config.OVERLAY_FRAME_COLOR, relief="solid", borderwidth=1)
    style.map("Overlay.TFrame", bordercolor=[('active', config.COLOR_PRIMARY_LIGHT)])
    style.configure("Overlay.TLabel", background=config.OVERLAY_FRAME_COLOR, foreground=config.COLOR_TEXT_PRIMARY, font=config.FONT_MESSAGE_OVERLAY)
    return style

# --- UI Element Classes ---
class LoadingOverlay(tk.Toplevel):
    # ... (LoadingOverlay class remains the same as before) ...
    def __init__(self, parent_window, message="Loading..."):
        super().__init__(parent_window)
        self.parent_window_ref = parent_window
        self.animation_job_id = None
        self.title("")
        parent_window.update_idletasks()
        self.geometry(f"{parent_window.winfo_width()}x{parent_window.winfo_height()}+{parent_window.winfo_x()}+{parent_window.winfo_y()}")
        self.configure(bg=config.OVERLAY_BACKGROUND_COLOR)
        self.attributes("-alpha", config.OVERLAY_ALPHA)
        self.transient(parent_window)
        self.overrideredirect(True)
        self.content_frame = ttk.Frame(self, style="Overlay.TFrame")
        self.content_frame.place(relx=0.5, rely=0.5, anchor="center")
        padding_frame = ttk.Frame(self.content_frame, style="Overlay.TFrame", padding=config.SPACING_LARGE)
        padding_frame.pack()
        self.animation_frames_list = config.UNICODE_SPINNER_FRAMES
        self.current_animation_idx = 0
        self.spinner_label = ttk.Label(padding_frame, text=self.animation_frames_list[0], style="Overlay.TLabel", font=config.FONT_SPINNER)
        self.spinner_label.pack(pady=(0, config.SPACING_MEDIUM))
        self.status_message_label = ttk.Label(padding_frame, text=message, style="Overlay.TLabel", font=config.FONT_MESSAGE_OVERLAY)
        self.status_message_label.pack()
        self._start_animation()
        parent_window.bind("<Configure>", self.update_position_and_size, add="+")
        self.update_idletasks()
        self.lift()
        self.grab_set()

    def update_position_and_size(self, event=None):
        if not self.winfo_exists() or not self.parent_window_ref.winfo_exists():
            if self.animation_job_id: self.after_cancel(self.animation_job_id); self.animation_job_id = None
            return
        self.geometry(f"{self.parent_window_ref.winfo_width()}x{self.parent_window_ref.winfo_height()}+{self.parent_window_ref.winfo_x()}+{self.parent_window_ref.winfo_y()}")

    def _start_animation(self):
        if not self.winfo_exists(): return
        self.current_animation_idx = (self.current_animation_idx + 1) % len(self.animation_frames_list)
        self.spinner_label.config(text=self.animation_frames_list[self.current_animation_idx])
        self.animation_job_id = self.after(config.UNICODE_SPINNER_DELAY_MS, self._start_animation)

    def update_message(self, new_message):
        if self.winfo_exists(): self.status_message_label.config(text=new_message)

    def destroy(self):
        if self.animation_job_id: self.after_cancel(self.animation_job_id); self.animation_job_id = None
        if self.parent_window_ref and self.parent_window_ref.winfo_exists():
            try: self.parent_window_ref.unbind("<Configure>")
            except tk.TclError: pass
        if self.winfo_exists(): self.grab_release()
        super().destroy()

class VideoDisplayFrame(ttk.Frame):
    # ... (VideoDisplayFrame class remains the same as before) ...
    def __init__(self, parent, initial_width=640, initial_height=480, **kwargs):
        super().__init__(parent, **kwargs)
        self.display_label = ttk.Label(self, background=config.COLOR_BACKGROUND_LIGHT)
        self.display_label.pack(expand=True, fill="both")
        self.current_photo_image = None
        self.last_displayed_frame_raw = None
        self.target_width = initial_width
        self.target_height = initial_height
        self._update_empty_display()
        self.bind("<Configure>", self._on_resize_display)

    def _on_resize_display(self, event):
        if abs(event.width - self.target_width) > 2 or abs(event.height - self.target_height) > 2:
            if event.width > 10 and event.height > 10:
                self.target_width = event.width; self.target_height = event.height
                if self.last_displayed_frame_raw is not None: self._display_cv2_frame(self.last_displayed_frame_raw)
                else: self._update_empty_display()

    def _update_empty_display(self):
        w = max(1, self.target_width); h = max(1, self.target_height)
        empty_pil_image = Image.new("RGB", (w, h), config.COLOR_TEXT_DISABLED)
        self.current_photo_image = ImageTk.PhotoImage(empty_pil_image)
        self.display_label.config(image=self.current_photo_image)
        self.last_displayed_frame_raw = None

    def _display_cv2_frame(self, cv2_frame_bgr):
        if cv2_frame_bgr is None: self._update_empty_display(); return
        frame_rgb = cv2.cvtColor(cv2_frame_bgr, cv2.COLOR_BGR2RGB)
        pil_image_original = Image.fromarray(frame_rgb)
        original_width, original_height = pil_image_original.size
        if original_width == 0 or original_height == 0: self._update_empty_display(); return
        aspect_ratio = original_width / original_height
        new_width = self.target_width; new_height = int(new_width / aspect_ratio)
        if new_height > self.target_height: new_height = self.target_height; new_width = int(new_height * aspect_ratio)
        new_width = max(1, new_width); new_height = max(1, new_height)
        resized_pil_image = pil_image_original.resize((new_width, new_height), Image.Resampling.LANCZOS)
        self.current_photo_image = ImageTk.PhotoImage(resized_pil_image)
        self.display_label.config(image=self.current_photo_image)

    def update_frame(self, new_cv2_frame_bgr):
        self.last_displayed_frame_raw = new_cv2_frame_bgr.copy() if new_cv2_frame_bgr is not None else None
        self._display_cv2_frame(self.last_displayed_frame_raw)

    def clear(self): self._update_empty_display()

# --- UI Section Creation Functions ---

def _create_file_upload_section(parent):
    frame = ttk.Frame(parent, style="Card.TFrame", padding=config.SPACING_MEDIUM)
    button = ttk.Button(frame, text="Upload File", style="Primary.TButton")
    label = ttk.Label(frame, text="No file selected", style="Card.TLabel", width=40)
    button.pack(side="left", padx=(0, config.SPACING_MEDIUM))
    label.pack(side="left", fill="x", expand=True)
    return {"file_upload_frame": frame, "file_upload_button": button, "file_upload_label": label}

def _create_process_buttons_section(parent):
    frame = ttk.Frame(parent, style="Card.TFrame", padding=config.SPACING_MEDIUM)
    process_btn = ttk.Button(frame, text="Process Real-time", style="Primary.TButton")
    process_btn.state(['disabled'])
    fast_process_btn = ttk.Button(frame, text="Fast Process Video", style="Secondary.TButton")
    fast_process_btn.state(['disabled'])
    process_btn.pack(side="left", padx=(0, config.SPACING_MEDIUM))
    fast_process_btn.pack(side="left")
    return {"process_buttons_frame": frame, "process_button": process_btn, "fast_process_button": fast_process_btn}

def _create_model_selector_section(parent):
    frame = ttk.LabelFrame(parent, text="Model Selection", style="TLabelframe")
    model_var = tk.StringVar()
    # Radiobuttons are added in main_app.py's setup_model_selector
    return {"model_selector_frame": frame, "model_var": model_var, "model_buttons": []}

def _create_threshold_sliders_section(parent):
    frame = ttk.LabelFrame(parent, text="Detection Thresholds", style="TLabelframe")
    components = {"sliders_frame": frame}

    # IoU Slider
    iou_sub_frame = ttk.Frame(frame, style="Card.TFrame") # Use Card.TFrame for consistency if desired, or TFrame
    iou_sub_frame.pack(fill="x", pady=config.SPACING_SMALL, padx=config.SPACING_SMALL)
    iou_sub_frame.columnconfigure(1, weight=1)
    ttk.Label(iou_sub_frame, text="IoU:", style="Card.TLabel").grid(row=0, column=0, sticky="w", padx=(0, config.SPACING_SMALL))
    components["iou_var"] = tk.DoubleVar(value=config.DEFAULT_IOU_THRESHOLD)
    components["iou_slider"] = ttk.Scale(iou_sub_frame, from_=0.01, to=1.0, orient="horizontal", variable=components["iou_var"], state="disabled")
    components["iou_slider"].grid(row=0, column=1, sticky="ew", padx=config.SPACING_SMALL)
    components["iou_value_label"] = ttk.Label(iou_sub_frame, text=f"{config.DEFAULT_IOU_THRESHOLD:.2f}", style="Card.TLabel", width=4, anchor="e")
    components["iou_value_label"].grid(row=0, column=2, sticky="e")

    # Confidence Slider
    conf_sub_frame = ttk.Frame(frame, style="Card.TFrame")
    conf_sub_frame.pack(fill="x", pady=config.SPACING_SMALL, padx=config.SPACING_SMALL)
    conf_sub_frame.columnconfigure(1, weight=1)
    ttk.Label(conf_sub_frame, text="Conf:", style="Card.TLabel").grid(row=0, column=0, sticky="w", padx=(0, config.SPACING_SMALL))
    components["conf_var"] = tk.DoubleVar(value=config.DEFAULT_CONF_THRESHOLD)
    components["conf_slider"] = ttk.Scale(conf_sub_frame, from_=0.01, to=1.0, orient="horizontal", variable=components["conf_var"], state="disabled")
    components["conf_slider"].grid(row=0, column=1, sticky="ew", padx=config.SPACING_SMALL)
    components["conf_value_label"] = ttk.Label(conf_sub_frame, text=f"{config.DEFAULT_CONF_THRESHOLD:.2f}", style="Card.TLabel", width=4, anchor="e")
    components["conf_value_label"].grid(row=0, column=2, sticky="e")
    
    return components

def _create_fast_progress_section(parent):
    frame = ttk.Frame(parent, style="Card.TFrame", padding=config.SPACING_MEDIUM)
    label = ttk.Label(frame, text="Progress: 0% | --:--:-- Time Left", style="Card.TLabel")
    var = tk.IntVar(value=0)
    bar = ttk.Progressbar(frame, orient="horizontal", mode="determinate", variable=var, length=200)
    label.pack(side="left", padx=(0, config.SPACING_MEDIUM))
    bar.pack(side="left", expand=True, fill="x")
    # This frame is initially hidden, its packing is managed in _ui_loading_manager
    return {"fast_progress_frame": frame, "fast_progress_label": label, "fast_progress_var": var, "fast_progress_bar": bar}

def _create_video_player_section(parent):
    container = ttk.Frame(parent, style="Card.TFrame") # Main container for video player and its controls
    
    display = VideoDisplayFrame(container, style="TFrame")
    
    controls_frame = ttk.Frame(container, style="TFrame")
    play_pause_btn = ttk.Button(controls_frame, text="Play", style="Primary.TButton")
    play_pause_btn.state(['disabled'])
    stop_btn = ttk.Button(controls_frame, text="Stop", style="Secondary.TButton")
    stop_btn.state(['disabled'])
    play_pause_btn.pack(side="left", padx=(0, config.SPACING_MEDIUM))
    stop_btn.pack(side="left")

    progress_frame = ttk.Frame(container, style="TFrame")
    progress_var = tk.IntVar(value=0)
    progress_slider = ttk.Scale(progress_frame, from_=0, to=100, orient="horizontal", variable=progress_var, state="disabled")
    time_label = ttk.Label(progress_frame, text="00:00 / 00:00", style="TLabel", width=12, anchor="e")
    progress_slider.pack(side="left", expand=True, fill="x", padx=(0, config.SPACING_MEDIUM))
    time_label.pack(side="left")

    info_frame = ttk.Frame(container, style="TFrame")
    fps_label = ttk.Label(info_frame, text="FPS: --", style="Info.TLabel", width=15, anchor="w")
    current_frame_label = ttk.Label(info_frame, text="Frame: -- / --", style="Info.TLabel", anchor="e")
    fps_label.pack(side="left", padx=(config.SPACING_SMALL, 0))
    current_frame_label.pack(side="right", padx=(0, config.SPACING_SMALL))

    # Layout within the container
    container.columnconfigure(0, weight=1)
    container.rowconfigure(2, weight=1) # Video display should expand
    controls_frame.grid(row=0, column=0, sticky="ew", padx=config.SPACING_SMALL, pady=(config.SPACING_SMALL,0))
    progress_frame.grid(row=1, column=0, sticky="ew", padx=config.SPACING_SMALL, pady=config.SPACING_SMALL)
    display.grid(row=2, column=0, sticky="nsew", padx=config.SPACING_SMALL, pady=(0, config.SPACING_SMALL))
    info_frame.grid(row=3, column=0, sticky="ew", padx=config.SPACING_SMALL, pady=(config.SPACING_SMALL, config.SPACING_SMALL))

    return {
        "video_player_container": container, "video_display": display,
        "video_controls_frame": controls_frame, "play_pause_button": play_pause_btn, "stop_button": stop_btn,
        "progress_frame": progress_frame, "progress_slider": progress_slider, "progress_var": progress_var, "time_label": time_label,
        "fps_label": fps_label, "current_frame_label": current_frame_label
    }

# --- Main UI Creation Function ---
def create_ui_components(root_window, parent_left_panel, parent_right_panel):
    """Create all UI components for the application by calling section-specific helpers."""
    setup_material_theme() 
    
    ui_components_dict = {}

    ui_components_dict.update(_create_file_upload_section(parent_left_panel))
    ui_components_dict.update(_create_process_buttons_section(parent_left_panel))
    ui_components_dict.update(_create_model_selector_section(parent_left_panel))
    ui_components_dict.update(_create_threshold_sliders_section(parent_left_panel))
    ui_components_dict.update(_create_fast_progress_section(parent_left_panel)) # Created but not packed here
    
    ui_components_dict.update(_create_video_player_section(parent_right_panel))
    
    return ui_components_dict
