#!/usr/bin/env python
"""
Vehicle Detection and Tracking Application - Standalone Version
Run this script from the project root directory (the parent of 'app')
e.g., python -m app.run_app --debug  OR  python app/run_app.py --debug
"""

import argparse
import os
import sys

# To make 'from app import ...' work correctly when run_app.py is executed as a script
# from the project root, ensure the project root is in sys.path.
# If run_app.py is 'app/run_app.py', and CWD is project root, this is usually automatic.
# If using 'python -m app.run_app', Python handles path setup.

# For robustness if script is run directly like 'python app/run_app.py':
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.utils.logger_setup import log_debug # Ensure log_debug is imported if not already for the new line
log_debug("app.run_app module initialized.")

def main():
    parser = argparse.ArgumentParser(description="Vehicle Detection and Tracking Application.")
    parser.add_argument(
        "--debug", 
        action="store_true", 
        help="Enable debug logging to debug.log"
    )
    args = parser.parse_args()

    # --- Step 1: Import config and set IS_DEBUG_MODE ---
    # Assuming 'app' is a package visible from the project root.
    from app import config 
    if args.debug:
        print("Debug mode explicitly enabled via --debug flag.")
        config.IS_DEBUG_MODE = True
    else:
        print(f"Debug mode not enabled via flag. Defaulting to config.IS_DEBUG_MODE = {config.IS_DEBUG_MODE}")

    # --- Step 2: Now that config.IS_DEBUG_MODE is set, setup logging ---
    from app.utils.logger_setup import setup_logging, log_debug # Corrected import
    
    print(f"run_app.py: Re-initializing logger with IS_DEBUG_MODE = {config.IS_DEBUG_MODE}")
    setup_logging() 
    log_debug("run_app.py: Application starting...") # Restored log

    # --- Step 3: Proceed with other application imports and launch ---
    from app.core.main_app import launch_app # Corrected import
    
    log_debug(f"run_app.py: main() executed. Debug mode from config: {config.IS_DEBUG_MODE}")
    print(f"Starting YOLO Object Detection application... Debug active: {config.IS_DEBUG_MODE}")
    launch_app()

if __name__ == "__main__":
    # This structure is designed to be run from the project's root directory.
    # For example:
    # C:\...\Vehicle-detection-and-tracking-classwise-using-YOLO11> python app/run_app.py --debug
    # OR
    # C:\...\Vehicle-detection-and-tracking-classwise-using-YOLO11> python -m app.run_app --debug
    main()
