# app/ui_custom_widgets.py
"""
Contains custom Tkinter widget classes for the application.
"""
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import cv2 
import math 
import time 
from . import config
from .logger_setup import log_debug 

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

        self.coe_spinner_angle = 0 
        self.coe_spinner_text_items = []
        self._setup_coe_spinner_text()
        
        self._animate_coe_spinner()

        parent_window.bind("<Configure>", self.update_position_and_size, add="+")
        
        self.update_idletasks()
        self.lift()
        self.grab_set()

    def _setup_coe_spinner_text(self):
        center_x = self.spinner_canvas_size / 2
        center_y = self.spinner_canvas_size / 2
        
        for i, char in enumerate(config.COE_SPINNER_TEXT):
            item = self.spinner_canvas.create_text(
                center_x, center_y, 
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
            char_angle_offset_deg = (360 / num_chars) * i
            effective_angle_deg = self.coe_spinner_angle + char_angle_offset_deg - 90
            effective_angle_rad = math.radians(effective_angle_deg)
            
            x = center_x + radius * math.cos(effective_angle_rad)
            y = center_y + radius * math.sin(effective_angle_rad) 
            
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
    def __init__(self, parent, initial_width=640, initial_height=480, **kwargs):
        super().__init__(parent, **kwargs)
        self.widget_name = self.winfo_name() 
        log_debug(f"VideoDisplayFrame ({self.widget_name}) __init__: Parent is {parent.winfo_name() if parent else 'None'}. Initial target WxH: {initial_width}x{initial_height}")
        self.display_label = ttk.Label(self, background=config.COLOR_BACKGROUND_LIGHT)
        self.display_label.pack(expand=True, fill="both") 
        self.current_photo_image = None
        self.last_displayed_frame_raw = None 
        self.target_width = initial_width
        self.target_height = initial_height
        self._initial_configure_done = False 
        self._update_empty_display(log_reason="init") 
        log_debug(f"VideoDisplayFrame ({self.widget_name}) initialized. Current target WxH: {self.target_width}x{self.target_height}. <Configure> NOT bound initially.")

    def _on_resize_display(self, event):
        widget_name = self.winfo_name()
        if not self.winfo_exists(): 
            log_debug(f"VideoDisplayFrame ({widget_name})._on_resize_display: Widget destroyed. Skipping.")
            return 
        if not self._initial_configure_done:
            log_debug(f"VideoDisplayFrame ({widget_name})._on_resize_display: _initial_configure_done is False. Skipping event.")
            return
            
        log_debug(f"VideoDisplayFrame ({widget_name})._on_resize_display: Event WxH: {event.width}x{event.height}, Current Target WxH: {self.target_width}x{self.target_height}, Actual WxH: {self.winfo_width()}x{self.winfo_height()}")
        
        # Only update if there's a significant change
        if event.width > 1 and event.height > 1 and \
           (abs(event.width - self.target_width) > 1 or abs(event.height - self.target_height) > 1):
            self.target_width = event.width
            self.target_height = event.height
            log_debug(f"VideoDisplayFrame ({widget_name})._on_resize_display: Target updated to {self.target_width}x{self.target_height}. Refreshing display.")
            if self.last_displayed_frame_raw is not None:
                self._display_cv2_frame(self.last_displayed_frame_raw)
            else:
                self._update_empty_display(log_reason="_on_resize_display (no raw frame)")
        else:
            log_debug(f"VideoDisplayFrame ({widget_name})._on_resize_display: Event dims {event.width}x{event.height} not different enough from target or invalid. No change. Target: {self.target_width}x{self.target_height}")


    def _update_empty_display(self, log_reason=""):
        widget_name = self.winfo_name()
        if not self.winfo_exists(): return
        
        # Use self.target_width and self.target_height for the empty image
        w = max(1, int(self.target_width))
        h = max(1, int(self.target_height))
        log_debug(f"VideoDisplayFrame ({widget_name})._update_empty_display (Reason: {log_reason}): Creating empty PIL Image {w}x{h}")
        try:
            empty_pil_image = Image.new("RGB", (w, h), config.COLOR_TEXT_DISABLED)
            self.current_photo_image = ImageTk.PhotoImage(empty_pil_image)
            self.display_label.config(image=self.current_photo_image)
            log_debug(f"VideoDisplayFrame ({widget_name})._update_empty_display: Empty image set on label.")
        except Exception as e:
            log_debug(f"VideoDisplayFrame ({widget_name})._update_empty_display: Error creating empty image for {w}x{h}: {e}", exc_info=True)


    def _display_cv2_frame(self, cv2_frame_bgr):
        widget_name = self.winfo_name()
        if not self.winfo_exists(): return
        
        current_target_w = max(1, int(self.target_width))
        current_target_h = max(1, int(self.target_height))
        log_debug(f"VideoDisplayFrame ({widget_name})._display_cv2_frame: Frame is None: {cv2_frame_bgr is None}. Using Target WxH: {current_target_w}x{current_target_h}")

        if cv2_frame_bgr is None:
            self._update_empty_display(log_reason="_display_cv2_frame (input None)")
            return

        try:
            t_start_display = time.perf_counter()
            frame_rgb = cv2.cvtColor(cv2_frame_bgr, cv2.COLOR_BGR2RGB)
            pil_image_original = Image.fromarray(frame_rgb)
            
            original_width, original_height = pil_image_original.size
            if original_width == 0 or original_height == 0: 
                log_debug(f"VideoDisplayFrame ({widget_name})._display_cv2_frame: Original frame dims zero.")
                self._update_empty_display(log_reason="_display_cv2_frame (original dims zero)")
                return

            aspect_ratio = original_width / original_height
            
            new_width = current_target_w
            new_height = int(new_width / aspect_ratio)
            
            if new_height > current_target_h:
                new_height = current_target_h
                new_width = int(new_height * aspect_ratio)
            
            new_width = max(1, int(new_width)) 
            new_height = max(1, int(new_height)) 

            log_debug(f"VideoDisplayFrame ({widget_name})._display_cv2_frame: Resizing to {new_width}x{new_height} from {original_width}x{original_height}")
            resized_pil_image = pil_image_original.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
            self.current_photo_image = ImageTk.PhotoImage(resized_pil_image)
            self.display_label.config(image=self.current_photo_image)
            t_end_display = time.perf_counter()
            log_debug(f"VideoDisplayFrame ({widget_name})._display_cv2_frame completed in {(t_end_display - t_start_display)*1000:.2f} ms.")

        except Exception as e:
            log_debug(f"VideoDisplayFrame ({widget_name})._display_cv2_frame: Error processing/displaying frame: {e}", exc_info=True)
            self._update_empty_display(log_reason=f"_display_cv2_frame (exception: {e})")

    def update_frame(self, new_cv2_frame_bgr):
        widget_name = self.winfo_name()
        if not self.winfo_exists(): return
        log_debug(f"VideoDisplayFrame ({widget_name}).update_frame called. Frame is None: {new_cv2_frame_bgr is None}. _initial_configure_done: {self._initial_configure_done}")
        self.last_displayed_frame_raw = new_cv2_frame_bgr.copy() if new_cv2_frame_bgr is not None else None
        self._display_cv2_frame(self.last_displayed_frame_raw)
    
    def clear(self):
        widget_name = self.winfo_name()
        if not self.winfo_exists(): return
        log_debug(f"VideoDisplayFrame ({widget_name}).clear called.")
        self.last_displayed_frame_raw = None
        self._update_empty_display(log_reason="clear method")

    def force_initial_resize_and_rebind(self):
        widget_name = self.winfo_name()
        if not self.winfo_exists(): 
            log_debug(f"VideoDisplayFrame ({widget_name}).force_initial_resize_and_rebind: Widget destroyed. Skipping.")
            return
            
        log_debug(f"VideoDisplayFrame ({widget_name}).force_initial_resize_and_rebind: START")
        
        # It's crucial that the widget is mapped and has a size before calling winfo_width/height
        # self.update_idletasks() # Call on top level if needed before this
        
        parent_container = self.master 
        if not parent_container.winfo_exists():
            log_debug(f"VideoDisplayFrame ({widget_name}).force_initial_resize_and_rebind: Parent container {parent_container.winfo_name()} destroyed. Skipping.")
            return

        parent_w = parent_container.winfo_width() 
        parent_h = parent_container.winfo_height()
        log_debug(f"VideoDisplayFrame ({widget_name}).force_initial_resize_and_rebind: Parent container ({parent_container.winfo_name()}) actual WxH: {parent_w}x{parent_h}")

        if parent_w > 1 and parent_h > 1:
            self.target_width = parent_w
            self.target_height = parent_h
        else:
            # Fallback if parent still has no meaningful size (e.g., not yet drawn by mainloop update)
            log_debug(f"VideoDisplayFrame ({widget_name}).force_initial_resize_and_rebind: Parent container size {parent_w}x{parent_h} invalid or too small. Using fallback target WxH: {config.DEFAULT_VIDEO_WIDTH}x{config.DEFAULT_VIDEO_HEIGHT}")
            self.target_width = config.DEFAULT_VIDEO_WIDTH 
            self.target_height = config.DEFAULT_VIDEO_HEIGHT
        
        log_debug(f"VideoDisplayFrame ({widget_name}).force_initial_resize_and_rebind: Set target_width={self.target_width}, target_height={self.target_height}")
        
        if self.last_displayed_frame_raw is not None:
            log_debug(f"VideoDisplayFrame ({widget_name}).force_initial_resize_and_rebind: Calling _display_cv2_frame with last_displayed_frame_raw.")
            self._display_cv2_frame(self.last_displayed_frame_raw)
        else:
            log_debug(f"VideoDisplayFrame ({widget_name}).force_initial_resize_and_rebind: Calling _update_empty_display.")
            self._update_empty_display(log_reason="force_initial_resize_and_rebind (no raw frame)")
        
        if not self._initial_configure_done:
            log_debug(f"VideoDisplayFrame ({widget_name}).force_initial_resize_and_rebind: Binding <Configure> and setting _initial_configure_done to True.")
            try:
                self.unbind("<Configure>") 
            except tk.TclError: pass 
            self.bind("<Configure>", self._on_resize_display)
            self._initial_configure_done = True
        else:
            log_debug(f"VideoDisplayFrame ({widget_name}).force_initial_resize_and_rebind: <Configure> was already bound or _initial_configure_done was True.")
        log_debug(f"VideoDisplayFrame ({widget_name}).force_initial_resize_and_rebind: END")
