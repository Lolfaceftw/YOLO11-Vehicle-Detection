# app/ui_layout_sections.py
"""
Contains functions for creating logical sections of the UI.
"""
import tkinter as tk
from tkinter import ttk
from . import config
from .ui_custom_widgets import VideoDisplayFrame # Import custom widget

def create_file_upload_section(parent):
    frame = ttk.Frame(parent, style="Card.TFrame", padding=config.SPACING_MEDIUM)
    button = ttk.Button(frame, text="Upload File", style="Primary.TButton")
    label = ttk.Label(frame, text="No file selected", style="Card.TLabel", width=40)
    button.pack(side="left", padx=(0, config.SPACING_MEDIUM))
    label.pack(side="left", fill="x", expand=True)
    return {"file_upload_frame": frame, "file_upload_button": button, "file_upload_label": label}

def create_process_buttons_section(parent):
    frame = ttk.Frame(parent, style="Card.TFrame", padding=config.SPACING_MEDIUM)
    process_btn = ttk.Button(frame, text="Process Real-time", style="Primary.TButton")
    process_btn.state(['disabled'])
    fast_process_btn = ttk.Button(frame, text="Fast Process Video", style="Secondary.TButton")
    fast_process_btn.state(['disabled'])
    process_btn.pack(side="left", padx=(0, config.SPACING_MEDIUM))
    fast_process_btn.pack(side="left")
    return {"process_buttons_frame": frame, "process_button": process_btn, "fast_process_button": fast_process_btn}

def create_model_selector_section(parent):
    frame = ttk.LabelFrame(parent, text="Model Selection", style="TLabelframe")
    model_var = tk.StringVar()
    
    # Custom model selection components
    custom_model_frame = ttk.Frame(frame, style="Card.TFrame", padding=config.SPACING_SMALL)
    custom_model_button = ttk.Button(custom_model_frame, text="Browse .pt File", style="Secondary.TButton")
    custom_model_button.state(['disabled'])  # Initially disabled
    custom_model_label = ttk.Label(custom_model_frame, text="No custom model selected", style="Card.TLabel", width=35)
    
    custom_model_button.pack(side="left", padx=(0, config.SPACING_MEDIUM))
    custom_model_label.pack(side="left", fill="x", expand=True)
    
    return {
        "model_selector_frame": frame, 
        "model_var": model_var, 
        "model_buttons": [],  # Radiobuttons added later
        "custom_model_frame": custom_model_frame,
        "custom_model_button": custom_model_button,
        "custom_model_label": custom_model_label
    }

def create_threshold_sliders_section(parent):
    frame = ttk.LabelFrame(parent, text="Detection Thresholds", style="TLabelframe")
    components = {"sliders_frame": frame}

    iou_sub_frame = ttk.Frame(frame, style="Card.TFrame") 
    iou_sub_frame.pack(fill="x", pady=config.SPACING_SMALL, padx=config.SPACING_SMALL)
    iou_sub_frame.columnconfigure(1, weight=1)
    ttk.Label(iou_sub_frame, text="IoU:", style="Card.TLabel").grid(row=0, column=0, sticky="w", padx=(0, config.SPACING_SMALL))
    components["iou_var"] = tk.DoubleVar(value=config.DEFAULT_IOU_THRESHOLD)
    components["iou_slider"] = ttk.Scale(iou_sub_frame, from_=0.01, to=1.0, orient="horizontal", variable=components["iou_var"], state="disabled")
    components["iou_slider"].grid(row=0, column=1, sticky="ew", padx=config.SPACING_SMALL)
    components["iou_value_label"] = ttk.Label(iou_sub_frame, text=f"{config.DEFAULT_IOU_THRESHOLD:.2f}", style="Card.TLabel", width=4, anchor="e")
    components["iou_value_label"].grid(row=0, column=2, sticky="e")

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

def create_fast_progress_section(parent):
    frame = ttk.Frame(parent, style="Card.TFrame", padding=config.SPACING_MEDIUM)
    label = ttk.Label(frame, text="Progress: 0% | --:--:-- Time Left", style="Card.TLabel")
    var = tk.IntVar(value=0)
    bar = ttk.Progressbar(frame, orient="horizontal", mode="determinate", variable=var, length=200)
    label.pack(side="left", padx=(0, config.SPACING_MEDIUM))
    bar.pack(side="left", expand=True, fill="x")
    return {"fast_progress_frame": frame, "fast_progress_label": label, "fast_progress_var": var, "fast_progress_bar": bar}

def create_video_player_section(parent):
    container = ttk.Frame(parent, style="Card.TFrame")
    
    display = VideoDisplayFrame(container, style="TFrame") # Using the custom widget
    
    controls_frame = ttk.Frame(container, style="TFrame")
    play_pause_btn = ttk.Button(controls_frame, text="Play", style="Primary.TButton")
    play_pause_btn.state(['disabled'])
    stop_btn = ttk.Button(controls_frame, text="Stop", style="Secondary.TButton")
    stop_btn.state(['disabled'])
    play_pause_btn.pack(side="left", padx=(0, config.SPACING_MEDIUM))
    stop_btn.pack(side="left")

    progress_frame = ttk.Frame(container, style="TFrame")
    progress_var = tk.IntVar(value=0)
    progress_slider = ttk.Scale(progress_frame, from_=0, to=1000, orient="horizontal", variable=progress_var, state="disabled")
    time_label = ttk.Label(progress_frame, text="00:00 / 00:00", style="TLabel", width=12, anchor="e")
    progress_slider.pack(side="left", expand=True, fill="x", padx=(0, config.SPACING_MEDIUM))
    time_label.pack(side="left")

    info_frame = ttk.Frame(container, style="TFrame")
    fps_label = ttk.Label(info_frame, text="FPS: --", style="Info.TLabel", width=15, anchor="w")
    current_frame_label = ttk.Label(info_frame, text="Frame: -- / --", style="Info.TLabel", anchor="e")
    fps_label.pack(side="left", padx=(config.SPACING_SMALL, 0))
    current_frame_label.pack(side="right", padx=(0, config.SPACING_SMALL))

    container.columnconfigure(0, weight=1)
    container.rowconfigure(2, weight=1) 
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
