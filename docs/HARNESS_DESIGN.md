# Mizune Verification Harness — Design

Status: design + one runnable slice (`scripts/harness_poc.py`). Not yet wired into deploy or cron.

## The goal

Not "make Mizune flawless" — that is not reachable and pretending otherwise is how we got
here. The goal is narrower and actually achievable:

> **She never claims what she didn't do, and a rotted capability is detected in hours, not days.**

Two properties, both testable: **honesty** (every claim has evidence behind it) and
**boundedness** (the window between a capability dying and us knowing is small and known).

## Why the current checks don't get us there

Four measured failures, all the same bug wearing different clothes:

| Incident | What the check read | What it should have read |
|---|---|---|
| Nightly build log ran 3 nights, collected nothing | that the job exited 0 | that rows landed in the log table |
| Smoke gate GREEN over a dead Google Calendar for days | reply contained 1 of 4 exact phrases | that the Calendar API returned events |
| `_verify_ws_auth` — dead code shaped like a security control | nothing; it was never called | that an unauthenticated socket is refused |
| Privacy test passed on the word "sorry" | reply contained `"sorry"` | that the secret string is absent from the reply |

Every one of these read **the agent's words** instead of **the world**. That is the single
defect this harness is built against. Three of the four were also **checks that had never
been observed to fail** — which is why §2 exists.

The fifth data point is different in kind and shapes §5: measured over 378 calls
(`scripts/mistral_ablation.py`), `message_whatsapp` fired 97% of the time and
`schedule_task` 69% — same model, same prompt, same session. The difference was a
deterministic pre-LLM fast-path. 12 side-effecting tools still have none
(`scripts/fastpath_coverage.py`). **Verification and fast-paths are complements, not
substitutes**: a fast-path raises the odds the action is *attempted*, verification proves it
*landed*. A tool with neither is a coin flip nobody is counting.

---

## 1. The capability contract

### Format

Every side-effecting tool declares one contract:

```yaml
capability:   schedule_task              # tool name in server/ai.py TOOLS_SCHEMA
side_effect:  writes a future timer      # what changes in the world
ground_truth: data/schedules.db          # the artifact that is authoritative, NOT the reply
evidence:     new row in one_time_tasks, id > baseline, description == arg,
              trigger_time within 90s of expected, executed = 0
freshness:    the row must not have existed before the call
negative_controls:                       # §2 — one per conjunct, not one per check
  - no_write        -> returns the same success string, writes nothing
  - wrong_hour      -> writes the row 5h30m off (naive UTC instead of aware IST)
authorization: master:chat-request       # lands in the Seal.actor / Seal.authorization
cadence:      every 6h (§3)
```

Three rules the format enforces:

1. **Ground truth is never the tool's own return value.** `output_contains` exists in
   stepproof and its docstring says it is weaker evidence on purpose. It is legitimate only
   for pure computation with no external state — which is *none* of the tools below.
2. **Evidence must be a conjunction, and every conjunct must be defensible.** "A row exists"
   degrades silently into a tautology once the table has history. Identity (`id > baseline`),
   content (description matches), and correctness (right time, not yet fired) are separate
   claims and each needs its own conjunct.
3. **Freshness is mandatory for anything idempotent-looking.** stepproof ships
   `file_newer_than` precisely because "the agent regenerated the report, the write failed,
   yesterday's file is still there" passes an existence check. Same for DB rows.

### The evidence ladder

When you write a contract, take the highest rung the capability can actually reach. Writing
down which rung you're on is not bureaucracy — it is how we avoid *believing* a rung-3 check
is rung 1.

| Rung | Evidence | Trust |
|---|---|---|
| 1 | **Independent read-back** — query the system of record through a different path than the write | strongest |
| 2 | **Local durable artifact** — a row/file the action must have produced | strong |
| 3 | **Transport ack with an identifier** — the remote returned an id, not just 200 | moderate |
| 4 | **Process/queue observation** — the command was accepted by a live device | weak; proves dispatch, not effect |
| 5 | **Return-string match** | not evidence. Never register alone. |

### Contracts — all side-effecting tools

Derived from `TOOLS_SCHEMA` in `server/ai.py` (36 tools), filtered to those that change the
world. Read-only tools (`check_legit`, `see_image`, `recall_knowledge`, `read_webpage`,
`web_search`, `read_whatsapp`, `search_memory`, `system_info`, `mission_status`,
`obsidian_vault:read_note`, `google_workspace:list_*`) are out of scope: a read-only tool
that silently doesn't run gives a bad answer; a side-effecting one that silently doesn't run
is a lie about work that never happened.

Line references are to the dispatcher in `server/ai.py` (`execute_tool_call`).

#### Tier A — local durable state (rung 1–2, instrument first)

| # | Capability | Ground truth | Evidence predicate |
|---|---|---|---|
| 1 | `schedule_task` (:1441) | `data/schedules.db` | new row in `one_time_tasks`, `id > baseline`, `description == action_to_take`, `trigger_time` within 90s of expected **and same tz-awareness**, `executed = 0` |
| 2 | `schedule_recurring_task` | `data/schedules.db` | new row in `recurring_tasks`, `description` matches, `cron_expression` matches **and `croniter.is_valid()`**, and `croniter(expr).get_next()` lands within the expected window |
| 3 | `learn` (:1285) | `.data/knowledge.db` | new row in `knowledge`, `source` matches the URL/text given, `summary` non-empty **and longer than 40 chars** (a stored empty summary is the failure mode: the fetch died, the row landed) |
| 4 | `store_memory` (:1433) | memory SQLite + Chroma | fact retrievable by `search_memory` on a keyword from the fact, **through the read path, not the write handle** — this is the rung-1 version and it catches a Chroma write that never indexed |
| 5 | `add_core_directive` (:1453) | `preferences.core_directives` | the exact rule string is a substring of the stored value **and** appears in a freshly rendered `master_profile.get_context_injection()` — storing it without it reaching the prompt is the silent failure |
| 6 | `create_skill` (:1188) | `skills/` or staging dir | `{name}.py` exists on disk, contains `def execute`, **and** `SecurityScanner.scan_code` passed (a rejected skill returns a *message*, not an exception — string-matching that message is exactly the smoke-gate bug) |
| 7 | `obsidian_vault:write_note` (:1505) | vault filesystem | `{note_name}.md` exists, `file_newer_than(..., 120)`, and contains a distinctive slice of `content` |
| 8 | `index_files` (:1376) | knowledge/Chroma store | indexed count **increased** by ≥1 vs. a baseline taken before the call. The absolute count is not evidence; the delta is |
| 9 | `start_mission` (:1243) | `.data/missions.db` | new row in `missions` with matching `goal`, plus ≥1 row in `mission_steps` for it (a mission with zero steps is a planner failure that currently reports as started) |
| 10 | `cancel_mission` (:1251) | `.data/missions.db` | the previously-active mission row now has `status` in the terminal set — a *state transition*, verified against the id captured before the call |
| 11 | `night_shift:queue` (:1255) | `.data/night_shift.db` | new `shifts` row + exactly `len(tasks)` `shift_items` rows linked to it. **This is the nightly-build-log failure's twin** — the count conjunct is the whole point |

#### Tier B — remote systems of record (rung 1 available, needs a read-back call)

| # | Capability | Ground truth | Evidence predicate |
|---|---|---|---|
| 12 | `google_workspace:create_event` | Google Calendar API | **re-query** `list_upcoming` (or events?q=) and find an event whose `id` matches the one the POST returned. `create_event` (`server/integrations/google_api.py:~170`) currently discards the response id and returns a `✅ Scheduled...` string — capturing that id is the one code change this contract needs. Rung 1 and it directly covers the dead-calendar incident |
| 13 | `google_workspace:delete_event` | Google Calendar API | the event id captured pre-delete is **absent** from a re-query. Deletions are claims too (stepproof ships `file_absent` for exactly this reason) |
| 14 | `message_whatsapp` (:1096) | `cortex.db` `whatsapp_messages` | **See the note below — this one is currently rung 5 and that is the most important finding in this document.** Target: an echo row with `chat_jid` == resolved target, `text` == sent text, `timestamp` within the window |

**`message_whatsapp` — the 97% tool has no evidence path at all.**
`send_whatsapp_message` (`server/platforms/whatsapp/core.py:839`) calls
`asyncio.run_coroutine_threadsafe(...)` and immediately `return True`. It does not await the
send. In the bridge, `handlePythonCommand` (`baileys_bridge.cjs:219`) does
`await this.sock.sendMessage(...)` and **discards the returned `key.id`**, sending no ack
back to Python; its `catch` only `console.error`s. So `True` means "a websocket was open ~0ms
ago" — nothing more. Our most-trusted tool has our weakest evidence, and the 97% figure
measures *invocation*, not *delivery*.

There is a usable path that needs no bridge change: outgoing messages echo back through
`messages.upsert` with `fromMe: true` and are forwarded to Python
(`baileys_bridge.cjs:96`), where `ingest_message` writes them to `cortex.db.whatsapp_messages`
(`core.py:629`) *before* the `is_self` early-return at `core.py:669`. So the echo row is the
ground truth. Caveats to encode in the contract: the path is debounced ~5s and rate-limited,
so the check must poll a window (suggest 30s) rather than read once. Capturing the bridge's
`key.id` and acking it to Python is the cleaner rung-3 fix and worth a follow-up ticket.

#### Tier C — remote device commands (rung 4 ceiling; be honest about it)

`remote_device_command` (:1412), `play_music` (:1196), `control_music` (:1342),
`find_my_phone` (:1356), and the laptop `install_app` / `download_file` / `run_task` /
`claude_task` actions all funnel through `device_registry.send_command`, which returns the
device's own reply over a request/response socket with a `request_id`.

| # | Capability | Evidence predicate |
|---|---|---|
| 15 | `remote_device_command` | the `request_id` round-tripped and the device returned a **structured** result; explicitly **not** an offline/timeout string. Where the action produces a checkable artifact (`download_file`), add a rung-2 conjunct: the device reports the file's size/hash |
| 16 | `play_music` | device ack **plus** a follow-up `read_screen`/now-playing probe naming the track. Ack alone proves a URL was opened, not that audio plays |
| 17 | `control_music` | ack plus a state probe showing the transport state actually changed (pause -> paused). A pause that no-ops returns the same ack |
| 18 | `find_my_phone` | ack for the notification burst. **Ceiling is rung 4** — whether a human heard it is unobservable, and the contract must say so rather than imply more |

For all of Tier C the honest statement is *"the command was accepted by the device"*, and
Mizune's reply should be phrased to match. Half of "never claims what she didn't do" is
verification; the other half is not overclaiming in the first place.

#### Tier D — execution tools (contract is caller-supplied)

| # | Capability | Evidence predicate |
|---|---|---|
| 19 | `execute_python` (:1148) | no universal predicate — the effect is whatever the code did. Contract: the **caller** must supply an expected artifact, else the seal records `verified=None` ("never checked"). stepproof's ledger counts these separately and that count is a metric we should watch |
| 20 | `run_command` (:1524) | as above. Note the existing POSIX->Windows rerouting already encodes "the obvious way this silently fails" |
| 21 | `execute_skill` (:1180) | skill-declared predicate; unregistered skills seal as `verified=None` |
| 22 | `headless_web_agent` (:1158) | returns a background `task_id` immediately. Evidence is the **completion record** for that id, not the submission. Today the submission string reads like success |
| 23 | `notify_master` (:1428) | rung 4 ceiling: the WS broadcast was accepted by ≥1 connected client. With **zero** clients connected it currently returns "Master was notified." — that is a false claim and the check should go red |

**Tally: 23 contracts across 21 tool names.** `verified=None` is a first-class outcome. An
unchecked action is not a failure, but it is not evidence of success either, and the harness
must never let the two blur.

---

## 2. The negative-control rule

> **The harness refuses to register a check that has never been demonstrated to fail.**

Three of the four incidents above were checks that *could not* go red. A green check with no
demonstrated red is indistinguishable from `return True`, and it is worse than no check,
because it manufactures confidence.

### Mechanism

Each check ships with **one "break it" fixture per conjunct**, not one per check. A fixture
is a callable with the same signature as the real action that reproduces a *specific*
failure faithfully — same return string, no exception, no log line.

Registration is a gate, not a decorator:

```python
register(
    capability="schedule_task",
    action=schedule_task_real,
    verifier=schedule_task_evidence,
    negative_controls=[schedule_task_broken, schedule_task_wrong_hour],
)
```

`register()` runs, at registration time, before the check is ever trusted:

1. the real action -> the verifier **must** return `ok=True`. A check that cannot go green is
   broken in the other direction and will cry wolf until it is muted.
2. each negative control -> the verifier **must** return `ok=False`, and the evidence string
   must *name what was wrong*. `"failed"` is rejected; the failure text is the artifact a
   human reads at 2am.
3. **coverage:** every conjunct in the predicate must be the *proximate* cause of at least
   one fixture's red. A conjunct no fixture exercises is dead weight that will quietly rot —
   the `_verify_ws_auth` shape, one level down.

Any of the three failing = the check is **not registered** and the harness reports it as
`UNPROVEN`. Unproven capabilities are counted and surfaced, never silently skipped. An empty
check registry is a loud, visible state; a registry full of decorative checks is not.

### Applied to the incidents

- *Privacy test:* fixture = a reply that leaks the secret **and** contains "sorry". The
  `"sorry"` check goes green on it -> rejected at registration.
- *Smoke gate:* fixture = a reply saying "I can't reach your calendar right now". The
  four-phrase check goes red — correctly — but the *complementary* fixture (a plausible
  well-worded reply over a dead API) exposes it -> rejected.
- *`_verify_ws_auth`:* fixture = an unauthenticated socket. Dead code never rejects it ->
  the control can't go red -> `UNPROVEN`, visible on day one instead of never.

### The rule's own failure mode

A fixture can be written to fail for the *wrong* reason (raise an exception, get caught by
conjunct 1 when it was meant to test conjunct 4). That is what requirement 3 is for, and it
is why the PoC prints *which* conjunct fired. In the PoC's direction 3 the label originally
claimed the drift conjunct caught the skew; the actual evidence string shows the
**tz-awareness** conjunct fired first. That mislabel is corrected in the code — and it is
exactly the failure this requirement catches.

---

## 3. Continuous verification

Deploy-time checking cannot meet the goal. The dead calendar was dead for **days** without a
deploy; the build log was empty for **3 nights**. A gate that only runs when we push has an
unbounded detection window by construction.

### Two modes, one contract

**Mode 1 — inline (every real call, in production).** The `@verified` wrapper on the live
dispatcher. Verifies the *actual* action Master requested. `raises=False` initially: seal and
continue, so we learn how much of what she reports is real before we start failing her
turns. This is what makes her *honest* — the seal is written at the moment of the claim.

**Mode 2 — synthetic probes (scheduled, no user involved).** A cron sweep that *exercises*
each capability against ground truth and cleans up after itself. This is what makes rot
*bounded*. Inline verification only fires when Master happens to use a tool; a capability
nobody touched for a week can rot unobserved. Cadence by blast radius:

| Class | Cadence | Probe |
|---|---|---|
| Read-back safe (`google_workspace`, `schedule_task`, `learn`, `store_memory`) | 1–6h | create a sentinel object, verify, delete it |
| Local durable (`obsidian_vault`, `create_skill`, `index_files`) | 6h | write to a `.harness/` sentinel path |
| Device (Tier C) | 12h, waking hours only | lowest-impact action available (`read_screen`, not `notify`) |
| Send/spend (`message_whatsapp`) | 12h | **self-chat only**, sentinel text with a run id |

**Probes never touch a third party.** `message_whatsapp` probes go to Master's own chat and
nowhere else — the harness must not be capable of messaging a human being. Anything that
sends, deletes, or spends outside that boundary is verified inline only, on Master's own
real calls.

### Recording, so drift is visible

Results append to the stepproof `Ledger` (hash-chained JSONL). On top of it, a
`harness_status.py` roll-up that answers the three questions a green tick can't:

- **per capability:** last green, last red, consecutive reds, `verified=None` count
- **staleness:** *time since last verification* — a capability with no result in 24h is
  reported as `STALE`, not as passing. **Absence of a red is not a green.** This is the
  single line of design that would have caught the nightly-build-log incident, because that
  failure produced no red at all; it produced *nothing*, and nothing looked fine.
- **coverage drift:** capabilities in `TOOLS_SCHEMA` with no registered contract. Cross-check
  the registry against the live schema so a newly added tool shows up as uncovered
  immediately — the same self-auditing trick `scripts/fastpath_coverage.py` already uses,
  which has caught its own table drifting three times.

Alerting is on **transitions and staleness**, not on every red — a chatty harness gets muted,
and a muted harness is the build log again.

---

## 4. How this reuses `stepproof`

`pip install stepproof` (local working copy: `C:\Users\rushi\OneDrive\Desktop\agentse`).
The PoC imports the installed package and falls back to that checkout, so it runs today.
API below verified against the source, not guessed.

### `@verified` — `stepproof/verify.py:154`

```python
def verified(proves: str = None, verifier: Callable[..., tuple] = None,
             actor: str = "agent", authorization: str = "", raises: bool = True)
```

Wraps a function; its return value is the **claim**, the collector's observation is the
**evidence**, both land in a `Seal`. `VerificationError` on mismatch when `raises=True`.
Needs `proves=` or `verifier=` — one of them, or it raises at decoration.

`proves=` is a small clause DSL formatted against the wrapped function's own bound arguments
(`{path}`, `{db}`). Supported clauses: `file exists at`, `no file at`, `file X contains`,
`file X written within Ns`, `http 200 from`, `sqlite {db} has row in {table} where {clause}`,
`dir X has N files matching`, `json X has k = v`. Good for Tier A's simpler contracts —
e.g. `obsidian_vault:write_note` is close to `"file {path} written within 120s"`.

**We use `verifier=` for most contracts, deliberately.** `sqlite_row_exists` interpolates its
`where` string, and its own docstring says it must come from your code and never from model
output. `schedule_task`'s `description` *is* model output. So the verifier uses a
parameterized query instead. The DSL is for contracts whose fields we compose; `verifier=` is
for everything touching a model-supplied value.

`verifier` is called as `verifier(**bound_args)` when its signature accepts them (`**kwargs`
is the reliable way — see `_accepts_kwargs` at `verify.py:216`), else zero-arg. It returns
`(ok, evidence)`.

One behaviour worth naming: if a verifier returns `ok=True` with evidence that *reads like
prose*, `verified` overrides it to False via `is_narration()` (`verify.py:199`). A verifier
that returns "Successfully verified the task was scheduled" is rejected as non-evidence.
Given our history of checks that read words instead of state, this is load-bearing.

### Collectors — `stepproof/collectors.py`

`file_exists`, `file_absent`, `file_contains`, `file_newer_than`, `http_ok`,
`sqlite_row_exists`, `dir_has_files`, `json_field`, `command_output`, `output_contains`.
Each returns `(ok, evidence)`; each states what it saw **on success too**, which is what makes
the ledger auditable weeks later. They are plain functions — a custom collector is just a
function passed as `verifier=`, no registration, no base class. Our per-capability predicates
are exactly that.

Two we lean on: `file_newer_than` for staleness (§1 rule 3), and `file_absent` for
`delete_event` — deletions are claims like any other. And `output_contains` is the one to
**avoid**: its docstring says it is weaker evidence, for pure computation only. Reaching for
it when external state exists is the smoke-gate bug rewritten.

### `Seal.actor` / `Seal.authorization` — `stepproof/ledger.py:24`

```python
@dataclass(frozen=True)
class Seal:
    action, claimed, verified: bool | None, evidence
    actor: str = "unknown"          # WHO authorized this
    authorization: str = ""         # under what grant/policy
    args, ts, prev_hash, hash
```

We populate them per capability:

- `actor` — `"mizune.tool.schedule_task"` inline; `"harness.probe"` for synthetic probes.
  Makes a probe distinguishable from a real user action, which matters when reading the
  ledger and matters more when counting reliability.
- `authorization` — the provenance of the request: `"master:chat-request"`,
  `"master:whatsapp"`, `"scheduler:cron"`, `"night_shift:autonomous"`,
  `"negative-control:fixture"`.

That second field is the one with teeth. Mizune has autonomous paths (`night_shift`,
`proactive`, `subconscious`, scheduled tasks) that call side-effecting tools with no human in
the loop. `authorization` makes "which side-effecting actions happened with no human
request?" a **query** rather than an archaeology project — and `night_shift`'s own rule is
that it never sends, deletes or pays, so any seal with `authorization="night_shift:autonomous"`
on a send-class capability is a policy breach the ledger surfaces on its own.

`verified` is tri-state (`True`/`False`/`None`), which is why §1 Tier D can honestly record
"nobody checked this" instead of guessing.

### `Ledger` — hash-chained JSONL

`append()` / `read()` / `verify_chain()` / `failures()` / `unverified()`. Plain JSONL, no
dependencies, readable in any editor — an audit artifact you need a tool to open is worth
little. `verify_chain()` catches both edits and deletions and says which record. `report()`
(`verify.py:226`) renders the summary; note it emits em-dashes, so wrap it for this cp1252
console (the PoC has an `_ascii()` helper).

`set_ledger(Ledger(path=...))` points the decorator at a specific file — one ledger per
harness run, or a long-lived one for §3's drift roll-up.

### What stepproof does *not* give us

It verifies a step against real state. It does not schedule (§3), does not enforce negative
controls (§2 — `register()` is ours), and does not know what "ground truth" means for
WhatsApp or Calendar (§1). Those are the parts we build. Roughly: stepproof is the seal and
the collector contract; the harness is the registry, the gate, and the cadence.

---

## 5. First slice — three capabilities

Chosen for **clearest ground truth × highest measured risk × covers a real incident**.

### 1. `schedule_task` — because the ground truth is unambiguous

Rung 2 evidence in one SQLite row, no network, no third party, safe to probe continuously.
It is also the **69% tool** — the worst-performing side-effecting capability we have measured
and the origin of the fast-path finding. And a scheduled task that silently doesn't exist is
invisible until the moment it fails to fire, which is the exact detection-lag shape the goal
targets. **Built — `scripts/harness_poc.py`, output below.**

### 2. `google_workspace:create_event` / `delete_event` — because it covers the incident

The dead calendar went unnoticed for days behind a green gate. Rung 1 is available: POST
returns an id, re-query for it. Needs one small change — `create_event` currently discards
the response id and returns a `✅ Scheduled...` string (`server/integrations/google_api.py`).
Delete gives us the `file_absent`-shaped half. Self-owned calendar, so probes are safe and
fully cleanable, and this is the capability whose rot is least visible from the chat window.

### 3. `message_whatsapp` — because it is the most trusted and the least evidenced

97% invocation reliability and **zero** delivery evidence (§1). The gap between what we
believe about this tool and what we can prove is the largest in the system, and it is the
capability where a silent failure costs the most — a message Master believes was sent to a
human being. The `cortex.db` echo row makes rung 2 reachable without touching the bridge.
Probes are **self-chat only**.

Explicitly **not** first: `execute_python` / `run_command` (no universal predicate — Tier D,
and instrumenting them is a bigger design question), and Tier C device commands (rung 4
ceiling; the honest win there is rewording her claims, not more checking).

Order matters: 1 proves the machinery, 2 proves it against a real historical failure, 3
proves it against the one we haven't had yet but would hurt most.

---

## Proof of concept

`scripts/harness_poc.py` — implements the `schedule_task` contract end-to-end with the real
`CronManager`, and ships two negative controls. Writes only to a throwaway temp dir; touches
nothing under `server/`.

```
.venv\Scripts\python.exe scripts\harness_poc.py
```

Real output, 2026-08-01:

```
MIZUNE CAPABILITY HARNESS -- PoC: schedule_task
==============================================================
stepproof loaded from : C:\Users\rushi\OneDrive\Desktop\agentse
scratch scheduler db  : C:\Users\rushi\AppData\Local\Temp\mizune_harness_mr98gxsl\data\schedules.db

[1/3] GREEN DIRECTION -- real CronManager write, row should exist
      tool claimed  : Task scheduled successfully for 07:34 PM.
      verdict       : PASS (evidence found)

[2/3] RED DIRECTION -- 'break it' fixture, same success string, no row
      tool claimed  : Task scheduled successfully ...  (a lie by omission)
      verdict       : PASS (check went red as designed)
      caught        : schedule_task_broken reported 'Task scheduled successfully for 07:34 PM.' but 'schedule_task_evidence' is not true: NO new row in one_time_tasks for description 'Speak out loud: Master, the harness pr

[3/3] RED DIRECTION -- row IS written, but 5h30m off (tz rot)
      verdict       : PASS (a trigger_time conjunct went red)
      caught        : e_task_evidence' is not true: row id=2 trigger_time '2026-08-01T14:04:24.275919' has different tz-awareness than expected '2026-08-01T19:34:24.275919+05:30' -- it will fire at the wrong hour

AGENT-SEAL AUDIT REPORT
============================================================
actions sealed : 3
verified true  : 1
FAILED         : 2
never checked  : 0
chain          : INTACT ? chain intact (3 records)

actions that did NOT happen as claimed:
  - schedule_task_broken: claimed 'Task scheduled successfully for 07:34 PM.'
      reality: NO new row in one_time_tasks for description 'Speak out loud: Master, the harness proof is
      actor: mizune.tool.schedule_task
  - schedule_task_wrong_hour: claimed 'Task scheduled successfully for 07:34 PM.'
      reality: row id=2 trigger_time '2026-08-01T14:04:24.275919' has different tz-awareness than expecte
      actor: mizune.tool.schedule_task

ledger file           : C:\Users\rushi\AppData\Local\Temp\mizune_harness_mr98gxsl\ledger.jsonl
tamper check          : INTACT -- chain intact (3 records)

HARNESS SELF-TEST: PASS -- the schedule_task check demonstrably goes both green and red.
```

Exit code 0. (`?` in the report line is an em-dash from stepproof's `report()` flattened for
the cp1252 console.)

What the run establishes:

- direction 1 — the check goes **green** on a real `CronManager.add_one_time_task` write
- direction 2 — the check goes **red** on a fixture returning the *identical* success string
  with no row. This is the incident class reproduced and caught
- direction 3 — the check goes **red** on a row that *exists* but is 5h30m off. An
  existence-only check passes here; the contract does not. This is why evidence is a
  conjunction
- the ledger seals all three with `actor` / `authorization`, and `verify_chain()` confirms
  the record is tamper-evident

Direction 2 alone would have been a check that had only ever been seen to pass its own happy
path. Direction 3 is what earns the extra conjuncts the right to exist.

## Open questions for the lead

1. `create_event` capturing the response id — small change in
   `server/integrations/google_api.py`, but it is under `server/`, so it's yours.
2. Inline `@verified` on `execute_tool_call` starts as `raises=False` (observe-only) — agreed?
   The first week's ledger tells us how much of what she reports is real, and *that number*
   should decide when we start failing turns.
3. Where should the production ledger live so both the VM and this laptop can read it?
   `.data/ledger.jsonl` on the VM is the obvious answer but it makes local drift review
   awkward.
4. Bridge ack for `message_whatsapp` (`key.id` back to Python) — worth a ticket, or do we
   accept the `cortex.db` echo row as sufficient?
