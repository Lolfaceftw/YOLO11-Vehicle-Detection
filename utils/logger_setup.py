import logging
import os # Added for os.path.abspath
from app import config 

app_logger = None

def setup_logging():
    global app_logger
    print(f"logger_setup.py: setup_logging() called. config.IS_DEBUG_MODE = {config.IS_DEBUG_MODE}")

    # Ensure logger is created if it's None
    if app_logger is None:
        app_logger = logging.getLogger('VehicleDetectionApp')
        # Set level on the logger itself, handlers can have their own levels too
        app_logger.setLevel(logging.DEBUG if config.IS_DEBUG_MODE else logging.INFO) 
    
    # Clear existing handlers to prevent duplicate messages if called multiple times
    if app_logger.hasHandlers():
        print("logger_setup.py: Clearing existing handlers.")
        app_logger.handlers.clear()

    if config.IS_DEBUG_MODE:
        try:
            log_file_path = os.path.abspath(config.DEBUG_LOG_FILE)
            print(f"logger_setup.py: Attempting to set up FileHandler for: {log_file_path}")
            
            fh = logging.FileHandler(log_file_path, mode='w')
            fh.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(threadName)s - %(funcName)s - %(message)s')
            fh.setFormatter(formatter)
            app_logger.addHandler(fh)
            # app_logger.info("Logging initialized to file.") # This would go to file if successful
            print(f"logger_setup.py: Logging to file {log_file_path} initialized.")
        except Exception as e:
            print(f"logger_setup.py: Error setting up file logger for {config.DEBUG_LOG_FILE}: {e}") 
            # Fallback to basic console logging for debug messages if file handler fails
            logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(threadName)s - %(funcName)s - %(message)s')
            app_logger = logging.getLogger('VehicleDetectionApp') # re-get logger after basicConfig
            app_logger.warning("File logger setup failed. Using basic console logging for debug messages.")
            print("logger_setup.py: File logger setup failed. Using basic console logging.")
    else: 
        # For non-debug mode, ensure it still logs INFO and above to console by default if no other handler is added.
        # Or, add a NullHandler if truly no output is desired unless other handlers are added elsewhere.
        # For now, let's make it output INFO to console if not debug.
        if not app_logger.hasHandlers(): # Add a console handler if none exist (e.g. for non-debug mode)
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO) # Or whatever level is desired for non-debug console output
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            ch.setFormatter(formatter)
            app_logger.addHandler(ch)
            print("logger_setup.py: Debug mode is OFF. Configured basic console logging for INFO level.")
        app_logger.propagate = False


def log_debug(message, exc_info=False):
    if app_logger and config.IS_DEBUG_MODE:
        app_logger.debug(message, exc_info=exc_info)
    elif not config.IS_DEBUG_MODE:
        pass 
    else: 
        # This case means app_logger is None, which shouldn't happen if setup_logging is called first.
        # Fallback to print for critical debug messages if logger isn't ready.
        print(f"DEBUG (logger not ready): {message}")

# Removed automatic call to setup_logging() at module import.
# It will be explicitly called by run_app.py after config is set.
print("logger_setup.py: Module loaded (setup_logging() NOT called automatically).")
