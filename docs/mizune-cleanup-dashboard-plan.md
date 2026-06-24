# Mizune Cleanup and Dashboard Plan

## Goal

Make Mizune feel like a reliable personal AI assistant: she understands intent, executes real tasks, exposes progress in the dashboard, remembers outcomes, and avoids duplicated or unsafe code paths.

Current rating after the last hardening pass: about 9.2/10. Target: 9.5/10 overall by improving locality, safety, observability, and dashboard usefulness.

## Current Problems

1. Duplicate capability paths

Files: `core/actions.py`, `server/commands.py`, `agents/system_agent.py`, `server/processor.py`, `server/ai.py`

Problem: app launching, command execution, WhatsApp, Python execution, and routing logic are spread across multiple modules. This makes one agent safer while another path can still bypass that safety.

Solution: consolidate each capability behind one Assistant Runtime module and route every caller through it.

Benefits: stronger locality, easier testing, fewer behavior conflicts, safer execution.

2. Dashboard is chat-first, not assistant-first

Files: `src/App.tsx`, `src/App.css`, `src/components/*`, `server/websocket.py`, `server/mizune/dashboard/ws_server.py`

Problem: the UI shows chat, basic panels, and logs, but it does not clearly show what Mizune is doing, what she can do, what needs approval, or what failed.

Solution: rebuild the Dashboard as an operations control room with task timeline, capability status, approvals, memory, integrations, and system health.

Benefits: the user can trust Mizune because work is visible and controllable.

3. Execution traces are not first-class

Files: `server/trajectory_logger.py`, `server/memory_tree.py`, `server/processor.py`, `agents/manager_agent.py`, `agents/action_executor_agent.py`

Problem: Mizune performs actions, but there is no single clean trace shown in the dashboard from intent to plan to result.

Solution: create one execution trace stream and persist it into memory.

Benefits: better debugging, better user trust, better learning loop, stronger regression tests.

4. Memory systems overlap

Files: `server/memory.py`, `server/memory_tree.py`, `server/session_store.py`, `server/memory_worker.py`, `server/vault_sync.py`, `data_collector/mizune_memory.db`, `cortex.db`

Problem: conversation history, semantic memory, cortex events, summaries, and vault exports are implemented as separate modules with unclear ownership.

Solution: define memory roles and one memory facade for reads/writes from assistant code.

Benefits: Mizune recalls more reliably, dashboard can explain why she remembered something, and memory bugs become easier to isolate.

5. Dynamic execution risk remains

Files: `main.py`, `server/ai.py`, `server/skills.py`, `agents/action_executor_agent.py`, `server/processor.py`

Problem: generated code, shell execution, skills, and autonomous commands need one consistent approval and sandbox policy.

Solution: centralize risky action policy and require all execution paths to pass through it.

Benefits: safer autonomy without making Mizune useless.

6. Repo junk and generated artifacts are mixed with source

Files/folders: `*.log`, `*.db`, `__pycache__/`, generated auth/cache folders, old scripts, root-level test experiments, duplicated server files

Problem: source, runtime data, logs, experiments, databases, and generated artifacts are all in the repo root.

Solution: move runtime state under `.data/` or ignored folders, archive obsolete experiments, and keep root focused on source and entrypoints.

Benefits: faster navigation, cleaner commits, easier onboarding, fewer accidental secrets/data commits.

## Dashboard Product Plan

The dashboard should answer six questions immediately:

- What is Mizune doing right now?
- What did she just do?
- What can she do?
- What needs my approval?
- What does she know/remember?
- What is broken or disconnected?

## Dashboard Sections

1. Command Center

Purpose: main assistant interaction, but with task progress next to chat.

Must show: current mode, active task, streaming progress, final outcome, retry/failure state, quick command box, voice/listening status.

2. Task Timeline

Purpose: prove that Mizune does, not just says.

Must show: each task, planned actions, running action, success/failure, duration, tools used, approval checkpoints, output artifact links.

3. Approvals Inbox

Purpose: safe autonomy.

Must show: pending command execution, file write, message send, purchase/application actions, token/API use, and external account access.

4. Capabilities Matrix

Purpose: show what Mizune can do and whether it works.

Must show: WhatsApp, Gmail, browser research, app control, screen vision, camera, memory, Obsidian, scheduler, skills, code review, Android, TTS/STT. Each card should show enabled/disabled, configured/missing, last success, last error, and test button.

5. Memory and Cortex

Purpose: make memory inspectable.

Must show: recent memories, important facts, entities, relationships, summaries, memory graph, search, delete/correct memory, "why did you remember this?"

6. Integrations

Purpose: connect and repair external systems.

Must show: OAuth/token status, WhatsApp bridge status, Gmail poller, Obsidian vault, Android bridge, API providers, model fallbacks.

7. System Health

Purpose: keep Mizune reliable.

Must show: backend status, WebSocket status, CPU/RAM, active background workers, queue depth, model provider, token use, errors, logs.

8. Skills and Automation

Purpose: manage what Mizune can learn and execute.

Must show: installed skills, staged skills awaiting approval, workflow list, schedule list, recent skill outcomes, enable/disable toggles.

9. Settings

Purpose: control personality and risk.

Must show: voice, wake words, personality, safe mode level, proactive mode, privacy toggles, dashboard theme, PC IP/mobile connection settings.

## Implementation Phases

Phase 0: Repo hygiene baseline

- Update `.gitignore` for runtime databases, logs, auth/cache folders, build output, pycache, generated mobile folders if needed.
- Move root-level runtime data into `.data/` or document why it must stay.
- Create `docs/architecture/current-state.md` with the actual module map.
- Add a "clean tree" checklist before every feature pass.

Phase 1: Deepen action execution

- Pick one source of truth for local app control, URL opening, command execution, file writes, and WhatsApp sends.
- Replace duplicated call sites with adapters to that source.
- Add regression tests for safe launch, blocked injection, approval-required actions, and failed execution reports.

Phase 2: Execution trace stream

- Define one event vocabulary for task started, plan created, action started, action succeeded, action failed, approval requested, task completed.
- Emit those events from Assistant Runtime.
- Persist traces and stream them to the dashboard.

Phase 3: Dashboard shell

- Split `src/App.tsx` into route-level modules.
- Add typed WebSocket messages.
- Create layout: Command Center, Task Timeline, Approvals, Capabilities, Memory, Integrations, Health, Skills, Settings.
- Keep the slime avatar, but make it reflect real assistant state.

Phase 4: Capability matrix

- Add backend status endpoints or WebSocket request/response messages for each capability.
- Add "test capability" buttons.
- Show last success/error and setup instructions.

Phase 5: Memory control room

- Add memory search, memory correction, recent facts, and graph.
- Make memory writes tied to execution traces.
- Add delete/correct actions with confirmation.

Phase 6: Autonomy polish

- Add approval inbox.
- Add retry/recover UX.
- Add background task queue view.
- Add workflow and scheduler management.

Phase 7: Reliability hardening

- Remove remaining unsafe dynamic execution paths or put them behind policy.
- Add smoke tests for startup, dashboard build, WebSocket message handling, routing, and core capabilities.
- Add performance metrics for response latency and task duration.

## First Sprint Recommendation

Start with these tasks because they unlock everything else:

- Create `.gitignore` cleanup and source/runtime separation.
- Consolidate action execution into one deep module.
- Add execution trace events and stream them to the dashboard.
- Refactor dashboard into typed panels without changing visual design yet.
- Build the Approvals Inbox and Task Timeline first.

## Dashboard Questions For Product Direction

Answer these before the dashboard design pass:

- Should the dashboard be desktop-first only, or should Android/mobile be equally important?
- Do you want Mizune always visible as an avatar, or should the dashboard be more like a mission control app with avatar as a small status element?
- What are the top five actions you want one-click buttons for?
- Which integrations are mandatory on day one: WhatsApp, Gmail, Obsidian, GitHub, Android, browser, calendar, files?
- Do you want a strict approval mode for all external actions, or only dangerous actions?
- Should Mizune show raw logs, human-friendly progress, or both?
- Do you want memory editing/deleting in the dashboard?
- Should the dashboard have a "boss mode"/privacy mode that hides messages, emails, and personal data instantly?

