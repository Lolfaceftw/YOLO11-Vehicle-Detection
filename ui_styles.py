# app/ui_styles.py
"""
Contains the theme and style setup for the Tkinter UI.
"""
import tkinter as tk
from tkinter import ttk
from . import config

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
    style.configure("Overlay.TFrame", background=config.OVERLAY_BACKGROUND_COLOR, relief="flat", borderwidth=0)
    style.configure("Overlay.TLabel", background=config.OVERLAY_FRAME_COLOR, foreground=config.COLOR_TEXT_PRIMARY, font=config.FONT_MESSAGE_OVERLAY)
    
    # Enhanced content area for overlay
    style.configure("OverlayContent.TFrame", background=config.OVERLAY_FRAME_COLOR, relief="raised", borderwidth=2)
    style.map("OverlayContent.TFrame", 
             background=[('active', config.OVERLAY_FRAME_COLOR)],
             relief=[('active', 'raised')])
    return style
