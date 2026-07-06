import re
import time
import json
import logging
import threading
from typing import Dict, Any

from .memory_tree import memory_tree_db
from .config import log_info

logger = logging.getLogger("mizune.memory_worker")

# Raw tool-call JSON like {"name": "store_memory", "parameters": {...}} — protocol
# junk that must never be distilled into a memory as-is.
_TOOLCALL_JSON_RE = re.compile(r'\{\s*"name"\s*:\s*"[\w-]+"\s*,\s*"(parameters|args|arguments)"\s*:.*?\}\s*\}', re.DOTALL)
_XML_FUNCTION_RE = re.compile(r'<function=.*?</function>|\[function=[^\]]+\]\s*\{.*?\}', re.DOTALL)


def _clean_for_distillation(text: str) -> str:
    """Strip tool-call artifacts so the summarizer only sees human-meaningful content."""
    if not text:
        return ""
    t = _XML_FUNCTION_RE.sub('', str(text))
    t = _TOOLCALL_JSON_RE.sub('', t)
    t = re.sub(r'\n{3,}', '\n\n', t).strip()
    return t


def _distill_summary_output(summary_text: str) -> str:
    """Clean the summarizer's own output; salvage the fact if it echoed a raw tool call."""
    s = (summary_text or "").strip()
    if not s:
        return ""
    # If the whole output is a tool-call JSON blob, pull the actual fact out of it.
    if s.startswith("{"):
        try:
            obj = json.loads(s)
            if isinstance(obj, dict):
                params = obj.get("parameters") or obj.get("args") or obj.get("arguments") or {}
                if isinstance(params, dict):
                    for key in ("fact", "note_text", "message", "content"):
                        if params.get(key):
                            return str(params[key]).strip()
        except Exception:
            pass
    return _clean_for_distillation(s)

class MemoryTreeWorker:
    """
    Background worker that processes the memory tree pipeline:
    extract_chunk -> append_buffer -> seal -> topic_route -> digest_daily
    """
    def __init__(self, config: Dict[str, Any], tick_seconds: int = 5):
        self.config = config
        self.tick_seconds = tick_seconds
        self.running = False
        self.thread = None
        
    def start(self):
        if self.running: return
        self.running = True
        self.thread = threading.Thread(target=self._worker_loop, daemon=True, name="MemoryTreeWorker")
        self.thread.start()
        log_info("[MEMORY WORKER] Background memory pipeline started.")
        
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
            
    def _worker_loop(self):
        while self.running:
            job = memory_tree_db.claim_next_job()
            if not job:
                time.sleep(self.tick_seconds)
                continue
                
            job_id = job["id"]
            job_type = job["job_type"]
            payload = job["payload"]
            
            try:
                success = False
                if job_type == "extract_chunk":
                    success = self._handle_extract_chunk(payload)
                elif job_type == "append_buffer":
                    success = self._handle_append_buffer(payload)
                elif job_type == "seal":
                    success = self._handle_seal(payload)
                elif job_type == "decay_connections":
                    success = self._handle_decay_connections()
                elif job_type == "update_connection":
                    success = self._handle_update_connection(payload)
                else:
                    log_info(f"[MEMORY WORKER] Unknown job type: {job_type}")
                    success = True # Mark complete to clear it
                    
                memory_tree_db.complete_job(job_id, success=success)
                
            except Exception as e:
                log_info(f"[MEMORY WORKER] Error processing job {job_id} ({job_type}): {e}")
                memory_tree_db.complete_job(job_id, success=False)
                time.sleep(1) # Prevent rapid failure loops
                
    def _handle_decay_connections(self) -> bool:
        """Apply a 5% daily decay rate to all emotional connection strengths."""
        try:
            cursor = memory_tree_db.db.cursor()
            now = time.time()
            cursor.execute("SELECT entity, strength, last_updated FROM connection_strength")
            rows = cursor.fetchall()
            
            DECAY_RATE = 0.95
            for entity, strength, last_updated in rows:
                days_passed = (now - last_updated) / 86400.0
                if days_passed > 0:
                    decayed = strength * (DECAY_RATE ** days_passed)
                    cursor.execute(
                        "UPDATE connection_strength SET strength = ?, last_updated = ? WHERE entity = ?",
                        (decayed, now, entity)
                    )
            memory_tree_db.db.commit()
            return True
        except Exception as e:
            log_info(f"[MEMORY WORKER] Decay error: {e}")
            return False

    def _handle_update_connection(self, payload: Dict[str, Any]) -> bool:
        """Update an entity's connection strength based on interaction impact."""
        entity = payload.get("entity")
        impact = payload.get("impact", 0.0)
        if not entity: return False
        
        try:
            cursor = memory_tree_db.db.cursor()
            now = time.time()
            cursor.execute("SELECT strength, last_updated FROM connection_strength WHERE entity = ?", (entity,))
            row = cursor.fetchone()
            
            DECAY_RATE = 0.95
            if row:
                old_strength, last_updated = row
                days_passed = max(0, (now - last_updated) / 86400.0)
                decayed = old_strength * (DECAY_RATE ** days_passed)
                
                # Formula: new_strength = decayed + impact * (1 - decayed) * 0.3
                new_strength = decayed + impact * (1 - decayed) * 0.3
                new_strength = max(0.0, min(1.0, new_strength))
                
                cursor.execute(
                    "UPDATE connection_strength SET strength = ?, last_updated = ?, interaction_count = interaction_count + 1 WHERE entity = ?",
                    (new_strength, now, entity)
                )
            else:
                # First time seeing this entity
                new_strength = max(0.0, min(1.0, impact * 0.3))
                cursor.execute(
                    "INSERT INTO connection_strength (entity, strength, last_updated, interaction_count, first_seen) VALUES (?, ?, ?, 1, ?)",
                    (entity, new_strength, now, now)
                )
            memory_tree_db.db.commit()
            return True
        except Exception as e:
            log_info(f"[MEMORY WORKER] Update connection error: {e}")
            return False
                
    def _handle_extract_chunk(self, payload: Dict[str, Any]) -> bool:
        """
        Processes a raw chunk: calculates deep score, extracts entities (soon),
        and decides whether to admit or drop.
        """
        chunk_id = payload.get("chunk_id")
        if not chunk_id: return False
        
        chunk = memory_tree_db.get_chunk(chunk_id)
        if not chunk: return False
        
        # 1. Scoring Logic
        # For now, a simple heuristic score based on length and keywords.
        # Later, we will integrate LLM-based entity hotness.
        content = chunk["content"].lower()
        score = 0.0
        
        # Basic importance heuristic
        if len(content) > 50: score += 0.2
        if "master" in content or "rushi" in content: score += 0.3
        if "remember" in content or "important" in content: score += 0.5
        if "error" in content or "failed" in content: score += 0.4
        
        # Determine fate
        admit_threshold = 0.3
        now = time.time()
        
        try:
            cursor = memory_tree_db.db.cursor()
            # (Skipped storing the heuristic score in the DB for now)
            
            if score >= admit_threshold:
                memory_tree_db.update_chunk_state(chunk_id, "admitted")
                
                # Queue the next phase: append to source buffer
                job_payload = json.dumps({"chunk_id": chunk_id, "source_id": chunk["source_id"]})
                cursor.execute(
                    "INSERT INTO jobs (job_type, payload, created_at) VALUES (?, ?, ?)",
                    ("append_buffer", job_payload, now)
                )
                
                # Extract entities and route to topic trees if hot
                from .entity_extractor import entity_extractor
                hot_entities = entity_extractor.extract_and_score(content)
                for ent in hot_entities:
                    topic_payload = json.dumps({
                        "chunk_id": chunk_id,
                        "source_id": f"topic_{ent['name']}"
                    })
                    cursor.execute(
                        "INSERT INTO jobs (job_type, payload, created_at) VALUES (?, ?, ?)",
                        ("append_buffer", topic_payload, now)
                    )
                    log_info(f"[MEMORY WORKER] Chunk {chunk_id} also routed to Hot Topic: {ent['name']}")

                log_info(f"[MEMORY WORKER] Chunk {chunk_id} ADMITTED (score: {score:.2f})")
            else:
                memory_tree_db.update_chunk_state(chunk_id, "dropped")
                log_info(f"[MEMORY WORKER] Chunk {chunk_id} DROPPED (score: {score:.2f})")
                
            memory_tree_db.db.commit()
            return True
        except Exception as e:
            log_info(f"[MEMORY WORKER] Extract failed: {e}")
            return False

    def _handle_append_buffer(self, payload: Dict[str, Any]) -> bool:
        """
        Moves an admitted chunk into the L0 buffer for its source.
        If the buffer hits the threshold, queues a seal job.
        """
        chunk_id = payload.get("chunk_id")
        source_id = payload.get("source_id")
        if not chunk_id or not source_id: return False
        
        memory_tree_db.update_chunk_state(chunk_id, "buffered")
        
        # Check buffer size for this source
        try:
            cursor = memory_tree_db.db.cursor()
            cursor.execute("SELECT id FROM episodic WHERE source = ? AND status = 'buffered'", (source_id,))
            buffered_chunks = cursor.fetchall()
            
            buffer_limit = 5 # Small limit for testing, normally ~10-20
            
            if len(buffered_chunks) >= buffer_limit:
                chunk_ids_to_seal = [row[0] for row in buffered_chunks]
                
                # Queue seal job
                job_payload = json.dumps({
                    "tree_type": "source",
                    "tree_id": source_id,
                    "level": 1,
                    "chunk_ids": chunk_ids_to_seal
                })
                
                now = time.time()
                cursor.execute(
                    "INSERT INTO jobs (job_type, payload, created_at) VALUES (?, ?, ?)",
                    ("seal", job_payload, now)
                )
                log_info(f"[MEMORY WORKER] Buffer full for {source_id}. Queued seal job for {len(chunk_ids_to_seal)} chunks.")
                
            memory_tree_db.db.commit()
            return True
        except Exception as e:
            log_info(f"[MEMORY WORKER] Append buffer failed: {e}")
            return False
            
    def _handle_seal(self, payload: Dict[str, Any]) -> bool:
        """
        Compresses a buffer of L0 chunks into an L1 summary (or L1s into L2).
        Updates state of children to 'sealed'.
        """
        tree_type = payload.get("tree_type")
        tree_id = payload.get("tree_id")
        level = payload.get("level", 1)
        chunk_ids = payload.get("chunk_ids", [])
        
        if not chunk_ids: return True
        
        log_info(f"[MEMORY WORKER] Sealing {len(chunk_ids)} items for {tree_type}:{tree_id} at Level {level}")
        
        try:
            cursor = memory_tree_db.db.cursor()
            
            # Fetch content to summarize
            content_to_summarize = []
            if level == 1:
                placeholders = ','.join('?' * len(chunk_ids))
                cursor.execute(f"SELECT content FROM episodic WHERE id IN ({placeholders})", chunk_ids)
                content_to_summarize = [row[0] for row in cursor.fetchall()]
            else:
                placeholders = ','.join('?' * len(chunk_ids))
                cursor.execute(f"SELECT content FROM episodic WHERE source='summary' AND id IN ({placeholders})", chunk_ids)
                content_to_summarize = [row[0] for row in cursor.fetchall()]
                
            if not content_to_summarize: return False

            # Distillation quality gate: strip raw tool-call JSON / XML artifacts so
            # memories are facts, not protocol junk. If a chunk is nothing but junk,
            # it contributes nothing to the summary.
            cleaned_chunks = [c for c in (_clean_for_distillation(c) for c in content_to_summarize) if c]
            if not cleaned_chunks:
                # All junk: seal the children so the job doesn't retry forever, no summary node.
                log_info("[MEMORY WORKER] Seal skipped: no substantive content after cleaning.")
                if level == 1:
                    cursor.execute(f"UPDATE episodic SET status = 'sealed' WHERE id IN ({placeholders})", chunk_ids)
                else:
                    cursor.execute(f"UPDATE episodic SET status = 'dropped' WHERE id IN ({placeholders})", chunk_ids)
                memory_tree_db.db.commit()
                return True

            # AI Summarization
            combined_text = "\n---\n".join(cleaned_chunks)
            prompt = (
                f"You are Mizune's subconscious memory compressor. Summarize the following events/data points "
                f"into a single, dense, coherent paragraph that captures the key entities, facts, and context. "
                f"DO NOT use conversational filler. Just the compressed facts.\n\n{combined_text}"
            )

            from .ai import get_ai_response
            try:
                # We use a forced prompt to avoid triggering tool calls
                summary_text, _ = get_ai_response(prompt, [], self.config, system_prompt_override="You are a data compression AI. Output only the summary.")
            except Exception as e:
                log_info(f"[MEMORY WORKER] Summarization AI failed: {e}")
                summary_text = f"[AUTO-SUMMARY FAILED] Merged {len(chunk_ids)} items."

            # The summarizer itself can echo a raw tool call (seen in old vault exports:
            # a literal store_memory JSON blob saved as a "memory"). Salvage the fact.
            summary_text = _distill_summary_output(summary_text) or f"[AUTO-SUMMARY EMPTY] Merged {len(chunk_ids)} items."
            
            # Insert the new summary
            summary_id = memory_tree_db.insert_summary(tree_id, summary_text, level=level, tree_type=tree_type)
            if summary_id is None:
                log_info("[MEMORY WORKER] Summary insert failed; seal job aborted.")
                return False

            # Export to Vault (non-fatal: the seal must survive a vault failure)
            try:
                from .vault_sync import vault_sync
                if vault_sync:
                    vault_sync.export_summary(summary_id)
            except Exception as e:
                log_info(f"[MEMORY WORKER] Vault export failed (non-fatal): {e}")

            # Update children state: seal raw chunks, drop consumed summaries
            # (dropping prevents the same L{n} summaries from cascading forever)
            now = time.time()
            if level == 1:
                cursor.execute(f"UPDATE episodic SET status = 'sealed' WHERE id IN ({placeholders})", chunk_ids)
            else:
                cursor.execute(f"UPDATE episodic SET status = 'dropped' WHERE id IN ({placeholders})", chunk_ids)
            
            # Cascade check: are there enough L{level} summaries to make an L{level+1}?
            cursor.execute(
                "SELECT id FROM episodic WHERE source = 'summary' AND session_id = ? AND status = 'sealed' "
                "AND COALESCE(json_extract(metadata, '$.level'), 1) = ?",
                (tree_id, level)
            )
            peer_summaries = cursor.fetchall()
            
            cascade_limit = 5
            if len(peer_summaries) >= cascade_limit:
                peer_ids = [row[0] for row in peer_summaries]
                job_payload = json.dumps({
                    "tree_type": tree_type,
                    "tree_id": tree_id,
                    "level": level + 1,
                    "chunk_ids": peer_ids
                })
                cursor.execute(
                    "INSERT INTO jobs (job_type, payload, created_at) VALUES (?, ?, ?)",
                    ("seal", job_payload, now)
                )
                log_info(f"[MEMORY WORKER] Cascade triggered! Queued Level {level+1} seal job.")
            
            memory_tree_db.db.commit()
            return True
            
        except Exception as e:
            log_info(f"[MEMORY WORKER] Seal failed: {e}")
            return False

# We don't initialize a global instance here anymore because it needs config.
# It will be initialized in server.py or memory_tree.py when config is available.
_worker_instance = None

def start_memory_worker(config: Dict[str, Any]):
    global _worker_instance
    if not _worker_instance:
        _worker_instance = MemoryTreeWorker(config)
        _worker_instance.start()

def stop_memory_worker():
    global _worker_instance
    if _worker_instance:
        _worker_instance.stop()
        _worker_instance = None
