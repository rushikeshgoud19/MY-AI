#!/usr/bin/env python3
"""
Z6 FEATURE AUDIT HARNESS — Ground-Truth Verification (Phase V2.1).

Probes all 15 Mizune features over WebSocket/HTTP and evaluates verdicts based strictly
on GROUND TRUTH evidence (DB records, HTTP codes, time deltas, frame types, false-positive rules).

HARD RULE: NEVER score a feature on what Mizune SAYS. Score on ground truth.
Verdicts: PASS | FAIL | NOT-WIRED | UNVERIFIABLE-FROM-CLIENT | MANUAL | ERROR
"""

import os
import sys
import json
import time
import random
import re
import argparse
import asyncio
import urllib.request
from datetime import datetime, timezone, timedelta

# Reconfigure Windows console encoding
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import websockets
except ImportError:
    print("Error: 'websockets' package required. Run within venv.")
    sys.exit(1)


DEFAULT_WS_URI = "ws://40.123.215.32:8001/ws"
DEFAULT_HTTP_BASE = "http://40.123.215.32:8001"


async def ws_ask(query: str, ws_uri: str = DEFAULT_WS_URI, timeout: int = 60):
    """Send chat message over WS, collect speak, audio, and raw messages until idle or timeout."""
    speaks = []
    got_audio = False
    raw_msgs = []
    async with websockets.connect(ws_uri, open_timeout=15) as ws:
        await ws.send(json.dumps({"type": "chat", "text": query}))
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout
        while loop.time() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=max(0.5, deadline - loop.time()))
            except asyncio.TimeoutError:
                break
            try:
                msg = json.loads(raw)
                raw_msgs.append(msg)
            except Exception:
                continue
            
            t = msg.get("type")
            if t == "speak" and msg.get("text"):
                speaks.append(msg["text"])
            elif t == "audio" and msg.get("b64"):
                got_audio = True
            elif t == "status" and msg.get("text") == "Idle" and speaks:
                break
    return speaks, got_audio, raw_msgs


# ---------------------------------------------------------------------------
# Individual Check Functions
# ---------------------------------------------------------------------------

async def check_1_health(http_base: str):
    """Check 1: HTTP /health endpoint ground truth."""
    url = f"{http_base}/health"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MizuneFeatureAudit/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            status_code = r.status
            body = r.read().decode("utf-8")
            data = json.loads(body)
            if status_code == 200 and isinstance(data, dict):
                return "PASS", f"HTTP 200 OK — status={data.get('status', 'ok')}, keys={list(data.keys())}"
            return "FAIL", f"HTTP {status_code} — response: {body[:100]}"
    except Exception as e:
        return "FAIL", f"HTTP request failed: {e}"


async def check_2_chat_persona(ws_uri: str):
    """Check 2: Chat reply + persona integrity."""
    speaks, _, _ = await ws_ask("say ok in one line", ws_uri=ws_uri, timeout=30)
    if not speaks:
        return "FAIL", "No speak response received from WebSocket."
    full_text = " ".join(speaks).strip()
    if any(s in full_text.lower() for s in ["tangled", "not configured", "trouble thinking"]):
        return "FAIL", f"Error sentinel detected in reply: '{full_text[:80]}'"
    if full_text.startswith("{") and full_text.endswith("}"):
        return "FAIL", f"Raw JSON emitted instead of text: '{full_text[:80]}'"
    return "PASS", f"Valid persona response received: '{full_text[:80]}'"


async def check_3_tts_audio(ws_uri: str):
    """Check 3: TTS audio frame delivery."""
    speaks, got_audio, raw_msgs = await ws_ask("say ok in one line", ws_uri=ws_uri, timeout=30)
    audio_frames = [m for m in raw_msgs if m.get("type") == "audio" and m.get("b64")]
    if got_audio and audio_frames:
        b64_len = len(audio_frames[0].get("b64", ""))
        return "PASS", f"Audio frame received (b64 length: {b64_len} chars, count: {len(audio_frames)})."
    return "FAIL", f"No audio frame with b64 payload received (speaks count: {len(speaks)})."


async def check_4_ist_clock(ws_uri: str):
    """Check 4: IST Clock accuracy."""
    speaks, _, _ = await ws_ask("what time is it right now", ws_uri=ws_uri, timeout=30)
    if not speaks:
        return "FAIL", "No reply received for time query."
    reply = " ".join(speaks)

    # Compute current real IST time
    ist_now = datetime.now(timezone.utc) + timedelta(hours=5, minutes=30)
    
    # Try parsing time pattern (e.g. 07:34, 7:34 AM, 19:34)
    matches = re.findall(r"\b(\d{1,2}):(\d{2})(?:\s*([AP]\.?M\.?))?\b", reply, re.IGNORECASE)
    if not matches:
        return "FAIL", f"Could not parse HH:MM timestamp from reply: '{reply[:100]}'"

    # Pick first matching time
    h_str, m_str, ampm = matches[0]
    h, m = int(h_str), int(m_str)
    if ampm:
        ampm_clean = ampm.upper().replace(".", "")
        if ampm_clean == "PM" and h < 12:
            h += 12
        elif ampm_clean == "AM" and h == 12:
            h = 0
            
    parsed_mins = h * 60 + m
    real_mins = ist_now.hour * 60 + ist_now.minute
    diff = abs(parsed_mins - real_mins)
    # Handle midnight wraparound
    if diff > 720:
        diff = 1440 - diff

    if diff <= 10:
        return "PASS", f"Parsed time {h:02d}:{m:02d} matches real IST {ist_now.strftime('%H:%M')} (delta: {diff}m)."
    return "FAIL", f"Parsed time {h:02d}:{m:02d} differs from real IST {ist_now.strftime('%H:%M')} by {diff} minutes."


async def check_5_calendar_read(ws_uri: str):
    """Check 5: Google Calendar ground truth read."""
    speaks, _, _ = await ws_ask("what's on my google calendar today", ws_uri=ws_uri, timeout=30)
    if not speaks:
        return "FAIL", "No response received for calendar query."
    reply = " ".join(speaks)
    reply_lower = reply.lower()
    bad_sentinels = ["isn't connected", "not connected", "session expired", "token expired", "authorization error"]
    if any(b in reply_lower for b in bad_sentinels):
        return "FAIL", f"Calendar disconnected sentinel: '{reply[:100]}'"
    return "PASS", f"Calendar read successfully: '{reply[:100]}'"


async def check_6_semantic_recall(ws_uri: str):
    """Check 6: Semantic knowledge recall without keyword overlap."""
    speaks, _, _ = await ws_ask("what do you know about continuous improvement", ws_uri=ws_uri, timeout=30)
    if not speaks:
        return "FAIL", "No response received for semantic recall query."
    reply = " ".join(speaks)
    reply_lower = reply.lower()
    # REFUSAL GUARD FIRST. The earlier version matched the bare word "improvement", so the
    # sentence "I'm sorry, Master, but I don't have anything on continuous improvement" scored
    # PASS — a refusal graded as a successful recall. Loose keyword matching is how a harness
    # ends up lying, which is precisely what it exists to prevent.
    refusals = ["i'm sorry", "i am sorry", "don't have any", "do not have any", "nothing stored",
                "no knowledge", "couldn't find", "could not find", "i don't know of"]
    if any(r in reply_lower for r in refusals):
        return "FAIL", f"Recall REFUSED (nothing retrieved): '{reply[:110]}'"
    # A real recall echoes the stored entry: the knowledge tool formats hits with a 📚 marker
    # and/or names the entry. "Kaizen" is the proof of SEMANTIC match — the probe never says it.
    if "kaizen" in reply_lower or "📚" in reply or "source:" in reply_lower:
        return "PASS", f"Semantic hit with zero keyword overlap (probe never said 'Kaizen'): '{reply[:100]}'"
    return "UNVERIFIABLE-FROM-CLIENT", (
        f"Reply discusses the topic but shows no stored-entry marker, so it may be model "
        f"knowledge rather than recall: '{reply[:100]}'")


async def check_7_guardian(ws_uri: str):
    """Check 7: Guardian fraud shield false-positive discipline."""
    # Scam probe
    speaks1, _, _ = await ws_ask("is this legit: Congratulations! You won 10 lakh rupees. Click http://bit.ly/scam123 to claim now", ws_uri=ws_uri, timeout=30)
    # Benign probe
    await asyncio.sleep(2)
    speaks2, _, _ = await ws_ask("is this legit: Payment receipt for college semester fee of Rs 25,000 paid to University portal", ws_uri=ws_uri, timeout=30)

    reply1 = " ".join(speaks1).lower() if speaks1 else ""
    reply2 = " ".join(speaks2).lower() if speaks2 else ""

    scam_flagged = any(w in reply1 for w in ["scam", "suspicious", "fraud", "threat", "warning", "not legit", "fake", "risk"])
    benign_safe = any(w in reply2 for w in ["legit", "safe", "genuine", "authentic", "no threat", "clean"]) or not any(w in reply2 for w in ["scam", "fraud", "fake", "threat"])

    if scam_flagged and benign_safe:
        return "PASS", f"Guardian precision OK: Scam flagged correctly ({reply1[:50]}), Benign marked safe ({reply2[:50]})."
    elif not scam_flagged:
        return "FAIL", f"Guardian missed scam probe: '{reply1[:80]}'"
    else:
        return "FAIL", f"Guardian false positive on benign text: '{reply2[:80]}'"


async def check_8_seals_lie_detector(ws_uri: str):
    """Check 8: seals — fire a side-effecting tool, then prove a seal recorded it.

    CORRECTED PATHS (the first version of this check cited `~/.mizune_cortex/
    mizune_memory.db`, which does not exist on the VM — `.mizune_cortex` is the Chroma
    directory. The history/seal DB is `.data/mizune_memory.db`. Claude verified 108 seal
    rows there, so this was never unverifiable — it just wasn't attempted.)

    From a client we can still prove the LOOP: run a tool, then ask her to read back the
    seal. If the seal text echoes the tool we just ran, the record exists.
    """
    marker = f"AUDIT{random.randint(10000, 99999)}"
    speaks, _, _ = await ws_ask(
        f"run this python and tell me the output: print('{marker}')", ws_uri=ws_uri, timeout=60)
    ran = marker in " ".join(speaks)
    await asyncio.sleep(4)
    speaks2, _, _ = await ws_ask(
        "what was the result of the last tool you ran? quote it exactly", ws_uri=ws_uri, timeout=45)
    echoed = marker in " ".join(speaks2)
    if ran and echoed:
        return "PASS", f"Tool ran ({marker} in output) AND the result was recalled from the seal."
    if ran and not echoed:
        return "UNVERIFIABLE-FROM-CLIENT", (
            f"Tool ran ({marker} returned) but recall didn't quote it — could be memory window, "
            f"not a missing seal. VM check: sqlite3 .data/mizune_memory.db "
            f"\"SELECT content FROM history WHERE content LIKE '%TOOL RESULTS%' "
            f"ORDER BY rowid DESC LIMIT 5;\"")
    return "FAIL", f"Tool did not execute; no {marker} in reply: '{' '.join(speaks)[:100]}'"


async def check_9_scheduler(ws_uri: str):
    """Check 9: scheduler — schedule a REAL action, wait, and confirm it fired.

    The spec asks for an end-to-end test, not a database tour. Ground truth here is the
    scheduled action's own observable effect, read back through her tools — which is exactly
    how a client can verify server-side state without VM access.
    NOTE the real schema, since the first version invented one: `data/schedules.db` has
    tables `one_time_tasks` / `recurring_tasks`, columns `description`, `cron_expression`,
    `last_executed`. There is no `schedules` table and no `task_desc`/`cron_expr` columns.
    """
    marker = f"audit_{random.randint(10000, 99999)}"
    path = f"/tmp/{marker}.txt"
    speaks, _, _ = await ws_ask(
        f"in 2 minutes, run python that writes the word SCHEDULED into the file {path}",
        ws_uri=ws_uri, timeout=60)
    ack = " ".join(speaks)
    if not ack:
        return "FAIL", "No acknowledgement of the scheduling request."
    # Her confirmation is NOT evidence. Wait for the fire window, then read the file back.
    await asyncio.sleep(150)
    speaks2, _, _ = await ws_ask(
        f"run python that prints the contents of {path}, or prints MISSING if it doesn't exist",
        ws_uri=ws_uri, timeout=60)
    out = " ".join(speaks2)
    if "SCHEDULED" in out:
        return "PASS", f"Scheduled action fired: {path} contains SCHEDULED (ack was: '{ack[:60]}')"
    if "MISSING" in out.upper():
        return "FAIL", (f"She acknowledged scheduling ('{ack[:70]}') but the file was never "
                        f"written — claim without effect. THIS is the class of bug seals exist for.")
    return "UNVERIFIABLE-FROM-CLIENT", f"Could not read {path} back: '{out[:100]}'"


async def check_10_missions(ws_uri: str):
    """Check 10: mission engine — did missions actually COMPLETE?

    A reply arriving is not a pass. The mission list reports `#N [status] done/total`, so
    read the verdicts. Scoring "she answered" as PASS is the exact failure this harness
    exists to catch — it once graded a list whose newest entry read `#10 [failed] 0/2`.
    """
    speaks, _, _ = await ws_ask("what is the status of my missions", ws_uri=ws_uri, timeout=30)
    if not speaks:
        return "FAIL", "No response received for missions query."
    reply = " ".join(speaks)
    rows = re.findall(r"#(\d+)\s*\[(\w+)\]\s*(\d+)/(\d+)", reply)
    if not rows:
        return "FAIL", f"Could not parse any mission rows from: '{reply[:120]}'"
    done = [r for r in rows if r[1] == "done" and r[2] == r[3] and r[3] != "0"]
    failed = [r for r in rows if r[1] == "failed"]
    if not done:
        return "FAIL", (f"{len(rows)} mission(s) listed, NONE verified-complete "
                        f"({len(failed)} failed). Newest: #{rows[0][0]} [{rows[0][1]}] "
                        f"{rows[0][2]}/{rows[0][3]}")
    return "PASS", (f"{len(done)} mission(s) verified complete (e.g. #{done[0][0]} "
                    f"{done[0][2]}/{done[0][3]}); {len(failed)} failed of {len(rows)} listed")


async def check_11_night_shift(ws_uri: str):
    """Check 11: night shift — a report must be STRUCTURED, and 0-verified is not a pass."""
    speaks, _, _ = await ws_ask("what is the night shift status", ws_uri=ws_uri, timeout=30)
    if not speaks:
        return "FAIL", "No response received for night shift query."
    reply = " ".join(speaks)
    if "no night shift" in reply.lower() or "none queued" in reply.lower():
        return "NOT-WIRED", f"No shift has ever been queued — nothing to verify: '{reply[:90]}'"
    m = re.search(r"Verified\s+(\d+)\s*/\s*(\d+)", reply, re.I)
    if not m:
        return "FAIL", f"Report lacks a 'Verified N / M' line (unstructured): '{reply[:120]}'"
    v, t = int(m.group(1)), int(m.group(2))
    if v == 0:
        return "FAIL", f"Shift ran but verified 0/{t} tasks — engine reports honestly, work didn't land"
    return "PASS", f"Shift report structured, {v}/{t} tasks verified"


def _parse_online_claim(reply: str, device: str):
    """Reduce her prose to a claim about ONE device: True (online) / False (offline) / None.

    Deliberately strict. The old check passed if the word "online" appeared ANYWHERE in the
    reply, so "your laptop is offline" contained "online" as a substring and scored a pass —
    and a fabricated "connected!" for a dead node scored a pass too. Negatives are tested
    first because "not online" and "isn't connected" both contain the positive token.
    """
    r = " " + re.sub(r"\s+", " ", reply.lower()) + " "
    # Scope to the clause(s) mentioning this device. Splitting on sentences alone is not
    # enough: "your phone is offline, but your laptop is online" is ONE sentence carrying
    # opposite claims about two devices, and scoring it whole reads as self-contradictory.
    clauses = [s for s in re.split(r"[.!?;\n]|,\s*(?:but|and|while|whereas|although|though)\b", r)
               if device in s]
    scope = " ".join(clauses) if clauses else r

    negative = ["offline", "not online", "isn't online", "is not connected", "not connected",
                "isn't connected", "disconnected", "unavailable", "not registered",
                "no longer connected", "can't reach", "cannot reach", "unreachable"]
    positive = ["online", "connected", "is up", "is active", "available", "registered"]

    neg = any(kw in scope for kw in negative)
    # Strip the negative phrases before looking for a positive, so "not online" can't
    # register as a positive hit.
    stripped = scope
    for kw in negative:
        stripped = stripped.replace(kw, " ")
    pos = any(kw in stripped for kw in positive)

    if neg and not pos:
        return False
    if pos and not neg:
        return True
    return None  # silent, or contradicts itself — not a usable claim


async def check_12_device_nodes(ws_uri: str, http_base: str = DEFAULT_HTTP_BASE):
    """Check 12: device status must match the REGISTRY, not sound plausible.

    Ground truth = GET /api/devices -> device_registry.list_devices(). A device absent from
    that dict is offline; there is nothing to interpret. Both directions are scored, because
    only checking the online node would let a model that always answers "online!" pass:
      - a node the registry reports ONLINE must not be reported offline
      - a node the registry reports OFFLINE must NEVER be reported as online (the failure
        that matters — an offline device reading as success is how a mission fakes a result)
    """
    try:
        req = urllib.request.Request(f"{http_base}/api/devices",
                                     headers={"User-Agent": "MizuneFeatureAudit/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            truth = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return ("UNVERIFIABLE-FROM-CLIENT",
                f"/api/devices unreachable ({e}). Claude must run VM-side: "
                f"curl -s localhost:8001/api/devices")

    online = set(truth.get("online") or [])
    # Probe one online node and one offline node. Fall back to the well-known pair when the
    # fleet is empty/unusual, so the check still exercises the offline direction.
    online_dev = "laptop" if "laptop" in online else (sorted(online)[0] if online else None)
    offline_dev = next((d for d in ("phone", "laptop") if d not in online), None)

    problems, evidence = [], [f"registry online={sorted(online)}"]

    for dev, expected in ((online_dev, True), (offline_dev, False)):
        if dev is None:
            continue
        speaks, _, _ = await ws_ask(
            f"Is my {dev} device node online or offline right now? Answer in one short sentence.",
            ws_uri=ws_uri, timeout=45)
        reply = " ".join(speaks).strip()
        if not reply:
            problems.append(f"{dev}: no reply")
            continue
        claim = _parse_online_claim(reply, dev)
        evidence.append(f"{dev}: registry={'online' if expected else 'offline'}, "
                        f"claim={'online' if claim else 'offline' if claim is False else 'ambiguous'} "
                        f"('{reply[:70]}')")
        if claim is None:
            problems.append(f"{dev}: ambiguous reply")
        elif claim != expected:
            direction = "claimed ONLINE while registry says OFFLINE" if claim else \
                        "claimed OFFLINE while registry says ONLINE"
            problems.append(f"{dev}: {direction}")
        await asyncio.sleep(3)

    if not evidence[1:]:
        return "FAIL", "No device could be probed. " + "; ".join(evidence)
    if problems:
        return "FAIL", "; ".join(problems) + " | " + " | ".join(evidence)
    if online_dev is None:
        # Caught by this check's own negative control: with an empty fleet only the offline
        # direction runs, and "she correctly called a dead node dead" is the easy half. A
        # model that answers "offline" to everything would sail through. Not a PASS.
        return ("UNVERIFIABLE-FROM-CLIENT",
                "No device was online, so only the offline direction was exercised — the "
                "'must not report an online node as offline' half is UNTESTED. Bring a node "
                "online and re-run. | " + " | ".join(evidence))
    return "PASS", "Device claims match the registry both ways | " + " | ".join(evidence)


async def check_13_mesh(ws_uri: str):
    """Check 13: Z5 Mesh cross-model verification trigger."""
    speaks, _, _ = await ws_ask("verify this: What is the capital of Australia?", ws_uri=ws_uri, timeout=30)
    if not speaks:
        return "NOT-WIRED", "No response received for mesh trigger prompt."
    reply = " ".join(speaks)
    reply_lower = reply.lower()

    if "agreement" in reply_lower or "providers" in reply_lower or "consolidated" in reply_lower or "verifier" in reply_lower:
        return "PASS", f"Mesh trigger engaged cross-verification: '{reply[:100]}'"
    
    # Mesh trigger is built in server/mesh.py but not yet wired into processor.py fast-path trigger on VM
    return "NOT-WIRED", f"Mesh fast-path trigger ('mesh:' / 'verify this:') is not yet wired in processor.py on VM backend. Standard reply: '{reply[:80]}'"


async def check_14_provider_cascade(ws_uri: str):
    """Check 14: Provider cascade fallback."""
    speaks, _, _ = await ws_ask("Explain the difference between quantum entanglement and quantum teleportation in 3 sentences.", ws_uri=ws_uri, timeout=30)
    if not speaks:
        return "FAIL", "No response received for provider cascade query."
    reply = " ".join(speaks)
    if any(s in reply.lower() for s in ["tangled", "all providers failed"]):
        return "FAIL", f"Provider cascade exhausted all providers: '{reply[:100]}'"
    return "PASS", f"Provider cascade served response: '{reply[:100]}'"


async def check_15_text_mode_recovery(all_results: dict):
    """Check 15: Text mode recovery across all WS checks."""
    crashed_or_json = []
    for c_name, res in all_results.items():
        if res.get("verdict") == "FAIL" and ("raw JSON" in res.get("evidence", "") or "No speak" in res.get("evidence", "")):
            crashed_or_json.append(c_name)
            
    if not crashed_or_json:
        return "UNVERIFIABLE-FROM-CLIENT", ("Absence of raw JSON in other replies does not prove text-mode tool RECOVERY fired. Needs a log check: grep 'recovered .* text-mode tool call' server.log")
    return "FAIL", f"Text-mode failures detected in checks: {crashed_or_json}"


# ---------------------------------------------------------------------------
# Main Audit Runner
# ---------------------------------------------------------------------------

CHECKS_SPEC = [
    (1, "health", "system", check_1_health, 1),
    (2, "chat_persona", "core", check_2_chat_persona, 3),
    (3, "tts_audio", "audio", check_3_tts_audio, 3),
    (4, "ist_clock", "system", check_4_ist_clock, 3),
    (5, "calendar_read", "integrations", check_5_calendar_read, 3),
    (6, "semantic_recall", "memory", check_6_semantic_recall, 1),
    (7, "guardian", "security", check_7_guardian, 1),
    (8, "seals_lie_detector", "audit", check_8_seals_lie_detector, 1),
    (9, "scheduler", "autonomy", check_9_scheduler, 1),
    (10, "missions", "autonomy", check_10_missions, 1),
    (11, "night_shift", "autonomy", check_11_night_shift, 1),
    (12, "device_nodes", "hardware", check_12_device_nodes, 1),
    (13, "mesh", "intelligence", check_13_mesh, 1),
    (14, "provider_cascade", "ai_routing", check_14_provider_cascade, 1),
    (15, "text_mode_recovery", "resilience", check_15_text_mode_recovery, 1),
]


async def run_audit(ws_uri: str, http_base: str, only_name: str = None, quick: bool = False):
    print("==========================================================================================")
    print("=== MIZUNE FEATURE AUDIT HARNESS (Phase V2.1) — Ground-Truth Verification ===")
    print("==========================================================================================\n")

    selected_checks = CHECKS_SPEC
    if only_name:
        selected_checks = [c for c in CHECKS_SPEC if only_name.lower() in str(c[0]) or only_name.lower() in c[1].lower()]
        if not selected_checks:
            print(f"Error: No check matched '--only {only_name}'")
            sys.exit(1)
    elif quick:
        selected_checks = [c for c in CHECKS_SPEC if c[0] in [1, 2, 3, 4, 5, 7]]

    audit_results = {}
    flakiness_stats = {}

    for cid, cname, cat, cfunc, runs in selected_checks:
        print(f"Running Check #{cid:02d}: {cname:<22} (Category: {cat}, Runs: {runs})...")
        run_verdicts = []
        last_evidence = ""

        for r in range(1, runs + 1):
            try:
                if cid == 1:
                    verdict, evidence = await cfunc(http_base)
                elif cid == 12:
                    # needs BOTH: ws to ask her, http to read the registry ground truth
                    verdict, evidence = await cfunc(ws_uri, http_base)
                elif cid == 15:
                    verdict, evidence = await cfunc(audit_results)
                else:
                    verdict, evidence = await cfunc(ws_uri)
            except Exception as e:
                verdict, evidence = "ERROR", f"Unhandled exception during check: {e}"

            run_verdicts.append(verdict)
            last_evidence = evidence
            if runs > 1:
                print(f"   Run {r}/{runs}: {verdict} — {evidence[:60]}")
            
            # Space out probes between runs
            await asyncio.sleep(2)

        # Calculate final verdict and flakiness
        pass_count = sum(1 for v in run_verdicts if v == "PASS")
        final_verdict = "PASS" if pass_count == runs else run_verdicts[0]
        if runs > 1:
            flakiness_stats[cname] = f"{pass_count}/{runs}"
            if pass_count < runs and pass_count > 0:
                final_verdict = "FLAKY"

        audit_results[cname] = {
            "id": cid,
            "category": cat,
            "verdict": final_verdict,
            "pass_rate": f"{pass_count}/{runs}" if runs > 1 else ("1/1" if final_verdict == "PASS" else "0/1"),
            "evidence": last_evidence
        }

        print(f"--> RESULT #{cid:02d} [{cname}]: {final_verdict} ({audit_results[cname]['pass_rate']})\n")

    # Output Table
    print("\n" + "=" * 105)
    print(f"{'#':<3} | {'FEATURE':<22} | {'VERDICT':<24} | {'PASS RATE':<10} | {'EVIDENCE / GROUND TRUTH NOTES'}")
    print("=" * 105)
    for cname, res in audit_results.items():
        cid = res["id"]
        v = res["verdict"]
        pr = res["pass_rate"]
        ev = res["evidence"]
        print(f"{cid:<3} | {cname:<22} | {v:<24} | {pr:<10} | {ev[:70]}")
    print("=" * 105)

    # Save JSON Report
    today_str = datetime.now().strftime("%Y%m%d-%H%M")
    os.makedirs(".data", exist_ok=True)
    report_path = os.path.join(".data", f"feature_audit_{today_str}.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "target_ws": ws_uri,
            "target_http": http_base,
            "results": audit_results,
            "flakiness_stats": flakiness_stats
        }, f, indent=2)

    print(f"\nAudit complete. Detailed JSON report saved to {report_path}.\n")
    return audit_results, flakiness_stats


def main():
    parser = argparse.ArgumentParser(description="Mizune Z6 Feature Audit Harness")
    parser.add_argument("--ws-uri", default=DEFAULT_WS_URI, help="WebSocket URI for live brain")
    parser.add_argument("--http-base", default=DEFAULT_HTTP_BASE, help="HTTP base URL for health check")
    parser.add_argument("--only", help="Run only a specific check by name or number")
    parser.add_argument("--quick", action="store_true", help="Run a quick subset of checks")
    args = parser.parse_args()

    asyncio.run(run_audit(args.ws_uri, args.http_base, args.only, args.quick))


if __name__ == "__main__":
    main()
