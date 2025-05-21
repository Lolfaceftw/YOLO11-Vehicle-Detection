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
import math
import numpy as np
from . import config
from .logger_setup import log_debug 

class LoadingOverlay:
    """
    Integrated loading overlay that dims the main content area but leaves the title bar visible.
    Implements a singleton pattern to ensure only one instance exists.
    Features a rotating "CoE197Z" text animation.
    """
    _instance = None  # Class variable to hold the singleton instance
    
    @classmethod
    def get_instance(cls, parent_window=None):
        """Get or create the singleton instance of LoadingOverlay"""
        if cls._instance is None and parent_window is not None:
            cls._instance = cls(parent_window)
        return cls._instance
    
    @classmethod
    def show(cls, parent_window, message="Loading..."):
        """Show the loading overlay with the specified message"""
        instance = cls.get_instance(parent_window)
        if instance:
            instance._show(message)
        return instance
            
    @classmethod
    def hide(cls):
        """Hide the loading overlay if it exists"""
        if cls._instance:
            cls._instance._hide()
            
    @classmethod
    def update(cls, message):
        """Update the message in the loading overlay if it exists"""
        if cls._instance:
            cls._instance._update_message(message)
    
    def __init__(self, parent_window):
        """Private initializer - use get_instance() or show() instead"""
        self.parent_window_ref = parent_window
        self.animation_job_id = None
        self.is_visible = False
        self.overlay_frames = {}
        self.spinner_widgets = {}
        
        # Get references to main UI containers from globals
        self.app_globals_refs = None
        
        log_debug(f"LoadingOverlay.__init__: Creating integrated loading overlay")
        
    def _create_overlay_for_panel(self, panel_name, panel_widget):
        """Create an overlay for a specific panel"""
        if not panel_widget or not panel_widget.winfo_exists():
            return None
            
        # Create semi-transparent overlay frame for this panel
        overlay_frame = tk.Frame(panel_widget)
            
        # Create darkened background effect
        # Use a dark canvas with custom transparency methods
        canvas = tk.Canvas(
            overlay_frame,
            bg=config.OVERLAY_BACKGROUND_COLOR,
            highlightthickness=0
        )
        canvas.place(x=0, y=0, relwidth=1, relheight=1)
        
        # Layered approach for better visual effect
        # First a solid but darker background
        canvas.create_rectangle(0, 0, 5000, 5000, 
                                fill=config.OVERLAY_BACKGROUND_COLOR, 
                                outline="")
        # Then overlay with a stippled pattern for semi-transparency effect
        canvas.create_rectangle(0, 0, 5000, 5000, 
                                fill="black", 
                                stipple="gray25", 
                                outline="")
        
        # Create spinner only for the main panel to avoid split display
        # Use left_panel for a consistent single overlay
        if panel_name == 'left_panel':
            # Loading message container with highlighted border
            content_frame = tk.Frame(overlay_frame, bg=config.OVERLAY_FRAME_COLOR, relief="raised", bd=2)
            content_frame.place(relx=0.5, rely=0.5, anchor="center")
            # Make the loading message stand out with a primary color border
            content_frame.configure(highlightbackground=config.COLOR_PRIMARY, highlightthickness=2)
            # Add inner padding for better visual appearance
            inner_frame = tk.Frame(content_frame, bg=config.OVERLAY_FRAME_COLOR, padx=2, pady=2)
            inner_frame.pack(fill="both", expand=True)
            content_frame = inner_frame  # Use inner frame as the content container
            
            padding_frame = tk.Frame(content_frame, bg=config.OVERLAY_FRAME_COLOR, 
                                     padx=config.SPACING_LARGE, pady=config.SPACING_LARGE)
            padding_frame.pack()
            
            # Increase spinner size for better visibility
            spinner_size = (config.COE_SPINNER_RADIUS + 25) * 2
            spinner_canvas = tk.Canvas(
                padding_frame,
                width=spinner_size,
                height=spinner_size,
                bg=config.OVERLAY_FRAME_COLOR, 
                highlightthickness=0
            )
            spinner_canvas.pack(pady=(0, config.SPACING_MEDIUM))
            
            # Status message label
            status_label = tk.Label(
                padding_frame,
                text="",
                bg=config.OVERLAY_FRAME_COLOR,
                fg=config.COLOR_TEXT_PRIMARY,
                font=config.FONT_MESSAGE_OVERLAY
            )
            status_label.pack()
            
            # Initialize spinner text items with initial positions around the circle
            spinner_items = []
            center_x = spinner_size / 2
            center_y = spinner_size / 2
            radius = config.COE_SPINNER_RADIUS
            
            # Pre-position each character around the circle
            for i, char in enumerate(config.COE_SPINNER_TEXT):
                angle = (360 / len(config.COE_SPINNER_TEXT)) * i - 90  # Start from top
                rad_angle = math.radians(angle)
                x = center_x + radius * math.cos(rad_angle)
                y = center_y + radius * math.sin(rad_angle)
                
                # Make initial character larger and use color based on position
                color = config.COLOR_PRIMARY if i == 0 else "#555555"
                font_size = 18 if i == 0 else 14
                font_weight = "bold" if i == 0 else "normal"
                
                item = spinner_canvas.create_text(
                    x, y, 
                    text=char,
                    font=(config.FONT_FAMILY_PRIMARY, font_size, font_weight),
                    fill=color
                )
                spinner_items.append(item)
                
            # Store spinner info in dictionary with animation properties
            self.spinner_widgets[panel_name] = {
                'canvas': spinner_canvas,
                'items': spinner_items,
                'angle': 0,
                'size': spinner_size,
                'center': (center_x, center_y),
                'radius': radius,
                'content_frame': content_frame,
                'message_label': status_label,
                'last_update': time.time(),
                'rotation_speed': 120.0  # degrees per second
            }
        
        return overlay_frame
        
    def _get_ui_panels(self):
        """Get references to all UI panels that need overlays"""
        # Access the global references
        from app import globals as app_globals
        
        panels = {}
        if app_globals.ui_references:
            # Get main panels
            for panel_name in ['left_panel', 'right_panel']:
                panel = app_globals.ui_references.get(panel_name)
                if panel and panel.winfo_exists():
                    panels[panel_name] = panel
                    
        return panels
        
    def _show(self, message="Loading..."):
        """Show the integrated loading overlay"""
        if self.is_visible:
            # If already visible, just update the message
            self._update_message(message)
            log_debug(f"LoadingOverlay._show: Already visible, updated message: {message}")
            return
            
        log_debug(f"LoadingOverlay._show: Creating and showing overlay with message: {message}")
        
        # Store original window state
        self.original_resizable = self.parent_window_ref.resizable()
        
        # Disable window resizing while loading
        self.parent_window_ref.resizable(False, False)
         
        # Change cursor to wait indicator
        self.parent_window_ref.config(cursor="wait")
        
        # Ensure window is up to date before creating overlays
        self.parent_window_ref.update_idletasks()
        
        # Get panels to overlay
        panels = self._get_ui_panels()
        
        # Only create left panel overlay to avoid split screen
        # The left panel overlay will cover the entire window
        if 'left_panel' in panels:
            panel_name = 'left_panel'
            panel_widget = panels[panel_name]
            
            if panel_widget and panel_widget.winfo_exists():
                # Create overlay for this panel if needed
                if panel_name not in self.overlay_frames or not self.overlay_frames[panel_name].winfo_exists():
                    self.overlay_frames[panel_name] = self._create_overlay_for_panel(panel_name, panel_widget)
                
                overlay = self.overlay_frames.get(panel_name)
                if overlay and overlay.winfo_exists():
                    # Make the overlay cover the entire application window instead of just the panel
                    # This prevents the split appearance of the loading overlay
                    # Use place instead of pack or grid to overlay without disturbing layout
                    overlay.place(x=0, y=0, relwidth=1, relheight=1)
                    overlay.lift()  # Ensure it's at the top of stacking order
                    
                    # Block all interactions with widgets underneath
                    # Mouse events
                    overlay.bind("<Button-1>", lambda e: "break")
                    overlay.bind("<Button-2>", lambda e: "break")
                    overlay.bind("<Button-3>", lambda e: "break")
                    overlay.bind("<ButtonRelease-1>", lambda e: "break")
                    overlay.bind("<ButtonRelease-2>", lambda e: "break")
                    overlay.bind("<ButtonRelease-3>", lambda e: "break")
                    overlay.bind("<Motion>", lambda e: "break")
                    overlay.bind("<B1-Motion>", lambda e: "break")
                    # Keyboard events
                    overlay.bind("<Key>", lambda e: "break")
                    overlay.bind("<KeyRelease>", lambda e: "break")
                    # Make sure it captures focus to prevent other widgets from getting input
                    overlay.focus_set()
                    
                    # Set initial message if this panel has a spinner
                    if panel_name in self.spinner_widgets:
                        spinner_info = self.spinner_widgets[panel_name]
                        if 'message_label' in spinner_info:
                            spinner_info['message_label'].config(text=message)
        
        # Start animation immediately with guaranteed execution
        # Cancel any existing animation first to prevent duplicates
        if self.animation_job_id:
            try:
                self.parent_window_ref.after_cancel(self.animation_job_id)
                log_debug("LoadingOverlay._show: Canceled existing animation timer")
            except Exception as e:
                log_debug(f"LoadingOverlay._show: Error canceling animation: {str(e)}")
        self.animation_job_id = None
        
        # Reset animation state
        for panel_name, spinner_info in self.spinner_widgets.items():
            spinner_info['angle'] = 0
            spinner_info['last_update'] = time.time()
        
        # Force animation to start immediately with detailed logging
        log_debug(f"LoadingOverlay._show: Starting animation...")
        # Direct call to ensure immediate start
        self._animate_spinners()
        
        # Also schedule a backup animation start in case the first one fails
        backup_id = self.parent_window_ref.after(100, self._ensure_animation)
        
        self.is_visible = True
        
        # Ensure UI is updated and visible
        for panel_name in self.overlay_frames:
            if panel_name in self.spinner_widgets:
                if 'content_frame' in self.spinner_widgets[panel_name]:
                    self.spinner_widgets[panel_name]['content_frame'].update_idletasks()
        
        # Force a full update to show overlay immediately
        self.parent_window_ref.update_idletasks()
        self.parent_window_ref.update()
        
        # Final lift to ensure overlay is on top
        for panel_name, overlay in self.overlay_frames.items():
            if overlay and overlay.winfo_exists():
                overlay.lift()
                
        # Start the animation with immediate effect
        self._animate_spinners()
        
        # Schedule a second animation check to ensure it's running
        if self.parent_window_ref and self.parent_window_ref.winfo_exists():
            self.parent_window_ref.after(100, self._ensure_animation)

    def _hide(self):
        """Hide the integrated loading overlay and restore UI state"""
        if not self.is_visible:
            log_debug("LoadingOverlay._hide: Already hidden")
            return
            
        log_debug("LoadingOverlay._hide: Hiding overlay")
        
        # Set state first to prevent animation updates
        self.is_visible = False
        
        # Cancel animation immediately with multiple safeguards
        if self.animation_job_id: 
            try:
                self.parent_window_ref.after_cancel(self.animation_job_id)
                log_debug("LoadingOverlay._hide: Animation timer canceled successfully")
            except Exception as e:
                log_debug(f"LoadingOverlay._hide: Error canceling animation: {str(e)}")
            self.animation_job_id = None
            
        # Reset animation state in all spinners
        for panel_name, spinner_info in self.spinner_widgets.items():
            spinner_info['angle'] = 0
            spinner_info['last_update'] = time.time()
        
        # Clean up event bindings first to prevent input capture issues
        for panel_name, overlay in self.overlay_frames.items():
            if overlay and overlay.winfo_exists():
                try:
                    # Unbind all events
                    overlay.unbind("<Button-1>")
                    overlay.unbind("<Button-2>")
                    overlay.unbind("<Button-3>")
                    overlay.unbind("<ButtonRelease-1>")
                    overlay.unbind("<ButtonRelease-2>")
                    overlay.unbind("<ButtonRelease-3>")
                    overlay.unbind("<Motion>")
                    overlay.unbind("<B1-Motion>")
                    overlay.unbind("<Key>")
                    overlay.unbind("<KeyRelease>")
                except Exception:
                    pass
                    
                # Hide from view
                overlay.place_forget()
                
        # Restore focus to main window
        if self.parent_window_ref and self.parent_window_ref.winfo_exists():
            try:
                self.parent_window_ref.focus_set()
            except Exception:
                pass
        
        # Restore window state
        if self.parent_window_ref and self.parent_window_ref.winfo_exists():
            try:
                # Reset cursor
                self.parent_window_ref.config(cursor="")
                
                # Restore original resizable state
                if hasattr(self, 'original_resizable'):
                    self.parent_window_ref.resizable(
                        self.original_resizable[0], 
                        self.original_resizable[1]
                    )
                else:
                    self.parent_window_ref.resizable(True, True)
            except Exception as e:
                log_debug(f"LoadingOverlay._hide: Error restoring window state: {str(e)}")
        
        # Update UI
        try:
            # Ensure main window regains proper input focus
            if self.parent_window_ref and self.parent_window_ref.winfo_exists():
                self.parent_window_ref.update_idletasks()
        except Exception:
            pass
            
        log_debug("LoadingOverlay._hide: Overlay hidden successfully")

    def _ensure_animation(self):
        """Ensure animation is running - backup method"""
        if self.is_visible and (self.animation_job_id is None):
            # Animation stopped but should be running - restart it
            log_debug("LoadingOverlay._ensure_animation: Restarting stopped animation")
            self._animate_spinners()
        elif self.is_visible:
            # Schedule another check in case animation stops unexpectedly
            self.parent_window_ref.after(500, self._ensure_animation)
    
    def _animate_spinners(self):
        """Animate spinner with rotating CoE197Z text"""
        # Return early if no animation should be running
        if not self.is_visible:
            self.animation_job_id = None
            log_debug("LoadingOverlay._animate_spinners: Animation stopped (overlay not visible)")
            return
            
        if not self.parent_window_ref or not self.parent_window_ref.winfo_exists():
            self.animation_job_id = None
            return
            
        # Only log animation once per 100 frames to reduce log size
        if getattr(self, '_animation_log_counter', 0) % 100 == 0:
            log_debug("LoadingOverlay._animate_spinners: Running animation")
        self._animation_log_counter = getattr(self, '_animation_log_counter', 0) + 1
        
        # Always use left_panel for consistent animation
        panel_name = 'left_panel'
        if panel_name not in self.spinner_widgets or panel_name not in self.overlay_frames:
            self.animation_job_id = None
            return
            
        spinner_info = self.spinner_widgets[panel_name]
        if not self.overlay_frames[panel_name].winfo_exists():
            self.animation_job_id = None
            return
            
        canvas = spinner_info.get('canvas')
        items = spinner_info.get('items', [])
        
        if not canvas or not canvas.winfo_exists() or not items:
            self.animation_job_id = None
            return
        
        try:
            # Get spinner parameters
            center_x, center_y = spinner_info.get('center', (50, 50))
            radius = spinner_info.get('radius', config.COE_SPINNER_RADIUS)
            current_angle = spinner_info.get('angle', 0)
            num_items = len(items)
            
            # Calculate rotation step based on time elapsed for consistent speed
            now = time.time()
            last_update = spinner_info.get('last_update', now - 0.05)
            elapsed = now - last_update
            rotation_step = 10.0 * elapsed * 60  # 10 degrees per frame at 60fps
            
            # Update current angle
            new_angle = (current_angle + rotation_step) % 360
            spinner_info['angle'] = new_angle
            spinner_info['last_update'] = now
            # Don't log angle updates to reduce log file size
            
            # Skip detailed position logging to reduce log size
            first_char_angle = new_angle
            first_char_rad = math.radians(first_char_angle)
            first_char_x = center_x + radius * math.cos(first_char_rad)
            first_char_y = center_y + radius * math.sin(first_char_rad)
            
            # Update each character position
            for i, item_id in enumerate(items):
                # Calculate character position on circle
                char_angle = (360.0 / num_items) * i + new_angle
                rad = math.radians(char_angle)
                x = center_x + radius * math.cos(rad)
                y = center_y + radius * math.sin(rad)
                
                # Update position
                canvas.coords(item_id, x, y)
                
                # Calculate frontal position (which character is in front) for visual emphasis
                # Front is at 90 degrees (top of circle)
                distance_from_front = abs(((char_angle % 360) - 90) % 360)
                if distance_from_front > 180:
                    distance_from_front = 360 - distance_from_front
                    
                # Emphasis based on position
                if distance_from_front < 45:  # Character is in front (top)
                    canvas.itemconfig(
                        item_id, 
                        fill=config.COLOR_PRIMARY,
                        font=(config.FONT_FAMILY_PRIMARY, 18, "bold")
                    )
                elif distance_from_front < 90:  # Character approaching front
                    color_value = max(80, 255 - int(distance_from_front * 1.5))
                    color = f"#{color_value:02x}{color_value:02x}{color_value:02x}"
                    canvas.itemconfig(
                        item_id, 
                        fill=color,
                        font=(config.FONT_FAMILY_PRIMARY, 16, "bold")
                    )
                else:  # Character in back half of circle
                    color_value = max(40, 120 - int(distance_from_front / 3))
                    color = f"#{color_value:02x}{color_value:02x}{color_value:02x}"
                    canvas.itemconfig(
                        item_id, 
                        fill=color,
                        font=(config.FONT_FAMILY_PRIMARY, 14, "normal")
                    )
            
            # Force immediate update to see animation
            try:
                canvas.update()
                # Skip success logging to reduce log size
            except Exception as update_error:
                log_debug(f"LoadingOverlay._animate_spinners: Canvas update failed: {update_error}")
            
            # Skip rotation logging to reduce log file size
            
            # Schedule next animation frame
            # Use 16ms (~60fps) for smooth animation
            animation_delay = 16  # milliseconds
            self.animation_job_id = self.parent_window_ref.after(
                animation_delay,
                self._animate_spinners
            )
            # Skip scheduling logging to reduce log file size
            
        except Exception as e:
            log_debug(f"LoadingOverlay._animate_spinners: Error in animation cycle: {str(e)}", exc_info=True)
            # Try to schedule again even if there was an error
            try:
                if self.parent_window_ref and self.parent_window_ref.winfo_exists():
                    self.animation_job_id = self.parent_window_ref.after(50, self._animate_spinners)
                    # Skip detailed recovery logging to reduce log file size
            except Exception as recovery_error:
                log_debug(f"LoadingOverlay._animate_spinners: Recovery scheduling failed: {recovery_error}")
                self.animation_job_id = None

    def _update_message(self, new_message):
        """Update the message text on all spinners"""
        if not self.is_visible:
            return
            
        for panel_name, spinner_info in self.spinner_widgets.items():
            if panel_name in self.overlay_frames and self.overlay_frames[panel_name].winfo_exists():
                label = spinner_info.get('message_label')
                if label and label.winfo_exists():
                    label.config(text=new_message)
                    
                    # Update content frame layout if needed
                    content_frame = spinner_info.get('content_frame')
                    if content_frame and content_frame.winfo_exists():
                        content_frame.update_idletasks()
                        # Re-center if needed
                        content_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        log_debug(f"LoadingOverlay._update_message: Updated to '{new_message}'")

class VideoDisplayFrame(ttk.Frame):
    def __init__(self, parent, initial_width=640, initial_height=480, **kwargs):
        super().__init__(parent, **kwargs)
        self.widget_name = self.winfo_name() 
        log_debug(f"VideoDisplayFrame ({self.widget_name}) __init__: Parent is {parent.winfo_name() if parent else 'None'}. Initial target WxH: {initial_width}x{initial_height}")
        # Use a tk.Label for better performance than ttk.Label with images
        self.display_label = tk.Label(self, background=config.COLOR_BACKGROUND_LIGHT)
        self.display_label.pack(expand=True, fill="both") 
        self.current_photo_image = None
        self.last_displayed_frame_raw = None 
        self.target_width = initial_width
        self.target_height = initial_height
        self._initial_configure_done = False
        self._resize_throttle_id = None
        self._last_resize_time = 0
        self._resize_in_progress = False
        self._resize_needs_refresh = False
        self._last_frame_update_time = 0
        # Cache for performance optimization
        self._cached_photo = None
        self._last_frame_size = None
        self._last_display_size = None
        self._previous_resize_dims = None
        self._resampling_method = Image.Resampling.NEAREST
        self._update_empty_display(log_reason="init") 
        log_debug(f"VideoDisplayFrame ({self.widget_name}) initialized. Current target WxH: {self.target_width}x{self.target_height}. <Configure> NOT bound initially.")

    def _rebind_configure_after_delay(self):
        """Rebind the Configure event after temporary unbinding to prevent recursive loops"""
        widget_name = self.winfo_name()
        if not self.winfo_exists(): return
        log_debug(f"VideoDisplayFrame ({widget_name})._rebind_configure_after_delay: Rebinding <Configure> event.")
        try:
            # Clear resize flags first
            self._resize_in_progress = False
            self._last_resize_time = time.perf_counter()
            # Then rebind the event
            self.bind("<Configure>", self._on_resize_display)
        except tk.TclError as e:
            log_debug(f"VideoDisplayFrame ({widget_name})._rebind_configure_after_delay: Error: {str(e)}")
    
    def _on_resize_display(self, event):
        widget_name = self.winfo_name()
        if not self.winfo_exists(): return
        if not self._initial_configure_done: return
        
        # Aggressive resize throttling during real-time playback
        # We need to limit resize operations to prevent UI thread overload
        from app import globals as app_globals
        is_playing = getattr(app_globals, 'is_playing_via_after_loop', False)
        
        # Use longer throttle period during active playback
        throttle_threshold = 0.5 if is_playing else 0.1  # 500ms during playback, 100ms otherwise
        
        # Get current time only once for efficiency
        current_time = time.perf_counter()
        
        # Skip if resize is already in progress or too soon after last resize
        if self._resize_in_progress or current_time - self._last_resize_time < throttle_threshold:
            # Ensure we only have one pending resize operation
            if self._resize_throttle_id:
                try:
                    self.after_cancel(self._resize_throttle_id)
                except Exception:
                    pass
                    
            # Schedule with longer delay during playback
            delay = 300 if is_playing else 150
            self._resize_throttle_id = self.after(delay, lambda: self._throttled_resize(event.width, event.height))
            return
        
        # Significant change detection with adaptive threshold based on window size
        # Use percentage-based threshold (2%) instead of fixed pixel value
        width_threshold = max(5, int(self.target_width * 0.02))  # At least 5px or 2%
        height_threshold = max(5, int(self.target_height * 0.02))  # At least 5px or 2%
        
        if event.width > 1 and event.height > 1 and \
           (abs(event.width - self.target_width) > width_threshold or 
            abs(event.height - self.target_height) > height_threshold):
            
            self._resize_in_progress = True
            self.target_width = event.width
            self.target_height = event.height
            
            # During playback, don't immediately refresh to avoid freezing
            delay = 100 if is_playing else 50
            
            # Cancel any pending resize to avoid queuing multiple operations
            if self._resize_throttle_id:
                try:
                    self.after_cancel(self._resize_throttle_id)
                except Exception:
                    pass
                    
            # Schedule the refresh with appropriate delay
            self._resize_throttle_id = self.after(delay, self._refresh_current_image)
            self._last_resize_time = current_time


    def _throttled_resize(self, width, height):
        """Handle resize after throttling to improve performance"""
        widget_name = self.winfo_name()
        if not self.winfo_exists(): 
            return
            
        # Clear throttle ID since this is the delayed execution
        self._resize_throttle_id = None
        
        # Check if dimensions are still valid
        if width <= 0 or height <= 0:
            self._resize_in_progress = False
            return
            
        # Check if real-time video is playing
        from app import globals as app_globals
        is_playing = getattr(app_globals, 'is_playing_via_after_loop', False)
        
        # Fast path: if dimensions haven't changed since throttling started, just update flags
        if self.target_width == width and self.target_height == height:
            self._resize_in_progress = False
            return
            
        # Update dimensions
        self.target_width = width
        self.target_height = height
        
        # Refresh image with special handling during playback
        if is_playing:
            # During playback, we'll update on next frame rather than forcing a refresh
            # This prevents freezing the UI during resize while playback is active
            self._resize_needs_refresh = True
        else:
            # Normal refresh when not in playback mode
            self._refresh_current_image()
            
        # Complete resize operation
        self._resize_in_progress = False
        
        # Clear cached photo to force redraw on next frame
        if hasattr(self, '_cached_photo'):
            self._cached_photo = None
    
    def _refresh_current_image(self):
        """Refresh the current image based on last frame or empty display"""
        if not self.winfo_exists(): return
        
        # Check playback status to optimize refresh behavior
        from app import globals as app_globals
        is_playing = getattr(app_globals, 'is_playing_via_after_loop', False)
        
        # Clear any cached sizing information to force proper resizing
        if hasattr(self, '_last_display_size'):
            delattr(self, '_last_display_size')
        if hasattr(self, '_previous_resize_dims'):
            delattr(self, '_previous_resize_dims')
        
        # Handle actual refresh
        if self.last_displayed_frame_raw is not None:
            # Use appropriate resampling method based on playback state
            if is_playing:
                # Use fastest method during playback
                self._resampling_method = Image.Resampling.NEAREST
            else:
                # Use higher quality when not in playback
                self._resampling_method = Image.Resampling.BILINEAR
                
            # Force redraw with current frame
            self._display_cv2_frame(self.last_displayed_frame_raw)
        else:
            self._update_empty_display(log_reason="refresh_current_image")
            
        # Clear resize pending flag
        self._resize_needs_refresh = False
    
    def _update_empty_display(self, log_reason=""):
        widget_name = self.winfo_name()
        if not self.winfo_exists(): return
        
        # Reset cached values to force refresh on next valid frame
        if hasattr(self, '_last_frame_size'):
            del self._last_frame_size
        if hasattr(self, '_last_display_size'):
            del self._last_display_size
        if hasattr(self, '_cached_photo'):
            del self._cached_photo
            
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
        
        # Add diagnostic logging
        log_debug(f"VideoDisplayFrame ({widget_name})._display_cv2_frame: Received frame type: {type(cv2_frame_bgr)}")
        if hasattr(cv2_frame_bgr, 'shape'):
            log_debug(f"VideoDisplayFrame ({widget_name})._display_cv2_frame: Frame shape: {cv2_frame_bgr.shape}")
        
        # Cache calculations to reduce computation overhead
        current_target_w = max(1, int(self.target_width))
        current_target_h = max(1, int(self.target_height))
        
        # Early return for null frames
        if cv2_frame_bgr is None:
            self._update_empty_display(log_reason="_display_cv2_frame (input None)")
            return

        try:
            # Cached resampling method for improved performance
            if not hasattr(self, '_resampling_method'):
                # When running real-time, prefer NEAREST method for best speed
                # On slower machines, BILINEAR is a good compromise
                # For best quality when paused, we'd use BICUBIC
                self._resampling_method = Image.Resampling.NEAREST
            
            # Validate frame shape before accessing it
            if not hasattr(cv2_frame_bgr, 'shape') or len(cv2_frame_bgr.shape) < 2:
                self._update_empty_display(log_reason="_display_cv2_frame (invalid frame shape)")
                return
                
            # Check for cached size to avoid unnecessary resizing (with additional safety checks)
            if (hasattr(self, '_last_frame_size') and hasattr(self, '_last_display_size') and 
                hasattr(cv2_frame_bgr, 'shape') and len(cv2_frame_bgr.shape) >= 2):
                # Skip processing completely if nothing has changed
                try:
                    if (current_target_w, current_target_h) == self._last_display_size and \
                       (cv2_frame_bgr.shape[1], cv2_frame_bgr.shape[0]) == self._last_frame_size and \
                       hasattr(self, '_cached_photo') and self._cached_photo is not None:
                        self.display_label.config(image=self._cached_photo)
                        return
                except Exception as e:
                    log_debug(f"VideoDisplayFrame ({widget_name})._display_cv2_frame: Error checking cached size: {e}")
                    # Continue with normal processing if cache check fails
            
            t_start_display = time.perf_counter()
            
            # Safe conversion to RGB format
            try:
                if hasattr(cv2_frame_bgr, 'shape') and len(cv2_frame_bgr.shape) >= 2:
                    try:
                        # Fast RGB conversion - OpenCV is optimized for this
                        frame_rgb = cv2.cvtColor(cv2_frame_bgr, cv2.COLOR_BGR2RGB)
                    
                        # Get frame dimensions directly from numpy array
                        original_width = cv2_frame_bgr.shape[1]  # Width is at index 1
                        original_height = cv2_frame_bgr.shape[0]  # Height is at index 0
                        self._last_frame_size = (original_width, original_height)
                    
                        if original_width <= 0 or original_height <= 0:
                            self._update_empty_display(log_reason="_display_cv2_frame (original dims zero)")
                            return
                    except Exception as e:
                        log_debug(f"VideoDisplayFrame ({widget_name})._display_cv2_frame: Error during color conversion: {e}")
                        # Try to use the frame directly if color conversion fails
                        if len(cv2_frame_bgr.shape) == 3 and cv2_frame_bgr.shape[2] == 3:
                            frame_rgb = cv2_frame_bgr  # Use directly, might be already in RGB
                            original_width = cv2_frame_bgr.shape[1]
                            original_height = cv2_frame_bgr.shape[0]
                            self._last_frame_size = (original_width, original_height)
                        else:
                            self._update_empty_display(log_reason="_display_cv2_frame (color conversion failed)")
                            return
            except Exception as cv_error:
                log_debug(f"VideoDisplayFrame ({widget_name})._display_cv2_frame: Error converting image: {cv_error}")
                self._update_empty_display(log_reason="_display_cv2_frame (conversion error)")
                return
                
                # Fast aspect ratio calculation and rounding
                aspect_ratio = original_width / original_height
                
                # Calculate dimensions preserving aspect ratio
                new_width = min(current_target_w, int(current_target_h * aspect_ratio))
                new_height = min(current_target_h, int(new_width / aspect_ratio))
                
                # Ensure minimum size and exact integer values
                new_width = max(1, int(new_width))
                new_height = max(1, int(new_height))
                self._last_display_size = (current_target_w, current_target_h)
                
                # Skip resize if delta is minor (within 5%) to improve performance
                skip_resize = False
                if hasattr(self, '_previous_resize_dims'):
                    prev_w, prev_h = self._previous_resize_dims
                    w_delta = abs(prev_w - new_width) / prev_w if prev_w > 0 else 1
                    h_delta = abs(prev_h - new_height) / prev_h if prev_h > 0 else 1
                    skip_resize = w_delta < 0.05 and h_delta < 0.05  # 5% threshold
                
                # Fast path for images that don't need resizing
                try:
                    if original_width == new_width and original_height == new_height:
                        pil_image = Image.fromarray(frame_rgb)
                        self._previous_resize_dims = (new_width, new_height)
                    elif skip_resize and hasattr(self, '_cached_photo'):
                        # Reuse previous image if resize delta is minor
                        self.display_label.config(image=self._cached_photo)
                        return
                    else:
                        # Fast resize using OpenCV for better performance than PIL
                        resized_frame = cv2.resize(
                            frame_rgb, 
                            (new_width, new_height),
                            interpolation=cv2.INTER_NEAREST  # Fastest method for real-time
                        )
                        pil_image = Image.fromarray(resized_frame)
                        self._previous_resize_dims = (new_width, new_height)
                except Exception as e:
                    log_debug(f"VideoDisplayFrame ({widget_name})._display_cv2_frame: Error during resize: {e}")
                    # Try direct PIL conversion as fallback
                    try:
                        pil_image = Image.fromarray(cv2.cvtColor(cv2_frame_bgr, cv2.COLOR_BGR2RGB))
                        pil_image = pil_image.resize((new_width, new_height), Image.Resampling.NEAREST)
                        self._previous_resize_dims = (new_width, new_height)
                    except Exception as fallback_error:
                        log_debug(f"VideoDisplayFrame ({widget_name})._display_cv2_frame: Fallback resize failed: {fallback_error}")
                        self._update_empty_display(log_reason="_display_cv2_frame (resize failed)")
                        return
                
                # Cache the photo image for potential reuse
                self.current_photo_image = ImageTk.PhotoImage(pil_image)
                self._cached_photo = self.current_photo_image
                
                # Update display with minimal overhead
                self.display_label.config(image=self.current_photo_image)
                
                # Performance tracking (only log significant issues)
                t_end_display = time.perf_counter()
                display_time = (t_end_display - t_start_display)*1000
                
                # Only log severe performance issues
                if display_time > 100:  # Only log very slow operations (>100ms)
                    log_debug(f"VideoDisplayFrame ({widget_name})._display_cv2_frame: Performance warning: {display_time:.1f} ms")
            else:
                # Try to handle non-standard format
                try:
                    log_debug(f"VideoDisplayFrame ({widget_name})._display_cv2_frame: Attempting to handle non-standard format")
                    # Create a compatible empty image with the right dimensions
                    if hasattr(cv2_frame_bgr, 'shape') and len(cv2_frame_bgr.shape) >= 2:
                        h, w = cv2_frame_bgr.shape[0], cv2_frame_bgr.shape[1]
                        empty_frame = np.zeros((h, w, 3), dtype=np.uint8)
                        # Copy data if possible
                        if len(cv2_frame_bgr.shape) == 3:
                            empty_frame = cv2_frame_bgr.copy()
                        # Convert to RGB and display
                        frame_rgb = cv2.cvtColor(empty_frame, cv2.COLOR_BGR2RGB)
                        pil_image = Image.fromarray(frame_rgb)
                        
                        # Calculate new dimensions preserving aspect ratio
                        aspect_ratio = w / h
                        new_width = min(current_target_w, int(current_target_h * aspect_ratio))
                        new_height = min(current_target_h, int(new_width / aspect_ratio))
                        new_width, new_height = max(1, new_width), max(1, new_height)
                        
                        # Resize and display
                        pil_image = pil_image.resize((new_width, new_height), Image.Resampling.NEAREST)
                        self.current_photo_image = ImageTk.PhotoImage(pil_image)
                        self.display_label.config(image=self.current_photo_image)
                        log_debug(f"VideoDisplayFrame ({widget_name})._display_cv2_frame: Successfully displayed non-standard format")
                        return
                except Exception as format_error:
                    log_debug(f"VideoDisplayFrame ({widget_name})._display_cv2_frame: Failed to handle non-standard format: {format_error}")
                    
                # Invalid frame format - fall back to empty display
                self._update_empty_display(log_reason="_display_cv2_frame (invalid format)")

        except Exception as e:
            # More detailed error logging
            log_debug(f"VideoDisplayFrame ({widget_name})._display_cv2_frame error: {str(e)}")
            log_debug(f"VideoDisplayFrame ({widget_name})._display_cv2_frame error details:", exc_info=True)
            
            # Try one last fallback method to display something
            try:
                if hasattr(cv2_frame_bgr, 'shape') and len(cv2_frame_bgr.shape) >= 2:
                    # Create a basic empty image with the same dimensions if possible
                    h, w = cv2_frame_bgr.shape[0], cv2_frame_bgr.shape[1]
                    fallback_img = np.zeros((h, w, 3), dtype=np.uint8)
                    fallback_img[:] = (200, 200, 200)  # Light gray
                    
                    # Just try to display the actual frame directly
                    try:
                        # Try direct display of original image first
                        if len(cv2_frame_bgr.shape) == 3 and cv2_frame_bgr.shape[2] == 3:
                            direct_rgb = cv2_frame_bgr.copy()
                            # Handle both BGR and RGB format
                            if direct_rgb.dtype == np.uint8:
                                direct_pil = Image.fromarray(direct_rgb)
                                # Resize if needed
                                aspect_ratio = w / h
                                new_width = min(current_target_w, int(current_target_h * aspect_ratio))
                                new_height = min(current_target_h, int(new_width / aspect_ratio))
                                if new_width != w or new_height != h:
                                    direct_pil = direct_pil.resize((new_width, new_height), Image.Resampling.NEAREST)
                                self.current_photo_image = ImageTk.PhotoImage(direct_pil)
                                self.display_label.config(image=self.current_photo_image)
                                log_debug(f"VideoDisplayFrame ({widget_name})._display_cv2_frame: Using direct display fallback")
                                return
                    except Exception as direct_error:
                        log_debug(f"VideoDisplayFrame ({widget_name})._display_cv2_frame: Direct display fallback failed: {direct_error}")
                    
                    # If direct display failed, try with error message
                    # Draw an error message
                    cv2.putText(fallback_img, "Display Error - Check Log", (int(w/2)-100, int(h/2)), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    
                    # Try to display this fallback
                    pil_image = Image.fromarray(cv2.cvtColor(fallback_img, cv2.COLOR_BGR2RGB))
                    self.current_photo_image = ImageTk.PhotoImage(pil_image)
                    self.display_label.config(image=self.current_photo_image)
                    log_debug(f"VideoDisplayFrame ({widget_name})._display_cv2_frame: Using error message fallback display")
            except Exception as fallback_error:
                log_debug(f"VideoDisplayFrame ({widget_name})._display_cv2_frame: Fallback display also failed: {fallback_error}")

    def update_frame(self, new_cv2_frame_bgr):
        widget_name = self.winfo_name()
        if not self.winfo_exists(): return
        
        # Add diagnostic logging for debugging
        log_debug(f"VideoDisplayFrame ({widget_name}).update_frame: Received frame type: {type(new_cv2_frame_bgr)}")
        if hasattr(new_cv2_frame_bgr, 'shape'):
            log_debug(f"VideoDisplayFrame ({widget_name}).update_frame: Frame shape: {new_cv2_frame_bgr.shape}")
        
        # Skip updates entirely if frame rate is too high
        current_time = time.perf_counter()
        if hasattr(self, '_last_frame_update_time'):
            # Throttle updates to maximum 60 FPS to prevent UI overload
            if current_time - self._last_frame_update_time < 0.016:  # ~60 FPS
                return
        self._last_frame_update_time = current_time
        
        # Skip processing if frame is None
        if new_cv2_frame_bgr is None:
            self.last_displayed_frame_raw = None
            self._update_empty_display(log_reason="update_frame (None)")
            return
        
        # Verify the frame is a valid numpy array
        if not isinstance(new_cv2_frame_bgr, np.ndarray):
            log_debug(f"VideoDisplayFrame ({widget_name}).update_frame: Frame is not a numpy array")
            try:
                # Try to convert to numpy array if it's not already
                new_cv2_frame_bgr = np.array(new_cv2_frame_bgr)
            except Exception as e:
                log_debug(f"VideoDisplayFrame ({widget_name}).update_frame: Failed to convert to numpy array: {e}")
                self._update_empty_display(log_reason="update_frame (conversion failed)")
                return
            
        # Use zero-copy reference when possible for better performance
        # Only copy when resize is in progress to prevent data race
        try:
            # Always make a copy to ensure we don't have issues with shared memory
            try:
                self.last_displayed_frame_raw = new_cv2_frame_bgr.copy()
            except Exception as copy_error:
                log_debug(f"VideoDisplayFrame ({widget_name}).update_frame: Copy failed, using direct reference: {copy_error}")
                self.last_displayed_frame_raw = new_cv2_frame_bgr
            
            # Process immediately
            self._display_cv2_frame(self.last_displayed_frame_raw)
        except Exception as e:
            # Only log errors, don't try to recover (performance optimization)
            log_debug(f"VideoDisplayFrame ({widget_name}).update_frame error: {str(e)}")
    
    def clear(self):
        widget_name = self.winfo_name()
        if not self.winfo_exists(): return
        log_debug(f"VideoDisplayFrame ({widget_name}).clear called.")
        
        # Cancel any pending resize operations
        if self._resize_throttle_id:
            try:
                self.after_cancel(self._resize_throttle_id)
                self._resize_throttle_id = None
            except Exception:
                pass
                
        self.last_displayed_frame_raw = None
        self._update_empty_display(log_reason="clear method")

    def force_initial_resize_and_rebind(self, prevent_recursive=False):
        widget_name = self.winfo_name()
        if not self.winfo_exists(): 
            log_debug(f"VideoDisplayFrame ({widget_name}).force_initial_resize_and_rebind: Widget destroyed. Skipping.")
            return
            
        log_debug(f"VideoDisplayFrame ({widget_name}).force_initial_resize_and_rebind: START (prevent_recursive={prevent_recursive})")
        
        # Cancel any pending resize operations
        if self._resize_throttle_id:
            try:
                self.after_cancel(self._resize_throttle_id)
                self._resize_throttle_id = None
            except Exception:
                pass
        
        # Get parent container dimensions
        parent_container = self.master 
        if not parent_container.winfo_exists():
            log_debug(f"VideoDisplayFrame ({widget_name}).force_initial_resize_and_rebind: Parent container destroyed. Skipping.")
            return

        try:
            parent_w = parent_container.winfo_width() 
            parent_h = parent_container.winfo_height()
            
            if parent_w > 1 and parent_h > 1:
                # Apply reasonable size limits
                if prevent_recursive:
                    # More conservative size limits when preventing recursive resizing
                    max_width = min(parent_w, config.DEFAULT_VIDEO_WIDTH * 1.2)
                    max_height = min(parent_h, config.DEFAULT_VIDEO_HEIGHT * 1.2)
                    self.target_width = max_width
                    self.target_height = max_height
                    log_debug(f"VideoDisplayFrame ({widget_name}).force_initial_resize_and_rebind: Using limited dimensions: {max_width}x{max_height}")
                else:
                    # Normal sizing based on parent dimensions
                    self.target_width = parent_w
                    self.target_height = parent_h
            else:
                # Fallback for invalid parent size
                self.target_width = config.DEFAULT_VIDEO_WIDTH 
                self.target_height = config.DEFAULT_VIDEO_HEIGHT
            
            # Update display with new dimensions
            self._refresh_current_image()
            
            # Handle Configure event binding
            if not self._initial_configure_done and not prevent_recursive:
                log_debug(f"VideoDisplayFrame ({widget_name}).force_initial_resize_and_rebind: Setting up initial Configure binding")
                try:
                    self.unbind("<Configure>") 
                except tk.TclError: pass 
                
                # Clear any resize flags
                self._resize_in_progress = False
                self._last_resize_time = time.perf_counter()
                
                # Bind resize event
                self.bind("<Configure>", self._on_resize_display)
                self._initial_configure_done = True
            elif prevent_recursive and self._initial_configure_done:
                # Temporarily unbind to prevent resize loops
                try:
                    self.unbind("<Configure>")
                    # Mark that we're in a resize operation
                    self._resize_in_progress = True
                    # Rebind after a longer delay for stability
                    self.after(800, self._rebind_configure_after_delay)
                except tk.TclError: pass
                
        except Exception as e:
            log_debug(f"VideoDisplayFrame ({widget_name}).force_initial_resize_and_rebind: Error: {str(e)}")
            
        log_debug(f"VideoDisplayFrame ({widget_name}).force_initial_resize_and_rebind: END")
