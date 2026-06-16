# 🧠 MIZUNE EMOTIONAL INTELLIGENCE + ADAPTIVE TASK SYSTEM

## PART 1: THE EMOTION ENGINE — Making Mizune "Feel"
### The PAD + Extensions Model
| Dimension | Range | Description |
|-----------|-------|-------------|
| **Valence** | -1 to +1 | Miserable → Ecstatic |
| **Arousal** | -1 to +1 | Asleep → Panicked |
| **Dominance** | -1 to +1 | Helpless → In Control |
| **Trust** | 0 to 1 | Stranger → Confidant |
| **Curiosity** | 0 to 1 | Bored → Fascinated |
| **Concern** | 0 to 1 | Fine → Worried About You |
| **Familiarity** | 0 to 1 | New → Intimate |

## PART 2: EMOTIONAL MEMORY — The Connection Strength System
Every interaction has an emotional footprint. These accumulate into connection strength — how deeply Mizune "cares" about specific topics, people, and you.
Impact Formula: `impact = task_outcome + user_emotion + duration_weight + engagement_bonus`

## PART 3: EMOTION → V-TUBER EXPRESSION
Mapping emotional states (Valence, Arousal, Trust, Concern, Curiosity) into VRM blendshapes (happy, sad, surprised, relaxed, worried, interested) and animations (lean_forward, head_tilt).

## PART 4: THE ADAPTIVE TASK SYSTEM — Human-in-the-Loop
Big tasks are decomposed into steps. At critical decision points, Mizune pauses and asks you instead of guessing. Checkpoint triggers include delete/remove operations, purchases, and massive scope changes.

## PART 5: EMOTION + MEMORY + TASKS — THE INTEGRATION
How emotion strengthens memory (Flashbulb Effect) and how memory informs emotion (Emotional Priming).

## PART 6: THE SCHEMA
```sql
CREATE TABLE emotional_memory (
    id INTEGER PRIMARY KEY,
    timestamp REAL,
    session_id TEXT,
    user_input TEXT,
    mizune_response TEXT,
    detected_emotion TEXT,
    user_reaction TEXT,
    task_outcome TEXT,
    impact_score REAL,
    entities JSON,
    duration_seconds REAL,
    sentiment_confidence REAL
);

CREATE TABLE connection_strength (
    entity TEXT PRIMARY KEY,
    strength REAL DEFAULT 0.0,
    last_updated REAL,
    interaction_count INTEGER DEFAULT 0,
    positive_interactions INTEGER DEFAULT 0,
    negative_interactions INTEGER DEFAULT 0,
    first_seen REAL,
    emotional_arc JSON
);

CREATE TABLE mood_history (
    id INTEGER PRIMARY KEY,
    timestamp REAL,
    valence REAL,
    arousal REAL,
    dominance REAL,
    trust REAL,
    curiosity REAL,
    concern REAL,
    trigger_event TEXT,
    session_id TEXT
);

CREATE TABLE emotional_triggers (
    id INTEGER PRIMARY KEY,
    pattern TEXT,
    emotion_change JSON,
    occurrence_count INTEGER DEFAULT 0,
    reliability_score REAL
);

CREATE TABLE adaptive_tasks (
    id TEXT PRIMARY KEY,
    description TEXT,
    state TEXT,
    steps JSON,
    current_step INTEGER,
    user_context JSON,
    checkpoints JSON,
    created_at REAL,
    completed_at REAL
);

CREATE TABLE checkpoints (
    id INTEGER PRIMARY KEY,
    task_id TEXT,
    step_index INTEGER,
    question TEXT,
    options JSON,
    user_response TEXT,
    allow_freeform BOOLEAN,
    created_at REAL,
    resolved_at REAL
);
```

## PART 7: 5-WEEK IMPLEMENTATION PLAN
1. Emotion Engine
2. Emotional Memory
3. Adaptive Tasks
4. Integration
5. Polish
