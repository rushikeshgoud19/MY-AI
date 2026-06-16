# COMPLETE MEMORY ARCHITECTURE COMPARISON
## OpenClaw vs Hermes Agent vs OpenHuman

## PART 1: OPENCLAW — The Blank Slate
(Refer to chat history for details)

## PART 2: HERMES AGENT — The Self-Improving Brain
(Refer to chat history for details)

## PART 3: OPENHUMAN — The Hierarchical Knowledge Forest
(Refer to chat history for details)

## PART 4: HEAD-TO-HEAD COMPARISON
(Refer to chat history for details)

## PART 5: WHAT MIZUNE SHOULD STEAL
### From Hermes (Copy These)
1. FTS5 full-text search — 10 ms recall is unbeatable
2. Skill lifecycle — Autonomous creation + Curator + security scan
3. Trajectory export — Generate training data from successful runs
4. Context compression at 90% — Prevent context window bloat
5. User model — Learn communication style and expertise
6. Three-layer memory — Ephemeral + persistent + user model

### From OpenHuman (Copy These)
1. Hierarchical tree structure — L0→L1→L2 compression
2. Obsidian vault mirror — Human-editable, full sovereignty
3. TokenJuice — 70-80% token reduction before LLM
4. Job queue with crash recovery — Lease-based worker system
5. Entity hotness tracking — Prioritize relevant topics
6. 20-minute auto-fetch — Keep memory fresh
7. Model routing by hint — Cost optimization per workload

### What Mizune Should Invent (Your Moat)
1. Screen-aware memory — Remember UI layouts, click coordinates
2. Executable skills — Skills as screenplays with vision verification
3. Frame-dedup vision cache — pHash-based screenshot dedup
4. Digital muscle memory — 1B param transformer for UI action prediction
5. Cross-app workflow memory — "How I exported Figma → PowerPoint → Email"
6. V-Tuber emotional state — Memory of user's mood, not just facts

## PART 6: RECOMMENDED MIZUNE MEMORY SCHEMA

```sql
-- EPISODIC: Raw events (Hermes sessions + OpenHuman chunks)
CREATE TABLE episodic (
    id INTEGER PRIMARY KEY,
    timestamp REAL,
    session_id TEXT,
    source TEXT CHECK(source IN ('chat', 'vision', 'tool', 'system', 'screen', 'voice', 'whatsapp')),
    content TEXT,
    content_hash TEXT UNIQUE,
    embedding BLOB,  -- 768-dim, only for chat/tool
    metadata JSON,     -- {"app": "vscode", "window_title": "main.py", "coords": [120, 340]}
    platform TEXT,     -- 'cli', 'whatsapp', 'telegram', 'desktop'
    status TEXT CHECK(status IN ('pending', 'admitted', 'buffered', 'sealed', 'dropped'))
);

-- SCREEN MEMORY: Mizune's unique advantage
CREATE TABLE screen_memory (
    id INTEGER PRIMARY KEY,
    timestamp REAL,
    frame_hash TEXT,  -- perceptual hash
    app_name TEXT,
    window_title TEXT,
    ui_elements JSON,  -- [{"id": "btn_export", "x": 1240, "y": 340}]
    action_sequence JSON,
    rarity_score REAL,
    screenshot_path TEXT  -- NULL if deduped
);

-- SKILLS: Hermes-style + executable steps
CREATE TABLE skills (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,
    version REAL DEFAULT 1.0,
    success_rate REAL DEFAULT 0.0,
    trigger_patterns JSON,
    markdown_body TEXT,      -- Human-readable
    executable_steps JSON,   -- [{"action": "click", "x": 1200, "y": 340}]
    screen_verification TEXT, -- pHash of expected screen state
    last_executed REAL,
    total_uses INTEGER DEFAULT 0,
    is_pinned BOOLEAN DEFAULT FALSE
);

-- TOPICS: OpenHuman-style entity tracking
CREATE TABLE topics (
    id INTEGER PRIMARY KEY,
    entity_name TEXT UNIQUE,
    entity_type TEXT,
    hotness REAL DEFAULT 0.0,
    l2_summary TEXT,
    related_topics JSON,
    last_accessed REAL
);

-- JOBS: OpenHuman-style background queue
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY,
    job_type TEXT,
    payload JSON,
    status TEXT,
    worker_id TEXT,
    lease_expires REAL,
    created_at REAL
);

-- FTS5
CREATE VIRTUAL TABLE episodic_fts USING fts5(content, content='episodic', content_rowid='id');
CREATE VIRTUAL TABLE skills_fts USING fts5(markdown_body, content='skills', content_rowid='id');
```
