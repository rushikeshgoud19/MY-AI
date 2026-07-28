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

CAPABILITIES = ["install_app", "download_file", "open_app", "open_url", "run_command", "claude_code",
                "run_task", "claude_task", "list_files", "read_file"]
DANGEROUS = ["del ", "rmdir ", "rm -", "format ", "diskpart", "shutdown", "reg delete", "mkfs"]
DOWNLOADS = os.path.join(os.path.expanduser("~"), "Downloads")

SENSITIVE_PATTERNS = [".env", "token", "secret", "credential", "id_rsa"]
SKIP_DIRS = {"node_modules", ".git", ".venv", "__pycache__"}

def _get_allowed_roots():
    user_home = os.path.expanduser("~")
    roots = [
        os.path.join(user_home, "Desktop"),
        os.path.join(user_home, "Documents"),
        os.path.join(user_home, "Downloads"),
        os.path.join(user_home, "OneDrive", "Desktop"),
        os.path.join(user_home, "OneDrive", "Documents"),
        os.path.join(user_home, "OneDrive", "Downloads"),
    ]
    return [os.path.normpath(r).lower() for r in roots if os.path.exists(r)]

def _is_path_allowed(target_path: str) -> bool:
    norm = os.path.normpath(os.path.abspath(target_path)).lower()
    allowed = _get_allowed_roots()
    return any(norm == r or norm.startswith(r + os.sep) for r in allowed)

def _is_sensitive_file(filename: str) -> bool:
    name_lower = filename.lower()
    return any(p in name_lower for p in SENSITIVE_PATTERNS)

def do_list_files(args: dict) -> str:
    root = (args.get("root") or args.get("path") or "Desktop").strip()
    user_home = os.path.expanduser("~")
    
    root_norm = root.replace("\\", "/").strip()
    first_part = root_norm.split("/")[0].lower()
    rest = "/".join(root_norm.split("/")[1:]) if "/" in root_norm else ""

    if first_part in ("desktop", "documents", "downloads"):
        folder_name = first_part.capitalize()
        od_base = os.path.join(user_home, "OneDrive", folder_name)
        normal_base = os.path.join(user_home, folder_name)
        cand1 = os.path.normpath(os.path.join(od_base, rest)) if rest else od_base
        cand2 = os.path.normpath(os.path.join(normal_base, rest)) if rest else normal_base
        if os.path.exists(cand1):
            abs_root = cand1
        elif os.path.exists(cand2):
            abs_root = cand2
        else:
            abs_root = cand1
    else:
        abs_root = os.path.abspath(root)

    if not _is_path_allowed(abs_root):
        return f"Refused: path '{root}' is outside allowlisted roots (Desktop, Documents, Downloads)."

    if not os.path.isdir(abs_root):
        return f"Error: directory '{abs_root}' does not exist."

    pattern = (args.get("pattern") or "").strip().lower()
    max_count = int(args.get("max") or 200)
    import fnmatch

    results = []
    for dirpath, dirnames, filenames in os.walk(abs_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for f in filenames:
            if _is_sensitive_file(f):
                continue
            if pattern and not fnmatch.fnmatch(f.lower(), pattern):
                continue
            full_path = os.path.join(dirpath, f)
            try:
                if os.path.getsize(full_path) > 20 * 1024 * 1024:
                    continue
            except Exception:
                continue
            results.append(full_path)
            if len(results) >= max_count:
                break
        if len(results) >= max_count:
            break

    return json.dumps(results)

def do_read_file(args: dict) -> str:
    path = args.get("path", "").strip()
    if not path:
        return "Error: no path specified."

    user_home = os.path.expanduser("~")
    path_norm = path.replace("\\", "/").strip()
    first_part = path_norm.split("/")[0].lower()
    rest = "/".join(path_norm.split("/")[1:]) if "/" in path_norm else ""

    if first_part in ("desktop", "documents", "downloads"):
        folder_name = first_part.capitalize()
        od_base = os.path.join(user_home, "OneDrive", folder_name)
        normal_base = os.path.join(user_home, folder_name)
        cand1 = os.path.normpath(os.path.join(od_base, rest)) if rest else od_base
        cand2 = os.path.normpath(os.path.join(normal_base, rest)) if rest else normal_base
        if os.path.exists(cand1):
            abs_path = cand1
        elif os.path.exists(cand2):
            abs_path = cand2
        else:
            abs_path = cand1
    else:
        abs_path = os.path.abspath(path)

    if not _is_path_allowed(abs_path):
        return f"Refused: path '{path}' is outside allowlisted roots."
    if not os.path.isfile(abs_path):
        return f"Error: file '{path}' does not exist."
    if _is_sensitive_file(os.path.basename(abs_path)):
        return "Refused: sensitive file."

    max_chars = int(args.get("max_chars", 20000))
    ext = os.path.splitext(abs_path)[1].lower()

    if ext == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(abs_path)
            pages_text = []
            for p in reader.pages:
                txt = p.extract_text()
                if txt:
                    pages_text.append(txt)
            text = "\n".join(pages_text)
        except Exception as e:
            return f"Error reading PDF: {e}"
    elif ext == ".docx":
        try:
            import docx
            doc = docx.Document(abs_path)
            text = "\n".join([p.text for p in doc.paragraphs if p.text])
        except ImportError:
            return "Can't read .docx yet (python-docx not installed)."
        except Exception as e:
            return f"Error reading .docx: {e}"
    else:
        try:
            with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read(max_chars * 2)
        except Exception as e:
            return f"Error reading file: {e}"

    if not text or not text.strip():
        return f"(No readable text content extracted from {os.path.basename(abs_path)})"

    return text.strip()[:max_chars]


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


ALLOWED_EXECUTABLES = {
    "python", "python.exe", "py", "py.exe",
    "git", "git.exe", "gh", "gh.exe",
    "node", "node.exe", "npm", "npm.cmd", "npx", "npx.cmd",
    "dir", "ls", "type", "cat", "echo", "where", "which"
}
SHELL_OPERATORS = ["|", ">", "<", "&&", "||", ";", "&", "^", "%", "$", "\n"]


def _get_active_allowlist() -> set:
    allowed = set(ALLOWED_EXECUTABLES)
    try:
        from server.config import load_config
        cfg = load_config()
        extra = cfg.get("device_command_allowlist", [])
        if isinstance(extra, list):
            for item in extra:
                if isinstance(item, str) and item.strip():
                    allowed.add(item.strip().lower())
    except Exception:
        pass
    return allowed


def do_install_app(args: dict) -> str:
    """Install an app by name via the OS package manager.
    Requires config['allow_remote_install'] == True to proceed.
    """
    try:
        from server.config import load_config
        cfg = load_config()
        if not cfg.get("allow_remote_install", False):
            return "Refused: Remote app installation is disabled. Set 'allow_remote_install: true' in config.json to enable."
    except Exception:
        return "Refused: Remote app installation is disabled."

    app = (args.get("app_name") or args.get("app") or args.get("name") or "").strip()
    if not app:
        return "Error: no app name given."
    if os.name == "nt":
        key = app.lower().strip()
        winget_id = WINGET_IDS.get(key)
        if not winget_id:
            for filler in (" media player", " browser", " editor", " app", " for windows"):
                key = key.replace(filler, "")
            key = key.strip()
            winget_id = WINGET_IDS.get(key)
        if winget_id:
            cmd = ["winget", "install", "--id", winget_id, "--source", "winget",
                   "--accept-package-agreements", "--accept-source-agreements", "--silent"]
        else:
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
        r = subprocess.run(f'start "" "{app}"', shell=True, capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "launch failed").strip()
            return f"Couldn't open {app} on the laptop: {err[:150]}"
    else:
        subprocess.Popen([app])
    return f"Opened {app}."


def do_open_url(args: dict) -> str:
    url = args.get("url", "")
    if url and not url.startswith(("http://", "https://")) and "." in url:
        url = "https://" + url
    if not url.startswith(("http://", "https://")):
        return "Error: invalid URL."
    webbrowser.open(url)
    return f"Opened {url} in the browser."


def do_run_command(args: dict) -> str:
    import shlex
    cmd_str = args.get("command", "").strip()
    if not cmd_str:
        return "Error: no command."

    # 1. Reject shell feature operators (pipes, redirects, command chaining)
    for op in SHELL_OPERATORS:
        if op in cmd_str:
            return f"Refused: Command uses shell feature '{op}' (pipes, redirects, chained commands) which are disallowed for safety."

    # 2. Tokenize command into list
    try:
        tokens = shlex.split(cmd_str)
    except Exception as e:
        return f"Refused: Invalid command syntax: {e}"

    if not tokens:
        return "Error: empty command."

    # 3. Check executable against allowlist
    exe_token = tokens[0]
    exe_name = os.path.basename(exe_token).lower()
    allowed_set = _get_active_allowlist()

    if exe_name not in allowed_set and exe_token.lower() not in allowed_set:
        return f"Refused: Executable '{exe_token}' is not in the allowed commands list. Allowed: {sorted(list(allowed_set))}"

    # 3b. AN ALLOWLIST OF INTERPRETERS IS NOT A RESTRICTION.
    # python, node, npm and git are general-purpose: allowing them allows anything, just
    # written in another language. Verified 2026-07-29 against the allowlist as first
    # shipped — each of these RAN and really created the file:
    #     python -c "open(path,'w').write('pwned')"
    #     node -e "require('fs').writeFileSync(path,'pwned')"
    #     git -c alias.x="!echo hi" x        <- git aliases beginning with ! run a shell
    # The earlier test only tried obviously-named destructive binaries (del, format,
    # diskpart), so it passed 15/15 while arbitrary execution was wide open.
    # Scripts stay allowed — the build-log collector is `python <script> --days 1 --json`,
    # and that is the whole reason run_command exists — but INLINE CODE does not.
    _EVAL_FLAGS = {
        "python": {"-c", "-m"}, "python.exe": {"-c", "-m"},
        "py": {"-c", "-m"}, "py.exe": {"-c", "-m"},
        "node": {"-e", "--eval", "-p", "--print"}, "node.exe": {"-e", "--eval", "-p", "--print"},
        "git": {"-c"}, "git.exe": {"-c"},          # git -c alias.x='!sh' is shell execution
    }
    _banned = _EVAL_FLAGS.get(exe_name, set())
    for tok in tokens[1:]:
        if tok.lower() in _banned:
            return (f"Refused: '{exe_name} {tok}' runs inline code, which is arbitrary "
                    f"execution wearing an allowed name. Put it in a script file and run "
                    f"that instead.")

    # 4. Handle Windows builtins (echo, dir, type) safely via cmd.exe /c
    if os.name == "nt" and exe_name in {"echo", "dir", "type"}:
        tokens = ["cmd.exe", "/c"] + tokens

    # Execute with shell=False
    try:
        result = subprocess.run(tokens, shell=False, capture_output=True, text=True, timeout=60)
        out = (result.stdout + "\n" + result.stderr).strip()
        if len(out) > 800:
            out = out[:800] + "...(truncated)"
        return f"Exit {result.returncode}.\n{out}"
    except FileNotFoundError:
        return f"Error: Executable '{tokens[0]}' not found on this system."
    except Exception as e:
        return f"Error executing command: {e}"


def do_claude_code(args: dict) -> str:
    """Open a Claude Code session on this machine, optionally pre-loaded with a task.
    Launches a VISIBLE terminal (Master can watch and steer) and returns immediately —
    Claude tasks run far longer than the 45s device-command timeout."""
    task = str(args.get("task") or args.get("prompt") or "").strip().replace('"', "'")
    project = str(args.get("project") or args.get("cwd") or "").strip()
    workdir = project if project and os.path.isdir(project) else os.path.join(
        os.path.expanduser("~"), "OneDrive", "Desktop", "my Ai")
    if not os.path.isdir(workdir):
        workdir = os.path.expanduser("~")
    if task:
        subprocess.Popen(f'start "Claude Code (via Mizune)" cmd /k claude "{task}"',
                         shell=True, cwd=workdir)
        return f"Claude Code opened on the laptop (in {workdir}) with task: {task[:120]}"
    subprocess.Popen('start "Claude Code (via Mizune)" cmd /k claude', shell=True, cwd=workdir)
    return f"Claude Code opened on the laptop (in {workdir})."


ACTIONS = {
    "install_app": do_install_app,
    "download_file": do_download,
    "open_app": do_open_app,
    "open_url": do_open_url,
    "run_command": do_run_command,
    "claude_code": do_claude_code,
    "list_files": do_list_files,
    "read_file": do_read_file,
}


async def run_background_task(ws, label: str, cmd: str, cwd=None, timeout=1800):
    """Run a long command in the background, then PUSH the outcome to the brain —
    Mizune relays it to Master (WhatsApp + voice). The Hermes-beater: delegate,
    walk away, get an honest report."""
    def work():
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                               timeout=timeout, cwd=cwd)
            out = (r.stdout + "\n" + r.stderr).strip()
            status = "succeeded" if r.returncode == 0 else f"FAILED (exit {r.returncode})"
            return f"{status}. " + (out[-1200:] if out else "(no output)")
        except subprocess.TimeoutExpired:
            return f"timed out after {timeout // 60} minutes."
        except Exception as e:
            return f"error: {e}"
    result = await asyncio.to_thread(work)
    print(f"[agent] background task '{label}' -> {result[:100]}")
    try:
        await ws.send(json.dumps({"type": "device_task_done", "label": label, "result": result}))
    except Exception as e:
        print(f"[agent] couldn't report task completion: {e}")


async def handle(ws, msg: dict):
    action = msg.get("action", "")
    # Background tasks: acknowledge instantly, push a completion report later.
    if action in ("run_task", "claude_task"):
        a = msg.get("args") or {}
        if action == "claude_task":
            task = str(a.get("task") or a.get("command") or "").strip().replace('"', "'")
            if not task:
                result = "Error: no task given."
            else:
                cwd = a.get("project") if a.get("project") and os.path.isdir(str(a.get("project"))) else \
                    os.path.join(os.path.expanduser("~"), "OneDrive", "Desktop", "my Ai")
                cmd = f'claude -p "{task}"'
                label = a.get("label") or task[:60]
                asyncio.create_task(run_background_task(ws, label, cmd, cwd=cwd))
                result = f"Started Claude on the laptop working on: {label}. I'll report when it finishes."
        else:
            cmd = str(a.get("command") or "").strip()
            if not cmd:
                result = "Error: no command."
            elif any(d in cmd.lower() for d in DANGEROUS):
                result = f"BLOCKED for safety: '{cmd}'."
            else:
                label = a.get("label") or cmd[:60]
                asyncio.create_task(run_background_task(ws, label, cmd))
                result = f"Started background task: {label}. I'll report when it finishes."
        print(f"[agent] {action} -> {result[:100]}")
        await ws.send(json.dumps({"type": "device_result",
                                  "request_id": msg.get("request_id", ""), "result": result}))
        return
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
