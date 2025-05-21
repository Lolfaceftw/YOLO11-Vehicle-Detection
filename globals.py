import threading

# --- Global State for Video Processing ---\n",
video_thread = None 
stop_video_processing_flag = threading.Event() 
video_paused_flag = threading.Event()
current_video_frame = None 
video_capture_global = None 
video_access_lock = threading.Lock() 
is_playing_via_after_loop = False 
after_id_playback_loop = None 

# --- FPS Counter Globals ---
real_time_fps_frames_processed = 0
real_time_fps_last_update_time = 0.0
real_time_fps_display_value = 0.0
prev_fps_value = 0.0

# --- Performance Tracking ---
heavy_frame_count = 0
frame_process_counter = 0
skip_processing_count = 0

# --- Seek Operation Tracking ---
last_seek_requested = False  # Flag to indicate a seek was requested
seek_in_progress = False     # Flag to indicate an active seek operation
seek_target_frame = 0        # Target frame position for current seek
seek_start_time = 0.0        # Timestamp when seek started
seek_complete_callback = None  # Function to call when seek completes
seek_lock = threading.Lock() # Lock for thread-safe seek operations

# --- Global State for Fast (Batch) Video Processing ---\n",
fast_video_processing_thread = None
stop_fast_processing_flag = threading.Event()
processed_video_temp_file_path_global = None 
fast_processing_active_flag = threading.Event()

# --- Global State for Slider Debouncing ---\n",
slider_debounce_timer = None
slider_target_frame_value = 0 
is_programmatic_slider_update = False 

# --- Global State for Model Management and Thresholds ---\n",
iou_threshold_global = 0.45 
conf_threshold_global = 0.25 

active_model_key = None
active_model_object_global = None
active_class_list_global = {}
active_processed_class_filter_global = None
device_to_use = 'cpu'


# --- UI State and File Info ---\n",
current_video_meta = {'fps': 0.0, 'total_frames': 0, 'duration_seconds': 0.0, 'current_frame': 0} 
uploaded_file_info = {} 

current_processed_image_for_display = None 
