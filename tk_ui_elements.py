"""
Tkinter UI Elements for the Vehicle Detection and Tracking Application
This module defines all the UI components used in the application.
"""

import tkinter as tk
from tkinter import ttk, filedialog
from PIL import Image, ImageTk
import cv2
import numpy as np 
import os 
from . import config

def setup_material_theme(style_instance=None):
    """Set up a Material Design theme for ttk widgets"""
    style = style_instance if style_instance else ttk.Style()
    
    style.configure(".", 
                    font=config.FONT_BODY,
                    background=config.COLOR_BACKGROUND) 
    
    style.configure("TFrame", 
                    background=config.COLOR_BACKGROUND) 
    
    style.configure("Card.TFrame",
                    background=config.COLOR_SURFACE, 
                    relief="solid", 
                    borderwidth=1) 
    style.map("Card.TFrame",
              bordercolor=[('active', config.COLOR_PRIMARY_LIGHT), ('!active', config.COLOR_BACKGROUND_LIGHT)])

    style.configure("TLabel", 
                    font=config.FONT_BODY,
                    background=config.COLOR_BACKGROUND, 
                    foreground=config.COLOR_TEXT_PRIMARY)
    
    style.configure("Card.TLabel", 
                    font=config.FONT_BODY,
                    background=config.COLOR_SURFACE,
                    foreground=config.COLOR_TEXT_PRIMARY)

    style.configure("Title.TLabel",
                    font=config.FONT_TITLE,
                    background=config.COLOR_SURFACE, 
                    foreground=config.COLOR_TEXT_PRIMARY)
                    
    style.configure("Subtitle.TLabel",
                    font=config.FONT_SUBTITLE,
                    background=config.COLOR_SURFACE, 
                    foreground=config.COLOR_TEXT_SECONDARY)
    
    style.configure("Caption.TLabel",
                    font=config.FONT_CAPTION,
                    foreground=config.COLOR_TEXT_SECONDARY) 
    
    style.configure("Info.TLabel", # New style for FPS/Frame count, inherits TFrame background
                    font=config.FONT_CAPTION,
                    background=config.COLOR_BACKGROUND, # Match parent TFrame background
                    foreground=config.COLOR_TEXT_SECONDARY)

    style.configure("TLabelframe", 
                    background=config.COLOR_SURFACE, 
                    relief="solid",
                    borderwidth=1,
                    padding=config.SPACING_MEDIUM)
    style.map("TLabelframe",
              bordercolor=[('active', config.COLOR_PRIMARY_LIGHT), ('!active', config.COLOR_BACKGROUND_LIGHT)])

    style.configure("TLabelframe.Label", 
                    font=config.FONT_SUBTITLE,
                    background=config.COLOR_SURFACE,
                    foreground=config.COLOR_TEXT_PRIMARY,
                    padding=(0,0,0,config.SPACING_SMALL)) 
    
    style.configure("TButton", 
                    font=config.FONT_BUTTON,
                    padding=(config.SPACING_MEDIUM, config.SPACING_SMALL),
                    relief="raised",
                    borderwidth=1,
                    focusthickness=1) 
    style.map("TButton",
              background=[('active', config.COLOR_BACKGROUND_LIGHT), 
                          ('!disabled', config.COLOR_SURFACE)],
              foreground=[('!disabled', config.COLOR_TEXT_PRIMARY)],
              relief=[('pressed', 'sunken'), ('!pressed', 'raised')])

    style.configure("Primary.TButton",
                    background=config.COLOR_PRIMARY,
                    foreground=config.COLOR_PRIMARY_TEXT)
    style.map("Primary.TButton",
              background=[('active', config.COLOR_PRIMARY_DARK), 
                          ('!disabled', config.COLOR_PRIMARY)],
              relief=[('pressed', 'sunken'), ('!pressed', 'raised')])
    
    style.configure("Secondary.TButton",
                    background=config.COLOR_SECONDARY,
                    foreground=config.COLOR_SECONDARY_TEXT)
    style.map("Secondary.TButton",
              background=[('active', config.COLOR_SECONDARY_DARK),
                          ('!disabled', config.COLOR_SECONDARY)],
              relief=[('pressed', 'sunken'), ('!pressed', 'raised')])
        
    style.configure("TRadiobutton",
                    font=config.FONT_BODY,
                    background=config.COLOR_SURFACE, 
                    foreground=config.COLOR_TEXT_PRIMARY,
                    indicatorrelief="flat",
                    indicatormargin=config.SPACING_SMALL,
                    padding=(config.SPACING_SMALL, config.SPACING_SMALL))
    style.map("TRadiobutton",
              background=[('active', config.COLOR_BACKGROUND_LIGHT)],
              indicatorbackground=[('selected', config.COLOR_PRIMARY), ('!selected', config.COLOR_SURFACE)],
              indicatorforeground=[('selected', config.COLOR_PRIMARY_TEXT), ('!selected', config.COLOR_TEXT_PRIMARY)])

    style.configure("TScale",
                    troughcolor=config.COLOR_BACKGROUND_LIGHT,
                    background=config.COLOR_SURFACE, 
                    sliderrelief="raised",
                    sliderthickness=18, 
                    borderwidth=1)
    style.map("TScale",
              background=[('active', config.COLOR_PRIMARY_LIGHT), ('disabled', config.COLOR_BACKGROUND_LIGHT)],
              troughcolor=[('disabled', config.COLOR_BACKGROUND_LIGHT)])
    
    style.configure("TProgressbar",
                    troughcolor=config.COLOR_BACKGROUND_LIGHT,
                    background=config.COLOR_SECONDARY, 
                    thickness=config.SPACING_MEDIUM) 
    
    style.configure("Overlay.TFrame", 
                    background=config.OVERLAY_FRAME_COLOR, 
                    relief="solid", borderwidth=1)
    style.map("Overlay.TFrame", bordercolor=[('active', config.COLOR_PRIMARY_LIGHT)])

    style.configure("Overlay.TLabel", 
                    background=config.OVERLAY_FRAME_COLOR, 
                    foreground=config.COLOR_TEXT_PRIMARY,
                    font=config.FONT_MESSAGE_OVERLAY) 
    
    return style

class LoadingOverlay(tk.Toplevel):
    """Loading overlay that blocks interaction with the main window"""
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
        
        self.spinner_label = ttk.Label(
            padding_frame, 
            text=self.animation_frames_list[0], 
            style="Overlay.TLabel", 
            font=config.FONT_SPINNER 
        )
        self.spinner_label.pack(pady=(0, config.SPACING_MEDIUM))
        
        self.status_message_label = ttk.Label(
            padding_frame, 
            text=message, 
            style="Overlay.TLabel", 
            font=config.FONT_MESSAGE_OVERLAY
        )
        self.status_message_label.pack()
        
        self._start_animation()
        
        parent_window.bind("<Configure>", self.update_position_and_size, add="+")
        
        self.update_idletasks() 
        self.lift() 
        self.grab_set() 

    def update_position_and_size(self, event=None):
        if not self.winfo_exists() or not self.parent_window_ref.winfo_exists():
            if self.animation_job_id: 
                self.after_cancel(self.animation_job_id)
                self.animation_job_id = None
            return
        
        new_width = self.parent_window_ref.winfo_width()
        new_height = self.parent_window_ref.winfo_height()
        new_x = self.parent_window_ref.winfo_x()
        new_y = self.parent_window_ref.winfo_y()
        self.geometry(f"{new_width}x{new_height}+{new_x}+{new_y}")
    
    def _start_animation(self):
        if not self.winfo_exists(): return 
        self.current_animation_idx = (self.current_animation_idx + 1) % len(self.animation_frames_list)
        self.spinner_label.config(text=self.animation_frames_list[self.current_animation_idx])
        self.animation_job_id = self.after(config.UNICODE_SPINNER_DELAY_MS, self._start_animation)
    
    def update_message(self, new_message):
        if self.winfo_exists():
            self.status_message_label.config(text=new_message)
    
    def destroy(self):
        if self.animation_job_id:
            self.after_cancel(self.animation_job_id)
            self.animation_job_id = None
        
        if self.parent_window_ref and self.parent_window_ref.winfo_exists():
            try:
                self.parent_window_ref.unbind("<Configure>") 
            except tk.TclError: 
                pass 
        
        if self.winfo_exists(): 
            self.grab_release() 
        super().destroy()

class VideoDisplayFrame(ttk.Frame):
    """Frame for displaying video frames, adapting to available space."""
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
                self.target_width = event.width
                self.target_height = event.height
                
                if self.last_displayed_frame_raw is not None:
                    self._display_cv2_frame(self.last_displayed_frame_raw) 
                else:
                    self._update_empty_display() 

    def _update_empty_display(self):
        w = max(1, self.target_width)
        h = max(1, self.target_height)
        empty_pil_image = Image.new("RGB", (w, h), config.COLOR_TEXT_DISABLED) 
        self.current_photo_image = ImageTk.PhotoImage(empty_pil_image)
        self.display_label.config(image=self.current_photo_image)
        self.last_displayed_frame_raw = None

    def _display_cv2_frame(self, cv2_frame_bgr):
        if cv2_frame_bgr is None:
            self._update_empty_display()
            return

        frame_rgb = cv2.cvtColor(cv2_frame_bgr, cv2.COLOR_BGR2RGB)
        pil_image_original = Image.fromarray(frame_rgb)
        
        original_width, original_height = pil_image_original.size
        if original_width == 0 or original_height == 0: 
            self._update_empty_display()
            return

        aspect_ratio = original_width / original_height
        
        new_width = self.target_width
        new_height = int(new_width / aspect_ratio)
        
        if new_height > self.target_height:
            new_height = self.target_height
            new_width = int(new_height * aspect_ratio)
        
        new_width = max(1, new_width)
        new_height = max(1, new_height)

        resized_pil_image = pil_image_original.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
        self.current_photo_image = ImageTk.PhotoImage(resized_pil_image)
        self.display_label.config(image=self.current_photo_image)

    def update_frame(self, new_cv2_frame_bgr):
        self.last_displayed_frame_raw = new_cv2_frame_bgr.copy() if new_cv2_frame_bgr is not None else None
        self._display_cv2_frame(self.last_displayed_frame_raw)
    
    def clear(self):
        self._update_empty_display()


def create_ui_components(root_window, parent_left_panel, parent_right_panel):
    """Create all UI components for the application, parenting them correctly. """
    style = setup_material_theme() 
    
    file_upload_frame = ttk.Frame(parent_left_panel, style="Card.TFrame", padding=config.SPACING_MEDIUM)
    file_upload_button = ttk.Button(file_upload_frame, text="Upload File", style="Primary.TButton")
    file_upload_label = ttk.Label(file_upload_frame, text="No file selected", style="Card.TLabel", width=40)
    file_upload_button.pack(side="left", padx=(0, config.SPACING_MEDIUM))
    file_upload_label.pack(side="left", fill="x", expand=True)
    
    process_buttons_frame = ttk.Frame(parent_left_panel, style="Card.TFrame", padding=config.SPACING_MEDIUM)
    process_button = ttk.Button(process_buttons_frame, text="Process Real-time", style="Primary.TButton", state="disabled")
    fast_process_button = ttk.Button(process_buttons_frame, text="Fast Process Video", style="Secondary.TButton", state="disabled")
    process_button.pack(side="left", padx=(0, config.SPACING_MEDIUM))
    fast_process_button.pack(side="left")
    
    model_selector_frame = ttk.LabelFrame(parent_left_panel, text="Model Selection", style="TLabelframe")
    model_var = tk.StringVar()
    model_buttons_list = [] 
    
    sliders_frame = ttk.LabelFrame(parent_left_panel, text="Detection Thresholds", style="TLabelframe")
    
    iou_sub_frame = ttk.Frame(sliders_frame) 
    iou_sub_frame.pack(fill="x", pady=config.SPACING_SMALL, padx=config.SPACING_SMALL)
    iou_sub_frame.columnconfigure(0, weight=0)  
    iou_sub_frame.columnconfigure(1, weight=1)  
    iou_sub_frame.columnconfigure(2, weight=0)  

    iou_label_text = ttk.Label(iou_sub_frame, text="IoU:", style="Card.TLabel") 
    iou_var = tk.DoubleVar(value=config.DEFAULT_IOU_THRESHOLD)
    iou_slider_widget = ttk.Scale(iou_sub_frame, from_=0.01, to=1.0, orient="horizontal", variable=iou_var, state="disabled")
    iou_value_display_label = ttk.Label(iou_sub_frame, text=f"{config.DEFAULT_IOU_THRESHOLD:.2f}", style="Card.TLabel", width=4, anchor="e")
    
    iou_label_text.grid(row=0, column=0, sticky="w", padx=(0, config.SPACING_SMALL))
    iou_slider_widget.grid(row=0, column=1, sticky="ew", padx=config.SPACING_SMALL)
    iou_value_display_label.grid(row=0, column=2, sticky="e")

    conf_sub_frame = ttk.Frame(sliders_frame) 
    conf_sub_frame.pack(fill="x", pady=config.SPACING_SMALL, padx=config.SPACING_SMALL)
    conf_sub_frame.columnconfigure(0, weight=0)  
    conf_sub_frame.columnconfigure(1, weight=1)  
    conf_sub_frame.columnconfigure(2, weight=0)  

    conf_label_text = ttk.Label(conf_sub_frame, text="Conf:", style="Card.TLabel")
    conf_var = tk.DoubleVar(value=config.DEFAULT_CONF_THRESHOLD)
    conf_slider_widget = ttk.Scale(conf_sub_frame, from_=0.01, to=1.0, orient="horizontal", variable=conf_var, state="disabled")
    conf_value_display_label = ttk.Label(conf_sub_frame, text=f"{config.DEFAULT_CONF_THRESHOLD:.2f}", style="Card.TLabel", width=4, anchor="e")

    conf_label_text.grid(row=0, column=0, sticky="w", padx=(0, config.SPACING_SMALL))
    conf_slider_widget.grid(row=0, column=1, sticky="ew", padx=config.SPACING_SMALL)
    conf_value_display_label.grid(row=0, column=2, sticky="e")

    fast_progress_frame = ttk.Frame(parent_left_panel, style="Card.TFrame", padding=config.SPACING_MEDIUM)
    fast_progress_label_text = ttk.Label(fast_progress_frame, text="Fast Processing:", style="Card.TLabel")
    fast_progress_var = tk.IntVar(value=0)
    fast_progress_bar_widget = ttk.Progressbar(fast_progress_frame, orient="horizontal", mode="determinate", variable=fast_progress_var, length=200)
    fast_progress_label_text.pack(side="left", padx=(0, config.SPACING_MEDIUM))
    fast_progress_bar_widget.pack(side="left", expand=True, fill="x")

    video_player_container_frame = ttk.Frame(parent_right_panel, style="Card.TFrame") 
    
    video_display_widget = VideoDisplayFrame(video_player_container_frame, style="TFrame")
    
    video_controls_subframe = ttk.Frame(video_player_container_frame, style="TFrame") 
    play_pause_button_widget = ttk.Button(video_controls_subframe, text="Play", style="Primary.TButton", state="disabled")
    stop_button_widget = ttk.Button(video_controls_subframe, text="Stop", style="Secondary.TButton", state="disabled")
    play_pause_button_widget.pack(side="left", padx=(0, config.SPACING_MEDIUM))
    stop_button_widget.pack(side="left")
    
    progress_subframe = ttk.Frame(video_player_container_frame, style="TFrame") 
    progress_var = tk.IntVar(value=0) 
    progress_slider_widget = ttk.Scale(
        progress_subframe, from_=0, to=100, orient="horizontal", variable=progress_var, state="disabled"
    )
    time_display_label = ttk.Label(progress_subframe, text="00:00 / 00:00", style="TLabel", width=12, anchor="e") 
    
    progress_slider_widget.pack(side="left", expand=True, fill="x", padx=(0, config.SPACING_MEDIUM))
    time_display_label.pack(side="left")

    # New frame for FPS and Current Frame labels, parented to video_player_container_frame
    video_info_subframe = ttk.Frame(video_player_container_frame, style="TFrame")
    fps_label_widget = ttk.Label(video_info_subframe, text="FPS: --", style="Info.TLabel", width=15, anchor="w")
    current_frame_label_widget = ttk.Label(video_info_subframe, text="Frame: -- / --", style="Info.TLabel", anchor="e")

    fps_label_widget.pack(side="left", padx=(config.SPACING_SMALL, 0))
    current_frame_label_widget.pack(side="right", padx=(0, config.SPACING_SMALL))


    video_player_container_frame.columnconfigure(0, weight=1)
    video_player_container_frame.rowconfigure(0, weight=0) 
    video_player_container_frame.rowconfigure(1, weight=0) 
    video_player_container_frame.rowconfigure(2, weight=1) 
    video_player_container_frame.rowconfigure(3, weight=0) # New row for video info labels

    video_controls_subframe.grid(row=0, column=0, sticky="ew", padx=config.SPACING_SMALL, pady=(config.SPACING_SMALL,0))
    progress_subframe.grid(row=1, column=0, sticky="ew", padx=config.SPACING_SMALL, pady=config.SPACING_SMALL)
    video_display_widget.grid(row=2, column=0, sticky="nsew", padx=config.SPACING_SMALL, pady=(0, config.SPACING_SMALL))
    video_info_subframe.grid(row=3, column=0, sticky="ew", padx=config.SPACING_SMALL, pady=(config.SPACING_SMALL, config.SPACING_SMALL))
    
    return {
        "file_upload_frame": file_upload_frame,
        "file_upload_button": file_upload_button,
        "file_upload_label": file_upload_label,
        "process_buttons_frame": process_buttons_frame,
        "process_button": process_button,
        "fast_process_button": fast_process_button,
        "model_selector_frame": model_selector_frame,
        "model_var": model_var,
        "model_buttons": model_buttons_list,
        "sliders_frame": sliders_frame,
        "iou_slider": iou_slider_widget,
        "iou_var": iou_var,
        "iou_value_label": iou_value_display_label,
        "conf_slider": conf_slider_widget,
        "conf_var": conf_var,
        "conf_value_label": conf_value_display_label,
        "fast_progress_frame": fast_progress_frame,
        "fast_progress_bar": fast_progress_bar_widget,
        "fast_progress_var": fast_progress_var,
        "video_player_container": video_player_container_frame,
        "video_display": video_display_widget,
        "video_controls_frame": video_controls_subframe, 
        "play_pause_button": play_pause_button_widget,
        "stop_button": stop_button_widget,
        "progress_frame": progress_subframe, 
        "progress_slider": progress_slider_widget,
        "progress_var": progress_var,
        "time_label": time_display_label,
        "fps_label": fps_label_widget, # Added
        "current_frame_label": current_frame_label_widget # Added
    }
