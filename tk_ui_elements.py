# app/tk_ui_elements.py
"""
Main orchestrator for creating Tkinter UI elements.
Imports UI styles, custom widgets, and layout sections.
"""
import tkinter as tk # Keep basic tk import if needed for tk.StringVar etc.
# from tkinter import ttk # ttk is mostly used within the imported modules now

# Import from the new modularized UI files
from .ui_styles import setup_material_theme
# ui_custom_widgets are used within ui_layout_sections, so not directly needed here
from . import ui_layout_sections as sections 
# from . import config # config is used by imported modules

def create_ui_components(root_window, parent_left_panel, parent_right_panel):
    """
    Create all UI components for the application by calling section-specific helpers
    from ui_layout_sections.
    """
    setup_material_theme() # Initialize styles first
    
    ui_components_dict = {}

    # Create sections for the left panel
    ui_components_dict.update(sections.create_file_upload_section(parent_left_panel))
    ui_components_dict.update(sections.create_process_buttons_section(parent_left_panel))
    ui_components_dict.update(sections.create_model_selector_section(parent_left_panel))
    ui_components_dict.update(sections.create_threshold_sliders_section(parent_left_panel))
    ui_components_dict.update(sections.create_fast_progress_section(parent_left_panel))
    
    # Create sections for the right panel
    ui_components_dict.update(sections.create_video_player_section(parent_right_panel))
    
    return ui_components_dict
