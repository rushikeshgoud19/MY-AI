import os
import sqlite3
import json
import time
import logging
import numpy as np
from typing import List, Dict, Any, Optional

from .config import log_info

logger = logging.getLogger("mizune.memory_tree")

def cosine_similarity(a, b):
    a = np.frombuffer(a, dtype=np.float32)
    b = np.frombuffer(b, dtype=np.float32)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))

class MemoryTreeDB:
    """
    Core SQLite database for the complete MIZUNE SELF-EVOLUTION SYSTEM v3.0
    Hybrid of Hermes + OpenHuman
    """
    def __init__(self, data_dir: str = ".mizune_cortex"):
        self.data_dir = data_dir
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            
        self.db_path = os.path.join(self.data_dir, "memory_tree.db")
        self.db = None
        self._init_db()
        
    def _init_db(self):
        try:
            self.db = sqlite3.connect(self.db_path, check_same_thread=False)
            # Register numpy array adapter for embeddings
            sqlite3.register_adapter(np.ndarray, lambda arr: arr.tobytes())
            
            cursor = self.db.cursor()
            
            # --- SECTION 1.1: SQLITE SCHEMA ---
            
            # EPISODIC: Raw events (Hermes-style sessions + OpenHuman-style chunks)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS episodic (
                    id INTEGER PRIMARY KEY,
                    timestamp REAL DEFAULT (strftime('%s', 'now')),
                    session_id TEXT,
                    source TEXT CHECK(source IN ('chat','vision','tool','system','screen','voice','whatsapp','telegram','discord','summary')),
                    content TEXT,
                    content_hash TEXT UNIQUE,
                    embedding BLOB,  -- 768-dim fp32, only for chat/tool
                    metadata JSON,   -- {"app":"vscode","window_title":"main.py","coords":[120,340]}
                    platform TEXT,   -- 'cli','whatsapp','telegram','desktop'
                    status TEXT CHECK(status IN ('pending','admitted','buffered','sealed','dropped')) DEFAULT 'pending'
                )
            ''')

            # SCREEN MEMORY
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS screen_memory (
                    id INTEGER PRIMARY KEY,
                    timestamp REAL DEFAULT (strftime('%s', 'now')),
                    frame_hash TEXT,
                    app_name TEXT,
                    window_title TEXT,
                    ui_elements JSON,
                    action_sequence JSON,
                    rarity_score REAL DEFAULT 1.0,
                    screenshot_path TEXT
                )
            ''')

            # SKILLS
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS skills (
                    id INTEGER PRIMARY KEY,
                    name TEXT UNIQUE,
                    version REAL DEFAULT 1.0,
                    success_rate REAL DEFAULT 0.0,
                    trigger_patterns JSON,
                    markdown_body TEXT,
                    executable_steps JSON,
                    source_chunks JSON,
                    screen_verification TEXT,
                    last_executed REAL,
                    total_uses INTEGER DEFAULT 0,
                    is_pinned BOOLEAN DEFAULT FALSE,
                    is_archived BOOLEAN DEFAULT FALSE,
                    created_at REAL DEFAULT (strftime('%s', 'now')),
                    updated_at REAL DEFAULT (strftime('%s', 'now'))
                )
            ''')

            # TOPICS
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS topics (
                    id INTEGER PRIMARY KEY,
                    entity_name TEXT UNIQUE,
                    entity_type TEXT,
                    hotness REAL DEFAULT 0.0,
                    l2_summary TEXT,
                    related_topics JSON,
                    last_accessed REAL DEFAULT (strftime('%s', 'now'))
                )
            ''')

            # ENTITIES — hotness tracking for entity_extractor.py. This table was
            # NEVER created (extractor failed with "no such table: entities" on every
            # call, silently caught → the whole hot-topic feature was dead). Caught in
            # the 2026-07-20 audit.
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS entities (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    type TEXT,
                    hotness_score REAL DEFAULT 0.0,
                    last_seen REAL,
                    first_seen REAL
                )
            ''')

            # JOBS
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY,
                    job_type TEXT CHECK(job_type IN ('extract_chunk','append_buffer','seal','topic_route','digest_daily','flush_stale','evolve_skill','evolve_behavior','evolve_architecture')),
                    payload JSON,
                    status TEXT CHECK(status IN ('pending','running','completed','failed')) DEFAULT 'pending',
                    worker_id TEXT,
                    lease_expires REAL,
                    created_at REAL DEFAULT (strftime('%s', 'now')),
                    completed_at REAL
                )
            ''')

            # EMOTIONAL MEMORY
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS emotional_memory (
                    id INTEGER PRIMARY KEY,
                    timestamp REAL DEFAULT (strftime('%s', 'now')),
                    session_id TEXT,
                    user_input TEXT,
                    mizune_response TEXT,
                    detected_emotion TEXT,
                    user_reaction TEXT,
                    task_outcome TEXT CHECK(task_outcome IN ('success','failure','abandoned','ongoing')),
                    impact_score REAL,
                    entities JSON,
                    duration_seconds REAL,
                    sentiment_confidence REAL
                )
            ''')

            # CONNECTION STRENGTH
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS connection_strength (
                    entity TEXT PRIMARY KEY,
                    strength REAL DEFAULT 0.0,
                    last_updated REAL DEFAULT (strftime('%s', 'now')),
                    interaction_count INTEGER DEFAULT 0,
                    positive_interactions INTEGER DEFAULT 0,
                    negative_interactions INTEGER DEFAULT 0,
                    first_seen REAL DEFAULT (strftime('%s', 'now')),
                    emotional_arc JSON
                )
            ''')

            # MOOD HISTORY
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS mood_history (
                    id INTEGER PRIMARY KEY,
                    timestamp REAL DEFAULT (strftime('%s', 'now')),
                    valence REAL,
                    arousal REAL,
                    dominance REAL,
                    trust REAL,
                    curiosity REAL,
                    concern REAL,
                    trigger_event TEXT,
                    session_id TEXT
                )
            ''')

            # EVOLUTION GENES
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS evolution_genes (
                    id TEXT PRIMARY KEY,
                    created_at REAL DEFAULT (strftime('%s', 'now')),
                    level INTEGER CHECK(level IN (1,2,3,4)),
                    name TEXT,
                    description TEXT,
                    implementation TEXT,
                    parent_genes JSON,
                    mutations JSON,
                    generation INTEGER,
                    activation_count INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0,
                    fitness_score REAL DEFAULT 0.5,
                    last_fitness_update REAL DEFAULT (strftime('%s', 'now')),
                    active BOOLEAN DEFAULT TRUE,
                    deprecated_by TEXT
                )
            ''')

            # EVOLUTION HYPOTHESES
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS evolution_hypotheses (
                    id TEXT PRIMARY KEY,
                    timestamp REAL DEFAULT (strftime('%s', 'now')),
                    level INTEGER,
                    target TEXT,
                    current_state TEXT,
                    proposed_change TEXT,
                    motivation TEXT,
                    expected_improvement TEXT,
                    expected_improvement_delta REAL,
                    validation_strategy TEXT,
                    rollback_strategy TEXT,
                    risk_level REAL,
                    blast_radius JSON,
                    status TEXT DEFAULT 'pending',
                    experiment_result JSON
                )
            ''')

            # EVOLUTION EXPERIMENTS
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS evolution_experiments (
                    id TEXT PRIMARY KEY,
                    hypothesis_id TEXT,
                    timestamp_start REAL DEFAULT (strftime('%s', 'now')),
                    timestamp_end REAL,
                    change_patch TEXT,
                    test_environment TEXT,
                    status TEXT CHECK(status IN ('pending','running','success','failure','partial','aborted')),
                    metrics_before JSON,
                    metrics_after JSON,
                    logs JSON,
                    user_feedback TEXT,
                    integrate BOOLEAN DEFAULT FALSE,
                    rollback_performed BOOLEAN DEFAULT FALSE
                )
            ''')

            # PENDING APPROVALS
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS pending_approvals (
                    request_id TEXT PRIMARY KEY,
                    hypothesis_id TEXT,
                    level INTEGER CHECK(level = 3),
                    target TEXT,
                    proposed_change TEXT,
                    risk_level REAL,
                    motivation TEXT,
                    expected_improvement TEXT,
                    rollback_strategy TEXT,
                    requested_at REAL DEFAULT (strftime('%s', 'now')),
                    rescheduled_for REAL,
                    status TEXT DEFAULT 'pending',
                    user_response TEXT,
                    responded_at REAL
                )
            ''')

            # Evolution Budget (Adding this from Week 1)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS evolution_budget (
                    date TEXT PRIMARY KEY,
                    tokens_used INTEGER DEFAULT 0,
                    cost_dollars REAL DEFAULT 0.0
                )
            ''')
            
            # FTS5 Tables
            cursor.execute("CREATE VIRTUAL TABLE IF NOT EXISTS episodic_fts USING fts5(content, content='episodic', content_rowid='id')")
            cursor.execute("CREATE VIRTUAL TABLE IF NOT EXISTS skills_fts USING fts5(markdown_body, content='skills', content_rowid='id')")

            # Indices
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_episodic_time ON episodic(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_episodic_session ON episodic(session_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_episodic_source ON episodic(source, platform)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_screen_hash ON screen_memory(frame_hash)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_skills_success ON skills(success_rate DESC)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_topics_hotness ON topics(hotness DESC)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, job_type)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_emotional_time ON emotional_memory(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_connection_strength ON connection_strength(strength DESC)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_genes_active ON evolution_genes(active, fitness_score DESC)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_hypotheses_status ON evolution_hypotheses(status, level)')

            self.db.commit()
            self._migrate_episodic_summary_source()
            log_info("[MEMORY CORE] Complete Self-Evolution Schema Initialized.")
        except Exception as e:
            log_info(f"[MEMORY CORE] Error initializing SQLite: {e}")

    def _migrate_episodic_summary_source(self):
        """Older DBs have a CHECK on episodic.source that rejects 'summary' rows.
        Rebuild the table once so the seal pipeline can store summaries."""
        try:
            cursor = self.db.cursor()
            row = cursor.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='episodic'"
            ).fetchone()
            if not row or "'summary'" in row[0]:
                return
            cursor.execute("ALTER TABLE episodic RENAME TO episodic_old")
            cursor.execute('''
                CREATE TABLE episodic (
                    id INTEGER PRIMARY KEY,
                    timestamp REAL DEFAULT (strftime('%s', 'now')),
                    session_id TEXT,
                    source TEXT CHECK(source IN ('chat','vision','tool','system','screen','voice','whatsapp','telegram','discord','summary')),
                    content TEXT,
                    content_hash TEXT UNIQUE,
                    embedding BLOB,
                    metadata JSON,
                    platform TEXT,
                    status TEXT CHECK(status IN ('pending','admitted','buffered','sealed','dropped')) DEFAULT 'pending'
                )
            ''')
            cursor.execute("INSERT INTO episodic SELECT * FROM episodic_old")
            cursor.execute("DROP TABLE episodic_old")
            self.db.commit()
            log_info("[MEMORY CORE] Migrated episodic table to allow summary rows.")
        except Exception as e:
            log_info(f"[MEMORY CORE] episodic migration failed: {e}")
            try:
                self.db.rollback()
            except Exception:
                pass

    def insert_chunk(self, chunk_id: str, source_id: str, content: str, token_count: int = 0, metadata: dict = None):
        """Compatibility method for older memory modules."""
        if not self.db: return
        try:
            import hashlib
            import json
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            
            # Check if hash already exists
            cursor = self.db.cursor()
            cursor.execute("SELECT id FROM episodic WHERE content_hash = ?", (content_hash,))
            if cursor.fetchone():
                return
                
            # source_id is a GROUPING key (e.g. 'rules', a session id) and belongs in
            # session_id — NOT the source column, whose CHECK only allows a fixed enum.
            # Cramming source_id into source raised "CHECK constraint failed" and every
            # insert_chunk write was lost.
            meta = dict(metadata or {})
            meta.setdefault("source_id", source_id)
            valid_sources = {'chat','vision','tool','system','screen','voice','whatsapp','telegram','discord','summary'}
            source_col = source_id if source_id in valid_sources else 'system'
            cursor.execute('''
                INSERT INTO episodic (session_id, source, content, content_hash, metadata)
                VALUES (?, ?, ?, ?, ?)
            ''', (source_id, source_col, content, content_hash, json.dumps(meta)))
            
            episodic_id = cursor.lastrowid
            cursor.execute('INSERT INTO episodic_fts (rowid, content) VALUES (?, ?)',
                          (episodic_id, content))
                          
            # Queue the extraction job for the background worker
            import time
            cursor.execute('''
                INSERT INTO jobs (job_type, payload, created_at)
                VALUES (?, ?, ?)
            ''', ("extract_chunk", json.dumps({"chunk_id": episodic_id}), time.time()))
                          
            self.db.commit()
        except Exception as e:
            log_info(f"[MEMORY CORE] Error inserting chunk: {e}")

    # --- 1.2 Memory Retrieval (Hermes FTS5 + OpenHuman Hierarchy) ---
    def recall(self, query: str, query_embedding: bytes, context: dict, limit: int = 10) -> list:
        """Three-phase retrieval: FTS5 -> metadata filter -> vector rerank -> topic expansion"""
        if not self.db: return []
        
        # Phase 1: FTS5 keyword search (< 10ms)
        try:
            candidates = self.db.execute("""
                SELECT rowid, rank FROM episodic_fts 
                WHERE episodic_fts MATCH ? ORDER BY rank LIMIT 50
            """, (query,)).fetchall()
        except sqlite3.OperationalError:
            # Table might be empty or syntax error in query
            return []
            
        candidate_ids = [str(r[0]) for r in candidates]
        if not candidate_ids:
            return []
            
        # Phase 2: Fetch candidates
        placeholders = ','.join('?' * len(candidate_ids))
        rows = self.db.execute(f"""
            SELECT id, content, metadata, status, embedding FROM episodic 
            WHERE id IN ({placeholders})
        """, candidate_ids).fetchall()
        
        # Phase 3: Vector similarity
        scored = []
        for row in rows:
            emb_bytes = row[4]
            if emb_bytes and query_embedding:
                similarity = cosine_similarity(query_embedding, emb_bytes)
                scored.append((similarity, row))
            else:
                scored.append((0.0, row))
                
        scored.sort(reverse=True, key=lambda x: x[0])
        
        # Phase 4: Topic tree expansion
        top_results = [{"id": r[1][0], "content": r[1][1], "metadata": r[1][2]} for _, r in scored[:limit]]
        
        # Very basic entity extraction for now
        entities = [word for word in query.split() if len(word) > 4]
        for entity in entities:
            topic = self.db.execute("SELECT l2_summary FROM topics WHERE entity_name = ?", (entity,)).fetchone()
            if topic:
                top_results.append({"topic_summary": topic[0], "entity": entity})
                
        return top_results

    def recall_screen(self, frame_hash: str, app_name: str) -> Optional[dict]:
        if not self.db: return None
        row = self.db.execute("""
            SELECT action_sequence, ui_elements FROM screen_memory
            WHERE frame_hash = ? AND app_name = ?
            ORDER BY timestamp DESC LIMIT 1
        """, (frame_hash, app_name)).fetchone()
        return json.loads(row[0]) if row else None
        
    def recall_procedural(self, intent: str) -> list:
        if not self.db: return []
        try:
            return self.db.execute("""
                SELECT name, markdown_body, executable_steps, success_rate
                FROM skills
                WHERE trigger_patterns MATCH ? AND active = TRUE
                ORDER BY success_rate DESC, total_uses DESC
                LIMIT 5
            """, (intent,)).fetchall()
        except sqlite3.OperationalError:
            return []

    def get_chunk(self, chunk_id: str) -> Optional[dict]:
        if not self.db: return None
        try:
            row = self.db.execute(
                "SELECT id, session_id, source, content, metadata, status FROM episodic WHERE id = ? OR session_id = ?", 
                (chunk_id, chunk_id)
            ).fetchone()
            if not row: return None
            import json
            return {
                "id": row[0],
                "session_id": row[1],
                "source": row[2],
                "content": row[3],
                "metadata": json.loads(row[4]) if row[4] else {},
                "status": row[5]
            }
        except Exception as e:
            logger.error(f"[MEMORY CORE] Error getting chunk: {e}")
            return None

    def update_chunk_state(self, chunk_id: str, new_state: str):
        if not self.db: return
        try:
            self.db.execute("UPDATE episodic SET status = ? WHERE id = ? OR session_id = ?", (new_state, chunk_id, chunk_id))
            self.db.commit()
        except Exception as e:
            logger.error(f"[MEMORY CORE] Error updating chunk state: {e}")

    def insert_summary(self, session_id: str, content: str, level: int = 1, tree_type: str = "session"):
        """Store a compressed summary row. Returns the episodic rowid, or None on failure."""
        if not self.db: return None
        try:
            import hashlib
            import json
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            cursor = self.db.cursor()
            cursor.execute('''
                INSERT INTO episodic (session_id, source, content, content_hash, metadata, status)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (session_id, "summary", content, content_hash,
                  json.dumps({"level": level, "tree_type": tree_type}), "sealed"))
            episodic_id = cursor.lastrowid
            cursor.execute('INSERT INTO episodic_fts (rowid, content) VALUES (?, ?)', (episodic_id, content))
            self.db.commit()
            return episodic_id
        except Exception as e:
            logger.error(f"[MEMORY CORE] Error inserting summary: {e}")
            return None

    def get_queue_depth(self) -> int:
        if not self.db: return 0
        try:
            row = self.db.execute("SELECT COUNT(*) FROM episodic WHERE status = 'pending'").fetchone()
            return row[0] if row else 0
        except Exception as e:
            logger.error(f"[MEMORY CORE] Error getting queue depth: {e}")
            return 0

    def claim_next_job(self) -> Optional[dict]:
        if not self.db: return None
        try:
            now = time.time()
            cursor = self.db.execute("""
                SELECT id, job_type, payload FROM jobs
                WHERE status = 'pending' OR (status = 'running' AND lease_expires < ?)
                ORDER BY created_at ASC LIMIT 1
            """, (now,))
            row = cursor.fetchone()
            if not row:
                return None
            
            job_id, job_type, payload_str = row
            lease_expires = now + 300 # 5 minutes lease
            self.db.execute("UPDATE jobs SET status = 'running', lease_expires = ? WHERE id = ?", (lease_expires, job_id))
            self.db.commit()
            
            return {
                "id": job_id,
                "job_type": job_type,
                "payload": json.loads(payload_str) if payload_str else {}
            }
        except Exception as e:
            logger.error(f"[MEMORY CORE] Error claiming job: {e}")
            return None

    def complete_job(self, job_id: int, success: bool):
        if not self.db: return
        try:
            status = 'completed' if success else 'failed'
            self.db.execute("UPDATE jobs SET status = ?, completed_at = ? WHERE id = ?", (status, time.time(), job_id))
            self.db.commit()
        except Exception as e:
            logger.error(f"[MEMORY CORE] Error completing job: {e}")

# Global instance
memory_tree_db = MemoryTreeDB()
