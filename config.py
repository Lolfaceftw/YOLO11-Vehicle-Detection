import os

# --- Configuration ---\n",
IS_DEBUG_MODE = False # Default to False, will be overridden by run_app.py if --debug is used
DEBUG_LOG_FILE = 'debug.log'

# Determine base path for model files. Assumes models are in a 'data' subdirectory
# relative to the project root, or in the project root itself.
# For this refactoring, let's assume the main script launching this app is in the project root.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
MODEL_DATA_PATH = os.path.join(PROJECT_ROOT, 'data') # Standardized path for models

# Check if 'data' directory exists, otherwise use project root
if not os.path.isdir(MODEL_DATA_PATH):
    MODEL_DATA_PATH = PROJECT_ROOT


YOLO_MODEL_FILENAME = 'yolo11x.pt'
RTDETR_MODEL_FILENAME = 'rtdetr-x.pt' # Ultralytics might download this if not found locally

YOLO_MODEL_PATH = os.path.join(MODEL_DATA_PATH, YOLO_MODEL_FILENAME)
RTDETR_MODEL_PATH = RTDETR_MODEL_FILENAME # Let Ultralytics handle path/download for standard models

YOLO_CLASS_FILTER_INDICES = [1, 2, 3, 5, 7] # bicycle, car, motorcycle, bus, truck (typical for COCO)
DEFAULT_MODEL_KEY = "YOLOv11x"

# --- Material Design Color System ---
# Primary colors
COLOR_PRIMARY = '#2196F3'         # Blue 500 (main primary color)
COLOR_PRIMARY_DARK = '#1976D2'    # Blue 700 (dark primary for headers/contrast)
COLOR_PRIMARY_LIGHT = '#BBDEFB'   # Blue 100 (light primary for backgrounds/highlights)
COLOR_PRIMARY_TEXT = '#000000'    # Text color on primary backgrounds

# Secondary/Accent colors
COLOR_SECONDARY = '#4CAF50'       # Green 500 (main secondary/accent color)
COLOR_SECONDARY_DARK = '#388E3C'  # Green 700 (dark secondary)
COLOR_SECONDARY_LIGHT = '#C8E6C9' # Green 100 (light secondary)
COLOR_SECONDARY_TEXT = '#FFFFFF'  # Text color on secondary backgrounds

# Surface colors
COLOR_SURFACE = '#FFFFFF'         # White (cards, dialogs)
COLOR_BACKGROUND = '#FAFAFA'      # Almost white (main background)
COLOR_BACKGROUND_LIGHT = '#F5F5F5' # Grey 100 (alternate background)

# Text colors
COLOR_TEXT_PRIMARY = '#212121'    # Very dark grey (primary text)
COLOR_TEXT_SECONDARY = '#757575'  # Medium grey (secondary text)
COLOR_TEXT_DISABLED = '#9E9E9E'   # Light grey (disabled text)
COLOR_TEXT_HINT = '#9E9E9E'       # Light grey (hint text)

# Additional colors 
COLOR_SUCCESS = '#4CAF50'         # Green 500 (success/positive)
COLOR_WARNING = '#FFC107'         # Amber 500 (warning)
COLOR_ERROR = '#F44336'           # Red 500 (error/negative)
COLOR_INFO = '#2196F3'            # Blue 500 (information)

# Legacy color mappings (for backward compatibility)
COLOR_ACCENT = COLOR_SECONDARY
COLOR_TEXT_ON_PRIMARY = COLOR_PRIMARY_TEXT
COLOR_BUTTON_GREY = '#78909C'     # Blue Grey 400
COLOR_ORANGE_ACCENT = '#FF9800'   # Orange 500

# --- Elevation (Shadow Effects) ---
# CSS-like shadow definitions for simulating Material elevation
SHADOW_NONE = ''
SHADOW_LOW = '0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24)'  # Elevation 1dp
SHADOW_MEDIUM = '0 3px 6px rgba(0,0,0,0.16), 0 3px 6px rgba(0,0,0,0.23)'  # Elevation 3dp
SHADOW_HIGH = '0 10px 20px rgba(0,0,0,0.19), 0 6px 6px rgba(0,0,0,0.23)'  # Elevation 6dp

# --- Spacing & Layout ---
SPACING_UNIT = 8        # Base unit for spacing in pixels
SPACING_SMALL = 8       # Small spacing (1x)
SPACING_MEDIUM = 16     # Medium spacing (2x)
SPACING_LARGE = 24      # Large spacing (3x)
SPACING_XLARGE = 32     # Extra large spacing (4x)
SPACING_XXLARGE = 48    # Double extra large spacing (6x)

# Border radius for rounded corners
BORDER_RADIUS_SMALL = 4     # Small rounding
BORDER_RADIUS_MEDIUM = 8    # Medium rounding
BORDER_RADIUS_LARGE = 16    # Large rounding (for cards)
BORDER_RADIUS_FULL = 999    # Full rounding (for pills/FABs)

# --- Typography ---
# Font families
FONT_FAMILY_PRIMARY = "Segoe UI"  # Primary font family
FONT_FAMILY_MONO = "Consolas"     # Monospace font for code/output

# Font styles/sizes
FONT_DISPLAY = (FONT_FAMILY_PRIMARY, 24, "bold")      # Large title text
FONT_TITLE = (FONT_FAMILY_PRIMARY, 20, "bold")        # Section titles
FONT_SUBTITLE = (FONT_FAMILY_PRIMARY, 16, "bold")     # Subtitle text
FONT_BODY = (FONT_FAMILY_PRIMARY, 12, "normal")       # Normal body text
FONT_CAPTION = (FONT_FAMILY_PRIMARY, 10, "normal")    # Small caption text
FONT_BUTTON = (FONT_FAMILY_PRIMARY, 12, "bold")       # Button text
FONT_CODE = (FONT_FAMILY_MONO, 12, "normal")          # Monospace/code text

# Legacy font definitions (for backward compatibility)
FONT_SPINNER = (FONT_FAMILY_PRIMARY, 28, "bold")
FONT_MESSAGE_OVERLAY = (FONT_FAMILY_PRIMARY, 12, "normal")

# --- Slider Debouncing Interval ---
SLIDER_DEBOUNCE_INTERVAL = 0.25

# --- Default Thresholds ---
DEFAULT_IOU_THRESHOLD = 0.45
DEFAULT_CONF_THRESHOLD = 0.25

# --- Loading Overlay Configuration ---
OVERLAY_BACKGROUND_COLOR = '#212121'    # Dark gray background (converted from rgba(33, 33, 33, 0.7))
OVERLAY_ALPHA = 0.85                    # Higher opacity for better contrast
OVERLAY_FRAME_COLOR = COLOR_SURFACE     # White frame for spinner and message

# Material Design circular progress indicator frames (spinner frames)
UNICODE_SPINNER_FRAMES = ["◜", "◠", "◝", "◞", "◡", "◟"]  # More modern spinner characters
UNICODE_SPINNER_DELAY_MS = 100
