"""
server.integrations package.

Previously this logic lived in server/integrations.py, but a package directory of the
same name (holding google_api.py / obsidian.py submodules) was added on the mobile-app
branch. Two objects named `integrations` (a module and a package) cannot coexist — the
package shadows the module, so `IntegrationsManager` became unreachable and every
`import server.*` crashed. The manager now lives here so both the manager and the
submodules import cleanly.
"""
import os
import json
import logging
from typing import Dict, Any, Optional
from urllib.parse import urlencode

try:
    from authlib.integrations.requests_client import OAuth2Session
except ImportError:
    OAuth2Session = None

from ..config import log_info

__all__ = ["IntegrationsManager", "integrations"]

class IntegrationsManager:
    """
    Manages OAuth2 connections to 3rd party services like OpenHuman does.
    Stores tokens securely.
    """
    def __init__(self, token_dir: str = ".data/tokens"):
        self.token_dir = token_dir
        if not os.path.exists(self.token_dir):
            os.makedirs(self.token_dir)

        config_data = {}
        try:
            with open("config.json", "r", encoding="utf-8", errors="replace") as f:
                config_data = json.load(f)
        except Exception:
            pass

        # These should normally be loaded from env vars or config
        self.oauth_configs = {
            "google": {
                "client_id": os.environ.get("GOOGLE_CLIENT_ID", "") or config_data.get("google_client_id", ""),
                "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", "") or config_data.get("google_client_secret", ""),
                "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
                "token_url": "https://oauth2.googleapis.com/token",
                "scopes": [
                    "https://www.googleapis.com/auth/calendar.events",
                    "https://www.googleapis.com/auth/gmail.readonly"
                ]
            },
            "github": {
                "client_id": os.environ.get("GITHUB_CLIENT_ID", ""),
                "client_secret": os.environ.get("GITHUB_CLIENT_SECRET", ""),
                "auth_url": "https://github.com/login/oauth/authorize",
                "token_url": "https://github.com/login/oauth/access_token",
                "scopes": ["repo", "read:user"]
            },
            "spotify": {
                "client_id": os.environ.get("SPOTIFY_CLIENT_ID", ""),
                "client_secret": os.environ.get("SPOTIFY_CLIENT_SECRET", ""),
                "auth_url": "https://accounts.spotify.com/authorize",
                "token_url": "https://accounts.spotify.com/api/token",
                "scopes": ["user-read-playback-state", "user-modify-playback-state"]
            }
        }

    def get_token_path(self, provider: str) -> str:
        return os.path.join(self.token_dir, f"{provider}_token.json")

    def load_token(self, provider: str) -> Optional[dict]:
        path = self.get_token_path(provider)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8', errors='replace') as f:
                    return json.load(f)
            except Exception as e:
                log_info(f"[OAUTH] Error loading token for {provider}: {e}")
        return None

    def save_token(self, provider: str, token: dict):
        path = self.get_token_path(provider)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(token, f)
            log_info(f"[OAUTH] Token saved for {provider}")
        except Exception as e:
            log_info(f"[OAUTH] Error saving token for {provider}: {e}")

    def get_auth_url(self, provider: str, redirect_uri: str) -> str:
        if not OAuth2Session:
            return "authlib not installed."

        config = self.oauth_configs.get(provider)
        if not config:
            return f"Provider {provider} not configured."

        if not config["client_id"]:
            return f"Missing client_id for {provider}."

        session = OAuth2Session(
            config["client_id"],
            config["client_secret"],
            scope=" ".join(config["scopes"]),
            redirect_uri=redirect_uri
        )
        extra = {}
        if provider == "google":
            # Without access_type=offline Google never issues a refresh_token,
            # and without prompt=consent it omits it on re-consent too.
            extra = {"access_type": "offline", "prompt": "consent"}
        uri, state = session.create_authorization_url(config["auth_url"], **extra)

        # Save state temporarily for verification
        self.save_token(f"{provider}_state", {"state": state})
        return uri

    def fetch_token(self, provider: str, redirect_response: str, redirect_uri: str) -> bool:
        if not OAuth2Session:
            return False

        config = self.oauth_configs.get(provider)
        if not config:
            return False

        state_data = self.load_token(f"{provider}_state")
        state = state_data.get("state") if state_data else None

        session = OAuth2Session(
            config["client_id"],
            config["client_secret"],
            state=state,
            redirect_uri=redirect_uri
        )

        try:
            token = session.fetch_token(
                config["token_url"],
                authorization_response=redirect_response
            )
            self.save_token(provider, token)
            return True
        except Exception as e:
            log_info(f"[OAUTH] Failed to fetch token for {provider}: {e}")
            return False

    def get_client(self, provider: str) -> Optional["OAuth2Session"]:
        if not OAuth2Session:
            return None

        token = self.load_token(provider)
        if not token:
            return None

        config = self.oauth_configs.get(provider)
        if not config:
            return None

        client = OAuth2Session(
            config["client_id"],
            config["client_secret"],
            token=token,
            # We would normally set token_updater here to auto-refresh and save
        )
        return client

    def auto_refresh_google_token(self) -> Optional[dict]:
        token = self.load_token("google")
        if not token or "refresh_token" not in token:
            return None

        config = self.oauth_configs.get("google")
        if not config:
            return None

        try:
            import urllib.request
            import urllib.parse
            import urllib.error

            data = urllib.parse.urlencode({
                'client_id': config['client_id'] or "",
                'client_secret': config['client_secret'] or "",
                'refresh_token': token['refresh_token'],
                'grant_type': 'refresh_token'
            }).encode('utf-8')

            req = urllib.request.Request(config['token_url'], data=data)
            with urllib.request.urlopen(req) as response:
                new_token_data = json.loads(response.read().decode())
                # Google doesn't return a new refresh_token on refresh, so keep the old one!
                if "refresh_token" not in new_token_data:
                    new_token_data["refresh_token"] = token["refresh_token"]

                self.save_token("google", new_token_data)
                self.mark_auth_ok("google")
                log_info("[OAUTH] Successfully auto-refreshed Google access token!")
                return new_token_data
        except urllib.error.HTTPError as e:
            # Auth failures come in two very different flavours, and the old code
            # logged both the same way at info level and returned None. A dead
            # refresh token is PERMANENT — only a fresh browser consent fixes it —
            # but it looked identical to a network blip, so calendar and gmail
            # stayed dead for weeks (640 identical log lines) and nothing escalated.
            # The HTTPError body is the only place the real reason appears, and
            # the old `except Exception` never read it.
            body = ""
            try:
                body = e.read().decode("utf-8", "replace")
            except Exception:
                pass
            err_code = ""
            try:
                err_code = (json.loads(body) or {}).get("error", "")
            except Exception:
                pass

            if err_code == "invalid_grant":
                # Expired or revoked. Retrying forever accomplishes nothing.
                self.mark_auth_dead("google", "invalid_grant (token expired or revoked)")
            else:
                log_info(f"[OAUTH] Failed to auto-refresh Google token: HTTP {e.code} {body[:200]}")
            return None
        except Exception as e:
            # Network blips, DNS, timeouts — transient. Don't cry wolf.
            log_info(f"[OAUTH] Failed to auto-refresh Google token: {e}")
            return None

    # --- auth health ---------------------------------------------------------
    # A dead token is invisible from the outside: API calls just return nothing
    # and Mizune cheerfully reports "no new email". These make a permanent auth
    # failure loud, exactly once per cooldown, and let other code (briefing,
    # dashboard) ask "is Google actually connected?" instead of assuming.

    AUTH_ALERT_COOLDOWN_SEC = 6 * 60 * 60

    def _auth_state_path(self) -> str:
        return os.path.normpath(
            os.path.join(self.token_dir, os.pardir, "oauth_alert_state.json")
        )

    def _read_auth_state(self) -> dict:
        try:
            with open(self._auth_state_path(), "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _write_auth_state(self, state: dict):
        try:
            with open(self._auth_state_path(), "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            log_info(f"[OAUTH] Could not persist auth state: {e}")

    def auth_failure(self, provider: str = "google") -> Optional[dict]:
        """The recorded permanent auth failure for a provider, or None if healthy."""
        return self._read_auth_state().get(provider)

    def mark_auth_ok(self, provider: str = "google"):
        state = self._read_auth_state()
        if state.pop(provider, None) is not None:
            self._write_auth_state(state)
            log_info(f"[OAUTH] {provider} auth recovered.")

    def mark_auth_dead(self, provider: str, reason: str):
        import time

        state = self._read_auth_state()
        prev = state.get(provider) or {}
        now = time.time()
        state[provider] = {
            "reason": reason,
            "first_seen": prev.get("first_seen", now),
            "last_alert_ts": prev.get("last_alert_ts", 0),
        }

        # The cooldown is persisted to disk, not held in memory, because the
        # original failure logged 640 times across many restarts. A restart must
        # not re-trigger the alert.
        if now - state[provider]["last_alert_ts"] >= self.AUTH_ALERT_COOLDOWN_SEC:
            if self._send_auth_alert(provider, reason):
                state[provider]["last_alert_ts"] = now
        self._write_auth_state(state)

    def _send_auth_alert(self, provider: str, reason: str) -> bool:
        # Code sends this, not the model. An LLM told to "mention it" forgets.
        # ASCII only — this also lands in logs read from a cp1252 console.
        msg = (
            f"[Mizune] {provider.title()} connection is DEAD.\n"
            f"Reason: {reason}\n"
            "Calendar and email are unavailable until it is reconnected.\n"
            "Fix: run  python scripts/google_consent.py  then copy the token to the VM."
        )
        log_info(f"[OAUTH] PERMANENT AUTH FAILURE for {provider}: {reason}")
        try:
            from ..platforms.whatsapp.core import send_whatsapp_message
            return bool(send_whatsapp_message(msg))
        except Exception as e:
            log_info(f"[OAUTH] Could not send auth alert over WhatsApp: {e}")
            return False

    def fetch_recent(self, provider: str) -> str:
        """
        Fetches recent notifications/emails/events for the given provider.
        Returns a formatted markdown string to be ingested into Memory Tree.
        """
        client = self.get_client(provider)
        if not client:
            return ""

        try:
            if provider == "google":
                # Very basic calendar fetch stub
                # In reality, this would hit https://www.googleapis.com/calendar/v3/calendars/primary/events
                # We return a stub that the system can use
                return "Fetched 0 new calendar events."

            elif provider == "github":
                res = client.get("https://api.github.com/notifications")
                if res.status_code == 200:
                    notifs = res.json()
                    if not notifs:
                        return ""
                    lines = [f"GitHub Notifications ({len(notifs)} new):"]
                    for n in notifs[:5]:
                        lines.append(f"- {n.get('subject', {}).get('title')} in {n.get('repository', {}).get('full_name')}")
                    return "\n".join(lines)

            elif provider == "spotify":
                res = client.get("https://api.spotify.com/v1/me/player/currently-playing")
                if res.status_code == 200:
                    data = res.json()
                    if data and data.get("is_playing"):
                        track = data.get("item", {}).get("name", "Unknown")
                        artist = data.get("item", {}).get("artists", [{}])[0].get("name", "Unknown")
                        return f"Master is currently listening to '{track}' by {artist}."

        except Exception as e:
            log_info(f"[OAUTH] Error fetching from {provider}: {e}")

        return ""

integrations = IntegrationsManager()
