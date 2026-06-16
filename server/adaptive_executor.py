import time
import re
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Optional
import asyncio

from server.config import log_info
from server.emotion_engine import global_emotion_state

class TaskState(Enum):
    PENDING = auto()
    ANALYZING = auto()
    AWAITING_CLARIFICATION = auto()
    EXECUTING = auto()
    CHECKPOINT = auto()
    COMPLETED = auto()
    FAILED = auto()
    ABANDONED = auto()

@dataclass
class TaskStep:
    id: str
    description: str
    action: str
    requires_clarification: bool = False
    clarification_prompt: str = ""
    estimated_risk: float = 0.0
    alternatives: List[str] = field(default_factory=list)
    status: str = 'pending'
    result: Optional[str] = None

@dataclass
class Checkpoint:
    step_index: int
    question: str
    options: List[str] = field(default_factory=list)
    user_response: Optional[str] = None
    allow_freeform: bool = True

@dataclass
class Task:
    id: str
    description: str
    state: TaskState
    steps: List[TaskStep]
    current_step: int = 0
    checkpoints: List[Checkpoint] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

CLARIFICATION_TRIGGERS = [
    {'pattern': r'delete|remove|rm -rf|drop|uninstall', 'risk': 0.8, 
     'prompt': 'This will permanently delete something. Are you sure?'},
    {'pattern': r'purchase|buy|payment|charge|billing', 'risk': 0.9,
     'prompt': 'This involves spending money. Shall I proceed?'},
    {'pattern': r'send email|message|notify|announce', 'risk': 0.6,
     'prompt': 'This will send a message. Review before sending?'},
    {'pattern': r'fix|improve|optimize|clean up', 'risk': 0.4,
     'prompt': 'There are multiple ways to fix this. Which approach do you prefer?'},
]

class AdaptiveExecutor:
    def __init__(self, broadcast_fn):
        self.emotion = global_emotion_state
        self.broadcast_fn = broadcast_fn
    
    def _detect_triggers(self, text: str) -> Optional[dict]:
        text_lower = text.lower()
        for trigger in CLARIFICATION_TRIGGERS:
            if re.search(trigger['pattern'], text_lower):
                return trigger
        return None

    async def execute(self, task: Task) -> Task:
        task.state = TaskState.EXECUTING
        
        for i, step in enumerate(task.steps):
            task.current_step = i
            
            # CHECKPOINT: Ask user before risky/ambiguous steps
            trigger = self._detect_triggers(step.description + " " + step.action)
            if trigger and step.status == 'pending':
                task.state = TaskState.AWAITING_CLARIFICATION
                checkpoint = Checkpoint(
                    step_index=i,
                    question=trigger['prompt'],
                    options=['Proceed', 'Abort', 'Skip'],
                    allow_freeform=True
                )
                task.checkpoints.append(checkpoint)
                await self._notify_checkpoint(task, checkpoint)
                return task  # PAUSED — wait for user
            
            # Execute step (Simulation for architecture hook)
            try:
                log_info(f"[ADAPTIVE EXECUTOR] Executing step: {step.action}")
                # Real execution logic goes here via mizune_manager
                await asyncio.sleep(0.5)
                
                step.status = 'completed'
                step.result = "Success"
                self.emotion.valence += 0.05  # Success feels good
            except Exception as e:
                step.status = 'failed'
                step.result = str(e)
                self.emotion.valence -= 0.1
                self.emotion.confidence -= 0.05
                
                task.state = TaskState.CHECKPOINT
                checkpoint = Checkpoint(
                    step_index=i,
                    question=f"Error: {e}. Retry, skip this step, or abort?",
                    options=['retry', 'skip', 'abort'],
                    allow_freeform=True
                )
                task.checkpoints.append(checkpoint)
                await self._notify_checkpoint(task, checkpoint)
                return task  # PAUSED
        
        task.state = TaskState.COMPLETED
        self.emotion.valence += 0.1
        self.emotion.confidence += 0.05
        return task
    
    async def resume_after_checkpoint(self, task: Task, user_response: str):
        if not task.checkpoints:
            return task
            
        checkpoint = task.checkpoints[-1]
        checkpoint.user_response = user_response
        
        if user_response.lower() in ['abort', 'cancel', 'stop']:
            task.state = TaskState.ABANDONED
            self.emotion.valence -= 0.15
            if self.broadcast_fn:
                self.broadcast_fn({"type": "status", "text": "Task aborted."})
            return task
        
        elif user_response.lower() in ['skip', 'next', 'proceed']:
            task.steps[task.current_step].status = 'skipped' if 'skip' in user_response.lower() else 'completed'
            task.state = TaskState.EXECUTING
        
        elif user_response.lower() in ['retry', 'try again']:
            task.state = TaskState.EXECUTING
            
        self.emotion.valence += 0.05
        return await self.execute(task)
    
    async def _notify_checkpoint(self, task: Task, checkpoint: Checkpoint):
        msg = f"CHECKPOINT: {checkpoint.question} Options: {checkpoint.options}"
        log_info(f"[ADAPTIVE EXECUTOR] {msg}")
        if self.broadcast_fn:
            self.broadcast_fn({"type": "status", "text": msg})
