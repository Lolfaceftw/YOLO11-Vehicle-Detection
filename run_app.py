#!/usr/bin/env python
"""
Vehicle Detection and Tracking Application - Standalone Version
Run this script to launch the application in a standalone window.
"""

import argparse
import os
import sys

# Ensure the 'app' directory is in the Python path *before* importing config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import config # Import config first to allow overriding IS_DEBUG_MODE

def main():
    parser = argparse.ArgumentParser(description="Vehicle Detection and Tracking Application.")
    parser.add_argument(
        "--debug", 
        action="store_true", 
        help="Enable debug logging to debug.log"
    )
    args = parser.parse_args()

    # Set IS_DEBUG_MODE in the config module based on the command-line argument
    # This must be done before other app modules (like logger_setup or main_app) are imported,
    # as they rely on config.IS_DEBUG_MODE at their import time.
    if args.debug:
        config.IS_DEBUG_MODE = True
    # If not args.debug, config.IS_DEBUG_MODE remains its default (False)

    # Now that config.IS_DEBUG_MODE is set, proceed with other imports
    from app.main_app import launch_app
    from app.logger_setup import log_debug # This will now respect the debug mode set above

    print("Starting YOLO Object Detection application...")
    log_debug(f"run_app.py: main() executed. Debug mode: {config.IS_DEBUG_MODE}")
    launch_app()

if __name__ == "__main__":
    main()