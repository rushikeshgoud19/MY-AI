# MIZUNE — session brief

Paste this whole file as the first message of a fresh session. It is self-contained.

---

## What you are working on

**Mizune** is Rushikesh's ("Master", "Rushi") self-hosted AI assistant, running 24/7 on a
single 896 MB Azure VM. She has a WebSocket brain, a WhatsApp bridge, a Gmail poller, an
Android app, a four-model debate engine, a memory tree, and a scheduler. There is also a
local operator console, **Claude OS**, that watches her.

The previous session spent itself on one theme: **she looked broken in ways that were
never about missing features.** Every bug found was a claim that did not match reality —
a tool call deleted in silence, a refusal counted as success, a fact stored as its own
error message. Assume that shape when you hunt.

---

## Hard rules — read before touching anything

1. **NEVER run gradle. Rushi builds every APK himself in Android Studio.** Write Kotlin
   and exact build/verify steps; you cannot compile-check Kotlin in-session. Review diffs
   by reading.
2. **The live phone app is `mizune-android/`** (native Kotlin + Compose, `com.mizune.app`).
   `android/` is a dead Capacitor scaffold — ignore it entirely.
3. **The VM is `azureuser@40.123.215.32`.** SSH works from Rushi's machine with the key
   already in `~/.ssh`. Health: `curl -s http://localhost:8001/health`.
4. **Deploy = copy `server/*.py` up, then restart.** The VM's entry file is
   `/home/azureuser/backend_main.py`, which is **NOT** part of the `server/` copy and must
   be mirrored by hand when an endpoint or startup hook changes.
5. **Several VM files are root-owned** (`server/ai.py`, `server/processor.py`,
   `backend_main.py`, `config.json`). `scp` to `/tmp/` then `sudo cp` into place.
6. **The restart that actually survives an ssh disconnect** — the only one that works:

       sudo bash -c 'cd /home/azureuser && setsid nohup /usr/bin/xvfb-run -a \
         /home/azureuser/venv311/bin/python -u backend_main.py >> server.log 2>&1 </dev/null &'

   `xvfb-run` is at `/usr/bin`, not in the venv. Then wait for health before testing.
7. **Never import a heavy `server.*` module on the VM to test something.** It pulls torch
   and ChromaDB and gets OOM-killed at 896 MB. Query the sqlite files directly instead.
8. **Windows console is cp1252.** Any script you run locally must print ASCII only.
9. **`config.json` is gitignored and holds live keys.** Never commit it; scan diffs before
   pushing, `MY-AI` is a public repo.

---

## Where things are

| | |
|---|---|
| Repo (server + phone) | `C:\Users\rushi\OneDrive\Desktop\my Ai` → `github.com/rushikeshgoud19/MY-AI`, branch `feature/mobile-app` |
| Console | `C:\Users\rushi\.claude\agentic-os` → `github.com/rushikeshgoud19/claude-os` (**private**) |
| VM | `/home/azureuser/` — `backend_main.py` + `server/` package + `.data/*.db` |
| Console URL | `http://127.0.0.1:4517` (`node server.js`, zero deps) |
| Feature probe | `scripts/probe_features.py` — run it, it talks to the live VM over the socket |
| Wayfinder maps | `.scratch/hands-free-voice/` (voice) and `.scratch/harness-level/` (architecture) |
| Feature audit | `docs/FEATURE_MATRIX.md` (stale — 2026-07-27) |
| Roadmap | `docs/MIZUNE_NEXT.md` |

---

## Verified working right now

Run `python scripts/probe_features.py` to confirm before trusting any of this.

- Chat: **0 errors across 13 consecutive turns**. Was 1 in 5.
- `web_search` returns live data (weather, company lookups).
- Reminders schedule in ~1.8 s. **8 cron jobs all firing on time** — morning briefing,
  evening digest, nightly review, bug report, night shift, build logs.
- **Auto-learn**: state a fact casually, she recalls it in a later turn without being
  told to remember. Secrets are refused honestly and never stored.
- Fast-paths answer deterministically: capabilities **1.0 s**, self-stats **0.7 s**.
- Console: seal feed and cron timeline live (40 seals, 68 jobs); deep links work.
- Sync is healthy: **13,776 WhatsApp messages, 759 emails**, both minutes-fresh.

---

## What the last session fixed — do not re-investigate

21 commits on `MY-AI` (`a1dbd9e..1ba13ca`) and 4 on `claude-os`.

**Her brain**
- **Turn ownership.** `broadcast_sync` stamps every frame with the client whose turn
  produced it (`turn_origin` ContextVar). The phone's old 90-second timer is now a
  fallback. Frames from cron/subconscious/WhatsApp carry `origin: "system"`.
- **`[SKIP]` was being spoken.** It only suppressed a reply when nothing remained after
  stripping the tag, so `"[SKIP] Nothing urgent, Master."` fell through. `[ACT]` and
  `[ESCALATE]` were never stripped at all.
- **Text-mode tool calls were deleted in silence.** `_clean_final_text` strips from the
  first `{"tool":` to end-of-string; recovery was gated on the reply cleaning to *empty*,
  so any chatty preamble meant the call was discarded. This is why the "background check
  on Autter" request was never answered.
- **Provider routing rebuilt on measurement.** Groq decommissioned
  `llama-3.3-70b-versatile`; Cerebras hit 402 and its key was retired. WhatsApp was
  hard-pinned to groq, which 413s on every full turn.
- **Knowledge retrieval.** The LIKE fallback used the whole question as one pattern (0
  matches, ever) and sat behind `if not rows:` which Chroma always filled. `learn()`
  stored the distiller's refusals *as the knowledge*.
- **Four sqlite connection leaks**, one of them `with con:` being a transaction context
  manager rather than a closing one.
- **Capability + self-stats fast-paths**, because a model asked to report a COUNT will
  eventually invent one.

**Architecture**
- `server/harness.py` — a seam registry (declare / provide / require). `require()` raises
  rather than degrading. The orchestra is wired through it and prints its capability
  graph at boot. Published as `stepproof/seams.py` too.
- `orchestra.llm` has a fallback chain (mistral → nvidia → cerebras) and says so in the
  receipt when a backup served.

**The phone** — all written, **none of it ever run on a device.**

**The console** — harness merged into the orchestra view as a second lane; a TDZ crash
that broke *all* data loading on any hash URL; panels frozen on "loading…"; `/api/seals`
and `/api/crons` built; stale-asset serving.

---

## Open work, ranked

**1. Build the APK. This is the biggest single gap.**
Ten phone fixes plus dispatcher containment are committed and have **never run on a
device**. The old voice templates on disk are still poisoned — the fix does not clean them
retroactively, so he **must recalibrate** after installing. Then:

    adb logcat -c && adb logcat -s MizuneService:D WakeWord:D MizuneWS:D

Expect `BUILD_STAMP: 2026-08-17-harness-pass-1`, `SCORE quiet rms=…` in a silent room, and
a subconscious tick arriving as `origin=system` with the phone staying silent for it.
`WAKE_SCORE_FIRE = 16.0` came from a python lab and has **never been measured on his
phone** — the new `SCORE` log makes the threshold arithmetic rather than a guess.

**2. The tool schema is 4,674 tokens — half her prompt, every turn.**
Static floor is ~7,415 tokens before any history; requests land at 9,297–9,386. Intent
filtering is the only lever big enough, and it risks the false-refusal bug
`_capability_lines` exists to prevent. **Measure before building** — a previous attempt to
blame tool *count* was disproved in ten minutes (0/5 at 3, 10, 20 and 34 tools; the real
variable was wording).

**3. She has one skill.** `create_skill` / `execute_skill` are built, sealed and audited,
and `skills/` contains only `music_discovery.py`. She should be writing a skill when she
does the same shaped work twice.

**4. Decisions only Rushi can make** — do not settle these alone:
- `ADOPT_MIN_SCORE = 9.0`: zero ADOPTs across every debate on record, so every one pays
  11 calls. Lower it, or accept the cost deliberately.
- The harness exists twice: `stepproof/seams.py` (published, tested) and
  `server/harness.py` (live). stepproof is zero-dep so Mizune could import it.
- `claude-os` is private; `public/avatars/` holds anime art, which is why.

---

## Gotchas that cost the last session real time

- **Writing `\b` into a non-raw Python string puts a literal BACKSPACE byte in your
  regex**, and it then matches nothing. Same class as the literal-`\n` bug the handoff doc
  records fixing in four files. Prefer heredocs to `python -c` string surgery.
- **Shell redirects gone wrong create zero-byte junk files** named things like
  `` `R2`) `` and `resolve({`. Six were removed. Check `git status` before committing.
- **The console cached `app.js` for three debugging rounds.** Fixed with `no-store`, but
  if a change seems not to apply, verify the served bytes.
- **`&&` after a failing `py_compile` silently skips your `scp`** while a later `;` still
  restarts the server — you can end up "deploying" the previous file.
- **Two `orchestra.db` files exist**: hers on the VM (22 debates) and the local one the
  console shows (257). Don't conflate them.

---

## How to verify anything

    python scripts/probe_features.py          # 8 checks against the live VM

Its own rule, inherited from `FEATURE_MATRIX.md`: **a feature passes only when evidence
proves it. Mizune saying it worked is never evidence.** The probe gave a false PASS once
by keyword-matching a refusal — score on frame types, tool executions and DB rows, not on
her prose.

---

## Suggested opening move

Ask Rushi whether he has built the APK. If yes, work item 1 — it unblocks a whole category
and three fixes are queued behind that one action. If not, take item 2 and **measure the
prompt composition before changing anything**.
