import os
import time
import json
import logging
from typing import List, Dict, Any

from .config import log_info

logger = logging.getLogger("mizune.trajectory")

class TrajectoryLogger:
    """
    Logs successful multi-step tool executions.
    This generates structured JSONL datasets that can be used to fine-tune future versions of Mizune.
    """
    def __init__(self, data_dir: str = ".data/trajectories"):
        self.data_dir = data_dir
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            
        # Rotate logs daily
        self.current_file = self._get_log_filepath()
        
    def _get_log_filepath(self) -> str:
        date_str = time.strftime("%Y-%m-%d")
        return os.path.join(self.data_dir, f"trajectory_{date_str}.jsonl")
        
    def log_trajectory(self, intent: str, context: List[Dict[str, Any]], tools_called: List[Dict[str, Any]], result: str):
        """
        Logs a single complex task resolution graph.
        """
        # We only care about complex tasks (2 or more tool calls, or coding/web actions)
        if len(tools_called) < 2 and not any(t.get("name") in ["execute_python", "headless_web_agent", "create_skill"] for t in tools_called):
            return
            
        trajectory = {
            "timestamp": time.time(),
            "intent": intent,
            "context_turns": len(context),
            "tools_sequence": tools_called,
            "final_result": result,
            "success": True # Since we only log after it completes
        }
        
        filepath = self._get_log_filepath()
        try:
            with open(filepath, 'a', encoding='utf-8') as f:
                f.write(json.dumps(trajectory) + "\\n")
            log_info(f"[TRAJECTORY] Exported multi-step execution graph (Length: {len(tools_called)})")
        except Exception as e:
            log_info(f"[TRAJECTORY] Error writing to log: {e}")

trajectory_logger = TrajectoryLogger()
