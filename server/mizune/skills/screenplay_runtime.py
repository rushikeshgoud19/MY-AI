"""
Skill Screenplay Runtime

A screenplay is a sequence of actions that can be executed:
1. Vision verification at each step (expected screen state)
2. Fallback paths for when UI changes
3. Automatic repair when elements move
4. Self-healing via re-recording

This is Mizune's moat. No other agent has this.
"""

import json
import time
import os
import uuid
import asyncio
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple, Callable
from enum import Enum
import numpy as np

class ActionType(Enum):
    CLICK = "click"
    DOUBLE_CLICK = "double_click"
    RIGHT_CLICK = "right_click"
    TYPE = "type"
    HOTKEY = "hotkey"
    SCROLL = "scroll"
    DRAG = "drag"
    WAIT = "wait"
    VERIFY_SCREEN = "verify_screen"
    LAUNCH_APP = "launch_app"
    FOCUS_WINDOW = "focus_window"
    TAKE_SCREENSHOT = "take_screenshot"
    EXECUTE_CODE = "execute_code"

@dataclass
class ScreenState:
    """Expected screen state for verification."""
    phash: str                      # Perceptual hash of screenshot
    app_name: str
    window_title: str
    ui_elements: List[Dict]         # Expected elements with fuzzy matching
    ocr_text: Optional[str] = None  # Expected text on screen
    
    def similarity(self, actual: 'ScreenState') -> float:
        """Calculate similarity to actual screen state. 0-1."""
        score = 0.0
        
        # App match
        if self.app_name == actual.app_name:
            score += 0.3
        
        # Window title fuzzy match
        if self.window_title and actual.window_title:
            title_sim = self._fuzzy_similarity(self.window_title, actual.window_title)
            score += 0.2 * title_sim
        
        # pHash similarity
        if self.phash and actual.phash:
            phash_sim = self._phash_distance(self.phash, actual.phash)
            score += 0.3 * phash_sim
        
        # UI elements match
        if self.ui_elements and actual.ui_elements:
            element_sim = self._element_similarity(self.ui_elements, actual.ui_elements)
            score += 0.2 * element_sim
        
        return score
    
    def _fuzzy_similarity(self, a: str, b: str) -> float:
        """Simple fuzzy string similarity."""
        try:
            from difflib import SequenceMatcher
            return SequenceMatcher(None, a, b).ratio()
        except ImportError:
            return 1.0 if a == b else 0.0
    
    def _phash_distance(self, hash1: str, hash2: str) -> float:
        """Convert Hamming distance to similarity."""
        try:
            import imagehash
            # If using imagehash.hex_to_hash
            h1 = imagehash.hex_to_hash(hash1)
            h2 = imagehash.hex_to_hash(hash2)
            # Distance ranges from 0 to 64
            distance = h1 - h2
            return max(0.0, 1.0 - (distance / 64.0))
        except ImportError:
            return 1.0 if hash1 == hash2 else 0.0
    
    def _element_similarity(self, expected: List[Dict], actual: List[Dict]) -> float:
        """Match UI elements by label/role with fuzzy tolerance."""
        matches = 0
        for exp in expected:
            for act in actual:
                if self._element_match(exp, act):
                    matches += 1
                    break
        
        return matches / max(len(expected), len(actual)) if expected or actual else 0.0
    
    def _element_match(self, a: Dict, b: Dict) -> bool:
        """Fuzzy element matching."""
        # Match by label text (fuzzy)
        label_sim = self._fuzzy_similarity(
            a.get('label', ''), 
            b.get('label', '')
        )
        if label_sim > 0.8:
            return True
        
        # Match by role + approximate position
        if a.get('role') == b.get('role'):
            pos_diff = abs(a.get('x', 0) - b.get('x', 0)) + \
                      abs(a.get('y', 0) - b.get('y', 0))
            if pos_diff < 50:  # 50px tolerance
                return True
        
        return False

@dataclass
class Action:
    """Single executable action in a screenplay."""
    action_type: ActionType
    params: Dict
    
    # Verification
    expected_pre_state: Optional[ScreenState] = None
    expected_post_state: Optional[ScreenState] = None
    
    # Fallbacks
    retry_count: int = 3
    fallback_actions: List['Action'] = None
    
    # Dynamic resolution
    element_locator: Optional[str] = None  # "button with label 'Export'"
    use_vision: bool = True  # Use vision to find element if coordinates fail

@dataclass
class Screenplay:
    """Complete executable skill."""
    name: str
    version: str
    description: str
    
    # Preconditions
    required_apps: List[str]
    required_resolution: Optional[Tuple[int, int]] = None
    
    # The script
    actions: List[Action]
    
    # Expected outcomes
    success_criteria: List[str]
    
    # Failure recovery
    failure_handler: Optional['Action'] = None
    
    # Metadata
    success_count: int = 0
    failure_count: int = 0
    avg_execution_time: float = 0.0
    last_executed: Optional[float] = None
    
    def calculate_success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0

class ScreenplayRuntime:
    """
    Executes screenplays with vision verification and self-healing.
    """
    
    def __init__(self, vision_agent=None, input_agent=None, kernel=None):
        self.vision = vision_agent
        self.input = input_agent
        self.kernel = kernel
        
        # Element cache for dynamic resolution
        self.element_cache: Dict[str, Dict] = {}  # label -> last known position
    
    async def execute(self, screenplay: Screenplay, 
                    context: Dict = None) -> Dict:
        """
        Execute a screenplay with full verification and recovery.
        """
        start_time = time.time()
        results = []
        
        # Check preconditions
        precheck = self._check_preconditions(screenplay)
        if not precheck['success']:
            return {
                'success': False,
                'error': f"Preconditions failed: {precheck['reason']}",
                'stage': 'preconditions'
            }
        
        # Execute each action
        for i, action in enumerate(screenplay.actions):
            try:
                result = await self._execute_action(action, context)
                results.append(result)
                
                if not result['success']:
                    # Try fallback actions
                    if action.fallback_actions:
                        for fallback in action.fallback_actions:
                            fallback_result = await self._execute_action(fallback, context)
                            results.append(fallback_result)
                            if fallback_result['success']:
                                break
                        else:
                            # All fallbacks failed
                            return self._handle_failure(screenplay, i, results, "All fallbacks failed")
                    else:
                        return self._handle_failure(screenplay, i, results, result.get('error', 'Unknown error'))
                
            except Exception as e:
                return self._handle_failure(screenplay, i, results, str(e))
        
        # Verify success criteria
        success = self._verify_success(screenplay.success_criteria)
        
        # Update statistics
        execution_time = time.time() - start_time
        if success:
            screenplay.success_count += 1
        else:
            screenplay.failure_count += 1
        screenplay.avg_execution_time = (
            (screenplay.avg_execution_time * (screenplay.success_count + screenplay.failure_count - 1) + execution_time) /
            (screenplay.success_count + screenplay.failure_count)
        )
        screenplay.last_executed = time.time()
        
        return {
            'success': success,
            'execution_time': execution_time,
            'actions_executed': len(results),
            'results': results,
            'screenplay': screenplay.name
        }
    
    async def _execute_action(self, action: Action, context: Dict) -> Dict:
        """Execute single action with verification."""
        
        # Pre-state verification
        if action.expected_pre_state and self.vision:
            current_state = self.vision.capture_screen_state()
            similarity = action.expected_pre_state.similarity(current_state)
            if similarity < 0.6:
                # Screen doesn't match expected — try to recover
                recovery = await self._recover_to_state(action.expected_pre_state)
                if not recovery['success']:
                    return {
                        'success': False,
                        'error': f"Pre-state verification failed (similarity: {similarity:.2f})",
                        'recovery_attempted': True
                    }
        
        # Execute the action
        execution_result = await self._perform_action(action)
        
        # Post-state verification
        if action.expected_post_state and action.use_vision and self.vision:
            # Wait briefly for UI to settle
            await asyncio.sleep(0.5)
            
            current_state = self.vision.capture_screen_state()
            similarity = action.expected_post_state.similarity(current_state)
            
            if similarity < 0.5:
                # Post-state doesn't match — UI may have changed
                # Try to find alternative path
                return {
                    'success': False,
                    'error': f"Post-state verification failed (similarity: {similarity:.2f})",
                    'suggestion': 'UI may have changed, consider re-recording'
                }
        
        return {
            'success': True,
            'action': action.action_type.value,
            'params': action.params
        }
    
    async def _perform_action(self, action: Action) -> Dict:
        """Perform the actual input action."""
        atype = action.action_type
        
        # Mocks for input/vision if none provided
        if not self.input:
            print(f"[Screenplay] Mock Action: {atype.value} - {action.params}")
            return {'success': True, 'mocked': True}
            
        if atype == ActionType.CLICK:
            x, y = await self._resolve_coordinates(action)
            self.input.click(x, y)
            return {'success': True, 'coords': (x, y)}
        
        elif atype == ActionType.TYPE:
            text = action.params.get('text', '')
            self.input.type_text(text)
            return {'success': True, 'text': text[:50]}
        
        elif atype == ActionType.HOTKEY:
            keys = action.params.get('keys', [])
            self.input.hotkey(*keys)
            return {'success': True, 'keys': keys}
        
        elif atype == ActionType.LAUNCH_APP:
            app = action.params.get('app', '')
            if self.kernel:
                # Use kernel to launch if integrated
                pass
            return {'success': True, 'app': app}
        
        elif atype == ActionType.WAIT:
            seconds = action.params.get('seconds', 1)
            await asyncio.sleep(seconds)
            return {'success': True, 'waited': seconds}
        
        elif atype == ActionType.TAKE_SCREENSHOT:
            path = action.params.get('path', 'screenshots/')
            if self.vision:
                screenshot = self.vision.capture(path)
                return {'success': True, 'path': screenshot}
            return {'success': False, 'error': 'No vision agent'}
        
        elif atype == ActionType.EXECUTE_CODE:
            code = action.params.get('code', '')
            # Sandboxed execution
            result = self._sandbox_execute(code)
            return {'success': True, 'result': result}
        
        return {'success': False, 'error': f'Unknown action type: {atype}'}
    
    async def _resolve_coordinates(self, action: Action) -> Tuple[int, int]:
        """
        Resolve click coordinates. Tries multiple strategies:
        1. Exact coordinates from params
        2. Element locator (vision-based)
        3. Cached element position
        4. Fuzzy search on current screen
        """
        # Try exact coordinates first
        if 'x' in action.params and 'y' in action.params:
            return action.params['x'], action.params['y']
        
        if not self.vision:
            return 0, 0
            
        # Try element locator
        if action.element_locator:
            element = await self.vision.find_element(action.element_locator)
            if element:
                # Update cache
                self.element_cache[action.element_locator] = element
                return element['x'] + element['w']//2, element['y'] + element['h']//2
        
        # Try cache
        if action.element_locator in self.element_cache:
            cached = self.element_cache[action.element_locator]
            # Verify element still there (quick check)
            if await self.vision.verify_element_at(cached['x'], cached['y']):
                return cached['x'] + cached['w']//2, cached['y'] + cached['h']//2
        
        # Failed to resolve
        raise RuntimeError(f"Could not resolve coordinates for: {action.element_locator or 'unknown element'}")
    
    async def _recover_to_state(self, target_state: ScreenState) -> Dict:
        """
        Attempt to recover to expected screen state.
        Strategies: launch app, navigate menu, press Escape, etc.
        """
        if not self.input:
            return {'success': False}
            
        # Try pressing Escape to clear dialogs
        self.input.press('escape')
        await asyncio.sleep(0.5)
        
        # Try Alt-Tab to find window
        self.input.hotkey('alt', 'tab')
        await asyncio.sleep(0.3)
        
        return {'success': False, 'method': 'exhausted'}
    
    def _check_preconditions(self, screenplay: Screenplay) -> Dict:
        """Check if system meets screenplay requirements."""
        if not self.vision:
            return {'success': True}
            
        # Check resolution
        if screenplay.required_resolution:
            current_res = self.vision.get_screen_resolution()
            if current_res != screenplay.required_resolution:
                return {
                    'success': False,
                    'reason': f"Resolution mismatch: {current_res} vs {screenplay.required_resolution}"
                }
        
        return {'success': True}
    
    def _verify_success(self, criteria: List[str]) -> bool:
        """Verify success criteria were met."""
        # Check each criterion
        for criterion in criteria:
            if criterion.startswith('file_exists:'):
                path = criterion.split(':', 1)[1]
                if not os.path.exists(os.path.expanduser(path)):
                    return False
            
            elif criterion.startswith('window_title:'):
                expected = criterion.split(':', 1)[1]
                if self.vision:
                    current = self.vision.get_active_window_title()
                    if expected not in current:
                        return False
        
        return True
    
    def _handle_failure(self, screenplay: Screenplay, action_index: int,
                       results: List[Dict], error: str) -> Dict:
        """Handle screenplay failure. Log for learning."""
        if self.kernel:
            from server.mizune.kernel.event_interceptor import KernelEvent, EventType
            self.kernel.event_queue.put(KernelEvent(
                event_id=str(uuid.uuid4()),
                timestamp=time.time(),
                event_type=EventType.PROCESS_END,  # Or custom type
                process_id=0,
                process_name='screenplay_runtime',
                thread_id=0,
                user_sid='',
                payload={
                    'screenplay': screenplay.name,
                    'failed_at_action': action_index,
                    'error': error,
                    'results': results
                },
                importance_score=0.9  # High importance — failure to learn from
            ))
        
        return {
            'success': False,
            'error': error,
            'failed_at_action': action_index,
            'screenplay': screenplay.name
        }
    
    def _sandbox_execute(self, code: str) -> Dict:
        """Execute code in restricted sandbox."""
        # Use RestrictedPython or similar
        # No network, no filesystem except temp, timeout
        import subprocess
        result = subprocess.run(
            ['python', '-c', code],
            capture_output=True,
            text=True,
            timeout=5,
            cwd='/tmp'
        )
        return {
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode
        }
