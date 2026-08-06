"""Standalone Google OAuth consent flow for Mizune.

Mints a fresh google_token.json without booting the full backend (no pyautogui,
no Baileys session, no wake-word listener). Stdlib only.

Why this exists: refresh tokens die (revoked, or 7-day expiry while the OAuth
consent screen is in "Testing"). When that happens calendar + gmail fail with
invalid_grant and there is no way to recover except a fresh browser consent.

Usage:
    python scripts/google_consent.py

Then open the printed URL, click through the "unverified app" warning
(Advanced -> Go to Mizune), and Allow. Token is written to
.data/tokens/google_token.json in the same shape the server expects.

ASCII-only output: the Windows console is cp1252 and non-ASCII stdout kills
the run mid-flow.
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(REPO, "config.json")
TOKEN_DIR = os.path.join(REPO, ".data", "tokens")
TOKEN_PATH = os.path.join(TOKEN_DIR, "google_token.json")

# Must match GOOGLE_REDIRECT_URI in server.py / legacy/backend_main.py.
REDIRECT_URI = "http://localhost:8001/connect/google/callback"
PORT = 8001

# Keep identical to the scopes the existing token carried, so nothing that
# already works starts asking for consent again.
SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.readonly",
]

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"

_result = {}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if not parsed.path.startswith("/connect/google/callback"):
            self.send_response(404)
            self.end_headers()
            return

        params = urllib.parse.parse_qs(parsed.query)
        if "error" in params:
            _result["error"] = params["error"][0]
            self._reply("Consent denied: %s. You can close this tab." % _result["error"])
            return

        code = params.get("code", [None])[0]
        if not code:
            _result["error"] = "no code in callback"
            self._reply("No authorization code returned. You can close this tab.")
            return

        _result["code"] = code
        self._reply("Mizune is connected to Google. You can close this tab.")

    def _reply(self, msg):
        body = ("<html><body style='font-family:sans-serif;padding:40px'>"
                "<h2>%s</h2></body></html>" % msg).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass  # keep the console clean


def exchange(client_id, client_secret, code):
    data = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    }).encode()
    req = urllib.request.Request(TOKEN_ENDPOINT, data=data)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def main():
    if not os.path.exists(CONFIG):
        print("ERROR: config.json not found at %s" % CONFIG)
        return 1

    cfg = json.load(open(CONFIG, encoding="utf-8"))
    client_id = cfg.get("google_client_id")
    client_secret = cfg.get("google_client_secret")
    if not client_id or not client_secret:
        print("ERROR: google_client_id / google_client_secret missing from config.json")
        return 1

    # access_type=offline + prompt=consent is what forces Google to return a
    # refresh_token. Without both, you get an access token that dies in an hour
    # and no way to renew it.
    auth_url = AUTH_ENDPOINT + "?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
    })

    server = HTTPServer(("localhost", PORT), Handler)
    print("Listening on %s" % REDIRECT_URI)
    print("")
    print("OPEN THIS URL IN YOUR BROWSER:")
    print("")
    print(auth_url)
    print("")
    print("Then: pick your account -> Advanced -> Go to Mizune (unsafe) -> Allow")
    print("Waiting for the callback...")
    sys.stdout.flush()

    while "code" not in _result and "error" not in _result:
        server.handle_request()
    server.server_close()

    if "error" in _result:
        print("FAILED: %s" % _result["error"])
        return 1

    try:
        tok = exchange(client_id, client_secret, _result["code"])
    except urllib.error.HTTPError as e:
        print("TOKEN EXCHANGE FAILED: HTTP %s" % e.code)
        print(e.read().decode())
        return 1

    if not tok.get("refresh_token"):
        print("WARNING: no refresh_token returned. Token will die in ~1 hour.")
        print("Revoke access at myaccount.google.com/permissions and re-run.")
        return 1

    os.makedirs(TOKEN_DIR, exist_ok=True)
    with open(TOKEN_PATH, "w", encoding="utf-8") as f:
        json.dump(tok, f, indent=2)

    print("")
    print("SUCCESS. Token written to %s" % TOKEN_PATH)
    print("  has refresh_token: yes")
    print("  scope: %s" % tok.get("scope"))
    print("  expires_in: %ss" % tok.get("expires_in"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
