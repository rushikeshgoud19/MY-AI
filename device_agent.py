"""Mizune Device Agent — turns this machine into one of Mizune's hands.

Run this on your laptop/PC while Mizune's brain runs in the cloud:

    python device_agent.py --server ws://40.123.215.32:8001/ws --name laptop

It connects OUTBOUND to the server (no ports to open here), registers its
capabilities, and executes commands Mizune routes to it — file downloads,
opening apps/URLs, shell commands (with a safety blocklist) — then reports
results back. Reconnects automatically if the link drops.
"""
import argparse
import asyncio
import json
import os
import subprocess
import sys
import webbrowser

try:
    import websockets
except ImportError:
    sys.exit("pip install websockets")

CAPABILITIES = ["download_file", "open_app", "open_url", "run_command"]
DANGEROUS = ["del ", "rmdir ", "rm -", "format ", "diskpart", "shutdown", "reg delete", "mkfs"]
DOWNLOADS = os.path.join(os.path.expanduser("~"), "Downloads")


def do_download(args: dict) -> str:
    import urllib.request
    url = args.get("url", "")
    if not url.startswith(("http://", "https://")):
        return "Error: invalid URL."
    filename = os.path.basename(args.get("filename") or url.split("?")[0].rstrip("/").split("/")[-1] or "download.bin")
    dest = os.path.join(DOWNLOADS, filename)
    urllib.request.urlretrieve(url, dest)
    size_mb = os.path.getsize(dest) / 1e6
    return f"Downloaded {filename} ({size_mb:.1f} MB) to {DOWNLOADS}."


def do_open_app(args: dict) -> str:
    app = args.get("app_name", "")
    if not app:
        return "Error: no app_name."
    if os.name == "nt":
        os.system(f'start "" "{app}"')
    else:
        subprocess.Popen([app])
    return f"Opened {app}."


def do_open_url(args: dict) -> str:
    url = args.get("url", "")
    if url and not url.startswith(("http://", "https://")) and "." in url:
        url = "https://" + url  # LLMs often drop the scheme
    if not url.startswith(("http://", "https://")):
        return "Error: invalid URL."
    webbrowser.open(url)
    return f"Opened {url} in the browser."


def do_run_command(args: dict) -> str:
    cmd = args.get("command", "")
    if not cmd:
        return "Error: no command."
    if any(d in cmd.lower() for d in DANGEROUS):
        return f"BLOCKED for safety: '{cmd}'. Master must run destructive commands manually."
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
    out = (result.stdout + "\n" + result.stderr).strip()
    if len(out) > 800:
        out = out[:800] + "...(truncated)"
    return f"Exit {result.returncode}.\n{out}"


ACTIONS = {
    "download_file": do_download,
    "open_app": do_open_app,
    "open_url": do_open_url,
    "run_command": do_run_command,
}


async def handle(ws, msg: dict):
    action = msg.get("action", "")
    request_id = msg.get("request_id", "")
    fn = ACTIONS.get(action)
    if fn is None:
        result = f"Unknown action: {action}"
    else:
        try:
            result = await asyncio.to_thread(fn, msg.get("args") or {})
        except Exception as e:
            result = f"Error executing {action}: {e}"
    print(f"[agent] {action} -> {str(result)[:100]}")
    await ws.send(json.dumps({"type": "device_result", "request_id": request_id, "result": result}))


async def run(server: str, name: str):
    while True:
        try:
            print(f"[agent] connecting to {server} as '{name}'...")
            async with websockets.connect(server, ping_interval=25, ping_timeout=15) as ws:
                await ws.send(json.dumps({
                    "type": "register_device",
                    "device_name": name,
                    "capabilities": CAPABILITIES,
                    "platform": sys.platform,
                }))
                print("[agent] registered. Waiting for commands.")
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except Exception:
                        continue
                    if msg.get("type") == "device_command":
                        asyncio.create_task(handle(ws, msg))
        except Exception as e:
            print(f"[agent] connection lost ({e}); retrying in 10s...")
            await asyncio.sleep(10)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--server", default=os.environ.get("MIZUNE_SERVER", "ws://40.123.215.32:8001/ws"))
    p.add_argument("--name", default=os.environ.get("MIZUNE_DEVICE_NAME", "laptop"))
    a = p.parse_args()
    asyncio.run(run(a.server, a.name))
