<div align="center">

# 🌊 Mizune

**A self-hosted autonomous AI assistant that runs 24/7 on a single 898 MB VM — and proves what it did.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-WebSocket-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Kotlin](https://img.shields.io/badge/Android-Kotlin-3DDC84?style=flat-square&logo=android&logoColor=white)](https://kotlinlang.org)
[![Azure](https://img.shields.io/badge/Cloud-Azure_VM-0078D4?style=flat-square&logo=microsoftazure&logoColor=white)](https://azure.microsoft.com)
[![ChromaDB](https://img.shields.io/badge/Vector_DB-ChromaDB-FF6F00?style=flat-square)](https://trychroma.com)
[![License](https://img.shields.io/badge/License-MIT-blue?style=flat-square)](LICENSE)

<samp>

**$0 inference spend** · **~2s typical reply** · **7-provider failover** · **~12.6k LOC** · solo build

</samp>

*Not a chatbot. A 24/7 assistant that schedules real actions, executes on remote devices,*
*briefs you every morning — and verifies its own claims against ground truth.*

</div>

---

## Why this exists

Every AI assistant you can rent is **request–response**: it helps for three minutes when prompted,
then stops existing. Its memory of you belongs to the vendor. It has no hands. And you cannot audit
whether it actually did what it said.

Mizune is the opposite of all four. It owns its data, runs on hardware I control, holds intentions
across days, acts through real devices — and every consequential action leaves a ground-truth record
that can be diffed against what it claimed.

That last property turned out to be the whole project. **Language models lie about their own
actions** — not maliciously, but because pattern-matching a plausible confirmation is easier than
doing the work. Mine once reported *"Task scheduled successfully for 2:32 PM"* with no row in the
scheduler database. Everything below is downstream of taking that seriously.

---

## Architecture

```
                            ┌──────────────────────────────────┐
                            │           CLOUD BRAIN            │
                            │    FastAPI · WebSocket :8001     │
                            │        (898 MB Azure VM)         │
                            │                                  │
   WhatsApp  ◄──Baileys───► │  processor ──► 7-provider cascade │ ◄──WS──► Voice UI /
   (loop-proof              │      │          groq → cerebras   │          Dashboard
    secretary)              │      │          → mistral →       │        (neural TTS
                            │      │          gemini →          │         streamed)
   Gmail  ◄────poll───────► │      │          openrouter →      │
   (+ Guardian scan)        │      │          nvidia → local    │ ◄──WS──► Device nodes
                            │      │                            │      laptop ✓  phone ✓
   Calendar ◄──OAuth──────► │  memory tree      scheduler       │      (AccessibilityService)
                            │  (episodic →      (IST-aware      │
   Obsidian ◄───sync──────► │   summary →        cron)          │
   vault (idempotent)       │   sealed)                         │
                            │  ChromaDB      [TOOL RESULTS]     │
                            │  semantic       truth seals       │
                            │  recall         (the lie detector)│
                            └──────────────────────────────────┘
```

**One brain, two entry points** — `main.py` → `server.py` locally; the same `server/` package runs on
the VM for 24/7 operation. A single `/ws` WebSocket carries chat, status, emotion state, streamed TTS
audio, and device-node registration.

---

## Capabilities

| Capability | How it works |
|---|---|
| **Messaging secretary** | Native WhatsApp (Baileys): contact tiering, rate limiting, 5s debounce, 4k chunking, voice-note transcription. Echo-loop-proof by design — she runs on my own number, so every reply echoes back as `is_self`. |
| **Verified missions** | A goal is decomposed into steps, each with an *objectively checkable* verification. A step is not done because she says so — it's done because evidence proved it. Failed verification triggers one informed retry, then an honest failure. |
| **Scheduled actions** | "In an hour, do X" schedules a real action, not a reminder. Stored code executes through the guarded dispatcher directly — never re-typed by the model, because models corrupt quote-heavy strings in tool JSON. |
| **Device hands** | Lightweight agents connect *outbound* from laptop and phone and register capabilities. The Android client drives arbitrary apps via a custom `AccessibilityService` (tap-by-text, type, scroll, screen-read) — the only way to act on Android 10+, which silently blocks background activity launches. |
| **Guardian fraud shield** | Rule-first scam detection on inbound mail and messages: candidate-fee demands, recruiter-domain impersonation, OTP/KYC urgency, shortened links. Warn-only — never auto-deletes, auto-replies, or clicks. |
| **Truth seals** | Every side-effecting tool call writes `[TOOL RESULTS] <tool>: <outcome>` to memory. Claims are auditable against seals; when words and seals disagree, **seals win**. |
| **Three-layer memory** | episodic → summary → sealed, plus ChromaDB semantic recall on every message, hard-capped by token budget. Recall is meaning-based: *"getting better at skills"* retrieves a note titled *"Deliberate Practice"* with zero keyword overlap. |
| **Morning briefing** | Deterministic collection (weather, calendar, due tasks, important mail) at a configurable hour. Code collects and code delivers; the model only voices it. If voicing fails, the raw data still ships — data over silence. |
| **Evaluation harness** | Scores every provider on response fidelity *and* tool-selection correctness against a fixed prompt set, separating **availability** from **fidelity** so a rate-limited provider isn't mistaken for a bad one. |
| **Cross-model verification** | Fans one question to K providers in parallel, then a *different* model reconciles the answers and flags disagreement. Nearly free because it runs across free tiers. |
| **Portable self** | `mizune_export.py` dumps identity, memory, knowledge and embeddings to one checksummed archive — secrets excluded, redacted config schema included. `mizune_import.py` reconstitutes her on a clean machine with integrity verification. |
| **Self-extension** | Writes, registers and version-tracks its own skill plugins, with success-rate telemetry. |
| **Neural voice** | Browser speech recognition in; server-generated neural TTS streamed back over WebSocket — real voice quality, not browser synthesis. |

---

## Measured results

All figures from production traces (TraceRoot), before → after the optimization program. Measured,
not estimated:

| Metric | Before | After |
|---|---|---|
| Typical response | 17s+ | **~2s** |
| Average response | 18.2s | **6.3s** |
| Median prompt size | 8,309 tokens | **5,211** (−37%) |
| Worst prompt spike | 45,216 tokens | **12,507** — structurally capped |
| Failure storms | 11% of traces | zero user-facing (cascade fallback) |
| Inference cost | — | **$0** (free tiers + key rotation) |

**Guardian**, on a real 186-email inbox: 185 safe / 1 suspicious / 0 threats, with a purpose-built
adversarial suite at 9/9. A false positive on a *legitimate* college fee demand was caught during
review and fixed — the rule now requires hiring context and exempts institutional domains, because
a student's inbox is full of real fee requests.

---

## Engineering notes

The interesting problems weren't the features.

**The model lies about its own actions.** It reported scheduling a task that was never scheduled,
having pattern-matched an earlier confirmation in its context. Fix, in two parts: every side-effecting
tool writes a ground-truth seal, so claims can be diffed against reality; and anything that *must*
happen gets a deterministic regex fast-path instead of relying on the model to choose a tool.
**LLMs voice, code delivers.**

**My own watchdog was causing the crashes it existed to prevent.** The assistant kept getting
OOM-killed. The app used only 220 MB of 898 MB — the rest was **~90 orphaned X11 display servers**,
displays `:120`–`:207`, the oldest running 18 days. `xvfb-run -a` allocates a new display and never
cleaned up, and a watchdog restarting every minute meant every crash leaked another one. Swap sat at
100%. Fixed the process lifecycle; swap dropped to 3%.

**Verification is only as good as its evidence.** A mission step failed because the verify stage
replied *"I will use the execute_python tool to check…"* — a plan, not evidence. The judge correctly
ruled FAIL on a step that had actually succeeded. Now narration is detected deterministically and
forces a real check; if it still won't act, the result is an honest *"inconclusive"* rather than a guess.

**Constraints produce better engineering.** 898 MB with `torch` blocked at the import level forced
ONNX embeddings, a hard context-token ceiling, and treating provider *availability* as a first-class
design input. The token work that came out of it cut cost and latency simultaneously.

---

## Quick start

```bash
git clone https://github.com/rushikeshgoud19/MY-AI.git && cd MY-AI
python -m venv .venv && .venv/Scripts/activate      # Windows
pip install -r requirements.txt

# 1. Configuration — secrets never leave your machine (gitignored)
cp config.example.json config.json                  # add your provider API keys

# 2. Start the brain
python main.py                                      # FastAPI on :8001

# 3. Voice interface
#    http://localhost:8001/ui/voice.html            (Chrome/Edge for microphone)

# 4. WhatsApp — the Baileys bridge starts with the core; scan the QR once.

# 5. Optional: register this machine as a device node
python device_agent.py --server ws://localhost:8001/ws --name laptop
```

**Free-tier friendly.** One provider key is enough to start; the cascade uses whatever is configured.

```bash
python scripts/smoke_test.py          # health · chat · TTS audio · calendar  (the deploy gate)
python scripts/mizune_export.py       # portable, checksummed, secret-free archive of her self
python scripts/persona_benchmark.py   # score providers on voice + tool-choice fidelity
```

---

## Repository layout

```
server/            core runtime — processor, AI cascade, memory, scheduler, missions,
                   night_shift, guardian, mesh, briefing, background agent,
                   platforms/ (whatsapp · gmail · android), TTS, vault sync
agents/            intent-routing manager (production dependency)
public/            voice UI and dashboard assets
character/         personality definition (SOUL.md)
mizune-android/    Kotlin companion app — WebSocket client, TTS, wake word,
                   MizuneAccessibilityService (the phone's hands)
device_agent.py    device-node agent for desktop machines
scripts/           smoke test · export/import · benchmarks · content engine
docs/              engineering ledger and architecture references
legacy/            retired implementations, kept for reference
```

---

## Engineering principles

1. **Measure before optimizing.** Every performance claim above comes from production trace data.
2. **Deterministic where it matters.** Data collection, scheduling and code execution are code paths,
   not model calls. The model handles language; the runtime handles truth.
3. **Trust but verify.** Claims are auditable against sealed outcome records. When words and seals
   disagree, the seals win.
4. **Fail honestly.** Errors surface as clear reports — never silent retries or invented success.
5. **Ask, don't act,** on anything with consequences. One confirming question, then do it.
6. **Quiet by default.** Every proactive channel has a usefulness bar, quiet hours and a daily cap.
   An assistant that pings 20× a day gets muted, and then it may as well not exist.
7. **Secrets stay home.** Keys live in gitignored config; telemetry capture is scrubbed at the
   decorator level.

---

## Status & roadmap

**Live:** WhatsApp secretary · semantic recall · vision · verified missions · 7-provider cascade with
key rotation · Guardian · scheduler with IST-canonical clock · morning briefing · laptop + phone
device nodes with accessibility control · nightly self-review (reports bugs, never auto-fixes) ·
export/import · provider evaluation harness · cross-model verification.

**In flight:** 8-hour autonomous night shifts with proof-of-work reporting (built; a full overnight
run on real tasks is not yet proven). Offline local-model fallback is designed and deferred.

**Next:** operator console (device fleet, seal feed, memory graph) · accessibility assistance for
blind and elderly users, built on the phone-control layer — the piece with a life beyond me.

---

<div align="center">
<samp>

MIT © [Rushikesh](https://github.com/rushikeshgoud19) · built because a companion that goes silent at 3 AM is a bug you *feel*

</samp>
</div>
