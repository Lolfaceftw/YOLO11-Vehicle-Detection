import logging
from . import config

app_logger = None

def setup_logging():
    global app_logger
    if config.IS_DEBUG_MODE:
        app_logger = logging.getLogger('VehicleDetectionApp')
        app_logger.setLevel(logging.DEBUG)
        
        if app_logger.hasHandlers():
            app_logger.handlers.clear()
        
        try:
            fh = logging.FileHandler(config.DEBUG_LOG_FILE, mode='w')
            fh.setLevel(logging.DEBUG)
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(threadName)s - %(funcName)s - %(message)s')
            fh.setFormatter(formatter)
            app_logger.addHandler(fh)
            app_logger.info("Logging initialized.")
        except Exception as e:
            print(f"Error setting up file logger: {e}") # Print error if logger setup fails
            # Fallback to basic console logging for debug messages if file handler fails
            if not app_logger.hasHandlers(): # ensure we don't add duplicate basicConfig if called again
                logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(threadName)s - %(funcName)s - %(message)s')
                app_logger = logging.getLogger('VehicleDetectionApp') # re-get logger after basicConfig
                app_logger.warning("File logger setup failed. Using basic console logging for debug messages.")

    else:
        app_logger = logging.getLogger('VehicleDetectionApp')
        if app_logger.hasHandlers(): app_logger.handlers.clear()
        app_logger.addHandler(logging.NullHandler())
        app_logger.propagate = False

def log_debug(message, exc_info=False):
    if config.IS_DEBUG_MODE and app_logger:
        app_logger.debug(message, exc_info=exc_info)

# Initialize logging system when this module is imported
setup_logging()
log_debug("Logger setup complete.")