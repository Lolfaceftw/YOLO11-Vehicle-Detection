import os

# --- Configuration ---
IS_DEBUG_MODE = False # Default to False, will be overridden by run_app.py if --debug is used
DEBUG_LOG_FILE = 'debug.log' # This will be created in the directory where run_app.py is executed.

# Assuming run_app.py is in 'app/' and this config.py will also be in 'app/'
# PROJECT_ROOT will be the parent of 'app/', e.g., 'Vehicle-detection-and-tracking-classwise-using-YOLO11/'
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Centralized model directory within the 'app' structure
# os.path.dirname(__file__) will be 'app/' if this config.py is in 'app/'
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')

# MODEL_DATA_PATH should be the absolute path to app/models
MODEL_DATA_PATH = os.path.abspath(MODEL_DIR)


YOLO_MODEL_FILENAME = 'yolo11x.pt' # Placeholder, actual file might not exist
YOLO11S_SMALL_TRAINED_FILENAME = 'yolo11s-small_trained.pt'
RTDETR_MODEL_FILENAME = 'rtdetr-x.pt'

YOLO_MODEL_PATH = os.path.join(MODEL_DATA_PATH, YOLO_MODEL_FILENAME)
YOLO11S_SMALL_TRAINED_PATH = os.path.join(MODEL_DATA_PATH, YOLO11S_SMALL_TRAINED_FILENAME)
RTDETR_MODEL_PATH = os.path.join(MODEL_DATA_PATH, RTDETR_MODEL_FILENAME)

# Check if the model files actually exist, log if not (requires logger to be set up)
# This is more for runtime check, not strictly config.
# import logging # Would import app.utils.logger_setup later
# if not os.path.exists(YOLO11S_SMALL_TRAINED_PATH):
#     logging.warning(f"Model file not found: {YOLO11S_SMALL_TRAINED_PATH}")
# if not os.path.exists(RTDETR_MODEL_PATH):
#     logging.warning(f"Model file not found: {RTDETR_MODEL_PATH}")


YOLO_CLASS_FILTER_INDICES = [1, 2, 3, 5, 7]
DEFAULT_MODEL_KEY = "YOLOv11s_small" # Changed to reflect available model

# --- Material Design Color System ---
COLOR_PRIMARY = '#2196F3'         
COLOR_PRIMARY_DARK = '#1976D2'    
COLOR_PRIMARY_LIGHT = '#BBDEFB'   
COLOR_PRIMARY_TEXT = '#000000'    

COLOR_SECONDARY = '#4CAF50'       
COLOR_SECONDARY_DARK = '#388E3C'  
COLOR_SECONDARY_LIGHT = '#C8E6C9' 
COLOR_SECONDARY_TEXT = '#FFFFFF'  

COLOR_SURFACE = '#FFFFFF'         
COLOR_BACKGROUND = '#FAFAFA'      
COLOR_BACKGROUND_LIGHT = '#F5F5F5' 

COLOR_TEXT_PRIMARY = '#212121'    
COLOR_TEXT_SECONDARY = '#757575'  
COLOR_TEXT_DISABLED = '#9E9E9E'   
COLOR_TEXT_HINT = '#9E9E9E'       

COLOR_SUCCESS = '#4CAF50'         
COLOR_WARNING = '#FFC107'         
COLOR_ERROR = '#F44336'           
COLOR_INFO = '#2196F3'            

COLOR_ACCENT = COLOR_SECONDARY
COLOR_TEXT_ON_PRIMARY = COLOR_PRIMARY_TEXT
COLOR_BUTTON_GREY = '#78909C'     
COLOR_ORANGE_ACCENT = '#FF9800'   

# --- Elevation (Shadow Effects) ---
SHADOW_NONE = ''
SHADOW_LOW = '0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24)'  
SHADOW_MEDIUM = '0 3px 6px rgba(0,0,0,0.16), 0 3px 6px rgba(0,0,0,0.23)'  
SHADOW_HIGH = '0 10px 20px rgba(0,0,0,0.19), 0 6px 6px rgba(0,0,0,0.23)'  

# --- Spacing & Layout ---
SPACING_UNIT = 8        
SPACING_SMALL = 8       
SPACING_MEDIUM = 16     
SPACING_LARGE = 24      
SPACING_XLARGE = 32     
SPACING_XXLARGE = 48    

BORDER_RADIUS_SMALL = 4     
BORDER_RADIUS_MEDIUM = 8    
BORDER_RADIUS_LARGE = 16    
BORDER_RADIUS_FULL = 999    

# --- Typography ---
FONT_FAMILY_PRIMARY = "Segoe UI"  
FONT_FAMILY_MONO = "Consolas"     

FONT_DISPLAY = (FONT_FAMILY_PRIMARY, 24, "bold")      
FONT_TITLE = (FONT_FAMILY_PRIMARY, 20, "bold")        
FONT_SUBTITLE = (FONT_FAMILY_PRIMARY, 16, "bold")     
FONT_BODY = (FONT_FAMILY_PRIMARY, 12, "normal")       
FONT_CAPTION = (FONT_FAMILY_PRIMARY, 10, "normal")    
FONT_BUTTON = (FONT_FAMILY_PRIMARY, 12, "bold")       
FONT_CODE = (FONT_FAMILY_MONO, 12, "normal")          

FONT_SPINNER_LEGACY = (FONT_FAMILY_PRIMARY, 28, "bold") 
FONT_COE_SPINNER = (FONT_FAMILY_PRIMARY, 10, "bold") 
FONT_MESSAGE_OVERLAY = (FONT_FAMILY_PRIMARY, 12, "normal")

# --- Slider Debouncing Interval ---
SLIDER_DEBOUNCE_INTERVAL = 0.25

# --- Default Thresholds ---
DEFAULT_IOU_THRESHOLD = 0.45
DEFAULT_CONF_THRESHOLD = 0.25

# --- Loading Overlay Configuration ---
OVERLAY_BACKGROUND_COLOR = '#212121'    
OVERLAY_ALPHA = 0.85                    
OVERLAY_FRAME_COLOR = COLOR_SURFACE     

UNICODE_SPINNER_FRAMES = ["◜", "◠", "◝", "◞", "◡", "◟"]
UNICODE_SPINNER_DELAY_MS = 100

# CoE 197Z Spinner Configuration
COE_SPINNER_TEXT = "CoE197Z "  # Space moved to the end
COE_SPINNER_RADIUS = 20  
COE_SPINNER_DELAY_MS = 75 
COE_SPINNER_ROTATION_STEP = 15 