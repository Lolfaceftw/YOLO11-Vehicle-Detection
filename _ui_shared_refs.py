# _ui_shared_refs.py
"""
Module to hold shared references for the Tkinter UI callback system.
This helps avoid circular dependencies and makes shared state explicit.
"""

# These will be populated by init_shared_refs in tk_ui_callbacks.py
ui_components = {}
root_window = None
loading_overlay = None # Managed by functions in _ui_loading_manager

def init_shared_refs(components_dict, root_ref):
    """Initialize the shared UI component dictionary and root window reference."""
    global ui_components, root_window
    ui_components = components_dict
    root_window = root_ref

def get_component(name):
    """Access a UI component by its name."""
    return ui_components.get(name)

def get_root():
    """Access the root window."""
    return root_window

def get_loading_overlay_ref():
    """Get the current loading overlay instance."""
    global loading_overlay
    return loading_overlay

def set_loading_overlay_ref(overlay_instance):
    """Set the current loading overlay instance."""
    global loading_overlay
    loading_overlay = overlay_instance
