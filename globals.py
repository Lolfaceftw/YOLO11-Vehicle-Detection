import threading

# --- Global State for Video Processing ---\n",
video_thread = None
stop_video_processing_flag = threading.Event()
video_paused_flag = threading.Event()
current_video_frame = None # Stores the raw frame (numpy array)
video_capture_global = None # Holds the cv2.VideoCapture object
video_access_lock = threading.Lock() # For synchronizing access to video_capture_global

# --- Global State for Fast (Batch) Video Processing ---\n",
fast_video_processing_thread = None
stop_fast_processing_flag = threading.Event()
processed_video_temp_file_path_global = None # Path to the fully processed temporary video file
fast_processing_active_flag = threading.Event()

# --- Global State for Slider Debouncing ---\n",
slider_debounce_timer = None
slider_target_frame_value = 0 # Target frame for debounced seek

# --- Global State for Model Management and Thresholds ---\n",
iou_threshold_global = 0.45 # Current IoU threshold
conf_threshold_global = 0.25 # Current Confidence threshold

# AVAILABLE_MODELS structure will be initialized in model_loader.py
# active_model_key, active_model_object_global, active_class_list_global,
# active_processed_class_filter_global, device_to_use will also be managed by model_loader.py
# and accessed via its functions or stored here if truly global access is simpler.
# For now, let model_loader manage them internally and expose via getters if needed,
# or ui_callbacks can update them here after model_loader operations.

# Let's define them here for now as they are accessed/modified by callbacks directly
# based on model_loader's results.
active_model_key = None
active_model_object_global = None
active_class_list_global = {}
active_processed_class_filter_global = None
device_to_use = 'cpu'


# --- UI State and File Info ---\n",
# current_video_meta stores {'fps': 0.0, 'total_frames': 0, 'duration_seconds': 0.0}
current_video_meta = {'fps': 0.0, 'total_frames': 0, 'duration_seconds': 0.0}
uploaded_file_info = {} # Stores info of the last uploaded file

# References to specific UI widgets that need to be globally accessible for updates
# These will be assigned when UI elements are created in main_app.py
ui_stack_widget = None
main_output_area_widget = None
processed_image_display_area_widget = None

# Video player specific widgets that are frequently managed by threads/callbacks
# These will also be assigned from ui_elements instances
video_display_widget_ref = None
play_pause_button_ref = None
stop_button_ref = None
progress_slider_ref = None
time_label_ref = None
fast_progress_bar_ref = None

# UI-related globals are no longer needed here as they're managed by the Tkinter implementation
# The Tkinter UI components are managed in tk_ui_callbacks.py using a dictionary