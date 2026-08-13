# Mizune — what to build next

Written 2026-08-09, after a session that read the phone app end to end, read the server
package, and deployed to the VM. Every number in the "Ground truth" section was measured
during that session, not recalled.

This document resolves the open question in
[`.scratch/hands-free-voice/tickets/09-the-feature-slate.md`](../.scratch/hands-free-voice/tickets/09-the-feature-slate.md):
*which capabilities earn a place, in what order, and what is the test for saying no?*

It deliberately does **not** re-derive two things that are already researched and correct:

- What Android 14 permits on a locked phone — [`05-FINDINGS.md`](../.scratch/hands-free-voice/tickets/05-FINDINGS.md).
- How production assistants handle wake words, speaker ID, arbitration and unprompted
  speech — [`VOICE-ARCHITECTURE-RESEARCH.md`](../.scratch/hands-free-voice/VOICE-ARCHITECTURE-RESEARCH.md).

Read those first if you're picking this up cold. This document assumes them.

---

## 1. Ground truth, measured

### The VM

| Fact | Value | Why it matters |
|---|---|---|
| RAM | **896 MB total, ~163 MB available** | This is the ceiling on everything. An attempt to import her own module set a second time was **OOM-killed** during this session. |
| CPU | 2 vCPU | Fine for I/O, hopeless for inference. |
| Disk | 29 GB, 13 GB free — `venv311` alone is **8.1 GB** | Not urgent, but no room for model weights. |
| Uptime | 8 days | The process is stable when left alone. |
| Tool surface | **36 tools, all wired** (checked each name for a real dispatch site, not just a schema entry) | The tool layer is genuinely built. This is not where the gaps are. |
| Skills | **1** (`music_discovery.py`) | `create_skill` / `execute_skill` exist and almost nothing uses them. |

### The phone

12 capabilities advertised, each with a real executor branch and a runtime precondition
(`DeviceCapabilities.kt` enforces that by construction — good design, keep it):

`notify` · `speak` · `open_url` · `open_app` · `tap` · `type` · `press` · `scroll` ·
`read_screen` · `media_play` · `media_pause` · `media_next`

Permissions currently held: `RECORD_AUDIO`, `CAMERA`, `INTERNET`, `VIBRATE`,
`POST_NOTIFICATIONS`, `SYSTEM_ALERT_WINDOW`, `QUERY_ALL_PACKAGES`,
`RECEIVE_BOOT_COMPLETED`, `FOREGROUND_SERVICE{,_DATA_SYNC,_MICROPHONE}`,
`ACCESS_NETWORK_STATE`.

**Not held** — and every one of these gates a candidate feature below:
`WAKE_LOCK` · `REQUEST_IGNORE_BATTERY_OPTIMIZATIONS` ·
`BIND_NOTIFICATION_LISTENER_SERVICE` · location · `READ_PHONE_STATE` ·
`BLUETOOTH_CONNECT`.

### Feature health

[`FEATURE_MATRIX.md`](FEATURE_MATRIX.md) (2026-07-27): **12 PASS · 1 FLAKY · 1 UNVERIFIABLE**.
It is now ~2 weeks stale and predates every change made this session.

Its central finding still holds and should govern this plan:

> **The binding constraint is the token budget, not the code.** The scheduler's failures
> were capability refusals produced when all 4 Groq keys hit their cap and the cascade
> dropped to a weaker model. The feature is correct; the fuel is not.

---

## 2. The three constraints that decide everything

Any feature proposal that ignores one of these is a wishlist item, not a plan.

**C1 — Token budget is the scarcest resource.** Free tiers, no credit card. Every
feature that calls the LLM competes with her ability to answer Rushi. The orchestra
costs **~11 calls and ~11,000 tokens per debate**; the subconscious used to burn ~8,300
input tokens per tick to answer `[SKIP]`. Adding load degrades what already works.

**C2 — The VM has ~163 MB of headroom.** No local models. No embedding server. No
Whisper. No second Python process. Anything "on-device" must mean *on the phone*, or it
must mean a free API.

**C3 — The fragile middle of the phone chain is waking/unlocking/launching**, not
hearing or speaking. `05-FINDINGS` established this: a plain service cannot turn the
screen on, and background activity launch is blocked without `SYSTEM_ALERT_WINDOW` or
the actual Assistant role — and OxygenOS can override even that.

---

## 3. The test for saying no

From the map's destination, sharpened:

> **Does it make her more useful without touching the phone — and does it cost less than
> it returns, in tokens and in trust?**

Three ways to fail it:

1. **Screen-required.** If it only works with the app open, it is a website with extra
   steps.
2. **Token-negative.** If it burns budget that her answers need, it makes her worse
   overall even when the feature itself works.
3. **Trust-negative.** Anything that speaks, buzzes, or reads private content without
   being asked. Both Alexa and Google Assistant document the same rule: *non-intrusive
   signal first, spoken content only on request.* Mizune violated this for months.

---

## 4. Phase 0 — finish what is already built (do this first)

Nothing here is a new feature. Every item is something that already exists and is
either unproven or half-wired. This is the highest-return work available and it costs
almost no tokens.

| # | Item | Why | Effort |
|---|---|---|---|
| 0.1 | **Build the APK and recalibrate.** | Ten phone fixes are written and unverified. The old voice templates on disk are still poisoned — the fix does not clean them retroactively. Nothing else on the phone can be judged until this happens. | Rushi, 10 min |
| 0.2 | **Re-run `scripts/feature_audit.py`.** | The matrix predates the turn-ownership deploy, the `[SKIP]` fix and the orchestra ship. Planning against a 2-week-old audit is how the `proactive.py` mistake happened. | 1 run |
| 0.3 | **Settle `ADOPT_MIN_SCORE`.** | 6 debates in `orchestra.db`, **0 ADOPTs** — every one took the expensive R2 path at 11 calls. Three were genuinely split; three scored `agreement=HIGH` and *still* went to R2. If 9.0 is unreachable in practice, the cheap path is dead code and every debate costs double. Lower it, or accept the cost deliberately. | 1 decision + a soak |
| 0.4 | **Wire `peek_due_soon`, or delete the branch.** | `CronManager` has no such method, so the subconscious's scheduled-task awareness has *never once* contributed an item. Memory backlog is the only thing that has ever populated a situation report. | 30 lines |
| 0.5 | **Use the skills system.** | `create_skill` / `execute_skill` are built, sealed and audited — and there is exactly **one** skill. Either she starts writing skills for repeated work, or the subsystem is decoration. | Behavioural, not code |
| 0.6 | **Cap `tts_cache` and `server.log`.** | 42 MB and 8.5 MB, both unbounded, on a box with 13 GB free and no log rotation. Slow-moving, but it is the kind of thing that takes her down at 3 a.m. | Small |

---

## 5. Phone slate — ranked, with the cut line

Each item is judged against the test in §3. "Perm" names the new grant required.

### Ship

**P1 — Battery / charging / DND awareness.** *Perm: none.*
The cheapest trust win available. She should not speak at 3 a.m., should not fire TTS
when the phone is face-down, and should throttle the listener below ~15% battery. No new
permission, no LLM cost, directly reduces the "annoying" failure mode that has dominated
this whole effort. It also gives ticket 04 (battery budget) something real to measure.
*Hands-free: pass. Token cost: zero.*

**P2 — `WAKE_LOCK` + battery-optimisation exemption.** *Perm: `WAKE_LOCK`,
`REQUEST_IGNORE_BATTERY_OPTIMIZATIONS`.*
Not a feature — the missing floor under the always-on listener. `05-FINDINGS` flagged the
exemption as "likely justified"; the app does not request it, and OxygenOS's battery
manager is documented as the biggest real-world risk to keeping the mic FGS alive. Until
this exists, every wake-word measurement is confounded by "did the OS just kill it?"
*Hands-free: pass. Prerequisite for judging P5.*

**P3 — Follow-up turns without re-waking.** *Perm: none.*
After she answers, keep the command window open for a few seconds so "and the weather?"
works. This is the single biggest jump in *feeling* like an assistant per line of code,
and the mic is already open. Needs the false-fire rate to be known first (0.1).
*Hands-free: pass. Token cost: normal turn.*

**P4 — Telephony state → go quiet during calls.** *Perm: `READ_PHONE_STATE`.*
Small, obvious, prevents an embarrassing failure. Also lets the listener release the mic
instead of fighting the call for it.
*Hands-free: pass.*

**P5 — Notification listening, allowlisted.** *Perm: `BIND_NOTIFICATION_LISTENER_SERVICE`.*
The richest context source on the phone — and the highest-trust grant in this document.
Ships **only** with: an explicit package allowlist (never banking, health, or messaging
bodies), on-device filtering before anything leaves the phone, and a visible kill switch
in the same place the accessibility toggle lives. This is the item most likely to be
regretted if rushed; it is above the line because the context is genuinely
transformative, not because it is easy.
*Hands-free: pass. Trust: needs the guardrails, not just the permission.*

### Cut line — everything below is explicitly not being built now

**P6 — Geofence / "remind me when I get home".** *Perm: location, background location.*
Background location is the most scrutinised permission on Android and the payoff is one
reminder pattern. Revisit only if P1–P5 land and Rushi asks for it by name.

**P7 — Floating bubble overlay (Jarvis-style).** *Perm: already held.*
Fails the hands-free test outright: it is a thing you look at. Cool, not useful in a
pocket.

**P8 — Direct Share / app shortcuts.** Screen-required. Same failure.

**P9 — Song-by-name while locked.** `05-FINDINGS` documents Spotify failing exactly this
case when the screen is off, with no confirmation YouTube Music honours the intent at
all. Best-effort at most; do not build a feature on it.

**P10 — Proactive speech on the phone.** Both Alexa and Google document the opposite
policy, and this codebase has months of evidence for why. The standing rule stays:
**visible, never audible, unless he woke her.**

---

## 6. VM slate — ranked

**V1 — Make the token budget visible.** *No new load.*
C1 says the budget decides everything, and there is currently no way to see it without
grepping a log. A `/api/budget` endpoint plus a line in the dashboard showing per-provider
headroom turns the binding constraint from folklore into a number. Everything below is
easier to judge once this exists.

**V2 — Route by cost, not just by availability.** *Saves load.*
The cascade currently falls back when a provider is exhausted. It should *start* cheap
for cheap work — a `[SKIP]` decision, an intent classification and a four-model debate
should not draw from the same pool. The subconscious already proved the pattern: a
deterministic gate before the LLM removed ~90% of its traffic.

**V3 — Second-stage wake verification on the VM.** *Small load, big trust win.*
`VOICE-ARCHITECTURE-RESEARCH` §1: every production assistant runs a cheap loose detector
on-device and a stricter verifier before acting. Mizune has the on-device half and a
`/api/voice/verify` endpoint that the acoustic path **does not call**. Wiring it closes
the loop the industry says is the answer to false accepts — and it lets the on-device
threshold stay generous without the phone acting on garbage.
*Depends on 0.1 (need the real score distribution first).*

**V4 — Retire `[ACT]` into real background work.** *Neutral.*
The subconscious can already decide `[ACT]`, but the useful version — she notices
something, does it silently, and it is waiting when he asks — needs the skills system
(0.5) and the scheduler (0.4) actually carrying load. This is the payoff item for Phase 0.

**V5 — Grounding quality.** *Small load.*
Two of three observed debates ran thin, one saying in its own answer "no verified source
confirms these rates". The marginalia timeout fix helped latency; it did not make the
sources better. Worth a look **after** V1, because better grounding costs tokens.

### Not now

- **Local models / embeddings on the VM.** C2 forbids it. 163 MB.
- **A second VM or paid tier.** No credit card ([`free-infra` memory](../.scratch/)).
  Any plan that starts "just move it to…" is not a plan.
- **Rewriting the wake engine (openWakeWord).** It is vendored and ready, but the DTW
  path has never been measured with clean templates. Measure first; ticket 10 stays open.

---

## 7. Sequencing

```
0.1 build + recalibrate  ──┬──> real score distribution ──> threshold is arithmetic
                           │                                  └──> V3 second-stage verify
                           └──> P2 wake-lock floor ──> P1 battery/DND ──> P3 follow-up turns
0.2 re-audit ──> 0.3 ADOPT decision ──> V1 budget visibility ──> V2 cost routing
                                                                    └──> V5 grounding
0.4 + 0.5 (scheduler + skills carrying load) ──> V4 real background work
```

Two things gate almost everything: **the APK build** on the phone side, and **budget
visibility** on the VM side.

---

## 8. Questions only Rushi can answer

1. **`ADOPT_MIN_SCORE`** — is a 2× cost per debate acceptable for the quality 9.0 buys?
   Six debates, zero adopts, is the data.
2. **Notification access (P5)** — is he willing to grant it, given the allowlist and kill
   switch? If not, it drops below the line and P3 becomes the top phone item.
3. **The orchestra's place** — is it for hard questions he explicitly invokes
   (`orchestra:`), or should the auto-triage promote questions on its own? Currently both
   paths exist; only the explicit one has been verified working.
4. **Skills** — should she be *told* to write a skill when she repeats work, or should
   that stay opportunistic? 0.5 is a behaviour decision, not a code one.

---

## 9. What this plan is betting on

That the reason Mizune has felt unreliable is **not** a shortage of features. She has 36
working tools, 12 phone capabilities, memory, missions, a night shift, a scheduler, a
debate engine and a voice. What she has lacked is:

- a way to tell her own turn from somebody else's (fixed this session),
- a wake word that fires on the right thing (fixed, unverified),
- a way to see the fuel gauge (V1, not built),
- and the discipline to not speak unless spoken to (fixed this session, in three places).

Phase 0 is deliberately unglamorous for that reason. The next visible jump in how good
she feels comes from P1–P3 and V1–V2, none of which is a new capability — all four are
about her using what she already has at the right moment.
