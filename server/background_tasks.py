import threading
import queue
import time
import uuid
import logging
from server.config import log_info

class BackgroundTaskRunner:
    """Runs Mizune's heavy tasks silently without disturbing Master's screen."""
    
    def __init__(self, max_workers=3):
        self._task_queue = queue.Queue()
        self._active_tasks = {}  # task_id -> {status, result, ...}
        self._workers = []
        self._lock = threading.Lock()
        
        for i in range(max_workers):
            t = threading.Thread(target=self._worker_loop, daemon=True)
            t.start()
            self._workers.append(t)
            
    def submit(self, func, *args, callback=None, **kwargs):
        """Submit a task to run in the background. Returns task_id."""
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        with self._lock:
            self._active_tasks[task_id] = {"status": "queued", "submitted": time.time(), "result": None}
        self._task_queue.put((task_id, func, args, kwargs, callback))
        return task_id
    
    def get_status(self, task_id):
        with self._lock:
            return self._active_tasks.get(task_id, {"status": "unknown"})
    
    def _worker_loop(self):
        while True:
            try:
                task_id, func, args, kwargs, callback = self._task_queue.get()
                
                with self._lock:
                    if task_id in self._active_tasks:
                        self._active_tasks[task_id]["status"] = "running"
                        
                log_info(f"[BACKGROUND] Started {task_id}")
                
                # Let the websocket manager know a task started
                from server.websocket import ws_manager
                ws_manager.broadcast_sync({"type": "task_update", "data": f"Started {task_id}..."})
                
                try:
                    result = func(*args, **kwargs)
                    with self._lock:
                        if task_id in self._active_tasks:
                            self._active_tasks[task_id].update({"status": "done", "result": result})
                            
                    log_info(f"[BACKGROUND] Finished {task_id}")
                    ws_manager.broadcast_sync({"type": "task_complete", "data": f"{task_id} finished successfully!"})
                    
                    if callback:
                        try:
                            callback(task_id, result)
                        except Exception as cb_e:
                            log_info(f"[BACKGROUND] Callback error for {task_id}: {cb_e}")
                            
                except Exception as e:
                    with self._lock:
                        if task_id in self._active_tasks:
                            self._active_tasks[task_id].update({"status": "error", "error": str(e)})
                    log_info(f"[BACKGROUND] Error in {task_id}: {e}")
                    ws_manager.broadcast_sync({"type": "task_complete", "data": f"Error in {task_id}: {e}"})
                finally:
                    self._task_queue.task_done()
                    
            except Exception as loop_e:
                log_info(f"[BACKGROUND] Worker loop error: {loop_e}")

# Global instance
task_runner = BackgroundTaskRunner()
