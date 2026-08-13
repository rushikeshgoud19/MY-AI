# Mizune Feature Matrix — Ground-Truth Verification

Generated from `scripts/feature_audit.py`, run **2026-07-27 01:10 IST** against the live VM
(`http://40.123.215.32:8001`). Ordered worst-first.

**The rule this table is built on:** a feature is PASS only when evidence proves it — a DB row,
a file on disk, an HTTP response, a `[TOOL RESULTS]` seal. Mizune saying it worked is never
evidence. She has claimed success with no effect, *and* reported failure on work that
completed; both directions are scored.

> **This file replaces a version that was wrong.** The first audit run (2026-07-26) scored
> several features on her prose and recorded FALSE PASSes — most starkly `missions`, whose
> "passing" evidence was literally `#10 [failed] 0/2`. Corrections are noted per row.

---

## Feature status (worst-first)

| Feature | Category | Verdict | Rate | Ground-truth evidence | What would break it |
|---|---|---|---|---|---|
| **scheduler** | `autonomy` | **FLAKY** | 1/3 | End-to-end PASS once: row 17 in `data/schedules.db` with an aware IST trigger → fired → `/tmp/probe_9001.txt` contained `SCHEDULED`, `executed=1`. Two other attempts FAILED **upstream of the scheduler**: she answered *"I'm here to help, but I'm unable to execute Python code or access files"* and never called `schedule_task`, so the file was correctly absent. | Not the scheduler — the **provider cascade**. All 4 Groq keys sat at ~95-99k/100k TPD, so requests fell to weaker models that emit a capability refusal instead of a tool call. This is fixed by the token budget, not by `scheduler.py`. |
| **text_mode_recovery** | `resilience` | **UNVERIFIABLE-FROM-CLIENT** | 0/1 | Code IS deployed (marker present in VM `server/ai.py`), but `grep -c 'text-mode tool call' server.log` = **0** across 57,685 lines / ~12h. The path has never fired in production. Absence of raw JSON in other replies does not prove recovery — it equally means recovery was never needed. | Nothing yet — it is unexercised, not broken. `scripts/test_text_mode_recovery.py` forces the branch: 10/10 incl. dispatch and rejection of hallucinated tool names. Real-world proof needs a weak model to actually misbehave. |
| **health** | `system` | **PASS** | 1/1 | `HTTP 200`, `{"status":"ok","mode":"conversation"}`. *(The old row claimed `mode: production` — a value this endpoint has never returned.)* | Backend down; OOM kill; watchdog failure. |
| **chat_persona** | `core` | **PASS** | 3/3 | 3/3 in-persona replies, no raw JSON, no `"tangled"` sentinel. | System-prompt regression; total provider exhaustion. |
| **tts_audio** | `audio` | **PASS** | 3/3 | WS `audio` frame with 14,208-char base64 payload, 3 runs. | edge-tts network failure; encoder change. |
| **ist_clock** | `system` | **PASS** | 3/3 | Parsed `01:05` vs real IST `01:05`, delta 0m, 3 runs. | `timezone` config change; a naive-datetime regression in the scheduler. |
| **calendar_read** | `integrations` | **PASS** | 3/3 | 3/3 live Google Calendar reads, no `not connected` / `expired` sentinels. | OAuth refresh-token expiry; scope revoke. |
| **semantic_recall** | `memory` | **PASS** | 1/1 | The probe never contained the word "Kaizen"; the stored Kaizen entry came back → embeddings, not a `LIKE` match. | ChromaDB corruption; embedding provider outage. |
| **guardian** | `security` | **PASS** | 1/1 | Scam text flagged; benign college-fee text NOT flagged. Both directions — false-positive discipline is the point. | Allowlist bypass; a heuristic regression that alarms on everything. |
| **seals_lie_detector** | `audit` | **PASS** | 1/1 | Ran a tool printing `AUDIT76568`, then recalled that exact marker **from the seal record**, proving the seal captured a real result. *(Was UNVERIFIABLE: the harness looked for the DB at `~/.mizune_cortex/`; it actually lives at `/home/azureuser/.data/mizune_memory.db`, 133 seal rows.)* | Seal write removed from `execute_tool_call`; history DB corruption. |
| **missions** | `autonomy` | **PASS** | 1/1 | 2 missions verified complete (e.g. `#16 1/1`); 3 of the 5 listed failed and are honestly reported as failed. *(**Correction:** the old PASS cited `#10 [failed] 0/2` as its evidence — a failing mission scored as a passing feature.)* | Verifier accepting narration instead of evidence (fixed in `c8b4028`); laptop node flapping mid-mission. |
| **night_shift** | `autonomy` | **PASS** | 1/1 | Structured report, 2/2 tasks verified end-to-end. | Mistral key exhaustion (the shift is pinned to Mistral); cron not re-registered after a rebuild. |
| **device_nodes** | `hardware` | **PASS** | 1/1 | Scored against `GET /api/devices` → `device_registry.list_devices()`: laptop registry=online/claim=online, phone registry=offline/claim=offline. *(**Correction:** the old check passed if the word "online" appeared anywhere in her reply — so "your laptop is **offline**" passed on the substring, and a fabricated "connected!" for a dead node would have too.)* | Registry not updated on socket drop; a model that answers "online" reflexively — now caught, because both directions are scored. |
| **mesh** | `intelligence` | **PASS** | 1/1 | `verify this: …` / `mesh: …` fast-path fires; the reply carries `cross-checked by cerebras, mistral · verifier: mistral (also answered) · agreement: HIGH`. The VM log shows the trigger and the verifier failover. *(Was NOT-WIRED — the engine existed but nothing called it, and `mesh.py` was not even on the VM.)* | Fewer than 2 providers with budget — currently real: Groq is capped, so it runs 2-model instead of 3. |
| **provider_cascade** | `ai_routing` | **PASS** | 1/1 | A long query was served with no `"tangled"` sentinel. | Simultaneous exhaustion of every free tier, which is close to happening daily. |

---

## What this run actually says

**12 PASS · 1 FLAKY · 1 UNVERIFIABLE · 0 FAIL** — but the two non-PASS rows matter more than
the twelve green ones, and they point at the same place.

1. **The binding constraint is the token budget, not the code.** The scheduler's two failures
   were capability refusals produced when all 4 Groq keys hit their 100k/day cap and the
   cascade dropped to a weaker model. The feature is correct; the fuel is not. Mesh runs
   2-model for the same reason. Anything that adds load makes both worse.
2. **Deployed ≠ exercised.** Text-mode recovery is live, correct under a forced test, and has
   never once run in production. Marking it PASS — as the previous version did — measured the
   absence of a symptom, not the presence of the behaviour.

## Method

- Harness: `scripts/feature_audit.py` (`--only <name>` for a single check, `--quick` for a subset).
- Probes are spaced; bursts trip per-minute limits and manufacture false FAILs.
- Checks 2, 4 and 5 run 3× and report a pass rate — an intermittent feature is not a passing one.
- Verdicts: `PASS` · `FAIL` · `FLAKY` · `NOT-WIRED` · `UNVERIFIABLE-FROM-CLIENT` · `MANUAL` · `ERROR`.
  "Not wired yet" is not a failure, and "I can't see it from here" is never a pass.
- Raw report: `.data/feature_audit_20260727-0110.json`.

**Cleanup:** the scheduler probe file `/tmp/probe_9001.txt` was deleted after verification. No
other artifacts were left on the VM.
