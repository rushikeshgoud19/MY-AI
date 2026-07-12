# ✨ Mizune — a companion with a brain in the cloud and hands on your devices

> *Tsundere anime idol. Personal secretary. Distributed agent runtime.*
> She calls exactly one person "Master" — and she actually gets things done.

Mizune is not a chatbot. She is a **24/7 autonomous companion** whose brain runs on an
Azure VM, whose voice lives in your browser, whose hands reach your laptop and your
WhatsApp — and whose memory of what actually happened is checked against reality.

```
                            ┌──────────────────────────────┐
                            │        ☁️  CLOUD BRAIN        │
                            │   FastAPI · port 8001 (VM)   │
                            │                              │
     WhatsApp ◄──Baileys──► │  processor ─► AI cascade     │ ◄──WS──► Voice UI /
     (text-only,            │  Groq→Gemini→OpenRouter→NVIDIA│          Agentic OS
      loop-proof)           │      │            │          │          (her real
                            │  memory tree   scheduler     │          edge-tts voice)
     Gmail ◄──poll────────► │  (L0→L1→L2     (IST-aware    │
                            │   seal+recall)  cron+one-shot)│ ◄──WS──► Device nodes
     Obsidian vault ◄─sync─ │  subconscious  [TOOL RESULTS]│          laptop ✓ phone ⏳
     (idempotent)           │  (gated ticks)  truth seals  │
                            └──────────────────────────────┘
```

---

## What she does

| | |
|---|---|
| 💬 **WhatsApp secretary** | Chats in persona, learns contact tiers (VIP/family/stranger), rate-limits, debounces, chunks long replies at 4k, understands voice notes (STT), replies in text. Loop-proof: she never answers her own echoes. |
| 🌅 **Morning briefing** | Every day at 8:00 AM IST she compiles weather (Open-Meteo), today's scheduled tasks, important unread email, important WhatsApp — deterministically — and messages you a warm in-persona summary. |
| ⏰ **Scheduled actions** | "In an hour, do X" — she schedules it, and at fire time she *does* it (tools included). Stored code executes deterministically, never re-typed by the model. All times in **your** timezone. |
| 🖥️ **Device-node execution** | Your laptop runs a thin agent connected outbound to the cloud brain. From WhatsApp: *"install Blender on my laptop"* → it happens. Phone node is next. |
| 🧠 **Memory that seals truth** | Three-layer memory tree (episodic → summary → sealed) + ChromaDB semantic recall on every message (token-capped). Tool outcomes are sealed as `[TOOL RESULTS]` — the *final* result, not her intention. |
| 🔍 **Honesty systems** | Seal rows double as a lie detector: if she claims she scheduled/did something, the seals are ground truth. Failed scheduled tasks get an honest *"Master, that task hit a problem: …"* instead of optimistic fiction. |
| 🌙 **Gated subconscious** | Background ticks only wake the LLM when something is actionable, never repeat the same ping within 2h, and respect quiet hours (23:00–08:00 IST) unless urgent. |
| 🎙️ **Real voice** | Browser voice UI (cosmic core) + Agentic OS dashboard tab. Speech-in via Web Speech API (Chrome/Edge), speech-out is her **actual** `ja-JP-Nanami` edge-tts voice streamed over WebSocket — not the robotic browser voice. |
| 📓 **Obsidian vault** | Daily logs, contacts, topics, skills and sealed memories sync into a personal knowledge vault — idempotently (re-sync never duplicates). |
| 🛠️ **Self-extension** | She writes and registers her own skills (`create_skill`), tracks success rates, and distills repeated wins into reusable plugins. |
| 👁️ **Screen vision** | Ask her to look at your screen: she analyzes what you're working on, catches bugs, and coaches out loud (local mode). |

## The numbers (measured, not vibes)

Production TraceRoot data, before → after the optimization pass:

| Metric | Before | After |
|--------|--------|-------|
| Typical reply | 17s+ | **~2s** |
| Average response | 18.2s | **6.3s** |
| Median prompt size | 8,309 tokens | **~5,000** (hard-capped history) |
| Worst prompt spike | 45,216 tokens | impossible (4k ceiling) |
| Reply failure storms | 11% of traces | cascade fallback, zero user-facing |

## Architecture in one breath

`main.py` → `server.py` (FastAPI :8001) → `server/` package. The **VM** runs the same
package under `backend_main.py` (xvfb). One `/ws` WebSocket carries chat, status,
emotion biometrics, her voice audio (base64 MP3), and device-node registration.
The AI cascade (`server/model_router.py` + `server/ai.py`) falls through
Groq → Gemini → OpenRouter → NVIDIA with 10s timeouts, zero same-provider retries,
side-effect dedup, and a single `_clean_final_text()` on every return path.
Tools execute once, seal their outcome, and the sealer (`memory_worker`) cascades
memories L0→L1→L2. The scheduler (`server/scheduler.py`) evaluates cron in
**Asia/Kolkata** (`mizune_now()` — the canonical clock for everything user-facing).

## Run her

```bash
# 1. Configure (never committed)
cp config.example.json config.json     # add your API keys
#    .env for TraceRoot etc.

# 2. Local brain
python main.py                          # FastAPI on :8001

# 3. Voice UI
#    http://localhost:8001/ui/voice.html   (Chrome/Edge for mic)

# 4. WhatsApp bridge (Baileys) starts with the core; scan the QR once.

# 5. Laptop as her hands (optional)
start_device_agent.bat                  # registers as a device node
```

**Cloud deploy** (Azure VM): push to `feature/mobile-app`, then on the VM:
clone to `/tmp` → `cp server/ public/` over home → restart `backend_main.py`.
`config.json`/`.env` never leave the machine (gitignored); patch VM config in place.

## Project map

```
server/           the brain — processor, ai cascade, memory, scheduler, briefing,
                  subconscious, platforms/ (whatsapp, gmail, android), tts, vault sync
character/        SOUL.md — her personality (tsundere; only Matt may call her "Mio")
public/           voice UI (voice.html/css/js) + dashboard assets
skills → .data/   her self-written skill plugins (active/staging/archive)
agents/           ManagerAgent intent routing (LIVE — do not "clean up")
mizune-android/   Kotlin companion app (WS client, TTS, wake word) — phone node WIP
device_agent.py   laptop node: download/open/run on Mizune's command
legacy/           retired code kept for reference
docs/MIZUNE_HANDOFF.md   the multi-agent work ledger (Claude plans, executors build)
```

## House rules (learned the hard way)

- **Every user-facing time goes through `mizune_now()`** — the VM clock is UTC, Master is IST.
- **Scheduled code never round-trips through the model** — models truncate quote-heavy code in tool JSON.
- **Only Ollama returns unexecuted tools** to the processor; every other provider executes inline and returns `[]` — anything else double-fires actions.
- **`msg.is_self` needs a wake word** — she runs on Master's number; her own echoes must never trigger replies.
- **The seal never lies** — when her words and `[TOOL RESULTS]` disagree, trust the seal.

## Roadmap

- 📱 **Phase D — phone as her second body**: the Android app registers as a device node
  (`notify / open_url / speak`); briefings land as phone notifications.
- 🔭 Operator console: device fleet panel, cortex graph, trace viewer in Agentic OS.
- 🗣️ Telegram adapter (deferred by choice — WhatsApp is home).

---

*Built by Rushikesh ([@rushikeshgoud19](https://github.com/rushikeshgoud19)) with a
multi-agent workshop: Claude plans and reviews, executors grind, the handoff file
remembers. Mizune herself was consulted; she pretended not to care. (She cared.)*
