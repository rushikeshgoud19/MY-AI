"""Deterministic slash commands: /usage, /insights, /model, /status, /help.

WHY THESE ARE CODE AND NOT PROMPTS
Every number here is a fact about Mizune herself — which provider is answering, how many of
her tool calls actually ran, whether groq is capped. A model cannot introspect any of it: it
has no view of the router's decision or the databases, so asked directly it either declines or
invents something plausible. An invented usage figure is unfalsifiable in chat and Rushi would
act on it. So the model never touches these: code reads ground truth and formats the reply.

WHY THEY LIVE IN ONE PLACE
`process_command` is the single door for BOTH the WebSocket/desktop path and inbound WhatsApp,
so implementing here means `/usage` works from WhatsApp with no second implementation to drift.
The WhatsApp wrapper is stripped first — inbound text really arrives as
"[MESSAGE FROM MASTER RUSHI (via WhatsApp)]: /usage\n(SYSTEM: ...)", and a suite once passed
13/13 on bare text while the feature was broken in production.

MEMORY DISCIPLINE: the VM has 898MB of RAM and torch is blocked. Every read here is bounded —
log reads are tail-limited and DB queries are windowed and counted, never SELECT *.
"""
import os
import re
import sqlite3
from collections import Counter

from server.config import log_info, mizune_now

# The VM's server.log is small today but grows unboundedly between restarts. Reading it whole
# on a 898MB box is how you OOM her, so every log scan is capped.
_LOG_TAIL_BYTES = 400_000
_LOG_PATH_CANDIDATES = ("server.log", "../server.log", "/home/azureuser/server.log")


def _strip_wrapper(text: str) -> str:
    """Inbound WhatsApp arrives wrapped. Strip it before matching anything."""
    t = re.sub(r"^\s*\[[^\]]*\]\s*:\s*", "", text or "")
    return t.split("\n(SYSTEM:")[0].strip()


def _tail_log() -> str:
    for p in _LOG_PATH_CANDIDATES:
        try:
            if not os.path.exists(p):
                continue
            size = os.path.getsize(p)
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                if size > _LOG_TAIL_BYTES:
                    f.seek(size - _LOG_TAIL_BYTES)
                    f.readline()          # discard the partial first line
                return f.read()
        except Exception as e:
            log_info(f"[SLASH] log read failed for {p}: {e}")
    return ""


def _db(name: str):
    """Open a Mizune database if it exists here. Returns None rather than raising, because a
    missing db on the wrong host must degrade to 'unknown', never to a confident 0 — that is
    the false zero that made the build log report no work on a busy day."""
    for base in (".data", "data", "/home/azureuser/.data"):
        p = os.path.join(base, name)
        if os.path.exists(p):
            try:
                return sqlite3.connect(p)
            except Exception:
                return None
    return None


def _since(days: float) -> str:
    import datetime
    return (mizune_now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")


# ── /usage ────────────────────────────────────────────────────────────────────────────────
def cmd_usage(config: dict) -> str:
    lines = ["📊 USAGE — providers and fuel"]
    problems = []

    try:
        from server.model_catalog import list_models
        cat = list_models(config)
        cur = next((m for m in cat if m.get("is_current")), None)
        if cur:
            lines.append(f"Brain now: {cur['provider']} · {cur['model']} "
                         f"(tools {cur.get('tool_reliability') or '?'})")
        ok = [m for m in cat if m.get("available")]
        dead = [m for m in cat if not m.get("available")]
        lines.append(f"Available: {len(ok)}/{len(cat)} providers")
        for m in cat:
            mark = "->" if m.get("is_current") else "  "
            state = "live" if m.get("available") else (m.get("detail") or "unavailable")
            lines.append(f" {mark} {m['provider']:<11} tools {str(m.get('tool_reliability') or '?'):<12} {state}")
        # A provider with NO KEY is a deliberate choice, not a fault. openrouter was removed on
        # purpose (account never bought credits, every call 402'd), so flagging it as
        # "incomplete" every single time trains him to ignore the warning line — and then the
        # line stops working for the faults that matter.
        broken = [m for m in dead if m.get("keyed")]
        if broken:
            problems.append(f"{len(broken)} keyed provider(s) unavailable: "
                            + ", ".join(m["provider"] for m in broken))
    except Exception as e:
        problems.append(f"model catalog: {str(e)[:70]}")

    log = _tail_log()
    if log:
        picks = Counter(re.findall(r"\[ROUTER\] Selected provider: ([a-z]+)", log))
        caps = len(re.findall(r"rate_limit_exceeded", log))
        fails = Counter(re.findall(r"Provider '([a-z]+)' failed", log))
        if picks:
            lines.append("")
            lines.append("Recent routing (last log window):")
            for p, n in picks.most_common(6):
                f = fails.get(p, 0)
                lines.append(f"    {p:<11} {n:>4} call(s)" + (f"  ({f} failed)" if f else ""))
        lines.append(f"Rate-limit hits in window: {caps}")
        if caps > 20:
            lines.append("  ⚠ heavy capping — the token budget is the binding constraint again")
    else:
        problems.append("server.log not readable from here")

    if problems:
        lines.append("")
        lines.append("! incomplete: " + "; ".join(problems))
    return "\n".join(lines)


# ── /insights ─────────────────────────────────────────────────────────────────────────────
def cmd_insights(config: dict, days: float = 1.0) -> str:
    since = _since(days)
    lines = [f"🔎 INSIGHTS — last {days:g} day(s)"]
    problems = []

    c = _db("mizune_memory.db")
    if c:
        try:
            msgs = list(c.execute(
                "SELECT role, COUNT(*) FROM history WHERE timestamp >= ? GROUP BY role",
                (since,)))
            by_role = {r: n for r, n in msgs}
            n_user = by_role.get("user", 0)
            n_her = by_role.get("assistant", 0) + by_role.get("model", 0)
            lines.append(f"Messages: {n_user} from you, {n_her} from her")
            # A zero here is easy to misread as "she did nothing". It usually means the turns
            # were handled by a deterministic fast-path, which returns BEFORE the history
            # write — so /usage, /model, reminders, music and WhatsApp sends never appear as
            # messages even though work happened. Say so rather than let the number imply
            # idleness; the seal count below is the honest measure of activity.
            if n_user == 0 and n_her == 0:
                lines.append("  (no conversational turns recorded — fast-pathed commands "
                             "return before the history write, so they don't show up here)")

            seals = [r[0] for r in c.execute(
                "SELECT content FROM history WHERE content LIKE '%[TOOL RESULTS]%' "
                "AND timestamp >= ?", (since,))]
            tools = Counter()
            failed = 0
            for s in seals:
                m = re.search(r"\[TOOL RESULTS\]\s*([a-z_]+)", s)
                if m:
                    tools[m.group(1)] += 1
                if re.search(r"\b(error|failed|refused|not online|could not|couldn't)\b", s, re.I):
                    failed += 1
            lines.append(f"Tool calls: {len(seals)} sealed" +
                         (f", {failed} reported a problem" if failed else ", none failed"))
            if tools:
                lines.append("Most used:")
                for t, n in tools.most_common(6):
                    lines.append(f"    {t:<24} {n}")

            # Busiest hour, over the SAME rows the counts above describe. The first version
            # counted every history row (including system seals) and called them "messages",
            # so it printed "0 messages from you" and "busiest hour: 7 messages" in the same
            # report. Two numbers that contradict each other destroy trust in both.
            hrs = Counter(r[0][11:13] for r in c.execute(
                "SELECT timestamp FROM history WHERE timestamp >= ? "
                "AND role IN ('user','model','assistant')", (since,)) if r[0])
            if hrs:
                h, n = hrs.most_common(1)[0]
                lines.append(f"Busiest hour: {h}:00 ({n} conversational turns)")
            else:
                seal_hrs = Counter(r[0][11:13] for r in c.execute(
                    "SELECT timestamp FROM history WHERE timestamp >= ? AND role='system'",
                    (since,)) if r[0])
                if seal_hrs:
                    h, n = seal_hrs.most_common(1)[0]
                    lines.append(f"Busiest hour: {h}:00 ({n} tool seals)")
        except Exception as e:
            problems.append(f"memory db: {str(e)[:70]}")
        finally:
            c.close()
    else:
        problems.append("mizune_memory.db not found on this host")

    m = _db("missions.db")
    if m:
        try:
            done = list(m.execute(
                "SELECT COUNT(*) FROM missions WHERE status='done' AND updated_at >= ?",
                (since,)))[0][0]
            tot = list(m.execute(
                "SELECT COUNT(*) FROM missions WHERE updated_at >= ?", (since,)))[0][0]
            lines.append(f"Missions: {done}/{tot} completed")
        except Exception as e:
            problems.append(f"missions db: {str(e)[:70]}")
        finally:
            m.close()
    else:
        problems.append("missions.db not found on this host")

    s = _db("schedules.db")
    if s:
        try:
            pend = list(s.execute(
                "SELECT COUNT(*) FROM one_time_tasks WHERE executed = 0"))[0][0]
            rec = list(s.execute("SELECT COUNT(*) FROM recurring_tasks"))[0][0]
            lines.append(f"Scheduled: {pend} pending, {rec} recurring job(s)")
        except Exception as e:
            problems.append(f"schedules db: {str(e)[:70]}")
        finally:
            s.close()

    # A dead source is STATED. Silence and "zero" must never look the same — that is exactly
    # how the build log reported no work on a day full of it.
    if problems:
        lines.append("")
        lines.append("! incomplete (these numbers are not the whole picture): " + "; ".join(problems))
    return "\n".join(lines)


# ── /model ────────────────────────────────────────────────────────────────────────────────
def cmd_model(config: dict, target: str = "") -> str:
    from server.model_catalog import list_models
    cat = list_models(config)

    if not target:
        cur = next((m for m in cat if m.get("is_current")), None)
        out = [f"🧠 Brain: {cur['provider']} · {cur['model']} "
               f"(tools {cur.get('tool_reliability') or '?'})" if cur else "🧠 Brain: unknown"]
        out.append("Switch with:  /model <provider>")
        out.append("Available:")
        for m in cat:
            mark = "->" if m.get("is_current") else "  "
            out.append(f" {mark} {m['provider']:<11} tools {str(m.get('tool_reliability') or '?'):<12}"
                       f"{'live' if m.get('available') else 'unavailable'}")
        return "\n".join(out)

    want = target.strip().lower().split()[0]
    match = next((m for m in cat if m["provider"] == want), None)
    if not match:
        return (f"No provider called '{want}', Master. Options: "
                + ", ".join(m["provider"] for m in cat))
    if not match.get("available"):
        # Switching to a dead provider would make her mute. Refuse with the reason.
        # NOTE: the reason is built OUTSIDE the f-string. Implicit concatenation inside an
        # f-string expression needs Python 3.12 (PEP 701); this laptop has 3.12 and the VM
        # does not, so it compiled here and failed there. Keep f-string expressions simple.
        why = match.get("detail") or "no key / unreachable"
        return (f"'{want}' is not available right now ({why}), so I won't switch to it "
                f"and go mute, Master.")

    # WRITE, then READ BACK. Reporting success from the value we just tried to set is the
    # claim-without-effect shape this whole project exists to catch.
    cfg_path = "config.json"
    try:
        import json
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        cfg["ai_model"] = want
        if match.get("model"):
            cfg[f"{want}_model"] = match["model"]
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
        config["ai_model"] = want          # live process, so the change takes effect now
        if match.get("model"):
            config[f"{want}_model"] = match["model"]
    except Exception as e:
        return f"Couldn't write the config, Master: {str(e)[:120]}"

    confirmed = next((m for m in list_models(config) if m.get("is_current")), None)
    if not confirmed or confirmed["provider"] != want:
        return (f"I wrote the config but it did NOT take — still on "
                f"{confirmed['provider'] if confirmed else 'unknown'}. Something else is "
                f"overriding it, Master.")
    log_info(f"[SLASH] model switched to {want} · {confirmed['model']}")
    return (f"🧠 Switched to {confirmed['provider']} · {confirmed['model']} "
            f"(tools {confirmed.get('tool_reliability') or '?'}), Master.")


# ── /status ───────────────────────────────────────────────────────────────────────────────
def cmd_status(config: dict) -> str:
    lines = ["✅ STATUS"]
    try:
        from server.device_registry import device_registry
        devs = device_registry.list_devices()
        lines.append("Devices online: " + (", ".join(devs.keys()) if devs else "none"))
    except Exception as e:
        lines.append(f"Devices: unreadable ({str(e)[:50]})")

    s = _db("schedules.db")
    if s:
        try:
            rec = list(s.execute("SELECT description, cron_expression FROM recurring_tasks"))
            lines.append(f"Crons: {len(rec)} registered")
            for d, cr in rec[:8]:
                lines.append(f"    {d:<26} {cr}")
        except Exception:
            pass
        finally:
            s.close()

    try:
        from server.model_catalog import list_models
        cur = next((m for m in list_models(config) if m.get("is_current")), None)
        if cur:
            lines.append(f"Brain: {cur['provider']} · {cur['model']}")
    except Exception:
        pass
    return "\n".join(lines)


HELP = """🛠 COMMANDS (work here AND on WhatsApp)
/usage              which provider is answering, what's capped
/insights [days]    messages, tool calls, missions, busiest hour
/model              show the current brain
/model <provider>   switch it (refuses if that provider is down)
/status             devices, crons, brain
/help               this list"""


def handle_slash(text: str, config: dict):
    """Return a reply string, or None when this is not a slash command.

    Returning None rather than a guess is deliberate: anything unrecognised must fall through
    to the normal path, so adding commands here can never swallow ordinary conversation.
    """
    clean = _strip_wrapper(text)
    if not clean.startswith("/"):
        return None

    parts = clean[1:].split(None, 1)
    if not parts:
        return None
    cmd = parts[0].lower().strip()
    arg = parts[1].strip() if len(parts) > 1 else ""

    try:
        if cmd in ("help", "commands", "?"):
            return HELP
        if cmd == "usage":
            return cmd_usage(config)
        if cmd in ("insights", "insight"):
            days = 1.0
            m = re.search(r"(\d+(?:\.\d+)?)", arg)
            if m:
                days = max(0.1, min(90.0, float(m.group(1))))
            return cmd_insights(config, days)
        if cmd in ("model", "brain"):
            return cmd_model(config, arg)
        if cmd in ("status", "health"):
            return cmd_status(config)
    except Exception as e:
        log_info(f"[SLASH] /{cmd} failed: {e}")
        return f"That command broke, Master: {str(e)[:150]}"

    return None       # unknown slash -> let the normal path handle it
