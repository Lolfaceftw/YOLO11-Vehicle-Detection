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

# Create a Material Design style theme
def setup_material_theme():
    """Set up a Material Design theme for ttk widgets"""
    style = ttk.Style()
    
    # Configure basic styles
    style.configure(".", 
                    font=config.FONT_BODY,
                    background=config.COLOR_BACKGROUND)
    
    # Frame styles
    style.configure("TFrame", 
                    background=config.COLOR_BACKGROUND)
    
    # Card frame style (with subtle elevation)
    style.configure("Card.TFrame",
                    background=config.COLOR_SURFACE,
                    relief="flat",
                    borderwidth=0)
    
    # Label styles
    style.configure("TLabel", 
                    font=config.FONT_BODY,
                    background=config.COLOR_BACKGROUND,
                    foreground=config.COLOR_TEXT_PRIMARY)
    
    # Title label style
    style.configure("Title.TLabel",
                    font=config.FONT_TITLE,
                    foreground=config.COLOR_TEXT_PRIMARY)
                    
    # Subtitle label style
    style.configure("Subtitle.TLabel",
                    font=config.FONT_SUBTITLE,
                    foreground=config.COLOR_TEXT_SECONDARY)
    
    # Caption label style
    style.configure("Caption.TLabel",
                    font=config.FONT_CAPTION,
                    foreground=config.COLOR_TEXT_SECONDARY)
    
    # LabelFrame styles
    style.configure("TLabelframe", 
                    background=config.COLOR_SURFACE,
                    borderwidth=0)
    style.configure("TLabelframe.Label", 
                    font=config.FONT_SUBTITLE,
                    background=config.COLOR_SURFACE,
                    foreground=config.COLOR_TEXT_PRIMARY)
    
    # Button styles
    style.configure("TButton", 
                    font=config.FONT_BUTTON,
                    background=config.COLOR_PRIMARY,
                    foreground=config.COLOR_PRIMARY_TEXT,
                    borderwidth=0,
                    focusthickness=0,
                    padding=(config.SPACING_MEDIUM, config.SPACING_SMALL))
    
    # Primary button (filled)
    style.configure("Primary.TButton",
                    background=config.COLOR_PRIMARY,
                    foreground=config.COLOR_PRIMARY_TEXT)
    
    # Secondary button (filled)
    style.configure("Secondary.TButton",
                    background=config.COLOR_SECONDARY,
                    foreground=config.COLOR_SECONDARY_TEXT)
    
    # Outline button
    style.configure("Outline.TButton",
                    background=config.COLOR_SURFACE,
                    foreground=config.COLOR_PRIMARY,
                    borderwidth=1)
    
    # Text button (no background)
    style.configure("Text.TButton",
                    background=config.COLOR_BACKGROUND,
                    foreground=config.COLOR_PRIMARY,
                    borderwidth=0)
    
    # Radio button styles
    style.configure("TRadiobutton",
                    font=config.FONT_BODY,
                    background=config.COLOR_BACKGROUND,
                    foreground=config.COLOR_TEXT_PRIMARY)
    
    # Checkbutton styles
    style.configure("TCheckbutton",
                    font=config.FONT_BODY,
                    background=config.COLOR_BACKGROUND,
                    foreground=config.COLOR_TEXT_PRIMARY)
    
    # Scale/Slider styles
    style.configure("TScale",
                    troughcolor=config.COLOR_BACKGROUND_LIGHT,
                    background=config.COLOR_BACKGROUND,
                    sliderrelief="flat",
                    sliderthickness=16)
    
    # Progressbar styles
    style.configure("TProgressbar",
                    troughcolor=config.COLOR_BACKGROUND_LIGHT,
                    background=config.COLOR_SECONDARY,  # Using secondary color for all progressbars
                    thickness=8)
    
    # Map progressbar colors for different states
    style.map("TProgressbar",
              background=[("selected", config.COLOR_SECONDARY),
                         ("active", config.COLOR_SECONDARY_DARK)])
    
    # Overlay styles
    style.configure("Overlay.TFrame", 
                    background=config.COLOR_SURFACE)
    style.configure("Overlay.TLabel", 
                    background=config.COLOR_SURFACE, 
                    foreground=config.COLOR_TEXT_PRIMARY)
    
    return style

class ScrollableFrame(ttk.Frame):
    """A scrollable frame widget"""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        
        # Create a canvas and scrollbar
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0,
                               background=config.COLOR_BACKGROUND)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        # Configure canvas
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Add frame to canvas
        self.canvas_frame = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        # Configure scrollable frame to expand to canvas width
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind(
            "<Configure>",
            lambda e: self.canvas.itemconfig(self.canvas_frame, width=e.width)
        )
        
        # Pack canvas and scrollbar
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Bind mousewheel to scroll
        self.bind_mousewheel()
        
    def bind_mousewheel(self):
        """Bind mousewheel events to the canvas for scrolling"""
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
    def unbind_mousewheel(self):
        """Unbind mousewheel events from the canvas"""
        self.canvas.unbind_all("<MouseWheel>")
        
    def _on_mousewheel(self, event):
        """Handle mousewheel events"""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


class RedirectText:
    """Class to redirect stdout to a tkinter Text widget"""
    def __init__(self, text_widget):
        self.text_widget = text_widget
        
    def write(self, string):
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.insert(tk.END, string)
        self.text_widget.see(tk.END)
        self.text_widget.config(state=tk.DISABLED)
        
    def flush(self):
        pass


class LoadingOverlay(tk.Toplevel):
    """Loading overlay that blocks interaction with the main window"""
    def __init__(self, parent, message="Loading..."):
        super().__init__(parent)
        self.parent = parent
        self.animation_job = None  # Initialize to None
        
        self.title("")
        # Ensure overlay covers parent - updated by update_position
        self.geometry(f"{parent.winfo_width()}x{parent.winfo_height()}+{parent.winfo_x()}+{parent.winfo_y()}")
        self.configure(bg=config.OVERLAY_BACKGROUND_COLOR)
        self.attributes("-alpha", config.OVERLAY_ALPHA)
        self.transient(parent)
        self.overrideredirect(True)
        
        # Create a card-like frame for the loading indicator
        self.frame = ttk.Frame(self, style="Overlay.TFrame")
        self.frame.place(relx=0.5, rely=0.5, anchor="center")

        # Add some padding around the content
        padding_frame = ttk.Frame(self.frame, style="Overlay.TFrame")
        padding_frame.pack(padx=config.SPACING_LARGE, pady=config.SPACING_LARGE)
        
        # Unicode Spinner Animation
        self.animation_frames = config.UNICODE_SPINNER_FRAMES
        self.current_animation_frame_index = 0
        self.animation_delay = config.UNICODE_SPINNER_DELAY_MS
        
        self.animation_label = ttk.Label(
            padding_frame, 
            text=self.animation_frames[0], 
            style="Overlay.TLabel", 
            font=config.FONT_SPINNER
        )
        self.animation_label.pack(pady=(config.SPACING_LARGE, config.SPACING_MEDIUM))
        
        self.message_label = ttk.Label(
            padding_frame, 
            text=message, 
            style="Overlay.TLabel", 
            font=config.FONT_MESSAGE_OVERLAY
        )
        self.message_label.pack(pady=(0, config.SPACING_LARGE))
        
        self._animate_spinner() # Start the animation
        
        parent.update_idletasks() # Ensure parent UI is stable before getting geometry
        self.update_position() # Initial position update
        parent.bind("<Configure>", self.update_position, add="+") # Use add="+" to not overwrite other binds
        
        # Ensure the overlay itself is drawn and updated
        self.update_idletasks()
        self.lift() # Ensure the overlay is on top
        self.focus_force() # Attempt to give focus to the overlay
    
    def update_position(self, event=None):
        if not self.winfo_exists() or not self.parent.winfo_exists():
            return
        self.geometry(f"{self.parent.winfo_width()}x{self.parent.winfo_height()}+{self.parent.winfo_x()}+{self.parent.winfo_y()}")
    
    def _animate_spinner(self):
        if not self.winfo_exists(): # Stop animation if widget is destroyed
            return
        self.current_animation_frame_index = (self.current_animation_frame_index + 1) % len(self.animation_frames)
        self.animation_label.config(text=self.animation_frames[self.current_animation_frame_index])
        self.animation_job = self.after(self.animation_delay, self._animate_spinner)
    
    def update_message(self, message):
        if self.winfo_exists():
            self.message_label.config(text=message)
    
    def destroy(self):
        if self.animation_job:
            self.after_cancel(self.animation_job)
            self.animation_job = None
        if self.parent.winfo_exists(): # Check if parent exists before unbinding
            try:
                self.parent.unbind("<Configure>") # Might fail if already unbound or other issues
            except tk.TclError:
                pass # Ignore TclError if unbind fails (e.g. binding doesn't exist)
        super().destroy()


class MaterialButton(ttk.Frame):
    """Material Design inspired button with hover effects and elevation"""
    def __init__(self, parent, text="Button", command=None, style="primary", **kwargs):
        super().__init__(parent, **kwargs)
        
        # Set up colors based on style
        if style == "primary":
            bg_color = config.COLOR_PRIMARY
            fg_color = config.COLOR_PRIMARY_TEXT
            hover_bg = config.COLOR_PRIMARY_DARK
        elif style == "secondary":
            bg_color = config.COLOR_SECONDARY
            fg_color = config.COLOR_SECONDARY_TEXT
            hover_bg = config.COLOR_SECONDARY_DARK
        elif style == "error":
            bg_color = config.COLOR_ERROR
            fg_color = "white"
            hover_bg = "#D32F2F"  # Red 700
        elif style == "text":
            bg_color = config.COLOR_BACKGROUND
            fg_color = config.COLOR_PRIMARY
            hover_bg = config.COLOR_PRIMARY_LIGHT
        else:  # Default/outline
            bg_color = config.COLOR_SURFACE
            fg_color = config.COLOR_PRIMARY
            hover_bg = config.COLOR_BACKGROUND_LIGHT
        
        # Button properties
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.hover_bg = hover_bg
        self.is_disabled = False
        
        # Create the button
        self.configure(background=bg_color)
        
        # Create the label inside the button frame
        self.label = ttk.Label(
            self, 
            text=text,
            background=bg_color,
            foreground=fg_color,
            font=config.FONT_BUTTON,
            anchor="center"
        )
        self.label.pack(padx=config.SPACING_MEDIUM, pady=config.SPACING_SMALL, fill="both", expand=True)
        
        # Bind events
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.label.bind("<Button-1>", self._on_click)
        self.label.bind("<ButtonRelease-1>", self._on_release)
        
        # Store command
        self._command = command
    
    def _on_enter(self, event):
        if not self.is_disabled:
            self.configure(background=self.hover_bg)
            self.label.configure(background=self.hover_bg)
    
    def _on_leave(self, event):
        if not self.is_disabled:
            self.configure(background=self.bg_color)
            self.label.configure(background=self.bg_color)
    
    def _on_click(self, event):
        if not self.is_disabled:
            # Darken on click
            darker_bg = self._darken_color(self.hover_bg, 20)
            self.configure(background=darker_bg)
            self.label.configure(background=darker_bg)
    
    def _on_release(self, event):
        if not self.is_disabled:
            # Return to hover state
            self.configure(background=self.hover_bg)
            self.label.configure(background=self.hover_bg)
            if self._command:
                self._command()
    
    def _darken_color(self, hex_color, percent):
        """Darken a hex color by the given percentage"""
        # Convert hex to RGB
        h = hex_color.lstrip('#')
        rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
        
        # Darken RGB values
        new_rgb = tuple(max(0, int(c * (1 - percent/100))) for c in rgb)
        
        # Convert back to hex
        return f'#{new_rgb[0]:02x}{new_rgb[1]:02x}{new_rgb[2]:02x}'
    
    def config(self, **kwargs):
        """Configure the button properties"""
        if 'state' in kwargs:
            state = kwargs.pop('state')
            self.is_disabled = (state == 'disabled')
            
            if self.is_disabled:
                self.configure(background=config.COLOR_BACKGROUND_LIGHT)
                self.label.configure(
                    background=config.COLOR_BACKGROUND_LIGHT, 
                    foreground=config.COLOR_TEXT_DISABLED
                )
            else:
                self.configure(background=self.bg_color)
                self.label.configure(background=self.bg_color, foreground=self.fg_color)
        
        if 'text' in kwargs:
            text = kwargs.pop('text')
            self.label.configure(text=text)
        
        if 'command' in kwargs:
            self._command = kwargs.pop('command')
        
        # Pass any remaining kwargs to the Frame config
        if kwargs:
            super().config(**kwargs)
    
    # Alias configure to config for ttk compatibility
    configure = config


class VideoDisplayFrame(ttk.Frame):
    """Frame for displaying video frames"""
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        
        # Create a card-like frame for the video display
        self.card_frame = ttk.Frame(self, style="Card.TFrame")
        self.card_frame.pack(fill="both", expand=True, padx=2, pady=2)
        
        # Create label for displaying video frames
        self.display_label = ttk.Label(self.card_frame)
        self.display_label.pack(expand=True, fill="both")
        
        # Store initial dimensions
        self.current_width = kwargs.get('width', 640) 
        self.current_height = kwargs.get('height', 480)
        
        # Create default empty image based on initial dimensions
        self.empty_image = ImageTk.PhotoImage(Image.new("RGB", (self.current_width if self.current_width > 0 else 1, self.current_height if self.current_height > 0 else 1), (33, 33, 33)))
        self.display_label.config(image=self.empty_image)
        
        # Store current PhotoImage to prevent garbage collection
        self.current_image = self.empty_image
        self.last_raw_frame = None # Store the last unprocessed frame

        # Bind resize event
        self.bind("<Configure>", self._on_resize)
    
    def _on_resize(self, event):
        """Handle widget resize events."""
        # Update dimensions if they have actually changed and are reasonable
        if (self.current_width != event.width or self.current_height != event.height) and event.width > 10 and event.height > 10:
            self.current_width = event.width
            self.current_height = event.height
            # If a frame was previously displayed, update it with the new size
            if self.last_raw_frame is not None:
                self._update_display_with_frame(self.last_raw_frame, resize=True)

    def _update_display_with_frame(self, frame_to_display, resize=True):
        """Internal method to process and display a frame, with optional resizing."""
        if frame_to_display is None:
            self.display_label.config(image=self.empty_image)
            self.current_image = self.empty_image
            return

        frame_rgb = cv2.cvtColor(frame_to_display, cv2.COLOR_BGR2RGB)
        
        if resize and self.current_width > 10 and self.current_height > 10:
            original_height, original_width = frame_rgb.shape[:2]
            if original_width > 0 and original_height > 0:
                aspect_ratio = original_width / original_height
                
                new_width = self.current_width
                new_height = int(new_width / aspect_ratio)
                
                if new_height > self.current_height:
                    new_height = self.current_height
                    new_width = int(new_height * aspect_ratio)
                
                # Ensure dimensions are positive and valid
                new_width = max(1, new_width)
                new_height = max(1, new_height)

                # Only resize if new dimensions are different to avoid unnecessary processing
                if new_width != original_width or new_height != original_height:
                    resized_frame_rgb = cv2.resize(frame_rgb, (new_width, new_height), interpolation=cv2.INTER_AREA)
                    pil_image = Image.fromarray(resized_frame_rgb)
                else:
                    pil_image = Image.fromarray(frame_rgb) # Use original if no resize needed
            else: # Fallback for invalid original dimensions
                pil_image = Image.fromarray(frame_rgb)
        else: # No resize requested or dimensions too small
            pil_image = Image.fromarray(frame_rgb)
            
        photo_image = ImageTk.PhotoImage(pil_image)
        self.display_label.config(image=photo_image)
        self.current_image = photo_image

    def update_frame(self, frame):
        """Update the displayed frame
        
        Args:
            frame: OpenCV BGR format frame (numpy array)
        """
        if frame is not None:
            self.last_raw_frame = frame.copy() # Store a copy of the raw frame
        else:
            self.last_raw_frame = None
            
        self._update_display_with_frame(self.last_raw_frame, resize=True)
    
    def clear(self):
        """Clear the display"""
        self.display_label.config(image=self.empty_image)
        self.current_image = self.empty_image


# Create UI components
def create_ui_components(root):
    """Create all UI components for the application
    
    Args:
        root: Root Tkinter window
        
    Returns:
        Dictionary of UI components
    """
    # Set up Material Design theme
    style = setup_material_theme()
    
    # File upload section
    file_upload_frame = ttk.Frame(root, style="Card.TFrame")
    file_upload_button = ttk.Button(
        file_upload_frame, 
        text="Upload File",
        style="Primary.TButton"
    )
    file_upload_label = ttk.Label(file_upload_frame, text="No file selected", width=60, anchor="w")
    
    # Use grid for better alignment within file_upload_frame
    file_upload_button.grid(row=0, column=0, padx=config.SPACING_MEDIUM, pady=config.SPACING_MEDIUM, sticky="w")
    file_upload_label.grid(row=0, column=1, padx=config.SPACING_MEDIUM, pady=config.SPACING_MEDIUM, sticky="ew")
    file_upload_frame.grid_columnconfigure(1, weight=1) # Allow label to expand
    
    # Processing buttons
    process_buttons_frame = ttk.Frame(root, style="Card.TFrame")
    process_button = ttk.Button(
        process_buttons_frame,
        text="Process Real-time",
        style="Primary.TButton",
        state="disabled"
    )
    fast_process_button = ttk.Button(
        process_buttons_frame,
        text="Fast Process Video",
        style="Secondary.TButton",
        state="disabled"
    )
    process_button.pack(side="left", padx=config.SPACING_MEDIUM, pady=config.SPACING_MEDIUM)
    fast_process_button.pack(side="left", padx=config.SPACING_MEDIUM, pady=config.SPACING_MEDIUM)
    
    # Model selection
    model_selector_frame = ttk.LabelFrame(root, text="Model Selection", style="Card.TFrame")
    model_var = tk.StringVar()
    model_buttons = []  # Will be populated later with available models
    
    # Threshold sliders with improved appearance
    sliders_frame = ttk.Frame(root, style="Card.TFrame")
    
    # IoU Threshold
    iou_frame = ttk.Frame(sliders_frame, style="Card.TFrame")
    iou_label = ttk.Label(iou_frame, text="IoU Threshold:", style="Subtitle.TLabel")
    iou_var = tk.DoubleVar(value=config.DEFAULT_IOU_THRESHOLD)
    iou_slider = ttk.Scale(
        iou_frame, 
        from_=0.01, 
        to=1.0, 
        orient="horizontal", 
        variable=iou_var,
        state="disabled"
    )
    iou_value_label = ttk.Label(iou_frame, text=f"{config.DEFAULT_IOU_THRESHOLD:.2f}")
    iou_label.pack(side="left", padx=config.SPACING_MEDIUM)
    iou_slider.pack(side="left", expand=True, fill="x", padx=config.SPACING_MEDIUM)
    iou_value_label.pack(side="left", padx=config.SPACING_MEDIUM)
    
    # Confidence Threshold
    conf_frame = ttk.Frame(sliders_frame, style="Card.TFrame")
    conf_label = ttk.Label(conf_frame, text="Conf Threshold:", style="Subtitle.TLabel")
    conf_var = tk.DoubleVar(value=config.DEFAULT_CONF_THRESHOLD)
    conf_slider = ttk.Scale(
        conf_frame, 
        from_=0.01, 
        to=1.0, 
        orient="horizontal", 
        variable=conf_var,
        state="disabled"
    )
    conf_value_label = ttk.Label(conf_frame, text=f"{config.DEFAULT_CONF_THRESHOLD:.2f}")
    conf_label.pack(side="left", padx=config.SPACING_MEDIUM)
    conf_slider.pack(side="left", expand=True, fill="x", padx=config.SPACING_MEDIUM)
    conf_value_label.pack(side="left", padx=config.SPACING_MEDIUM)
    
    # Pack slider frames
    iou_frame.pack(fill="x", pady=config.SPACING_MEDIUM)
    conf_frame.pack(fill="x", pady=config.SPACING_MEDIUM)
    
    # Output area with monospace font for better readability
    output_frame = ttk.LabelFrame(root, text="Output", style="Card.TFrame")
    output_text = tk.Text(
        output_frame, 
        height=5, 
        width=50, 
        state="disabled",
        font=config.FONT_CODE,
        background=config.COLOR_BACKGROUND_LIGHT,
        foreground=config.COLOR_TEXT_PRIMARY,
        borderwidth=0,
        padx=config.SPACING_SMALL,
        pady=config.SPACING_SMALL
    )
    output_scrollbar = ttk.Scrollbar(output_frame, command=output_text.yview)
    output_text.configure(yscrollcommand=output_scrollbar.set)
    output_text.pack(side="left", fill="both", expand=True, padx=2, pady=2)
    output_scrollbar.pack(side="right", fill="y", padx=0, pady=2)
    
    # Fast progress bar (initially hidden)
    fast_progress_frame = ttk.Frame(root, style="Card.TFrame")
    fast_progress_label = ttk.Label(fast_progress_frame, text="Fast Progress:", style="Subtitle.TLabel")
    fast_progress_var = tk.IntVar(value=0)
    fast_progress_bar = ttk.Progressbar(
        fast_progress_frame, 
        orient="horizontal", 
        mode="determinate", 
        variable=fast_progress_var,
        style="TProgressbar"
    )
    fast_progress_label.pack(side="left", padx=config.SPACING_MEDIUM, pady=config.SPACING_MEDIUM)
    fast_progress_bar.pack(side="left", expand=True, fill="x", padx=config.SPACING_MEDIUM, pady=config.SPACING_MEDIUM)
    
    # Video Player Container
    video_player_container = ttk.Frame(root, style="Card.TFrame")

    # Video display
    video_display = VideoDisplayFrame(
        video_player_container, 
        width=640, 
        height=640, 
        style="Card.TFrame"
    )
    
    # Video controls with improved appearance
    video_controls_frame = ttk.Frame(video_player_container, style="Card.TFrame")
    play_pause_button = ttk.Button(
        video_controls_frame,
        text="Play",
        style="Primary.TButton",
        state="disabled"
    )
    stop_button = ttk.Button(
        video_controls_frame,
        text="Stop",
        style="Secondary.TButton",
        state="disabled"
    )
    play_pause_button.pack(side="left", padx=config.SPACING_MEDIUM, pady=config.SPACING_MEDIUM)
    stop_button.pack(side="left", padx=config.SPACING_MEDIUM, pady=config.SPACING_MEDIUM)
    
    # Video progress with improved appearance
    progress_frame = ttk.Frame(video_player_container, style="Card.TFrame")
    progress_var = tk.IntVar(value=0)
    progress_slider = ttk.Scale(
        progress_frame, 
        from_=0, 
        to=100, 
        orient="horizontal", 
        variable=progress_var,
        state="disabled"
    )
    time_label = ttk.Label(progress_frame, text="00:00 / 00:00", style="Caption.TLabel")
    progress_slider.pack(side="left", expand=True, fill="x", padx=config.SPACING_MEDIUM, pady=config.SPACING_MEDIUM)
    time_label.pack(side="left", padx=config.SPACING_MEDIUM, pady=config.SPACING_MEDIUM)

    # Layout within video_player_container
    video_player_container.columnconfigure(0, weight=1)
    video_player_container.rowconfigure(0, weight=0)  # Controls row
    video_player_container.rowconfigure(1, weight=0)  # Progress row
    video_player_container.rowconfigure(2, weight=1)  # Video display row (expandable)

    video_controls_frame.grid(row=0, column=0, sticky="ew", padx=2, pady=(2,0))
    progress_frame.grid(row=1, column=0, sticky="ew", padx=2, pady=(0,2))
    video_display.grid(row=2, column=0, sticky="nsew", padx=2, pady=2)
    
    # Return UI components in a dictionary
    return {
        "file_upload_frame": file_upload_frame,
        "file_upload_button": file_upload_button,
        "file_upload_label": file_upload_label,
        "process_buttons_frame": process_buttons_frame,
        "process_button": process_button,
        "fast_process_button": fast_process_button,
        "model_selector_frame": model_selector_frame,
        "model_var": model_var,
        "model_buttons": model_buttons,
        "sliders_frame": sliders_frame,
        "iou_slider": iou_slider,
        "iou_var": iou_var,
        "iou_value_label": iou_value_label,
        "conf_slider": conf_slider,
        "conf_var": conf_var,
        "conf_value_label": conf_value_label,
        "output_frame": output_frame,
        "output_text": output_text,
        "fast_progress_frame": fast_progress_frame,
        "fast_progress_bar": fast_progress_bar,
        "fast_progress_var": fast_progress_var,
        "video_player_container": video_player_container,
        "video_display": video_display,
        "video_controls_frame": video_controls_frame,
        "play_pause_button": play_pause_button,
        "stop_button": stop_button,
        "progress_frame": progress_frame,
        "progress_slider": progress_slider,
        "progress_var": progress_var,
        "time_label": time_label
    } 