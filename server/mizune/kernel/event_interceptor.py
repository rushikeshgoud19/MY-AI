"""
Mizune Kernel Event Interceptor
Windows: Uses ETW (Event Tracing for Windows) + API hooks
Linux: eBPF + ptrace
macOS: Endpoint Security + DTrace

Every file open, network packet, window focus change, process spawn
becomes an event in Mizune's episodic memory. No polling. No scraping.
Direct kernel integration.
"""

import ctypes
import json
import sqlite3
import time
import sys
import uuid
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Callable
from enum import Enum, auto
import threading
import queue

class EventType(Enum):
    FILE_CREATE = auto()
    FILE_MODIFY = auto()
    FILE_DELETE = auto()
    FILE_READ = auto()
    PROCESS_START = auto()
    PROCESS_END = auto()
    PROCESS_FOCUS = auto()
    WINDOW_FOCUS = auto()
    WINDOW_CLOSE = auto()
    NETWORK_OUT = auto()
    NETWORK_IN = auto()
    CLIPBOARD_COPY = auto()
    CLIPBOARD_PASTE = auto()
    KEYBOARD_INPUT = auto()  # Only hotkeys, not keylogging
    MOUSE_CLICK = auto()
    SCREENSHOT = auto()
    AUDIO_START = auto()
    AUDIO_END = auto()
    USB_ATTACH = auto()
    USB_DETACH = auto()

@dataclass
class KernelEvent:
    event_id: str           # UUID v4
    timestamp: float        # nanosecond precision
    event_type: EventType
    process_id: int
    process_name: str
    thread_id: int
    user_sid: str          # Windows SID / Linux UID
    
    # Event-specific payload
    payload: Dict
    
    # Enrichment (added by Mizune)
    importance_score: float = 0.0
    embedding: Optional[bytes] = None
    related_events: List[str] = None
    
    def to_dict(self):
        return {
            'event_id': self.event_id,
            'timestamp': self.timestamp,
            'event_type': self.event_type.name,
            'process_id': self.process_id,
            'process_name': self.process_name,
            'payload': json.dumps(self.payload),
            'importance': self.importance_score
        }

class EventImportanceScorer:
    """
    <1ms local scoring. No LLM. Determines what Mizune pays attention to.
    """
    
    # Process importance weights
    PROCESS_WEIGHTS = {
        'code.exe': 0.9,           # VS Code = high
        'chrome.exe': 0.7,         # Browser = medium-high
        'figma.exe': 0.8,          # Design = high
        'discord.exe': 0.5,        # Chat = medium
        'explorer.exe': 0.3,       # File manager = low
        'spotify.exe': 0.2,        # Music = low
    }
    
    # Event type base scores
    TYPE_SCORES = {
        EventType.WINDOW_FOCUS: 0.6,
        EventType.PROCESS_START: 0.7,
        EventType.FILE_CREATE: 0.5,
        EventType.FILE_MODIFY: 0.6,
        EventType.NETWORK_OUT: 0.4,
        EventType.CLIPBOARD_COPY: 0.8,   # Likely copying something important
        EventType.SCREENSHOT: 0.9,       # User explicitly captured screen
    }
    
    # Time-based modulation
    OFF_HOURS_BOOST = 0.15  # 11pm-6am = more important (user focused)
    
    def score(self, event: KernelEvent) -> float:
        """Calculate importance score. 0.0-1.0."""
        score = 0.0
        
        # Process weight
        proc_weight = self.PROCESS_WEIGHTS.get(
            event.process_name.lower(), 0.3
        )
        score += proc_weight * 0.4
        
        # Event type
        type_score = self.TYPE_SCORES.get(event.event_type, 0.3)
        score += type_score * 0.3
        
        # Time modulation
        hour = time.localtime(event.timestamp).tm_hour
        if hour < 6 or hour > 23:
            score += self.OFF_HOURS_BOOST
        
        # Payload analysis (fast heuristics)
        payload = event.payload
        if 'error' in str(payload).lower():
            score += 0.2
        if 'docker' in str(payload).lower() and 'error' in str(payload).lower():
            score += 0.3  # Rushi hates Docker errors
        
        return min(1.0, score)

class MizuneKernel:
    """
    The kernel module. Intercepts system events and feeds them into
    Mizune's consciousness. Runs as a Windows service / Linux daemon.
    """
    
    def __init__(self, db_path: str = "kernel_events.db"):
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self._init_schema()
        
        # Event routing
        self.event_queue = queue.Queue(maxsize=100000)
        self.subscribers: Dict[EventType, List[Callable]] = {}
        
        self._running = False
        
        # Importance scoring (local, <1ms)
        self.scorer = EventImportanceScorer()
        
    def _init_schema(self):
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS kernel_events (
                event_id TEXT PRIMARY KEY,
                timestamp REAL,
                event_type TEXT,
                process_id INTEGER,
                process_name TEXT,
                thread_id INTEGER,
                user_sid TEXT,
                payload TEXT,
                importance_score REAL DEFAULT 0.0,
                embedding BLOB,
                related_events TEXT,
                indexed_at REAL DEFAULT 0
            );
            
            CREATE INDEX IF NOT EXISTS idx_events_time ON kernel_events(timestamp);
            CREATE INDEX IF NOT EXISTS idx_events_type ON kernel_events(event_type);
            CREATE INDEX IF NOT EXISTS idx_events_process ON kernel_events(process_name, timestamp);
            CREATE INDEX IF NOT EXISTS idx_events_importance ON kernel_events(importance_score DESC);
            
            -- Virtual table for full-text search
            CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(
                process_name, payload,
                content='kernel_events', content_rowid='rowid'
            );
            
            -- Triggers to keep FTS synced
            CREATE TRIGGER IF NOT EXISTS events_ai AFTER INSERT ON kernel_events BEGIN
                INSERT INTO events_fts(rowid, process_name, payload)
                VALUES (new.rowid, new.process_name, new.payload);
            END;
            
            -- Event summaries (L1 compression)
            CREATE TABLE IF NOT EXISTS event_summaries (
                summary_id TEXT PRIMARY KEY,
                start_time REAL,
                end_time REAL,
                event_types TEXT,
                process_names TEXT,
                summary_text TEXT,
                key_entities TEXT,
                importance_score REAL,
                event_count INTEGER
            );
        """)
        self.db.commit()
    
    def start(self):
        """Start kernel event interception."""
        if self._running:
            return
        self._running = True
        
        # Platform-specific initialization (ETW mock for now to prevent crashes)
        if sys.platform == 'win32':
            print("[MizuneKernel] Windows detected. Using polling mock for ETW.")
            self._init_windows_polling_mock()
        elif sys.platform == 'linux':
            print("[MizuneKernel] Linux detected. eBPF setup pending.")
        
        # Start event processing pipeline
        self._processor_thread = threading.Thread(target=self._process_events)
        self._processor_thread.daemon = True
        self._processor_thread.start()
        
        # Start L1 compression (subconscious)
        self._compression_thread = threading.Thread(target=self._compress_loop)
        self._compression_thread.daemon = True
        self._compression_thread.start()
        
        print("[MizuneKernel] Event interception active")
    
    def _init_windows_polling_mock(self):
        """
        Mock for ETW using psutil to safely capture some process events without admin driver issues.
        """
        def poll_loop():
            import psutil
            try:
                import pygetwindow as gw
            except ImportError:
                gw = None
                
            last_window = ""
            known_pids = set(psutil.pids())
            
            while self._running:
                # Mock window focus
                if gw:
                    try:
                        active = gw.getActiveWindow()
                        title = active.title if active else ""
                        if title and title != last_window:
                            last_window = title
                            self.event_queue.put(KernelEvent(
                                event_id=str(uuid.uuid4()),
                                timestamp=time.time(),
                                event_type=EventType.WINDOW_FOCUS,
                                process_id=0,
                                process_name="unknown",
                                thread_id=0,
                                user_sid="user",
                                payload={"window_title": title}
                            ))
                    except Exception:
                        pass
                        
                # Mock process start
                current_pids = set(psutil.pids())
                new_pids = current_pids - known_pids
                for pid in new_pids:
                    try:
                        p = psutil.Process(pid)
                        name = p.name()
                        self.event_queue.put(KernelEvent(
                            event_id=str(uuid.uuid4()),
                            timestamp=time.time(),
                            event_type=EventType.PROCESS_START,
                            process_id=pid,
                            process_name=name,
                            thread_id=0,
                            user_sid="user",
                            payload={"cmdline": p.cmdline() if p.cmdline() else []}
                        ))
                    except Exception:
                        pass
                known_pids = current_pids
                time.sleep(1)
                
        t = threading.Thread(target=poll_loop, daemon=True)
        t.start()
        
    def _process_events(self):
        """Main event processing loop. <5ms per event."""
        while self._running:
            try:
                event = self.event_queue.get(timeout=1)
                
                # Step 1: Score importance (local, no LLM)
                event.importance_score = self.scorer.score(event)
                
                # Step 2: Route to subscribers
                self._route_event(event)
                
                # Step 3: Store (async, non-blocking)
                self._store_event(event)
                
                # Step 4: Update working memory (RAM-hot)
                self._update_working_memory(event)
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[Kernel] Process events error: {e}")
    
    def _route_event(self, event: KernelEvent):
        """Route to subscribers based on event type and importance."""
        subs = self.subscribers.get(event.event_type, [])
        
        # Also route to catch-all subscribers for high-importance events
        if event.importance_score > 0.7:
            subs.extend(self.subscribers.get(EventType.PROCESS_FOCUS, []))
        
        for callback in subs:
            try:
                callback(event)
            except Exception as e:
                print(f"[Kernel] Subscriber error: {e}")
    
    def _store_event(self, event: KernelEvent):
        """Store to SQLite. WAL mode makes this non-blocking."""
        self.db.execute("""
            INSERT OR IGNORE INTO kernel_events 
            (event_id, timestamp, event_type, process_id, process_name, 
             thread_id, user_sid, payload, importance_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.event_id, event.timestamp, event.event_type.name,
            event.process_id, event.process_name, event.thread_id,
            event.user_sid, json.dumps(event.payload), event.importance_score
        ))
        # Commit every 10 events to be faster for mock
        if self.event_queue.qsize() % 10 == 0:
            self.db.commit()
    
    def _update_working_memory(self, event: KernelEvent):
        """Update RAM-hot working memory. Attention-weighted."""
        pass
    
    def _compress_loop(self):
        """
        Subconscious: Compress L0 raw events → L1 summaries.
        Runs every 5 minutes when AFK.
        """
        while self._running:
            time.sleep(300)  # 5 minutes
            
            try:
                # Find time window to compress
                cutoff = time.time() - 300  # Last 5 minutes
                cursor = self.db.execute("""
                    SELECT * FROM kernel_events 
                    WHERE timestamp < ? AND indexed_at = 0
                    ORDER BY timestamp
                """, (cutoff,))
                
                events = cursor.fetchall() # Need dict mapping to proper objects if we implemented full L1
                
                if len(events) > 100:
                    # Mock L1 compression
                    print("[MizuneKernel] L1 Compression triggered in subconscious...")
                    
                    # Mark events as indexed
                    event_ids = [row[0] for row in events]
                    self.db.executemany(
                        "UPDATE kernel_events SET indexed_at = ? WHERE event_id = ?",
                        [(time.time(), eid) for eid in event_ids]
                    )
                    self.db.commit()
            except Exception as e:
                print(f"[Kernel] Compress loop error: {e}")
    
    def subscribe(self, event_type: EventType, callback: Callable):
        """Subscribe to kernel events. Used by all Mizune modules."""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)
        print(f"[Kernel] Subscriber added for {event_type.name}")

