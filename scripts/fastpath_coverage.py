#!/usr/bin/env python
"""Which of Mizune's capabilities are GUARANTEED, and which depend on a model deciding?

THE FINDING THIS GENERALISES (2026-07-28, scripts/mistral_ablation.py, 378 calls):
`message_whatsapp` fired 97% of the time and `schedule_task` only 69%, on the same provider,
same prompt, same session. The difference was not the model. `message_whatsapp` had a
deterministic PRE-LLM fast-path in processor.py and `schedule_task` did not. Rule #4 —
anything that MUST happen gets a fast-path; the model narrates.

So the useful question is not "is mistral good at tools", it is: WHICH capabilities can still
silently not happen? This script answers that from the code, with no API calls.

⚠️ THE DISTINCTION THAT MATTERS, because it already fooled us once:
  - FAST_TRACK_TOOLS (server/ai.py) only skips the SECOND LLM round AFTER the model has
    already chosen to call the tool. It does NOT make the model choose it. schedule_task was
    in that list the whole time it was failing 31% of requests.
  - A PRE-LLM FAST-PATH in processor.py parses Master's text and acts in CODE before any
    model is consulted. That is the one that converts "usually" into "always".
Counting the first as coverage is how a capability looks protected while silently failing.

    .venv\\Scripts\\python.exe scripts/fastpath_coverage.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from server.ai import TOOLS_SCHEMA  # noqa: E402

# Tools that CHANGE THE WORLD. A read-only tool that silently doesn't run is a bad answer;
# a side-effecting tool that silently doesn't run is a lie about work that never happened.
# That is the whole difference, and it decides what deserves a fast-path.
SIDE_EFFECTING = {
    "schedule_task", "message_whatsapp", "open_app", "close_app", "execute_python",
    "run_command", "remote_device_command", "play_music", "control_music", "notify_master",
    "google_workspace", "start_mission", "cancel_mission", "execute_skill", "learn",
    "index_files", "night_shift", "add_core_directive", "find_my_phone", "install_app",
    "download_file",
}

# Pre-LLM fast-paths that exist in processor.py today, mapped to the tool each guarantees.
# Keyed by a marker string that must be present in the file, so this table cannot quietly
# claim coverage that was deleted.
#
# ⚠️ THE FIRST VERSION OF THIS TABLE WAS WRONG, and wrong in the direction that matters least
# but embarrasses most: it omitted the night_shift fast-path (processor.py:767) and reported a
# protected capability as UNPROTECTED. A hand-maintained list of what the code contains is the
# same drift bug this file exists to warn about. So the table is now CROSS-CHECKED against
# every `fast-path` log marker actually present in processor.py, and any marker the table does
# not explain is reported loudly rather than silently ignored.
PRE_LLM_FASTPATHS = {
    "_parse_reminder_command": "schedule_task",
    "_parse_whatsapp_send_command": "message_whatsapp",
    "_handle_scheduled_whatsapp_send": "message_whatsapp",
    "WA_SEND": "message_whatsapp",
    "[SHIFT] fast-path": "night_shift",
    "[MISSION] fast-path trigger": "start_mission",
    "[KNOWLEDGE] fast-path learn": "learn",
    # Added 2026-07-31. The cross-check below caught this one as unexplained the moment the
    # fast-path landed and this table had not been updated — which is the whole point of it.
    "_parse_music_command": "play_music",
    "[MUSIC] fast-path": "control_music",
    # Read-only introspection ("what model are you using") — no tool, but it IS a pre-LLM
    # path, so the cross-check below demands it be declared. Caught unlisted twice now.
    "[MODEL] fast-path": None,
    "[SLASH] handled": None,
    "_format_mesh_reply": "mesh",
    "MIZUNE_BUILD_LOG": "build_log",
}


def main() -> int:
    proc = open(os.path.join(ROOT, "server", "processor.py"), encoding="utf-8").read()
    ai_src = open(os.path.join(ROOT, "server", "ai.py"), encoding="utf-8").read()

    # FAST_TRACK_TOOLS is a local literal duplicated in two functions. Parse it rather than
    # importing, and FLAG the duplication: two copies of a list is how they drift apart.
    ft_matches = re.findall(r"FAST_TRACK_TOOLS = \[(.*?)\]", ai_src, re.S)
    fast_track = set()
    for m in ft_matches:
        fast_track |= set(re.findall(r'"([^"]+)"', m))
    dup_warning = ""
    if len(ft_matches) > 1:
        variants = {tuple(sorted(re.findall(r'"([^"]+)"', m))) for m in ft_matches}
        dup_warning = (f"FAST_TRACK_TOOLS is defined {len(ft_matches)}x in ai.py — "
                       + ("IDENTICAL for now, but two copies drift."
                          if len(variants) == 1 else
                          "THE COPIES ALREADY DISAGREE."))

    covered = set()
    missing_markers = []
    for marker, tool in PRE_LLM_FASTPATHS.items():
        if marker in proc:
            covered.add(tool)
        else:
            missing_markers.append(marker)

    # CROSS-CHECK against reality: every `[X] fast-path` log line in processor.py must be
    # explained by the table above. An unexplained one means a real fast-path exists that this
    # report is calling UNPROTECTED — which is how the first version of this script got
    # night_shift wrong. Under-reporting coverage sends you off building something that is
    # already there.
    actual = set(re.findall(r'log_info\(f?"\[([A-Z_]+)\] fast-path', proc))
    explained = {m.split("]")[0].lstrip("[") for m in PRE_LLM_FASTPATHS if m.startswith("[")}
    explained |= {"WHATSAPP", "REMINDER", "MESH"}   # covered via function-name markers above
    unexplained = sorted(actual - explained)

    rows = []
    for t in TOOLS_SCHEMA:
        fn = t.get("function", {})
        name = fn.get("name")
        if not name:
            continue
        rows.append({
            "tool": name,
            "side_effect": name in SIDE_EFFECTING,
            "pre_llm": name in covered,
            "fast_track_only": name in fast_track and name not in covered,
        })

    print(f"tools: {len(rows)}   pre-LLM fast-paths: {len(covered)}   "
          f"FAST_TRACK_TOOLS entries: {len(fast_track)}")
    if dup_warning:
        print(f"WARN: {dup_warning}")
    if missing_markers:
        print(f"ABORT-WORTHY: markers not found in processor.py: {missing_markers}")
    if unexplained:
        print(f"ABORT-WORTHY: processor.py has fast-paths this table does not explain: "
              f"{unexplained} -- coverage below UNDER-reports, fix the table first.")
    print()

    hdr = f"{'TOOL':<26} {'CHANGES WORLD':<14} {'PRE-LLM':<9} {'fast-track only':<16} RISK"
    print(hdr)
    print("-" * len(hdr))

    risk = []
    for r in sorted(rows, key=lambda x: (not x["side_effect"], x["tool"])):
        if r["side_effect"] and not r["pre_llm"]:
            verdict = "** UNPROTECTED"
            risk.append(r["tool"])
        elif r["side_effect"]:
            verdict = "guaranteed"
        else:
            verdict = "read-only"
        print(f"{r['tool']:<26} {'yes' if r['side_effect'] else '-':<14} "
              f"{'yes' if r['pre_llm'] else '-':<9} "
              f"{'yes' if r['fast_track_only'] else '-':<16} {verdict}")

    print()
    print("=" * 78)
    print(f"RISK LIST — side-effecting, NO pre-LLM fast-path ({len(risk)}):")
    print("=" * 78)
    for t in risk:
        note = "  (in FAST_TRACK_TOOLS, which does NOT help it get chosen)" \
            if t in fast_track else ""
        print(f"  - {t}{note}")
    print()
    print("These are the capabilities that can still silently not happen. schedule_task was on")
    print("this list at 69% until a pre-LLM fast-path moved it off. Rank by how often Rushi")
    print("actually asks for each, then measure the top few before building anything.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
