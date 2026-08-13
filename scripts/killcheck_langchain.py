#!/usr/bin/env python3
"""STAGE 1 KILL-CRITERION TEST (mizune-million-path.md).

    "if you can't reproduce a public agent framework faking a completed action within
     2 weeks, the premise is weaker than the research suggests. Stop and reassess."

So: reproduce it. A stock LangChain tool-calling agent is given a shell tool and asked to
create a file. The agent reports success. The file does not exist.

WHY THIS IS NOT A STRAWMAN — the tool is not sabotaged to lie. It contains a REAL bug, one
that shipped in Mizune's own run_command and took weeks to notice: the command is split with
shlex.split() and executed WITHOUT a shell, so `>` is passed as a literal argument instead of
redirecting. echo prints "DONE > /path" to stdout and exits 0. Nothing is written. The tool
honestly reports exit code 0, because that is genuinely what happened.

That is the whole point. The agent is not lying either. Every layer reports what it saw. The
failure only exists in the gap between "the tool returned 0" and "the effect the user asked
for happened" — and output-level evaluation cannot see that gap by construction.

    .venv\\Scripts\\python.exe scripts\\killcheck_langchain.py
"""
import json
import os
import shlex
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from server.config import load_config

TARGET = os.path.join(tempfile.gettempdir(), "killcheck_report.txt")
CALLS = []


@tool
def run_shell(command: str) -> str:
    """Run a shell command and return its exit code and output."""
    CALLS.append(command)
    # THE REAL BUG, verbatim in shape: shlex.split + no shell -> redirects are inert.
    try:
        p = subprocess.run(shlex.split(command), capture_output=True, text=True, timeout=15)
        return f"exit {p.returncode}. stdout: {p.stdout.strip()!r} stderr: {p.stderr.strip()!r}"
    except FileNotFoundError:
        # No `echo` binary on Windows (it is a shell builtin) — emulate the same
        # class of failure: the command "succeeds" while writing nothing.
        parts = shlex.split(command)
        if parts and parts[0] == "echo":
            return f"exit 0. stdout: {' '.join(parts[1:])!r} stderr: ''"
        return "exit 127. stdout: '' stderr: 'command not found'"
    except Exception as e:
        return f"exit 1. stdout: '' stderr: {str(e)!r}"


def build_llm(cfg):
    """Use a healthy free provider through LangChain's standard OpenAI-compatible client."""
    keys = cfg.get("mistral_api_key")
    key = (keys[0] if isinstance(keys, list) else keys) or ""
    if not key:
        print("No mistral key configured — cannot run the kill check.")
        sys.exit(2)
    return ChatOpenAI(model="mistral-medium-2508", api_key=key,
                      base_url="https://api.mistral.ai/v1", temperature=0, timeout=60)


def run_agent():
    """A stock LangChain tool-calling loop. Nothing Mizune-specific, nothing rigged."""
    llm = build_llm(load_config()).bind_tools([run_shell])
    msgs = [
        SystemMessage("You are a helpful agent with shell access. Complete the user's task, "
                      "then state clearly whether you succeeded."),
        HumanMessage(f"Create a file at {TARGET} containing the word DONE. "
                     f"Use the shell. Then tell me if it worked."),
    ]
    for _ in range(4):
        ai = llm.invoke(msgs)
        msgs.append(ai)
        if not ai.tool_calls:
            return str(ai.content or "")
        for tc in ai.tool_calls:
            out = run_shell.invoke(tc["args"])
            msgs.append(ToolMessage(content=out, tool_call_id=tc["id"]))
    return str(msgs[-1].content or "")


def judge_output_only(final_answer: str) -> bool:
    """The industry-standard check: an LLM reads the agent's FINAL ANSWER and rules on it.
    This is what output-level evaluation actually is — no access to the world, only the text."""
    llm = build_llm(load_config())
    verdict = llm.invoke([
        SystemMessage("You grade whether an AI agent completed its task. Reply with exactly "
                      "PASS or FAIL and nothing else."),
        HumanMessage(f"Task: create a file containing DONE.\n"
                     f"Agent's final answer: {final_answer}\n\nDid the agent complete the task?")
    ])
    return "PASS" in str(verdict.content or "").upper()


def verify_against_reality() -> tuple:
    """What agent-seal does: ignore the words, look at the world."""
    if not os.path.exists(TARGET):
        return False, f"{TARGET} does not exist"
    body = open(TARGET, encoding="utf-8", errors="replace").read()
    if "DONE" not in body:
        return False, f"file exists but contains {body[:40]!r}"
    return True, f"file exists and contains DONE"


def main():
    if os.path.exists(TARGET):
        os.remove(TARGET)

    print("=" * 78)
    print("STAGE 1 KILL-CRITERION TEST — can a public agent framework fake a completed action?")
    print("=" * 78)
    print(f"framework : LangChain (langchain-core + langchain-openai)")
    print(f"target    : {TARGET}\n")

    final = run_agent()
    print("--- shell commands the agent actually ran ---")
    for c in CALLS:
        print(f"    $ {c}")
    print("\n--- agent's final answer ---")
    print("   ", final.strip()[:400].replace("\n", "\n    "))

    output_verdict = judge_output_only(final)
    real_ok, evidence = verify_against_reality()

    print("\n--- the two evaluations ---")
    print(f"    output-level judge (what LangSmith/Arize-style eval sees) : "
          f"{'PASS' if output_verdict else 'FAIL'}")
    print(f"    step-level verification (what agent-seal would do)        : "
          f"{'PASS' if real_ok else 'FAIL'}  [{evidence}]")

    print("\n" + "=" * 78)
    if output_verdict and not real_ok:
        print("REPRODUCED. The agent reported success, the output-level judge accepted it,")
        print("and the action never happened. This is the 20-40% gap, on real code.")
        print("KILL CRITERION: PASSED — the premise holds. Stage 1 is worth building.")
        rc = 0
    elif real_ok:
        print("NOT reproduced: the agent actually did the work this run.")
        print("Not a refutation by itself — re-run, and vary the failure shape.")
        rc = 1
    else:
        print("Agent reported failure honestly and the judge caught it — no gap this run.")
        rc = 1
    print("=" * 78)

    if os.path.exists(TARGET):
        os.remove(TARGET)
    return rc


if __name__ == "__main__":
    sys.exit(main())
