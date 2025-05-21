# app/ui_custom_widgets.py
"""
Contains custom Tkinter widget classes for the application.
"""
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import cv2 
import math 
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

        self.spinner_canvas_size = (config.COE_SPINNER_RADIUS + 15) * 2 
        self.spinner_canvas = tk.Canvas(
            padding_frame,
            width=self.spinner_canvas_size,
            height=self.spinner_canvas_size,
            bg=config.OVERLAY_FRAME_COLOR, 
            highlightthickness=0
        )
        self.spinner_canvas.pack(pady=(0, config.SPACING_MEDIUM))
        
        self.status_message_label = ttk.Label(
            padding_frame,
            text=message,
            style="Overlay.TLabel", 
            font=config.FONT_MESSAGE_OVERLAY
        )
        self.status_message_label.pack()

        self.coe_spinner_angle = 0 # Initial overall rotation angle
        self.coe_spinner_text_items = []
        self._setup_coe_spinner_text()
        
        self._animate_coe_spinner()

        parent_window.bind("<Configure>", self.update_position_and_size, add="+")
        
        self.update_idletasks()
        self.lift()
        self.grab_set()

    def _setup_coe_spinner_text(self):
        """Create initial text items for the CoE spinner."""
        center_x = self.spinner_canvas_size / 2
        center_y = self.spinner_canvas_size / 2
        
        for i, char in enumerate(config.COE_SPINNER_TEXT):
            item = self.spinner_canvas.create_text(
                center_x, center_y, # Placeholder, will be updated by _animate_coe_spinner
                text=char,
                font=config.FONT_COE_SPINNER,
                fill="black" 
            )
            self.coe_spinner_text_items.append(item)

    def _animate_coe_spinner(self):
        if not self.winfo_exists(): return

        center_x = self.spinner_canvas_size / 2
        center_y = self.spinner_canvas_size / 2
        radius = config.COE_SPINNER_RADIUS
        num_chars = len(config.COE_SPINNER_TEXT)

        for i, item_id in enumerate(self.coe_spinner_text_items):
            # Angle for each character, distributed around the circle
            char_angle_offset_deg = (360 / num_chars) * i
            
            # Effective angle for this character: initial offset + overall rotation
            # To make 'C' (index 0) start at the top (270 deg or -90 deg), we adjust the angle.
            # Standard math angles: 0=right, 90=up. Tkinter canvas: 0=right, Y grows downwards.
            # So, for top, we need an angle of -90 degrees (or 270).
            effective_angle_deg = self.coe_spinner_angle + char_angle_offset_deg - 90
            
            effective_angle_rad = math.radians(effective_angle_deg)
            
            x = center_x + radius * math.cos(effective_angle_rad)
            y = center_y + radius * math.sin(effective_angle_rad) # sin handles Y correctly for math angles
            
            self.spinner_canvas.coords(item_id, x, y)

        self.coe_spinner_angle = (self.coe_spinner_angle + config.COE_SPINNER_ROTATION_STEP) % 360
        
        self.animation_job_id = self.after(config.COE_SPINNER_DELAY_MS, self._animate_coe_spinner)


    def update_position_and_size(self, event=None):
        if not self.winfo_exists() or not self.parent_window_ref.winfo_exists():
            if self.animation_job_id: self.after_cancel(self.animation_job_id); self.animation_job_id = None
            return
        self.geometry(f"{self.parent_window_ref.winfo_width()}x{self.parent_window_ref.winfo_height()}+{self.parent_window_ref.winfo_x()}+{self.parent_window_ref.winfo_y()}")

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
