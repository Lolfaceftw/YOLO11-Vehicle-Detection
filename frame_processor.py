import cv2
import numpy as np
import time
from . import config # For colors
from . import globals as app_globals
from .logger_setup import log_debug

def process_frame_yolo(frame_to_process, current_model_obj, current_class_list, persist_tracking=True, is_video_mode=False,
                         active_filter_list=None, current_conf_thresh=0.25, current_iou_thresh=0.45):
    # Define constants outside of function call for better performance
    MAROON_COLOR = (48, 48, 176) # BGR
    WHITE_COLOR = (255, 255, 255)
    BLACK_COLOR = (0, 0, 0)
    TEXT_BG_PADDING = 5
    
    # Skip performance tracking in video mode for speed 
    t_start = time.perf_counter() if not is_video_mode else 0

    if current_model_obj is None:
        # Fast path when no model is loaded
        cv2.putText(frame_to_process, "Active Model Not Loaded", (50, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        return frame_to_process, 0

    # Performance optimization: avoid copying for real-time mode when possible
    if is_video_mode:
        # Use direct reference in video mode when possible
        annotated_frame = frame_to_process
    else:
        # Deep copy for image mode to ensure original is preserved
        annotated_frame = frame_to_process.copy()
        
    detected_vehicle_count_in_frame = 0

    try:
        # Measure prediction time for performance monitoring
        t_pred_start = time.perf_counter()
        
        # Get current FPS for adaptive processing
        current_fps = getattr(app_globals, 'real_time_fps_display_value', 30.0)
        is_low_fps = is_video_mode and current_fps < 15.0
        
        # Process frame with the model
        if is_video_mode:
            # Add additional optimization flags for tracking during real-time processing
            results = current_model_obj.track(
                annotated_frame, 
                persist=persist_tracking, 
                classes=active_filter_list, 
                conf=current_conf_thresh, 
                iou=current_iou_thresh, 
                verbose=False,
                # Speed optimization settings
                stream=True,  # Enable streaming mode for faster processing
                augment=False,  # Disable augmentation in real-time
                imgsz=640 if not is_low_fps else 416,  # Reduce resolution when FPS is low
                half=is_low_fps,  # Use half precision for low FPS scenarios
            )
            # When streaming mode is enabled, results is a generator
            # Convert the first result from the generator to use
            result = next(results, None)
        else:
            # For images, use standard prediction
            results = current_model_obj.predict(
                annotated_frame, 
                classes=active_filter_list, 
                conf=current_conf_thresh, 
                iou=current_iou_thresh, 
                verbose=False
            )
            # results is a list in non-streaming mode
            result = results[0] if results else None
            
        # Only track prediction time in non-video mode or when FPS is low
        if not is_video_mode or is_low_fps:
            t_pred_time = (time.perf_counter() - t_pred_start) * 1000
            if t_pred_time > 100:  # Log only if prediction is unusually slow (>100ms)
                log_debug(f"YOLO prediction took {t_pred_time:.1f}ms")

        # Efficiently process detection results
        t_draw_start = time.perf_counter()
        
        # Skip processing if no results (common in real-time streams)
        if not result or not hasattr(result, 'boxes') or result.boxes.data is None or len(result.boxes.data) == 0:
            detected_vehicle_count_in_frame = 0
        else:
            # Fast extraction of all detection data at once (vectorized operations)
            # This is much faster than per-object processing
            boxes = result.boxes.xyxy.cpu().numpy()
            detected_vehicle_count_in_frame = len(boxes)
            class_indices = result.boxes.cls.cpu().numpy().astype(int)
            confidences = result.boxes.conf.cpu().numpy()
            
            # Only extract tracking IDs if they exist
            track_ids = None
            if is_video_mode and hasattr(result.boxes, 'id') and result.boxes.id is not None:
                track_ids = result.boxes.id.cpu().numpy().astype(int)

            # Adaptive drawing based on performance and detection count
            # Use more aggressive skipping for real-time mode when FPS is low
            if is_video_mode:
                current_fps = getattr(app_globals, 'real_time_fps_display_value', 30.0)
                if detected_vehicle_count_in_frame > 30 and current_fps < 10.0:
                    # Very aggressive - only draw 1/4 of detections for very poor performance
                    draw_indices = np.arange(0, detected_vehicle_count_in_frame, 4)
                elif detected_vehicle_count_in_frame > 20 and current_fps < 20.0:
                    # Moderate optimization - draw every 3rd detection
                    draw_indices = np.arange(0, detected_vehicle_count_in_frame, 3)
                elif detected_vehicle_count_in_frame > 10:
                    # Light optimization - draw every other detection
                    draw_indices = np.arange(0, detected_vehicle_count_in_frame, 2)
                else:
                    # Few detections - draw all
                    draw_indices = range(detected_vehicle_count_in_frame)
            else:
                # For image mode, always draw all detections
                draw_indices = range(detected_vehicle_count_in_frame)
            
            # Process and draw each detection
            for i in draw_indices:
                # Convert coordinates to integers directly in a faster way
                x1, y1, x2, y2 = int(boxes[i][0]), int(boxes[i][1]), int(boxes[i][2]), int(boxes[i][3])
                class_idx = class_indices[i]
                conf = confidences[i]
                
                # Fast class name lookup with dict get (faster than if-else)
                class_name = current_class_list.get(class_idx, f"CLS_IDX_{class_idx}") if current_class_list else f"CLS_IDX_{class_idx}"
                
                # Optimize label creation
                if track_ids is not None and i < len(track_ids):
                    track_id_val = track_ids[i]
                    label = f"ID:{track_id_val} {class_name} {conf:.2f}"
                else:
                    label = f"{class_name} {conf:.2f}"

                # Optimize drawing for performance in video mode
                if is_video_mode and getattr(app_globals, 'real_time_fps_display_value', 30.0) < 15.0:
                    # Use thinner lines for better performance
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), MAROON_COLOR, 1)
                    cv2.putText(annotated_frame, label, (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, MAROON_COLOR, 1)
                else:
                    # Normal drawing
                    cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), MAROON_COLOR, 2)
                    cv2.putText(annotated_frame, label, (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, MAROON_COLOR, 2)
                            
        t_draw_time = (time.perf_counter() - t_draw_start) * 1000
        if t_draw_time > 50:  # Log only if drawing is unusually slow (>50ms)
            log_debug(f"Drawing {detected_vehicle_count_in_frame} objects took {t_draw_time:.1f}ms")
                
        # Only draw counter when it's not in low-FPS video mode
        current_fps = getattr(app_globals, 'real_time_fps_display_value', 30.0)
        should_draw_counter = not is_video_mode or current_fps >= 15.0
        
        if should_draw_counter:
            # Cache text dimensions calculation which is expensive
            if not hasattr(process_frame_yolo, 'cached_text_dims'):
                # Initialize cache for text dimensions
                font_face = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.8
                text_thickness = 2
                process_frame_yolo.cached_text_dims = {
                    'font_face': font_face,
                    'font_scale': font_scale,
                    'text_thickness': text_thickness,
                    'sizes': {}  # Cache for different text strings
                }
            
            # Get cached font settings
            font_face = process_frame_yolo.cached_text_dims['font_face']
            font_scale = 0.8 if not is_video_mode else 0.7  # Smaller text for video mode
            text_thickness = 2 if not is_video_mode else 1  # Thinner text for video mode
            
            # Create text with count
            total_vehicles_text = f"Total Vehicles: {detected_vehicle_count_in_frame}"
            text_origin = (50, 30)
            
            # Skip complex text calculations in video mode for performance
            if is_video_mode:
                # Use fixed dimensions for video mode
                rect_x1 = text_origin[0] - TEXT_BG_PADDING
                rect_y1 = text_origin[1] - 14 - TEXT_BG_PADDING  # Approximated height
                rect_x2 = text_origin[0] + 180 + TEXT_BG_PADDING  # Approximated width
                rect_y2 = text_origin[1] + TEXT_BG_PADDING
            else:
                # Get or calculate text dimensions for image mode
                if total_vehicles_text in process_frame_yolo.cached_text_dims['sizes']:
                    text_width, text_height, baseline = process_frame_yolo.cached_text_dims['sizes'][total_vehicles_text]
                else:
                    (text_width, text_height), baseline = cv2.getTextSize(
                        total_vehicles_text, font_face, font_scale, text_thickness
                    )
                    # Cache for future use
                    process_frame_yolo.cached_text_dims['sizes'][total_vehicles_text] = (text_width, text_height, baseline)
                
                # Calculate background rectangle
                rect_x1 = text_origin[0] - TEXT_BG_PADDING
                rect_y1 = text_origin[1] - text_height - TEXT_BG_PADDING - baseline
                rect_x2 = text_origin[0] + text_width + TEXT_BG_PADDING
                rect_y2 = text_origin[1] + TEXT_BG_PADDING
            
            # Draw background and text
            cv2.rectangle(annotated_frame, (rect_x1, rect_y1), (rect_x2, rect_y2), BLACK_COLOR, cv2.FILLED)
            cv2.putText(annotated_frame, total_vehicles_text, text_origin,
                        font_face, font_scale, WHITE_COLOR, text_thickness)
                    
        # Skip performance logging in video mode unless debugging
        if not is_video_mode and t_start > 0:
            t_total = (time.perf_counter() - t_start) * 1000
            if t_total > 150:  # Only log when unusually slow (>150ms total)
                log_debug(f"Slow frame processing: {t_total:.1f}ms for {detected_vehicle_count_in_frame} objects")
            
    except Exception as e:
        # More robust error handling with minimal impact
        try:
            # Minimal error handling to keep processing going
            cv2.putText(annotated_frame, "Processing Error", (50, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            log_debug(f"Error in process_frame_yolo: {e}")
        except:
            # Fallback if even error annotation fails
            pass
            
    return annotated_frame, detected_vehicle_count_in_frame
