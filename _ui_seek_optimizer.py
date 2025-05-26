"""
Seek Optimizer Module
Handles high-performance video seeking with debouncing, thread management, and race condition prevention.
"""
import threading
import time
import cv2
from collections import deque

from . import _ui_shared_refs as refs
from . import globals as app_globals
from .logger_setup import log_debug
from .frame_processor import process_frame_yolo
from .video_handler import format_time_display


class SeekOptimizer:
    """High-performance seek manager with debouncing and thread optimization."""
    
    def __init__(self):
        self.seek_queue = deque(maxlen=1)  # Only keep the latest seek request
        self.current_seek_thread = None
        self.seek_cancel_event = threading.Event()
        self.seek_lock = threading.Lock()
        self.debounce_timer = None
        self.last_seek_time = 0.0
        self.is_seeking = False
        
        # Performance settings
        self.DEBOUNCE_DELAY_MS = 50  # 50ms debounce for rapid interactions
        self.MIN_SEEK_INTERVAL = 0.02  # 20ms minimum between seeks
        self.MAX_CONCURRENT_SEEKS = 1
        
        # Performance monitoring
        self.stats = {
            'total_requests': 0,
            'completed_seeks': 0,
            'cancelled_seeks': 0,
            'debounced_requests': 0,
            'immediate_requests': 0,
            'total_seek_time': 0.0,
            'max_seek_time': 0.0,
            'min_seek_time': float('inf'),
            'avg_seek_time': 0.0,
            'queue_drops': 0,
            'thread_spawns': 0,
            'ui_update_failures': 0
        }
        self.performance_history = deque(maxlen=100)  # Keep last 100 seek times
        self.start_time = time.perf_counter()
        
    def request_seek(self, target_frame, is_real_time_mode=False, force_immediate=False):
        """
        Request a seek operation with intelligent debouncing and optimization.
        
        Args:
            target_frame: Target frame number to seek to
            is_real_time_mode: Whether real-time processing should be applied
            force_immediate: Skip debouncing for immediate seek (e.g., play button)
        """
        current_time = time.perf_counter()
        
        # Performance monitoring
        self.stats['total_requests'] += 1
        
        # Validate frame bounds
        total_frames = app_globals.current_video_meta.get('total_frames', 0)
        if total_frames <= 0:
            log_debug("SeekOptimizer: Invalid total frames, ignoring seek request")
            return
            
        target_frame = max(0, min(target_frame, total_frames - 1))
        
        # Check if we're seeking to the same frame
        if target_frame == app_globals.current_frame_number_global:
            log_debug(f"SeekOptimizer: Already at frame {target_frame}, skipping seek")
            return
        
        # Update queue with latest request (automatic debouncing via maxlen=1)
        seek_request = {
            'frame': target_frame,
            'real_time': is_real_time_mode,
            'timestamp': current_time,
            'force_immediate': force_immediate,
            'request_id': self.stats['total_requests']
        }
        
        with self.seek_lock:
            # Track queue drops
            if self.seek_queue:
                self.stats['queue_drops'] += 1
            self.seek_queue.clear()
            self.seek_queue.append(seek_request)
            
        # Handle immediate vs debounced execution
        if force_immediate or (current_time - self.last_seek_time) > self.MIN_SEEK_INTERVAL:
            self.stats['immediate_requests'] += 1
            self._execute_seek_immediate()
        else:
            self.stats['debounced_requests'] += 1
            self._schedule_debounced_seek()
    
    def _schedule_debounced_seek(self):
        """Schedule a debounced seek execution."""
        root = refs.get_root()
        if not root or not root.winfo_exists():
            return
            
        # Cancel existing timer
        if self.debounce_timer:
            try:
                root.after_cancel(self.debounce_timer)
            except:
                pass
                
        # Schedule new execution
        self.debounce_timer = root.after(self.DEBOUNCE_DELAY_MS, self._execute_seek_from_timer)
    
    def _execute_seek_from_timer(self):
        """Execute seek from timer callback (runs on main thread)."""
        self.debounce_timer = None
        self._execute_seek_immediate()
    
    def _execute_seek_immediate(self):
        """Execute the latest seek request immediately."""
        with self.seek_lock:
            if not self.seek_queue:
                return
                
            seek_request = self.seek_queue.popleft()
        
        # Cancel any existing seek operation
        self._cancel_current_seek()
        
        # Performance monitoring
        self.stats['thread_spawns'] += 1
        seek_request['start_time'] = time.perf_counter()
        
        # Start new seek operation
        self.seek_cancel_event.clear()
        self.current_seek_thread = threading.Thread(
            target=self._seek_worker,
            args=(seek_request,),
            daemon=True,
            name=f"SeekWorker-{seek_request['frame']}-{seek_request['request_id']}"
        )
        
        self.is_seeking = True
        self.last_seek_time = time.perf_counter()
        self.current_seek_thread.start()
        
        log_debug(f"SeekOptimizer: Started seek to frame {seek_request['frame']} (ID: {seek_request['request_id']})")
    
    def _cancel_current_seek(self):
        """Cancel the current seek operation if running."""
        if self.current_seek_thread and self.current_seek_thread.is_alive():
            log_debug("SeekOptimizer: Cancelling previous seek operation")
            self.seek_cancel_event.set()
            self.stats['cancelled_seeks'] += 1
            
            # Give it a moment to cancel gracefully
            self.current_seek_thread.join(timeout=0.1)
            
            if self.current_seek_thread.is_alive():
                log_debug("SeekOptimizer: Previous seek did not cancel in time")
                
        self.current_seek_thread = None
    
    def _seek_worker(self, seek_request):
        """
        Worker thread for performing the actual seek operation.
        
        Args:
            seek_request: Dictionary containing seek parameters
        """
        target_frame = seek_request['frame']
        is_real_time_mode = seek_request['real_time']
        
        try:
            # Check for cancellation before starting
            if self.seek_cancel_event.is_set():
                log_debug(f"SeekOptimizer: Seek to {target_frame} cancelled before start")
                return
            
            # Perform the seek operation with video access lock
            with app_globals.video_access_lock:
                if self.seek_cancel_event.is_set():
                    return
                    
                if not app_globals.video_capture_global or not app_globals.video_capture_global.isOpened():
                    log_debug("SeekOptimizer: Video capture not available")
                    return
                
                # Perform the actual seek
                app_globals.video_capture_global.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                
                if self.seek_cancel_event.is_set():
                    return
                    
                ret, frame = app_globals.video_capture_global.read()
                
                if not ret or frame is None:
                    log_debug(f"SeekOptimizer: Failed to read frame {target_frame}")
                    return
                
                if self.seek_cancel_event.is_set():
                    return
                    
                # Update global state
                app_globals.current_frame_number_global = target_frame
                app_globals.current_video_meta['current_frame'] = target_frame
                
                # Process frame if in real-time mode
                display_frame = frame.copy()
                if is_real_time_mode and app_globals.active_model_object_global:
                    if self.seek_cancel_event.is_set():
                        return
                        
                    try:
                        display_frame, _ = process_frame_yolo(
                            frame, app_globals.active_model_object_global, app_globals.active_class_list_global,
                            is_video_mode=True, active_filter_list=app_globals.active_processed_class_filter_global,
                            current_conf_thresh=app_globals.conf_threshold_global, current_iou_thresh=app_globals.iou_threshold_global
                        )
                    except Exception as e:
                        log_debug(f"SeekOptimizer: Error processing frame: {e}")
                        display_frame = frame.copy()
            
            # Check for cancellation before UI update
            if self.seek_cancel_event.is_set():
                return
                
            # Schedule UI update on main thread
            root = refs.get_root()
            if root and root.winfo_exists():
                root.after(0, lambda: self._update_ui_after_seek(display_frame, target_frame))
                
            # Performance monitoring
            if 'start_time' in seek_request:
                seek_duration = time.perf_counter() - seek_request['start_time']
                self._record_seek_performance(seek_duration, True)
                log_debug(f"SeekOptimizer: Successfully completed seek to frame {target_frame} in {seek_duration:.3f}s")
            else:
                log_debug(f"SeekOptimizer: Successfully completed seek to frame {target_frame} (no timing data)")
            
        except Exception as e:
            log_debug(f"SeekOptimizer: Error during seek to {target_frame}: {e}", exc_info=True)
            if 'start_time' in seek_request:
                seek_duration = time.perf_counter() - seek_request['start_time']
                self._record_seek_performance(seek_duration, False)
        finally:
            self.is_seeking = False
    
    def _update_ui_after_seek(self, display_frame, target_frame):
        """Update UI after seek completion (runs on main thread)."""
        try:
            ui_comps = refs.ui_components
            if not ui_comps:
                return
                
            # Update video display
            if ui_comps.get("video_display") and display_frame is not None:
                ui_comps["video_display"].update_frame(display_frame)
            
            # Update progress slider
            total_frames = app_globals.current_video_meta.get('total_frames', 0)
            if total_frames > 0:
                # Temporarily disable slider updates to prevent feedback loop
                app_globals.is_programmatic_slider_update = True
                try:
                    if ui_comps.get("progress_var"):
                        # Use frame number directly since slider is configured with frame range
                        ui_comps["progress_var"].set(target_frame)
                finally:
                    app_globals.is_programmatic_slider_update = False
            
            # Update time and frame labels
            fps = app_globals.current_video_meta.get('fps', 30.0)
            current_time_sec = target_frame / fps if fps > 0 else 0
            total_time_sec = app_globals.current_video_meta.get('duration_seconds', 0)
            
            if ui_comps.get("time_label"):
                ui_comps["time_label"].config(text=format_time_display(current_time_sec, total_time_sec))
                
            if ui_comps.get("current_frame_label"):
                ui_comps["current_frame_label"].config(text=f"Frame: {target_frame} / {total_frames}")
                
        except Exception as e:
            log_debug(f"SeekOptimizer: Error updating UI after seek: {e}", exc_info=True)
            self.stats['ui_update_failures'] += 1
    
    def _record_seek_performance(self, duration, success):
        """Record performance metrics for a completed seek operation."""
        if success:
            self.stats['completed_seeks'] += 1
            self.stats['total_seek_time'] += duration
            self.stats['max_seek_time'] = max(self.stats['max_seek_time'], duration)
            self.stats['min_seek_time'] = min(self.stats['min_seek_time'], duration)
            
            if self.stats['completed_seeks'] > 0:
                self.stats['avg_seek_time'] = self.stats['total_seek_time'] / self.stats['completed_seeks']
            
            # Add to performance history
            self.performance_history.append({
                'duration': duration,
                'timestamp': time.perf_counter(),
                'success': True
            })
        else:
            # Record failed seek
            self.performance_history.append({
                'duration': duration,
                'timestamp': time.perf_counter(),
                'success': False
            })
    
    def get_status(self):
        """Get current status for debugging."""
        return {
            'is_seeking': self.is_seeking,
            'queue_size': len(self.seek_queue),
            'has_active_thread': self.current_seek_thread and self.current_seek_thread.is_alive(),
            'last_seek_time': self.last_seek_time
        }
        
    def get_performance_stats(self):
        """Get detailed performance statistics."""
        uptime = time.perf_counter() - self.start_time
        recent_seeks = [s for s in self.performance_history if s['timestamp'] > time.perf_counter() - 10.0]
        recent_success_rate = len([s for s in recent_seeks if s['success']]) / max(len(recent_seeks), 1) * 100
            
        stats = self.stats.copy()
        stats.update({
            'uptime_seconds': uptime,
            'requests_per_second': self.stats['total_requests'] / max(uptime, 0.001),
            'success_rate_percent': (self.stats['completed_seeks'] / max(self.stats['total_requests'], 1)) * 100,
            'recent_success_rate_percent': recent_success_rate,
            'queue_efficiency_percent': ((self.stats['total_requests'] - self.stats['queue_drops']) / max(self.stats['total_requests'], 1)) * 100,
            'recent_seeks_count': len(recent_seeks),
            'performance_history_size': len(self.performance_history)
        })
            
        return stats
        
    def reset_stats(self):
        """Reset performance statistics."""
        self.stats = {
            'total_requests': 0,
            'completed_seeks': 0,
            'cancelled_seeks': 0,
            'debounced_requests': 0,
            'immediate_requests': 0,
            'total_seek_time': 0.0,
            'max_seek_time': 0.0,
            'min_seek_time': float('inf'),
            'avg_seek_time': 0.0,
            'queue_drops': 0,
            'thread_spawns': 0,
            'ui_update_failures': 0
        }
        self.performance_history.clear()
        self.start_time = time.perf_counter()
        log_debug("SeekOptimizer: Performance statistics reset")
        
    def log_performance_summary(self):
        """Log performance summary for debugging."""
        stats = self.get_performance_stats()
            
        log_debug("=== SeekOptimizer Performance Summary ===")
        log_debug(f"Uptime: {stats['uptime_seconds']:.1f}s")
        log_debug(f"Total requests: {stats['total_requests']}")
        log_debug(f"Completed seeks: {stats['completed_seeks']}")
        log_debug(f"Success rate: {stats['success_rate_percent']:.1f}%")
        log_debug(f"Recent success rate: {stats['recent_success_rate_percent']:.1f}%")
        log_debug(f"Queue efficiency: {stats['queue_efficiency_percent']:.1f}%")
        log_debug(f"Requests/sec: {stats['requests_per_second']:.1f}")
        log_debug(f"Average seek time: {stats['avg_seek_time']:.3f}s")
        log_debug(f"Min/Max seek time: {stats['min_seek_time']:.3f}s / {stats['max_seek_time']:.3f}s")
        log_debug(f"Thread spawns: {stats['thread_spawns']}")
        log_debug(f"Cancelled seeks: {stats['cancelled_seeks']}")
        log_debug(f"UI update failures: {stats['ui_update_failures']}")
        log_debug("===========================================")
    
    def cancel_all_operations(self):
        """Cancel all pending and active seek operations."""
        log_debug("SeekOptimizer: Cancelling all seek operations")
        
        # Cancel debounce timer
        root = refs.get_root()
        if self.debounce_timer and root and root.winfo_exists():
            try:
                root.after_cancel(self.debounce_timer)
            except:
                pass
            self.debounce_timer = None
        
        # Cancel current seek
        self._cancel_current_seek()
        
        # Clear queue
        with self.seek_lock:
            self.seek_queue.clear()
        
        self.is_seeking = False
    
    def is_busy(self):
        """Check if seek optimizer is currently processing."""
        return self.is_seeking or bool(self.seek_queue)
    
    def get_status(self):
        """Get current status for debugging."""
        return {
            'is_seeking': self.is_seeking,
            'queue_size': len(self.seek_queue),
            'has_active_thread': self.current_seek_thread and self.current_seek_thread.is_alive(),
            'last_seek_time': self.last_seek_time
        }


# Global seek optimizer instance
_seek_optimizer = SeekOptimizer()

def request_seek(target_frame, is_real_time_mode=False, force_immediate=False):
    """Public interface for requesting seek operations."""
    return _seek_optimizer.request_seek(target_frame, is_real_time_mode, force_immediate)

def cancel_all_seeks():
    """Public interface for cancelling all seek operations."""
    return _seek_optimizer.cancel_all_operations()

def is_seek_busy():
    """Check if seek operations are currently active."""
    return _seek_optimizer.is_busy()

def get_seek_status():
    """Get current seek optimizer status."""
    return _seek_optimizer.get_status()

def get_performance_stats():
    """Get detailed performance statistics."""
    return _seek_optimizer.get_performance_stats()

def reset_performance_stats():
    """Reset performance statistics."""
    return _seek_optimizer.reset_stats()

def log_performance_summary():
    """Log performance summary for debugging."""
    return _seek_optimizer.log_performance_summary()

def cleanup_seek_optimizer():
    """Clean up seek optimizer resources."""
    global _seek_optimizer
    _seek_optimizer.log_performance_summary()  # Log final stats before cleanup
    _seek_optimizer.cancel_all_operations()
    log_debug("SeekOptimizer: Cleanup completed")