import cv2
from . import config # For colors
from .logger_setup import log_debug

def process_frame_yolo(frame_to_process, current_model_obj, current_class_list, persist_tracking=True, is_video_mode=False,
                         active_filter_list=None, current_conf_thresh=0.25, current_iou_thresh=0.45):
    MAROON_COLOR = (48, 48, 176) # BGR
    WHITE_COLOR = (255, 255, 255)
    BLACK_COLOR = (0, 0, 0)
    TEXT_BG_PADDING = 5

    if current_model_obj is None:
        # log_debug("process_frame_yolo: Active Model Not Loaded") # Avoid flooding logs
        cv2.putText(frame_to_process, "Active Model Not Loaded", (50, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        return frame_to_process, 0

    annotated_frame = frame_to_process.copy()
    detected_vehicle_count_in_frame = 0

    try:
        if is_video_mode:
            results = current_model_obj.track(annotated_frame, persist=persist_tracking, classes=active_filter_list, 
                                              conf=current_conf_thresh, iou=current_iou_thresh, verbose=False)
        else:
            results = current_model_obj.predict(annotated_frame, classes=active_filter_list, 
                                                conf=current_conf_thresh, iou=current_iou_thresh, verbose=False)

        if results and results[0].boxes.data is not None and len(results[0].boxes.data) > 0:
            detected_vehicle_count_in_frame = len(results[0].boxes.data)
            boxes = results[0].boxes.xyxy.cpu().numpy()
            class_indices = results[0].boxes.cls.cpu().numpy().astype(int)
            confidences = results[0].boxes.conf.cpu().numpy()
            
            track_ids = None
            if is_video_mode and results[0].boxes.id is not None:
                track_ids = results[0].boxes.id.cpu().numpy().astype(int)

            for i in range(len(boxes)):
                x1, y1, x2, y2 = map(int, boxes[i])
                class_idx = class_indices[i]
                conf = confidences[i]
                
                class_name = f"CLS_IDX_{class_idx}"
                if current_class_list and isinstance(current_class_list, dict) and class_idx in current_class_list:
                    class_name = current_class_list[class_idx]
                
                label = f"{class_name} {conf:.2f}"
                
                if track_ids is not None and i < len(track_ids):
                    track_id_val = track_ids[i]
                    label = f"ID:{track_id_val} {label}"

                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), MAROON_COLOR, 2)
                cv2.putText(annotated_frame, label, (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, MAROON_COLOR, 2)
                
        total_vehicles_text = f"Total Vehicles: {detected_vehicle_count_in_frame}"
        text_origin = (50, 30)
        font_face = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.8
        text_thickness = 2

        (text_width, text_height), baseline = cv2.getTextSize(total_vehicles_text, font_face, font_scale, text_thickness)
        
        rect_x1 = text_origin[0] - TEXT_BG_PADDING
        rect_y1 = text_origin[1] - text_height - TEXT_BG_PADDING - baseline # Adjusted for baseline
        rect_x2 = text_origin[0] + text_width + TEXT_BG_PADDING
        rect_y2 = text_origin[1] + TEXT_BG_PADDING # Adjusted for baseline

        cv2.rectangle(annotated_frame, (rect_x1, rect_y1), (rect_x2, rect_y2), BLACK_COLOR, cv2.FILLED)
        cv2.putText(annotated_frame, total_vehicles_text, text_origin,
                    font_face, font_scale, WHITE_COLOR, text_thickness)
    except Exception as e:
        log_debug(f"Error in process_frame_yolo: {e}", exc_info=True)
        cv2.putText(annotated_frame, "Processing Error", (50, 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            
    return annotated_frame, detected_vehicle_count_in_frame
