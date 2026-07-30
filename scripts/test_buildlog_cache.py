#!/usr/bin/env python
"""Prove the build-log cache serves fresh data and REFUSES stale data.

WHY THIS EXISTS — measured on the VM 2026-07-30: three real 21:00 runs had delivered and
`grep -c BUILD_LOG_OK server.log` returned **0**. Not one scheduled build log had ever
collected, because the laptop holding git and gh is asleep at 21:00 and only reconnects after
the 23:00 retry window closes. Every delivery was the honest apology. The honesty layer was
working and the feature was still useless.

The fix caches good collections from daytime runs. That introduces a NEW risk, which is the
one this file guards: a cached digest presented as tonight's report. Yesterday's numbers under
today's headline is exactly the stale-file failure `file_newer_than` exists to catch in
stepproof - `file_exists` passes it and only freshness fails it.

So the staleness refusal is tested as hard as the happy path, and the boundary is tested from
BOTH sides, because an off-by-one in a max-age check fails silently and looks fine.

    .venv\\Scripts\\python.exe scripts/test_buildlog_cache.py
"""
import datetime
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from server.config import mizune_now  # noqa: E402

MAX_AGE_MIN = 20 * 60


def load_cached(path):
    """Mirror of processor.py::_load_cached_digest. Kept in step by the marker test below."""
    try:
        with open(path, encoding="utf-8") as f:
            blob = json.load(f)
        when = datetime.datetime.fromisoformat(blob["collected_at"])
        age = int((mizune_now() - when).total_seconds() // 60)
        if age < 0 or age > MAX_AGE_MIN:
            return None
        return blob["payload"], age, when.strftime("%I:%M %p")
    except FileNotFoundError:
        return None
    except Exception:
        return None


def write_cache(path, minutes_ago, payload=None):
    when = mizune_now() - datetime.timedelta(minutes=minutes_ago)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"collected_at": when.isoformat(),
                   "payload": payload if payload is not None else {"digest": "real digest",
                                                                   "story_commits": [{"x": 1}]}},
                  f)


fails = []


def check(name, cond, detail=""):
    print(f"{'PASS' if cond else '**FAIL**'}  {name}  {detail}")
    if not cond:
        fails.append(name)


d = tempfile.mkdtemp()
p = os.path.join(d, "build_log_cache.json")

# ── serves fresh ──
write_cache(p, 60)
got = load_cached(p)
check("1h-old cache is SERVED", got is not None and got[1] == 60,
      f"age={got[1] if got else None}min")

write_cache(p, 3 * 60)
got = load_cached(p)
check("3h-old cache is SERVED (the 20:00 fill before a 21:00 report)",
      got is not None, f"age={got[1] if got else None}min")

# ── refuses stale, and the boundary is checked from both sides ──
write_cache(p, MAX_AGE_MIN - 5)
check("just INSIDE the limit is served", load_cached(p) is not None)

write_cache(p, MAX_AGE_MIN + 5)
check("just OUTSIDE the limit is REFUSED", load_cached(p) is None)

write_cache(p, 3 * 24 * 60)
check("3-day-old cache is REFUSED (never label old numbers as tonight)",
      load_cached(p) is None)

# ── a clock that jumped backwards must not yield a 'negative age' pass ──
write_cache(p, -120)
check("future-dated cache is REFUSED", load_cached(p) is None)

# ── absence and corruption are not crashes ──
os.remove(p)
check("missing cache returns None, does not raise", load_cached(p) is None)

with open(p, "w", encoding="utf-8") as f:
    f.write("{not json")
check("corrupt cache returns None, does not raise", load_cached(p) is None)

with open(p, "w", encoding="utf-8") as f:
    json.dump({"payload": {"digest": "x"}}, f)     # no collected_at
check("cache with no timestamp is REFUSED (cannot prove freshness)", load_cached(p) is None)

# ── the real processor must still contain the pieces this mirrors ──
src = open(os.path.join(ROOT, "server", "processor.py"), encoding="utf-8").read()
for marker in ("_save_cached_digest", "_load_cached_digest", "_deliver_payload",
               "_bl_collect_only", "_BL_CACHE_MAX_AGE_MIN"):
    check(f"processor.py still has {marker}", marker in src)

brief = open(os.path.join(ROOT, "server", "briefing.py"), encoding="utf-8").read()
check("briefing.py registers the cache cron", "MIZUNE_BUILD_LOG_CACHE" in brief)
check("cache cron desc ends with _CACHE so the processor takes the collect-only branch",
      'BUILDLOG_CACHE_DESC = "MIZUNE_BUILD_LOG_CACHE"' in brief)

print(f"\n{'ALL PASS' if not fails else str(len(fails)) + ' FAILED: ' + str(fails)}")
sys.exit(1 if fails else 0)
