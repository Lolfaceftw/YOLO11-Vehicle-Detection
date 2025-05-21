# app/ui_custom_widgets.py
"""
Contains custom Tkinter widget classes for the application.
"""
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import cv2 # Keep cv2 import if VideoDisplayFrame uses it directly, otherwise remove
# import numpy as np # Not directly used here, but VideoDisplayFrame might imply its use via cv2
from . import config

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
    """Frame for displaying video frames, adapting to available space."""
    def __init__(self, parent, initial_width=640, initial_height=480, **kwargs):
        super().__init__(parent, **kwargs)
        self.display_label = ttk.Label(self, background=config.COLOR_BACKGROUND_LIGHT)
        self.display_label.pack(expand=True, fill="both")
        self.current_photo_image = None
        self.last_displayed_frame_raw = None # Stores the raw cv2 frame
        self.target_width = initial_width
        self.target_height = initial_height
        self._update_empty_display()
        self.bind("<Configure>", self._on_resize_display)

    def _on_resize_display(self, event):
        if abs(event.width - self.target_width) > 2 or abs(event.height - self.target_height) > 2:
            if event.width > 10 and event.height > 10: # Avoid resizing to tiny dimensions
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
        
        new_width = max(1, new_width) # Ensure dimensions are at least 1
        new_height = max(1, new_height)

        resized_pil_image = pil_image_original.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
        self.current_photo_image = ImageTk.PhotoImage(resized_pil_image)
        self.display_label.config(image=self.current_photo_image)

    def update_frame(self, new_cv2_frame_bgr):
        # Store a copy of the raw frame for resizing later if needed
        self.last_displayed_frame_raw = new_cv2_frame_bgr.copy() if new_cv2_frame_bgr is not None else None
        self._display_cv2_frame(self.last_displayed_frame_raw)
    
    def clear(self):
        self._update_empty_display()
