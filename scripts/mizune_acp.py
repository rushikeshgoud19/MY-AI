"""ACP adapter: lets Buzz talk to the real Mizune.

Speaks Agent Client Protocol (JSON-RPC 2.0 over stdio) to the client, and
forwards every user turn to Mizune's POST /chat endpoint. Because the turn
goes through her normal processor, her memory tree, persona and tools all
apply -- nothing is duplicated here.

Config via env vars:
    MIZUNE_URL      base URL of her backend (default http://localhost:8001)
    MIZUNE_API_KEY  sent as X-API-Key and Bearer token if /chat is protected
"""

import json
import os
import sys
import urllib.error
import urllib.request

MIZUNE_URL = os.environ.get("MIZUNE_URL", "http://localhost:8001").rstrip("/")
MIZUNE_API_KEY = os.environ.get("MIZUNE_API_KEY", "")
TIMEOUT = int(os.environ.get("MIZUNE_TIMEOUT", "120"))


def log(msg):
    # stdout is the protocol channel -- diagnostics must go to stderr
    print(f"[mizune-acp] {msg}", file=sys.stderr, flush=True)


def send(payload):
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def notify(method, params):
    send({"jsonrpc": "2.0", "method": method, "params": params})


def reply(req_id, result):
    send({"jsonrpc": "2.0", "id": req_id, "result": result})


def reply_error(req_id, code, message):
    send({"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}})


def ask_mizune(text):
    """POST the user's text to /chat and return her reply."""
    body = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        f"{MIZUNE_URL}/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    if MIZUNE_API_KEY:
        # the deployed backend's _require_key() checks this header against
        # CFG["dashboard_api_key"]; X-API-Key is the older local-only scheme
        req.add_header("X-Mizune-Key", MIZUNE_API_KEY)
        req.add_header("X-API-Key", MIZUNE_API_KEY)

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("response") or "(she went quiet, Master)"
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        log(f"HTTP {e.code} from /chat: {detail}")
        if e.code in (401, 403):
            return f"[/chat rejected the request ({e.code}) -- set MIZUNE_API_KEY]"
        return f"[/chat returned HTTP {e.code}: {detail}]"
    except urllib.error.URLError as e:
        log(f"cannot reach {MIZUNE_URL}: {e.reason}")
        return f"[can't reach Mizune at {MIZUNE_URL} -- is the backend running?]"


def extract_text(prompt_blocks):
    """Pull the text out of ACP content blocks, ignoring images/audio."""
    parts = []
    for block in prompt_blocks or []:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "\n".join(p for p in parts if p).strip()


def handle(msg):
    method = msg.get("method")
    req_id = msg.get("id")
    params = msg.get("params") or {}
    is_notification = req_id is None

    if method == "initialize":
        # echo the client's version back so we work with either an int or a
        # string protocolVersion rather than guessing which this build uses
        reply(req_id, {
            "protocolVersion": params.get("protocolVersion", 1),
            "agentCapabilities": {
                "loadSession": False,
                "promptCapabilities": {
                    "image": False,
                    "audio": False,
                    "embeddedContext": False,
                },
            },
            "agentInfo": {"name": "Mizune", "version": "1.0.0"},
            "authMethods": [],
        })

    elif method == "authenticate":
        reply(req_id, {})

    elif method == "session/new":
        reply(req_id, {"sessionId": "mizune-main"})

    elif method == "session/load":
        reply(req_id, {})

    elif method == "session/prompt":
        session_id = params.get("sessionId", "mizune-main")
        text = extract_text(params.get("prompt"))
        if not text:
            reply(req_id, {"stopReason": "end_turn"})
            return

        answer = ask_mizune(text)

        notify("session/update", {
            "sessionId": session_id,
            "update": {
                "kind": "agent_message_chunk",
                "chunk": {"content": {"type": "text", "text": answer}},
            },
        })
        reply(req_id, {"stopReason": "end_turn"})

    elif method == "session/cancel":
        pass  # one-way; nothing to interrupt since /chat is a single call

    elif is_notification:
        log(f"ignoring unknown notification: {method}")

    else:
        reply_error(req_id, -32601, f"method not found: {method}")


def main():
    log(f"started, forwarding to {MIZUNE_URL}/chat")
    for line in sys.stdin:
        line = line.lstrip("﻿").strip()  # some clients prefix a BOM
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            log(f"bad JSON on stdin: {line[:200]}")
            continue
        try:
            handle(msg)
        except Exception as e:  # never die mid-session
            log(f"handler crashed on {msg.get('method')}: {e}")
            if msg.get("id") is not None:
                reply_error(msg["id"], -32603, str(e))


if __name__ == "__main__":
    main()
