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

CAPABILITIES = ["install_app", "download_file", "open_app", "open_url", "run_command"]
DANGEROUS = ["del ", "rmdir ", "rm -", "format ", "diskpart", "shutdown", "reg delete", "mkfs"]
DOWNLOADS = os.path.join(os.path.expanduser("~"), "Downloads")


def do_download(args: dict) -> str:
    import urllib.request
    url = args.get("url", "")
    if not url.startswith(("http://", "https://")):
        return "Error: invalid URL."
    filename = os.path.basename(args.get("filename") or url.split("?")[0].rstrip("/").split("/")[-1] or "download.bin")
    dest = os.path.join(DOWNLOADS, filename)
    # Mirrors 403 Python's default user-agent; present as a normal browser
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=300) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(1024 * 256)
            if not chunk:
                break
            f.write(chunk)
    size_mb = os.path.getsize(dest) / 1e6
    return f"Downloaded {filename} ({size_mb:.1f} MB) to {DOWNLOADS}."


# Common apps -> official winget IDs, so we install the RIGHT thing from the
# winget community source (not a flaky Microsoft Store lookalike).
WINGET_IDS = {
    "blender": "BlenderFoundation.Blender",
    "chrome": "Google.Chrome",
    "google chrome": "Google.Chrome",
    "firefox": "Mozilla.Firefox",
    "vscode": "Microsoft.VisualStudioCode",
    "vs code": "Microsoft.VisualStudioCode",
    "visual studio code": "Microsoft.VisualStudioCode",
    "discord": "Discord.Discord",
    "spotify": "Spotify.Spotify",
    "vlc": "VideoLAN.VLC",
    "obs": "OBSProject.OBSStudio",
    "notepad++": "Notepad++.Notepad++",
    "git": "Git.Git",
    "python": "Python.Python.3.12",
    "node": "OpenJS.NodeJS",
    "nodejs": "OpenJS.NodeJS",
    "steam": "Valve.Steam",
    "zoom": "Zoom.Zoom",
    "7zip": "7zip.7zip",
    "audacity": "Audacity.Audacity",
    "gimp": "GIMP.GIMP",
    "brave": "Brave.Brave",
}


def do_install_app(args: dict) -> str:
    """Install an app by name via the OS package manager. No URL guessing — this
    is how 'download/install blender' should actually work."""
    app = (args.get("app_name") or args.get("app") or args.get("name") or "").strip()
    if not app:
        return "Error: no app name given."
    if os.name == "nt":
        winget_id = WINGET_IDS.get(app.lower())
        if winget_id:
            cmd = ["winget", "install", "--id", winget_id, "--source", "winget",
                   "--accept-package-agreements", "--accept-source-agreements", "--silent"]
        else:
            # Unknown app: search the winget source by name (avoids the msstore path)
            cmd = ["winget", "install", "--name", app, "--source", "winget",
                   "--accept-package-agreements", "--accept-source-agreements", "--silent"]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        except FileNotFoundError:
            return "winget is not available on this PC. Master can install 'App Installer' from the Microsoft Store, or give me a direct download link."
        except subprocess.TimeoutExpired:
            return f"Install of '{app}' is taking a while; it may still be running in the background."
        out = (r.stdout + "\n" + r.stderr).strip()
        if r.returncode == 0 or "successfully installed" in out.lower():
            return f"Installed {app} successfully."
        if "no package found" in out.lower() or "no available upgrade" in out.lower():
            return (f"Couldn't find '{app}' in the winget catalog. "
                    f"Master can give me the exact app name or a direct download link.")
        return f"Install of '{app}' failed (code {r.returncode}). {out[-250:]}"
    else:
        # linux/mac best-effort
        for mgr in (["brew", "install"], ["apt-get", "install", "-y"]):
            if subprocess.run(["which", mgr[0]], capture_output=True).returncode == 0:
                r = subprocess.run(mgr + [app.lower()], capture_output=True, text=True, timeout=600)
                return f"Ran {mgr[0]} install {app}: exit {r.returncode}."
        return "No supported package manager found on this device."


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
    "install_app": do_install_app,
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
