# app/_ui_async_logic.py
"""
Handles asynchronous operations and the main video playback loop.
"""
import os
import cv2
import threading
import time 
from tkinter import messagebox 

from . import _ui_shared_refs as refs
from . import _ui_loading_manager as loading_manager 
from . import globals as app_globals
from .logger_setup import log_debug
from .frame_processor import process_frame_yolo
from .video_handler import format_time_display, _cleanup_processed_video_temp_file, \
                           fast_video_processing_thread_func 
from .model_loader import load_model as model_loader_load_model


_last_frame_display_time_ns = 0 # Module-level global

def _video_playback_loop(process_frames_real_time: bool):
    """
    Main video playback loop, driven by root.after().
    Handles both real-time processed playback and pre-processed video playback.
    """
    global _last_frame_display_time_ns 
    
    loop_start_time = time.perf_counter_ns()
    log_debug(f"_video_playback_loop: Starting loop, process_frames_real_time={process_frames_real_time}")
    
    # Get UI references safely
    try:
        root = app_globals.ui_references.get("root")
        ui_comps = app_globals.ui_references.get("ui_components_dict", {})
        
        # Early exit checks
        if not root or not root.winfo_exists():
            log_debug("_video_playback_loop: Root window no longer exists, stopping playback")
            app_globals.is_playing_via_after_loop = False
            app_globals.stop_video_processing_flag.set()
            return
        
        # Ensure any available frame is displayed, even if we're just starting
        video_display = ui_comps.get("video_display")
        if video_display and video_display.winfo_exists() and app_globals.current_video_frame is not None:
            video_display.update_frame(app_globals.current_video_frame)
            log_debug("_video_playback_loop: Displayed existing frame at start of loop")
    except Exception as e:
        log_debug(f"_video_playback_loop: Error accessing UI references: {str(e)}")
        return

    # Check if playback should stop
    if app_globals.stop_video_processing_flag.is_set() or not app_globals.is_playing_via_after_loop:
        log_debug("_video_playback_loop: Stopping playback (flag set or mode changed)")
        app_globals.is_playing_via_after_loop = False 
        app_globals.real_time_fps_display_value = 0.0 
        try:
            if ui_comps.get("fps_label"): ui_comps["fps_label"].config(text="FPS: --")
        except Exception as e:
            log_debug(f"_video_playback_loop: Error updating FPS label on stop: {str(e)}")
        return

    # Handle paused state
    if app_globals.video_paused_flag.is_set():
        try:
            if root and root.winfo_exists():
                app_globals.after_id_playback_loop = root.after(50, lambda: _video_playback_loop(process_frames_real_time))
                log_debug("_video_playback_loop: Video paused, waiting...")
        except Exception as e:
            log_debug(f"_video_playback_loop: Error in paused state: {str(e)}")
        return

    # Initialize variables for this iteration
    frame_read_success = False
    raw_frame = None 
    output_frame = None 
    current_frame_pos_from_cv = -1
    frame_read_time = 0

    # Time-critical section: Read frame from video source
    try:
        frame_read_start = time.perf_counter_ns()
        with app_globals.video_access_lock:
            if app_globals.video_capture_global and app_globals.video_capture_global.isOpened():
                current_frame_pos_from_cv = int(app_globals.video_capture_global.get(cv2.CAP_PROP_POS_FRAMES))
            
                # Handle seek requests initiated by slider with improved performance
                if app_globals.last_seek_requested and hasattr(app_globals, 'seek_target_frame'):
                    log_debug(f"_video_playback_loop: Detected seek request to frame {app_globals.seek_target_frame}")
                    
                    # Calculate keyframe optimization for faster seeking
                    target_frame = app_globals.seek_target_frame
                    current_pos = int(app_globals.video_capture_global.get(cv2.CAP_PROP_POS_FRAMES))
                    seek_distance = abs(target_frame - current_pos)
                    
                    # For large seeks, use a two-step approach for faster response
                    if seek_distance > 100:
                        # First seek to a keyframe near the target for faster initial positioning
                        keyframe_offset = target_frame - (target_frame % 30)  # Assuming keyframes every ~30 frames
                        app_globals.video_capture_global.set(cv2.CAP_PROP_POS_FRAMES, keyframe_offset)
                        # Then seek to the exact frame
                        app_globals.video_capture_global.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                    else:
                        # Direct seek for shorter distances
                        app_globals.video_capture_global.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                    
                    current_frame_pos_from_cv = target_frame
                    app_globals.current_video_meta['current_frame'] = target_frame
                    app_globals.last_seek_requested = False
                    
                    # Reset timing with longer buffer to ensure smooth playback after seek
                    _last_frame_display_time_ns = time.perf_counter_ns() - (target_frame_duration_ns * 2)
                # Improved position check during regular playback
                elif abs(current_frame_pos_from_cv - app_globals.current_video_meta['current_frame']) > 1:
                    # Only log serious discrepancies to reduce log spam
                    if abs(current_frame_pos_from_cv - app_globals.current_video_meta['current_frame']) > 5:
                        log_debug(f"_video_playback_loop: Significant position discrepancy. OpenCV: {current_frame_pos_from_cv}, Meta: {app_globals.current_video_meta['current_frame']}")
                    
                    # Position correction with frame skipping for better performance
                    target_pos = app_globals.current_video_meta['current_frame']
                    # If we're more than 10 frames off, use smarter correction strategy
                    if abs(current_frame_pos_from_cv - target_pos) > 10:
                        # Skip to nearest keyframe then proceed normally
                        keyframe_pos = target_pos - (target_pos % 15)
                        app_globals.video_capture_global.set(cv2.CAP_PROP_POS_FRAMES, keyframe_pos)
                        # Read forward to target position
                        frames_to_skip = target_pos - keyframe_pos
                        for _ in range(frames_to_skip):
                            app_globals.video_capture_global.grab()  # Just grab frames without decoding for speed
                    else:
                        # For smaller corrections, direct seek
                        app_globals.video_capture_global.set(cv2.CAP_PROP_POS_FRAMES, target_pos)
                    
                    current_frame_pos_from_cv = target_pos
                
                # Optimized frame reading with smart buffering and seek awareness
                # Check if a seek operation is in progress from another thread
                if getattr(app_globals, 'seek_in_progress', False):
                    # Skip frame reading during active seek operations
                    frame_read_success = False
                    log_debug("_video_playback_loop: Skipping frame read due to active seek operation")
                else:
                    # Track time before read for performance monitoring
                    read_start_time = time.perf_counter_ns()
                    
                    # Optimized reading strategy based on playback state
                    try:
                        # Check if we need to read multiple frames (for catching up after lag)
                        frames_behind = 0
                        if hasattr(app_globals, 'target_frame_time'):
                            current_time = time.time()
            
                            # For real-time mode, use lower effective FPS to slow down playback
                            effective_fps = app_globals.current_video_meta.get('fps', 30)
                            if process_frames_real_time:
                                # Reduce speed by using half the FPS for real-time mode
                                effective_fps = effective_fps * 0.5
                
                            expected_frame = int((current_time - app_globals.target_frame_time) * effective_fps)
                            frames_behind = max(0, expected_frame - app_globals.current_video_meta['current_frame'])
            
                        # For real-time mode, limit frame skipping to ensure smoother appearance
                        max_skip_frames = 3 if process_frames_real_time else 10
        
                        # Skip decoding intermediate frames if we're significantly behind
                        if frames_behind > 5:
                            # Just grab frames without decoding for catching up
                            for _ in range(min(frames_behind-1, max_skip_frames)):
                                app_globals.video_capture_global.grab()
                                app_globals.current_video_meta['current_frame'] += 1
                        
                        # Now read the actual frame we'll display
                        frame_read_success, raw_frame = app_globals.video_capture_global.read()
                            
                        # Calculate read performance for logging
                        read_time_ms = (time.perf_counter_ns() - read_start_time) / 1_000_000
                        if read_time_ms > 30:  # Only log slow reads
                            log_debug(f"_video_playback_loop: Slow frame read: {read_time_ms:.1f}ms")
                            
                        if frame_read_success:
                            # Track time for synchronization
                            if not hasattr(app_globals, 'target_frame_time'):
                                app_globals.target_frame_time = time.time()
                                    
                            # Use direct reference for better performance
                            app_globals.current_video_frame = raw_frame
                            app_globals.current_video_meta['current_frame'] += 1
                            output_frame = raw_frame
                                
                            # For real-time mode, add delay to slow down playback if running too fast
                            if process_frames_real_time and app_globals.real_time_fps_display_value > app_globals.current_video_meta.get('fps', 30) * 1.2:
                                time.sleep(0.015)  # Add a small delay to slow down processing
                        else:
                            # End of video or read error
                            app_globals.current_video_meta['current_frame'] = app_globals.current_video_meta.get('total_frames', 0)
                    except Exception as read_error:
                        log_debug(f"_video_playback_loop: Error reading frame: {str(read_error)}")
                        frame_read_success = False
            else:
                log_debug("_video_playback_loop: Video capture not available")
        
        frame_read_time = (time.perf_counter_ns() - frame_read_start) / 1_000_000  # Convert to ms
        
        # Only log frame read time if it's unusually slow (>30ms) to reduce log spam
        if frame_read_time > 30:
            log_debug(f"_video_playback_loop: Slow frame read: {frame_read_time:.1f}ms")
            
    except Exception as e:
        log_debug(f"_video_playback_loop: Critical error during frame read: {str(e)}")
        frame_read_success = False


    if not frame_read_success:
        log_debug(f"Video playback: End of video or read error at frame {app_globals.current_video_meta['current_frame']}.")
        # Set flags to stop processing
        app_globals.stop_video_processing_flag.set() 
        app_globals.is_playing_via_after_loop = False
        app_globals.real_time_fps_display_value = 0.0 
        
        # Use a non-blocking approach for cleanup to avoid freezing
        def cleanup_ui_on_end():
            try:
                # Update UI elements
                if ui_comps.get("fps_label"): 
                    ui_comps["fps_label"].config(text="FPS: --")
                if ui_comps.get("play_pause_button"): 
                    ui_comps["play_pause_button"].config(text="Play")
                
                # Set progress to end position
                final_frame = app_globals.current_video_meta.get('total_frames', 0) - 1
                if final_frame < 0: final_frame = 0
                loading_manager.update_progress(final_frame)
                
                # Force UI update before hiding overlay
                if root and root.winfo_exists():
                    root.update_idletasks()
                
                # Hide overlay last to prevent UI inconsistency
                loading_manager.hide_loading_and_update_controls()
                log_debug("_video_playback_loop: Video playback ended, cleanup complete")
            except Exception as e:
                log_debug(f"_video_playback_loop: Error during end cleanup: {str(e)}")
        
        # Schedule cleanup on main thread with higher priority (use 1ms instead of 0)
        if root and root.winfo_exists():
            root.after(1, cleanup_ui_on_end)
        return

    # FPS calculation - only increment counter for successful frames
    app_globals.real_time_fps_frames_processed += 1
    current_time_fps_calc = time.perf_counter()
    time_delta_fps = current_time_fps_calc - app_globals.real_time_fps_last_update_time
    fps_updated = False
    
    # Update FPS more frequently for real-time (every 0.25 seconds) for more responsive UI
    fps_update_interval = 0.25 if process_frames_real_time else 0.5
    if time_delta_fps >= fps_update_interval:
        fps_updated = True
        if time_delta_fps > 0:
            # Calculate actual displayed FPS
            new_fps_value = app_globals.real_time_fps_frames_processed / time_delta_fps
            # Apply adaptive smoothing - less smoothing at low FPS for faster recovery
            if new_fps_value > 0:
                prev_fps = getattr(app_globals, 'prev_fps_value', new_fps_value)
                # More responsive smoothing at lower FPS
                if new_fps_value < 10:
                    smoothing_factor = 0.5  # Faster response at low FPS
                else:
                    smoothing_factor = 0.3  # Normal smoothing at good FPS
                app_globals.real_time_fps_display_value = prev_fps * smoothing_factor + new_fps_value * (1 - smoothing_factor)
                app_globals.prev_fps_value = app_globals.real_time_fps_display_value
        else:
            app_globals.real_time_fps_display_value = 30  # Default reasonable value
        
        # Reset counter and timer
        app_globals.real_time_fps_frames_processed = 0
        app_globals.real_time_fps_last_update_time = current_time_fps_calc
        
        # Force FPS UI update on every calculation to ensure display is up-to-date
        fps_label = ui_comps.get("fps_label")
        if fps_label and fps_label.winfo_exists():
            fps_label.config(text=f"FPS: {app_globals.real_time_fps_display_value:.1f}")
            
        # Only log FPS updates occasionally
        if app_globals.real_time_fps_display_value < 10:  # Only log if FPS is concerning
            log_debug(f"_video_playback_loop: Low FPS detected: {app_globals.real_time_fps_display_value:.2f}")

    # Process frame with ML model (the most intensive operation)
    processing_time = 0
    if process_frames_real_time and app_globals.active_model_object_global and output_frame is not None:
        processing_start = time.perf_counter_ns()
        try:
            # Highly optimized adaptive frame processing
            # Adjust processing frequency based on current FPS
            current_fps = app_globals.real_time_fps_display_value
            
            # Initialize frame counter if not exists
            if not hasattr(app_globals, 'frame_process_counter'):
                app_globals.frame_process_counter = 0
            app_globals.frame_process_counter += 1
            
            # Adaptive processing strategy based on performance
            if current_fps < 5.0:
                # Critical performance mode - process 1 in 5 frames
                should_process = (app_globals.frame_process_counter % 5 == 0)
            elif current_fps < 10.0:
                # Low performance mode - process 1 in 3 frames
                should_process = (app_globals.frame_process_counter % 3 == 0)
            elif current_fps < 20.0:
                # Medium performance mode - process every other frame
                should_process = (app_globals.frame_process_counter % 2 == 0)
            else:
                # Good performance - process all frames
                should_process = True
                
            # Store current detection count for metrics
            if not hasattr(app_globals, 'last_detection_count'):
                app_globals.last_detection_count = 0
                
            if should_process:
                output_frame, detection_count = process_frame_yolo(
                    output_frame, 
                    app_globals.active_model_object_global, 
                    app_globals.active_class_list_global,
                    persist_tracking=True, 
                    is_video_mode=True,
                    active_filter_list=app_globals.active_processed_class_filter_global,
                    current_conf_thresh=app_globals.conf_threshold_global,
                    current_iou_thresh=app_globals.iou_threshold_global
                )
                
                # Store detection count for display
                app_globals.last_detection_count = detection_count
                
                # Convert to milliseconds for readability
                processing_time = (time.perf_counter_ns() - processing_start) / 1_000_000
                
                # Only log slow processing
                if processing_time > 100:  # Only log if processing took more than 100ms
                    log_debug(f"_video_playback_loop: Slow processing: {processing_time:.1f}ms, {detection_count} objects")
            else:
                # Skip processing this frame but still measure overhead time
                processing_time = (time.perf_counter_ns() - processing_start) / 1_000_000
                
        except Exception as e_process:
            processing_time = (time.perf_counter_ns() - processing_start) / 1_000_000
            log_debug(f"Error during frame processing: {e_process}, took {processing_time:.1f}ms", exc_info=True)
            
    # Update UI elements - the most critical part for smooth playback
    display_start = time.perf_counter_ns()
    display_time = 0
    
    try:
        # Only update UI if we have frames to display
        if output_frame is not None:
            # Track if UI update is needed to avoid unnecessary operations
            ui_update_needed = False
            
            # Update the video display - the most visible UI element
            video_display = ui_comps.get("video_display")
            if video_display and video_display.winfo_exists():
                # Check if we're in a resize operation (avoid updates during resize)
                if not getattr(video_display, '_resize_in_progress', False):
                    video_display.update_frame(output_frame)
                    ui_update_needed = True
            
            # Update FPS label - less critical, can be updated less frequently
            if fps_updated and ui_comps.get("fps_label"):
                fps_label = ui_comps.get("fps_label")
                if fps_label and fps_label.winfo_exists():
                    fps_label.config(text=f"FPS: {app_globals.real_time_fps_display_value:.1f}")
            
            # Enhanced UI update strategy for real-time mode
            # Always update frame counter even when skipping progress bar
            current_frame = app_globals.current_video_meta['current_frame']
            total_frames = app_globals.current_video_meta.get('total_frames', 0)
            
            # Update frame counter display directly for better responsiveness
            frame_label = ui_comps.get("current_frame_label")
            if frame_label and frame_label.winfo_exists() and current_frame % 2 == 0:
                frame_label.config(text=f"Frame: {current_frame} / {total_frames}")
                
            # Update detection count display if available
            if hasattr(app_globals, 'last_detection_count'):
                detection_label = ui_comps.get("detection_count_label")
                if detection_label and detection_label.winfo_exists() and current_frame % 3 == 0:
                    detection_label.config(text=f"Detections: {app_globals.last_detection_count}")
            
            # Use throttled progress updates to avoid overwhelming the UI thread
            # Only update progress slider every 10 frames in real-time mode for better performance
            update_interval = 10 if process_frames_real_time else 5
            if app_globals.current_video_meta['current_frame'] % update_interval == 0 and root and root.winfo_exists():
                # Use a higher delay (15ms) for progress updates to prioritize frame display in real-time mode
                delay_ms = 15 if process_frames_real_time else 5
                if app_globals.fast_processing_active_flag.is_set():
                    # For fast processing mode
                    root.after(delay_ms, lambda cf=current_frame: loading_manager.update_fast_progress(cf))
                else:
                    # For real-time mode
                    root.after(delay_ms, lambda cf=current_frame: loading_manager.update_progress(cf))
            
            # Process any pending UI events to keep interface responsive
            if ui_update_needed and root and root.winfo_exists():
                # Only process critical UI updates, avoid full update() calls
                try:
                    root.update_idletasks()
                except Exception as e:
                    log_debug(f"_video_playback_loop: Error in update_idletasks: {str(e)}")
        
        display_time = (time.perf_counter_ns() - display_start) / 1_000_000  # Convert to ms
        
        # Only log slow display updates
        if display_time > 50:  # Log only if display update took more than 50ms
            log_debug(f"_video_playback_loop: Slow display update: {display_time:.1f}ms")
            
    except Exception as e_ui:
        log_debug(f"_video_playback_loop: UI update error: {str(e_ui)}")
        display_time = (time.perf_counter_ns() - display_start) / 1_000_000


    # Calculate optimal timing for next frame with adaptive scheduling
    # This is the most critical part for smooth playback
    target_fps = app_globals.current_video_meta.get('fps', 30)
    if target_fps <= 0 or target_fps > 60: 
        target_fps = 30  # Default reasonable FPS, cap at 60 to prevent UI overload
        
    # Calculate target frame duration in nanoseconds
    target_frame_duration_ns = int((1 / target_fps) * 1_000_000_000)
        
    # Get current time for calculations
    current_time_ns = time.perf_counter_ns()
        
    # Advanced timing control with enhanced seek handling
    if getattr(app_globals, 'seek_in_progress', False):
        # During seek operations, use minimal delay for responsiveness
        delay_ns = 5_000_000  # 5ms during seek for better responsiveness
        _last_frame_display_time_ns = current_time_ns  # Reset timing reference
            
        # Track cumulative seek time for timeout detection
        if not hasattr(app_globals, 'seek_start_tracking_time'):
            app_globals.seek_start_tracking_time = time.perf_counter()
        elif time.perf_counter() - app_globals.seek_start_tracking_time > 2.0:
            # Seek taking too long - might be stuck
            log_debug("_video_playback_loop: Seek operation timeout - forcing completion")
            app_globals.seek_in_progress = False  # Force completion
            delattr(app_globals, 'seek_start_tracking_time')
    else:
        # Clear seek tracking if no longer seeking
        if hasattr(app_globals, 'seek_start_tracking_time'):
            delattr(app_globals, 'seek_start_tracking_time')
                
        # Optimized timing for smooth playback with frame dropping/duplication
        # Initialize or reset timing reference if needed
        if _last_frame_display_time_ns == 0:
            _last_frame_display_time_ns = current_time_ns - target_frame_duration_ns
            
        # Calculate timing with dynamic adjustment based on performance
        fps_ratio = 1.0
        if app_globals.real_time_fps_display_value > 0:
            target_fps = app_globals.current_video_meta.get('fps', 30)
        
            # For real-time mode, target lower FPS explicitly to slow down playback
            if process_frames_real_time:
                # Target half the normal speed for real-time processing
                target_fps = target_fps * 0.5
            
            if target_fps > 0:
                fps_ratio = min(2.0, max(0.5, app_globals.real_time_fps_display_value / target_fps))
    
        # Adjust frame timing based on performance
        adjusted_frame_duration = int(target_frame_duration_ns / fps_ratio)
    
        # For real-time mode, ensure minimum frame duration to prevent too-fast playback
        if process_frames_real_time:
            # Ensure minimum display time of 33ms per frame (~30fps max)
            adjusted_frame_duration = max(adjusted_frame_duration, 33_000_000)
        
        next_ideal_display_time_ns = _last_frame_display_time_ns + adjusted_frame_duration
    
        # Calculate delay with performance compensation
        delay_ns = next_ideal_display_time_ns - current_time_ns
    
    # Enhanced adaptive frame timing with realtime optimization
    total_processing_time_ms = (frame_read_time + processing_time + display_time)
    target_duration_ms = target_frame_duration_ns / 1_000_000
    
    # Calculate processing load ratio (how much of the frame time we're using)
    processing_load = total_processing_time_ms / target_duration_ms if target_duration_ms > 0 else 1.0
    
    # Store processing load for external monitoring
    app_globals.last_processing_load = processing_load
    
    # Real-time optimized timing strategy with frame dropping
    if process_frames_real_time:
        # More aggressive optimization for real-time mode
        if processing_load > 0.9:  # Critically overloaded
            # Ultra-minimal delay to catch up as fast as possible
            delay_ns = 1_000_000  # 1ms absolute minimum
            
            # Track severe performance issues
            app_globals.heavy_frame_count = getattr(app_globals, 'heavy_frame_count', 0) + 1
            
            # Highly aggressive adaptation for real-time mode
            if app_globals.heavy_frame_count > 5:
                # First level - immediately start skipping frames
                app_globals.skip_processing_ratio = 5  # Process only 1 in 5 frames
                # Force UI refresh to display current metrics
                if app_globals.heavy_frame_count % 10 == 0:
                    # Update performance indicator in UI if available
                    perf_label = ui_comps.get("performance_label")
                    if perf_label and perf_label.winfo_exists():
                        perf_label.config(text="Performance: Poor", foreground="red")
                    log_debug(f"_video_playback_loop: Critical performance issue - processing load: {processing_load:.2f}")
        elif processing_load > 0.7:  # Heavily loaded
            delay_ns = 1_000_000  # Still use minimal delay
            # Use moderate frame skipping
            app_globals.skip_processing_ratio = 3  # Process only 1 in 3 frames
            # Gradually reduce heavy frame count
            app_globals.heavy_frame_count = max(0, getattr(app_globals, 'heavy_frame_count', 0) - 1)
            # Update performance indicator 
            perf_label = ui_comps.get("performance_label")
            if perf_label and perf_label.winfo_exists() and getattr(app_globals, 'ui_update_counter', 0) % 15 == 0:
                perf_label.config(text="Performance: Fair", foreground="orange")
        elif processing_load > 0.5:  # Moderately loaded
            delay_ns = 2_000_000  # 2ms delay
            app_globals.skip_processing_ratio = 2  # Process every other frame
            app_globals.heavy_frame_count = 0  # Reset heavy count
            # Update performance indicator
            perf_label = ui_comps.get("performance_label")
            if perf_label and perf_label.winfo_exists() and getattr(app_globals, 'ui_update_counter', 0) % 15 == 0:
                perf_label.config(text="Performance: Good", foreground="black")
        else:  # Lightly loaded
            # Good performance - process all frames
            app_globals.skip_processing_ratio = 1
            app_globals.heavy_frame_count = 0
            delay_ns = min(delay_ns, 5_000_000)  # Cap at 5ms for responsiveness
            # Update performance indicator
            perf_label = ui_comps.get("performance_label")
            if perf_label and perf_label.winfo_exists() and getattr(app_globals, 'ui_update_counter', 0) % 15 == 0:
                perf_label.config(text="Performance: Excellent", foreground="green")
    else:
        # Standard optimization for fast-process playback mode
        if processing_load > 0.9:  # Heavily loaded (>90% of frame time used for processing)
            # Critical performance mode - minimal delay to catch up
            delay_ns = 1_000_000  # 1ms minimum delay
            
            # Track performance issues
            app_globals.heavy_frame_count = getattr(app_globals, 'heavy_frame_count', 0) + 1
            
            # Escalating adaptation strategies based on sustained load
            if app_globals.heavy_frame_count > 10 and app_globals.heavy_frame_count <= 20:
                # First level adaptation - start skipping processing on some frames
                app_globals.skip_processing_count = getattr(app_globals, 'skip_processing_count', 0) + 1
                if app_globals.skip_processing_count >= 3:
                    app_globals.skip_processing_count = 0
                    log_debug(f"_video_playback_loop: Performance adaptation - processing every 3rd frame")
            elif app_globals.heavy_frame_count > 20 and app_globals.heavy_frame_count <= 30:
                # Second level adaptation - reduce resolution temporarily
                log_debug(f"_video_playback_loop: Performance adaptation - processing at reduced resolution")
            elif app_globals.heavy_frame_count > 30:
                # Final adaptation level - report performance issue and reset counter
                app_globals.heavy_frame_count = 0
                log_debug(f"_video_playback_loop: Severe performance issue - processing taking {total_processing_time_ms:.1f}ms (target: {target_duration_ms:.1f}ms)")
        elif processing_load > 0.7:  # Moderately loaded (70-90% of frame time)
            # Medium performance mode - slightly reduced delay for stability
            delay_ns = min(delay_ns, 5_000_000)  # Cap at 5ms
            # Reset adaptation if performance is improving
            app_globals.heavy_frame_count = max(0, getattr(app_globals, 'heavy_frame_count', 0) - 1)
        else:
            # Good performance - reset adaptation counters
            app_globals.heavy_frame_count = 0
            app_globals.skip_processing_count = 0
            
            # Normal operating conditions with upper bound for responsiveness
            # Never wait more than 33ms (to maintain minimum 30fps UI responsiveness)
            delay_ns = min(delay_ns, 33_000_000)
            
            # For very light loads, ensure we don't render too many frames unnecessarily
            if processing_load < 0.3 and delay_ns < 5_000_000:
                delay_ns = 5_000_000  # Min 5ms delay for light loads to avoid CPU waste
                
    # Track UI update counter for staggered updates
    app_globals.ui_update_counter = getattr(app_globals, 'ui_update_counter', 0) + 1
    
    # Finalize delay calculation with protection against negative values
    delay_ns = max(1_000_000, delay_ns)  # Ensure minimum 1ms delay
    delay_ms = max(1, int(delay_ns / 1_000_000))
    
    # Dynamic timestamp update with frame synchronization
    if app_globals.video_paused_flag.is_set():
        # When paused, don't advance the timestamp
        _last_frame_display_time_ns = current_time_ns
    else:
        # Update with precise timing for next frame
        _last_frame_display_time_ns = current_time_ns + (delay_ms * 1_000_000)
    
    # Calculate and store synchronization metrics
    total_loop_duration_ns = time.perf_counter_ns() - loop_start_time
    loop_duration_ms = total_loop_duration_ns / 1_000_000
    
    # Adaptive logging based on performance issues
    if loop_duration_ms > 50:  # Only log slow loops
        processing_percent = int((total_processing_time_ms / loop_duration_ms) * 100)
        log_debug(f"_video_playback_loop: Slow loop: {loop_duration_ms:.1f}ms (processing: {processing_percent}%, delay: {delay_ms}ms)")
        
    # Update tracking timestamp for frame rate synchronization
    if not app_globals.video_paused_flag.is_set() and frame_read_success:
        app_globals.target_frame_time = time.time() + (delay_ms / 1000.0)
    
    # Schedule next frame processing with error handling
    if root and root.winfo_exists():
        try:
            # Enhanced scheduling with real-time optimizations
            if getattr(app_globals, 'seek_in_progress', False):
                # Prioritize responsiveness during seek operations
                delay_ms = 5  # 5ms for immediate response during seeks
            elif app_globals.video_paused_flag.is_set():
                # Power-saving mode when paused
                delay_ms = 100  # 100ms while paused to reduce CPU usage
            elif process_frames_real_time and app_globals.real_time_fps_display_value < 10:
                # Ultra critical performance mode for real-time processing
                delay_ms = 1  # Absolute minimum delay for real-time mode when performance is poor
            elif total_processing_time_ms > target_duration_ms * 0.9:
                # Critical performance mode - ensure we don't fall further behind
                delay_ms = 1  # Absolute minimum delay for heavy processing
            elif process_frames_real_time:
                # Set a higher minimum delay for real-time mode to prevent too-fast playback
                # This is a key change to slow down real-time processing
                delay_ms = max(20, delay_ms)  # Ensure at least 20ms between frames (~50fps max)
            
            # Use advanced lambda with error checking for more robust scheduling
            app_globals.after_id_playback_loop = root.after(
                delay_ms, 
                lambda p=process_frames_real_time: _safe_video_loop_call(p)
            )
            
            # Define safer wrapper function in local scope
            def _safe_video_loop_call(process_frames):
                try:
                    _video_playback_loop(process_frames)
                except Exception as e:
                    log_debug(f"Error in video playback loop: {str(e)}")
                    # Attempt recovery
                    if root and root.winfo_exists():
                        root.after(100, lambda: _video_playback_loop(process_frames))
        except Exception as e:
            log_debug(f"_video_playback_loop: Critical scheduling error: {str(e)}")
            # Emergency recovery - stop playback and reset UI
            app_globals.stop_video_processing_flag.set()
            app_globals.is_playing_via_after_loop = False
            
            # Reset any in-progress seek operations
            app_globals.seek_in_progress = False
            
            # Schedule emergency cleanup with higher priority
            if root and root.winfo_exists():
                root.after(1, loading_manager.hide_loading_and_update_controls)


def _process_uploaded_file_in_thread(file_path, stop_processing_logic_func):
    import cv2
    log_debug(f"Thread started for processing file: {file_path}")
    # Start timing for performance tracking
    start_time = time.time()
    root = app_globals.ui_references.get("root")
    file_type = None 
    success = False
    detected_objects_count = 0

    try:
        file_name = os.path.basename(file_path)
        _, ext = os.path.splitext(file_path.lower())
        
        mime_type = "" 
        if ext in ['.jpg', '.jpeg', '.png']:
            file_type = 'image'; mime_type = f'image/{ext[1:]}'
        elif ext in ['.mp4', '.avi', '.mov', '.mkv']:
            file_type = 'video'; mime_type = f'video/{ext[1:] if ext != ".mkv" else "x-matroska"}'
        else:
            log_debug(f"Unsupported file type in thread: {ext}")
            if root and root.winfo_exists(): root.after(0, lambda: messagebox.showerror("Error", f"Unsupported file type: {ext}"))
            app_globals.uploaded_file_info = {}; app_globals.current_video_meta.update({'fps': 0.0, 'total_frames': 0, 'duration_seconds': 0.0, 'current_frame': 0})
            app_globals.current_processed_image_for_display = None; return 

        log_debug(f"File type determined in thread: {file_type}, mime: {mime_type}")
        app_globals.uploaded_file_info = {'path': file_path, 'name': file_name, 'type': mime_type, 'file_type': file_type}
        app_globals.current_video_meta.update({'fps': 0.0, 'total_frames': 0, 'duration_seconds': 0.0, 'current_frame': 0})
        app_globals.current_video_frame = None; app_globals.current_processed_image_for_display = None 
        
        _cleanup_processed_video_temp_file()
        if callable(stop_processing_logic_func): stop_processing_logic_func() 

        if file_type == 'image':
            log_debug("Image file: reading in thread...")
            img = cv2.imread(file_path)
            if img is None:
                log_debug(f"Could not read image file in thread: {file_path}")
                if root and root.winfo_exists(): root.after(0, lambda: messagebox.showerror("Error", "Could not read image data."))
                app_globals.uploaded_file_info = {}; return

            # Store original image first
            app_globals.current_processed_image_for_display = img.copy()
            
            # Display image immediately before processing to improve perceived responsiveness
            if root and root.winfo_exists():
                video_display = app_globals.ui_references.get("ui_components_dict", {}).get("video_display")
                if video_display and video_display.winfo_exists():
                    root.after(0, lambda: video_display.update_frame(img))
                    log_debug("Displaying original image immediately before processing")
            
            # Then process if needed (after displaying original)
            if app_globals.active_model_object_global:
                log_debug("Model loaded, processing uploaded image...")
                processed_img, detected_objects_count = process_frame_yolo(
                    img, app_globals.active_model_object_global, app_globals.active_class_list_global,
                    is_video_mode=False,
                    active_filter_list=app_globals.active_processed_class_filter_global,
                    current_conf_thresh=app_globals.conf_threshold_global, 
                    current_iou_thresh=app_globals.iou_threshold_global
                )
                app_globals.current_processed_image_for_display = processed_img 
                
                # Update the display with processed image
                if root and root.winfo_exists() and video_display and video_display.winfo_exists():
                    root.after(0, lambda: video_display.update_frame(processed_img))
                    log_debug("Displaying processed image after processing")
            
            success = True

        elif file_type == 'video':
            log_debug("Video file: opening and reading first frame in thread.")
            
            # Optimize video opening with more efficient settings
            try:
                # Set OpenCV options for faster video loading
                os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;udp'
                
                with app_globals.video_access_lock: 
                    if app_globals.video_capture_global and app_globals.video_capture_global.isOpened(): 
                        app_globals.video_capture_global.release()
                    
                    # Try to open with optimized settings for faster loading
                    cap = cv2.VideoCapture(file_path)
                    
                    # Apply optimized video capture settings
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)  # Use small buffer
                    
                    if not cap.isOpened():
                        log_debug(f"Could not open video file in thread: {file_path}"); success = False
                        if root and root.winfo_exists(): root.after(0, lambda: messagebox.showerror("Error", "Could not open video file."))
                        app_globals.uploaded_file_info = {}; return
                    
                    app_globals.video_capture_global = cap 
                    
                    # Get video metadata with timeout protection
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    if fps <= 0 or fps > 120:  # Sanity check for FPS
                        fps = 30.0  # Use reasonable default if invalid
                    
                    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                    if total_frames <= 0:  # Some videos don't report frames properly
                        # Estimate based on duration if available or use placeholder
                        duration = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                        total_frames = int(duration * fps) if duration > 0 else 1000
                    
                    duration_seconds = total_frames / fps if fps > 0 else 0
                    app_globals.current_video_meta.update({
                        'fps': fps, 
                        'total_frames': total_frames, 
                        'duration_seconds': duration_seconds, 
                        'current_frame': 0
                    })
                    
                    # Just read the first frame without processing initially for speed
                    ret, first_frame = cap.read()
                    if ret and first_frame is not None:
                        app_globals.current_video_frame = first_frame.copy()
                        # Store original frame first
                        app_globals.current_processed_image_for_display = first_frame.copy()
                        
                        # Display unprocessed frame immediately for faster response
                        if root and root.winfo_exists():
                            video_display = app_globals.ui_references.get("ui_components_dict", {}).get("video_display")
                            if video_display and video_display.winfo_exists():
                                root.after(0, lambda: video_display.update_frame(first_frame))
                                log_debug("Displaying first video frame immediately")
                        
                        # Skip initial processing - it will be done during playback
                        # This significantly speeds up initial loading
                        success = True
                    else: 
                        log_debug(f"Failed to read first frame of video: {file_path}"); success = False
                        if root and root.winfo_exists(): 
                            root.after(0, lambda: messagebox.showerror("Error", "Could not read first frame of video."))
                        with app_globals.video_access_lock:
                            if app_globals.video_capture_global: 
                                app_globals.video_capture_global.release()
                                app_globals.video_capture_global = None
                        app_globals.uploaded_file_info = {}
            except Exception as video_e:
                log_debug(f"Error opening video: {video_e}", exc_info=True)
                if root and root.winfo_exists(): 
                    root.after(0, lambda: messagebox.showerror("Error", f"Error opening video: {str(video_e)}"))
                app_globals.uploaded_file_info = {}; success = False
                
        elapsed = time.time() - start_time
        log_debug(f"Thread processing for {file_path} completed in {elapsed:.2f}s. Success: {success}")

    except Exception as e_thread:
        log_debug(f"General error in _process_uploaded_file_in_thread for {file_path}: {e_thread}", exc_info=True)
        if root and root.winfo_exists():
            root.after(0, lambda: messagebox.showerror("Error", f"Error processing file: {str(e_thread)}"))
        success = False
        if root and root.winfo_exists():
             root.after(0, lambda bound_e=e_thread: messagebox.showerror("Error", f"Error processing file: {bound_e}"))
        app_globals.uploaded_file_info = {} 
    finally:
        if root and root.winfo_exists():
            log_debug(f"Thread for {file_path} scheduling final hide_loading_and_update_controls. Success: {success}")
            # hide_loading_and_update_controls will use app_globals.current_processed_image_for_display
            root.after(0, loading_manager.hide_loading_and_update_controls)
            if file_type == 'image' and success and detected_objects_count > 0: # Only print if objects were detected
                 root.after(10, lambda c=detected_objects_count: print(f"Processed uploaded image. Detected {c} objects."))


def _perform_seek_action_in_thread():
    root = app_globals.ui_references.get("root")
    ui_comps = app_globals.ui_references.get("ui_components_dict", {})
    
    if root and root.winfo_exists(): root.after(0, lambda: loading_manager.show_loading("Seeking video...")); root.after(0, root.update_idletasks) 
    log_debug(f"Seek thread: Performing seek to frame: {app_globals.slider_target_frame_value}")
    try:
        target_frame = int(app_globals.slider_target_frame_value)
        with app_globals.video_access_lock:
            if not app_globals.video_capture_global or not app_globals.video_capture_global.isOpened():
                log_debug("Seek thread: No valid video capture."); 
                if root and root.winfo_exists(): root.after(0, loading_manager.hide_loading_and_update_controls); return 
            
            was_playing_before_seek = app_globals.is_playing_via_after_loop and not app_globals.video_paused_flag.is_set()
            if was_playing_before_seek: # If it was playing, pause it for the seek
                app_globals.video_paused_flag.set() 
                if root and root.winfo_exists() and ui_comps.get("play_pause_button"): 
                    root.after(0, lambda: ui_comps["play_pause_button"].config(text="Play")) # Update button text
            
            app_globals.video_capture_global.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            ret, frame = app_globals.video_capture_global.read()
            
            if ret and frame is not None:
                app_globals.current_video_frame = frame.copy()
                # After setting position, CAP_PROP_POS_FRAMES points to the *next* frame. So current is target_frame.
                app_globals.current_video_meta['current_frame'] = target_frame 
                
                global _last_frame_display_time_ns 
                target_fps_meta = app_globals.current_video_meta.get('fps', 30); target_fps_meta = target_fps_meta if target_fps_meta > 0 else 30
                _last_frame_display_time_ns = time.perf_counter_ns() - int((1.0 / target_fps_meta) * 1_000_000_000) # Reset for smooth resume
                
                app_globals.real_time_fps_last_update_time = time.perf_counter(); app_globals.real_time_fps_frames_processed = 0; app_globals.real_time_fps_display_value = 0.0
                
                # Determine if we are in real-time processing mode (not playing a pre-processed temp file)
                is_real_time_mode = not (app_globals.processed_video_temp_file_path_global and os.path.exists(app_globals.processed_video_temp_file_path_global))
                                             
                output_frame_on_seek = frame.copy() # Use a copy for processing
                if is_real_time_mode and app_globals.active_model_object_global : 
                    output_frame_on_seek, _ = process_frame_yolo(
                        output_frame_on_seek, app_globals.active_model_object_global, app_globals.active_class_list_global,
                        persist_tracking=True, is_video_mode=True, 
                        active_filter_list=app_globals.active_processed_class_filter_global,
                        current_conf_thresh=app_globals.conf_threshold_global, current_iou_thresh=app_globals.iou_threshold_global
                    )
                
                app_globals.current_processed_image_for_display = output_frame_on_seek # Store for hide_loading

                if root and root.winfo_exists():
                    # The actual display update will now be handled by hide_loading_and_update_controls
                    root.after(0, loading_manager.hide_loading_and_update_controls)
                    # If it was playing, unpause it after seek and UI update
                    if was_playing_before_seek:
                        root.after(10, lambda: app_globals.video_paused_flag.clear()) # Small delay for UI to settle
            else:
                log_debug(f"Seek thread: Failed to read frame at position {target_frame}")
                if root and root.winfo_exists():
                    root.after(0, lambda: messagebox.showinfo("Seek Info", "Could not seek to selected frame. End of video or read error."))
                    root.after(0, loading_manager.hide_loading_and_update_controls)
    except Exception as e:
        log_debug(f"Error during seek task (thread): {e}", exc_info=True)
        if root and root.winfo_exists():
            root.after(0, lambda bound_e=e: messagebox.showerror("Seek Error", f"Error during seek: {bound_e}"))
            root.after(0, loading_manager.hide_loading_and_update_controls)


def run_model_load_in_thread(selected_model_key, stop_processing_logic_func):
    root = app_globals.ui_references.get("root")
    ui_comps = app_globals.ui_references.get("ui_components_dict", {})
    def load_model_task():
        model_loader_load_model(selected_model_key) 
        if root and root.winfo_exists(): root.after(0, loading_manager.hide_loading_and_update_controls)
        
        # If an image is already loaded, reprocess it with the new model
        if app_globals.uploaded_file_info.get('file_type') == 'image' and \
           app_globals.uploaded_file_info.get('path') and \
           app_globals.active_model_object_global is not None:
            try:
                original_image_path = app_globals.uploaded_file_info.get('path')
                img_to_reprocess = cv2.imread(original_image_path)
                if img_to_reprocess is not None:
                    log_debug(f"Re-processing image {original_image_path} with new model {selected_model_key}")
                    processed_img, detected_count = process_frame_yolo(
                        img_to_reprocess, app_globals.active_model_object_global, app_globals.active_class_list_global,
                        is_video_mode=False, active_filter_list=app_globals.active_processed_class_filter_global,
                        current_conf_thresh=app_globals.conf_threshold_global, current_iou_thresh=app_globals.iou_threshold_global
                    )
                    app_globals.current_processed_image_for_display = processed_img # Update global
                    # UI update will be handled by the hide_loading_and_update_controls call above
                    if root and root.winfo_exists(): # For the print message
                        root.after(10, lambda c=detected_count: print(f"Re-processed image with {selected_model_key}. Detected {c} objects."))
            except Exception as e_reprocess: 
                log_debug(f"Error re-processing image with new model: {e_reprocess}", exc_info=True)
                if root and root.winfo_exists(): root.after(0, lambda: print(f"Error re-processing image: {e_reprocess}"))

    if callable(stop_processing_logic_func): stop_processing_logic_func()
    loading_manager.show_loading(f"Loading model: {selected_model_key}...")
    threading.Thread(target=load_model_task, daemon=True).start()


def run_image_processing_in_thread(file_path):
    """Processes an image in a thread. Assumes model is loaded."""
    root = app_globals.ui_references.get("root")
    # ui_comps = app_globals.ui_references.get("ui_components_dict", {})
    loading_manager.show_loading("Processing image...")
    if root and root.winfo_exists(): root.update_idletasks()

    def process_image_task():
        try:
            img = cv2.imread(file_path)
            if img is None: raise ValueError(f"Could not read image file: {file_path}")

            processed_img, detected_count = process_frame_yolo(
                img, app_globals.active_model_object_global, app_globals.active_class_list_global,
                is_video_mode=False, active_filter_list=app_globals.active_processed_class_filter_global,
                current_conf_thresh=app_globals.conf_threshold_global, current_iou_thresh=app_globals.iou_threshold_global
            )
            app_globals.current_processed_image_for_display = processed_img # Key step

            if root and root.winfo_exists():
                # hide_loading_and_update_controls will now pick up current_processed_image_for_display
                root.after(0, loading_manager.hide_loading_and_update_controls) 
                root.after(10, lambda c=detected_count: print(f"Processed image. Detected {c} objects."))
        except Exception as e:
            log_debug(f"Error processing image (thread): {e}", exc_info=True)
            app_globals.current_processed_image_for_display = None # Clear on error
            if root and root.winfo_exists():
                root.after(0, lambda bound_e=e: messagebox.showerror("Error", f"Error processing image: {bound_e}"))
                root.after(0, loading_manager.hide_loading_and_update_controls) # Still update UI
    threading.Thread(target=process_image_task, daemon=True).start()


def run_fast_video_processing_in_thread(file_path, stop_processing_logic_func):
    root = app_globals.ui_references.get("root")
    ui_comps = app_globals.ui_references.get("ui_components_dict", {})
    from ._ui_loading_manager import update_fast_progress 

    if callable(stop_processing_logic_func): stop_processing_logic_func() 
    app_globals.fast_processing_active_flag.set()
    log_debug("run_fast_video_processing_in_thread: fast_processing_active_flag SET.")
    
    # Show first frame immediately to ensure the user sees something right away
    video_display = ui_comps.get("video_display")
    if video_display and video_display.winfo_exists() and app_globals.current_video_frame is not None:
        # Ensure first frame is displayed
        video_display.update_frame(app_globals.current_video_frame)
        log_debug("run_fast_video_processing_in_thread: Displaying first frame immediately")
    
    if root and root.winfo_exists(): 
        root.after(0, loading_manager.hide_loading_and_update_controls) # This will show the progress bar frame

    def fast_process_task():
        try:
            if root and root.winfo_exists() and ui_comps.get("fps_label"): 
                root.after(0, lambda: ui_comps["fps_label"].config(text="FPS: Processing..."))

            temp_cap_check = cv2.VideoCapture(file_path)
            if temp_cap_check.isOpened():
                app_globals.current_video_meta['fps'] = temp_cap_check.get(cv2.CAP_PROP_FPS)
                app_globals.current_video_meta['total_frames'] = int(temp_cap_check.get(cv2.CAP_PROP_FRAME_COUNT))
                app_globals.current_video_meta['duration_seconds'] = \
                    app_globals.current_video_meta['total_frames'] / app_globals.current_video_meta['fps'] if app_globals.current_video_meta['fps'] > 0 else 0
                temp_cap_check.release()
            else: 
                raise ValueError(f"Fast Process: Could not open video for metadata: {file_path}")
            
            app_globals.stop_fast_processing_flag.clear()
            if ui_comps.get("fast_progress_var"): 
                root.after(0, lambda: ui_comps["fast_progress_var"].set(0))
            if ui_comps.get("fast_progress_label"): 
                 root.after(0, lambda: ui_comps["fast_progress_label"].config(text="Progress: 0% | Calculating..."))

            
            app_globals.fast_video_processing_thread = threading.Thread(
                target=fast_video_processing_thread_func, 
                kwargs={
                    'video_file_path': file_path,
                    'progress_callback': lambda p, t: update_fast_progress(p, t) if ui_comps else None
                }, daemon=True)
            app_globals.fast_video_processing_thread.start()
        except Exception as e:
            log_debug(f"Error setting up fast processing (thread): {e}", exc_info=True)
            if root and root.winfo_exists():
                root.after(0, lambda: messagebox.showerror("Error", f"Error setting up fast processing: {e}"))
            app_globals.fast_processing_active_flag.clear() 
            if root and root.winfo_exists():
                root.after(0, loading_manager.hide_loading_and_update_controls)
    
    threading.Thread(target=fast_process_task, daemon=True).start()
