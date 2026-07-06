# Legacy code — quarantined 2026-07-06

Nothing in here is imported by the live server (`main.py` → `server.py` → `server/` package).
Kept for reference only. Safe to delete once you're confident nothing is missed.

| Item | What it was | Replaced by |
|------|-------------|-------------|
| `server_old.py` | 2,849-line pre-refactor monolith | `server.py` + `server/` package |
| `server_ai.py` | Old root-level AI module | `server/ai.py` |
| `backend_main.py` | Alternate entry point | `main.py` |
| `core/` | Old core helpers (actions, audio, config, llm_service, ws_handler) | `server/` modules |
| `server_memory_tree.py` | Old MemoryTreeDB variant | `server/memory_tree.py` |
| `server_memory.py`, `server_emotion.py`, `server_tts.py` | Old root-level modules | `server/memory.py`, `server/emotion.py`, `server/tts.py` |
| `token_juice.py` | Small TokenJuice variant | `server/tokenjuice.py` (merged) |
| `lumina/` | Early prototype (May 2026), depends on old `agents/` | the whole current codebase |

NOTE: the root `agents/` package (ManagerAgent, TaskPlanner, ActionExecutor, ...) is NOT
legacy — `server/agents.py` lazy-imports it at runtime. It stays at the repo root.

Root-level `test_*.py` scripts were moved to `tests/root_scripts/` — run them from the
repo root (e.g. `python tests/root_scripts/test_agents.py`) so imports resolve.
