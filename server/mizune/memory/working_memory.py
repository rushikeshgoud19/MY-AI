"""
Working Memory: Attention-weighted RAM cache.
Not FIFO. Not LRU. Attention-based eviction.

Mizune pays attention to:
- Current window focus
- Recent user speech
- Active task context
- Emotional salience
- Predicted next needs
"""

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import time
import heapq
import uuid

class AttentionSource(Enum):
    USER_DIRECT = 5.0      # User said/typed this
    WINDOW_FOCUS = 4.0     # User is looking at this
    TASK_CONTEXT = 3.5     # Part of active task
    PREDICTED_NEED = 3.0   # Subconscious predicted this
    EMOTIONAL_SALIENCE = 2.5  # Strong emotional content
    RECENT_EVENT = 2.0     # Happened recently
    BACKGROUND = 1.0       # System noise

@dataclass
class MemoryItem:
    """Single item in working memory."""
    item_id: str
    content: str                    # Text content
    embedding: np.ndarray           # 768-dim vector
    timestamp: float
    source: AttentionSource
    attention_weight: float = 0.0   # Current attention (0-10)
    decay_rate: float = 0.95        # How fast attention fades
    access_count: int = 0
    last_accessed: float = 0.0
    related_items: List[str] = field(default_factory=list)
    
    def update_attention(self, current_time: float):
        """Decay attention based on time since last access."""
        time_delta = current_time - self.last_accessed
        # Exponential decay
        self.attention_weight *= (self.decay_rate ** time_delta)
        
        # Boost for recent access
        if self.access_count > 0:
            self.attention_weight += 0.5 * self.access_count
    
    def __lt__(self, other):
        """For heapq — higher attention = higher priority."""
        return self.attention_weight > other.attention_weight  # Inverted for max-heap

class WorkingMemory:
    """
    Attention-based working memory. 10,000 items max.
    Eviction: Lowest attention weight, not oldest.
    """
    
    MAX_ITEMS = 10000
    ATTENTION_THRESHOLD = 1.0  # Below this, eligible for eviction
    
    def __init__(self, embedding_dim: int = 768):
        self.items: Dict[str, MemoryItem] = {}
        self.access_heap: List[Tuple[float, str]] = []  # (attention, item_id)
        self.embedding_dim = embedding_dim
        
        # Current focus window
        self.focus_process: Optional[str] = None
        self.focus_window_title: Optional[str] = None
        self.focus_start_time: float = 0.0
        
        # Active task context
        self.active_task_id: Optional[str] = None
        self.task_stack: List[str] = []  # Task hierarchy
        
    def add(self, content: str, embedding: np.ndarray, 
            source: AttentionSource,
            item_id: Optional[str] = None) -> MemoryItem:
        """Add item to working memory."""
        item_id = item_id or str(uuid.uuid4())
        
        # Calculate initial attention based on source
        base_attention = source.value
        
        # Boost if related to current focus
        if self._is_related_to_focus(content):
            base_attention += 2.0
        
        # Boost if part of active task
        if self._is_related_to_task(content):
            base_attention += 1.5
        
        item = MemoryItem(
            item_id=item_id,
            content=content,
            embedding=embedding,
            timestamp=time.time(),
            source=source,
            attention_weight=base_attention,
            last_accessed=time.time()
        )
        
        # Evict if at capacity
        if len(self.items) >= self.MAX_ITEMS:
            self._evict_lowest_attention()
        
        self.items[item_id] = item
        heapq.heappush(self.access_heap, (item.attention_weight, item_id))
        
        return item
    
    def _is_related_to_focus(self, content: str) -> bool:
        """Check if content relates to current window focus."""
        if not self.focus_window_title:
            return False
        
        # Simple keyword overlap
        focus_words = set(self.focus_window_title.lower().split())
        content_words = set(content.lower().split())
        overlap = len(focus_words & content_words)
        
        return overlap > 0
    
    def _is_related_to_task(self, content: str) -> bool:
        """Check if content relates to active task."""
        if not self.active_task_id:
            return False
        
        # Check task context
        # Implementation depends on task representation
        return False  # Placeholder
    
    def _evict_lowest_attention(self):
        """Evict item with lowest attention weight."""
        while self.access_heap:
            attention, item_id = heapq.heappop(self.access_heap)
            if item_id in self.items:
                item = self.items[item_id]
                item.update_attention(time.time())
                
                if item.attention_weight < self.ATTENTION_THRESHOLD:
                    # Evict this item
                    del self.items[item_id]
                    # Archive to episodic store before eviction
                    self._archive_item(item)
                    return
                else:
                    # Re-insert with updated attention
                    heapq.heappush(self.access_heap, (item.attention_weight, item_id))
    
    def _archive_item(self, item: MemoryItem):
        """Archive evicted item to episodic store."""
        # Send to EpisodicStore for L0→L1 compression
        pass
    
    def retrieve(self, query_embedding: np.ndarray, 
                 top_k: int = 10,
                 min_attention: float = 0.0) -> List[MemoryItem]:
        """
        Retrieve items by semantic similarity + attention weight.
        Not pure vector search — attention biases results.
        """
        if not self.items:
            return []
        
        # Update all attention weights
        current_time = time.time()
        for item in self.items.values():
            item.update_attention(current_time)
        
        # Calculate hybrid scores: similarity * attention
        scores = []
        for item in self.items.values():
            if item.attention_weight < min_attention:
                continue
            
            # Cosine similarity
            similarity = np.dot(query_embedding, item.embedding) / (
                np.linalg.norm(query_embedding) * np.linalg.norm(item.embedding)
            )
            
            # Hybrid score: similarity weighted by attention
            # High attention items can outrank more similar low-attention items
            hybrid_score = similarity * (1 + item.attention_weight / 10)
            scores.append((hybrid_score, item))
        
        # Sort by hybrid score
        scores.sort(reverse=True)
        
        # Update access counts for retrieved items
        for _, item in scores[:top_k]:
            item.access_count += 1
            item.last_accessed = current_time
        
        return [item for _, item in scores[:top_k]]
    
    def update_focus(self, process_name: str, window_title: str):
        """Update current focus. Boosts attention of related items."""
        self.focus_process = process_name
        self.focus_window_title = window_title
        self.focus_start_time = time.time()
        
        # Boost attention of related items
        for item in self.items.values():
            if self._is_related_to_focus(item.content):
                item.attention_weight += 1.0
                item.last_accessed = time.time()
    
    def get_attention_landscape(self) -> Dict:
        """Get current attention distribution. For dashboard visualization."""
        attention_values = [item.attention_weight for item in self.items.values()]
        
        return {
            'total_items': len(self.items),
            'max_attention': max(attention_values) if attention_values else 0,
            'mean_attention': np.mean(attention_values) if attention_values else 0,
            'attention_distribution': np.histogram(
                attention_values, 
                bins=[0, 1, 2, 3, 5, 7, 10]
            )[0].tolist() if attention_values else [],
            'top_focus_items': [
                {
                    'id': item.item_id,
                    'content': item.content[:50],
                    'attention': item.attention_weight,
                    'source': item.source.name
                }
                for item in sorted(
                    self.items.values(), 
                    key=lambda x: x.attention_weight, 
                    reverse=True
                )[:5]
            ]
        }
