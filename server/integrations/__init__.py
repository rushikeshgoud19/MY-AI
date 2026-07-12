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
                    "https://www.googleapis.com/auth/calendar.readonly",
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
        uri, state = session.create_authorization_url(config["auth_url"])

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
                log_info("[OAUTH] Successfully auto-refreshed Google access token!")
                return new_token_data
        except Exception as e:
            log_info(f"[OAUTH] Failed to auto-refresh Google token: {e}")
            return None

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
