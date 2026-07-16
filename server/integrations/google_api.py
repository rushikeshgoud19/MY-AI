import json
import logging
import datetime
import urllib.request
import urllib.error
import urllib.parse

from server.config import log_info

logger = logging.getLogger("mizune.google_api")

_TZ = "Asia/Kolkata"


class GoogleAPIBridge:
    """Real Google Calendar access, reusing the OAuth token the Gmail poller uses
    (integrations.load_token('google') + auto_refresh_google_token). Reading works with
    the calendar.readonly scope; creating events needs the calendar.events scope (user
    reconnects Google once — see handoff)."""

    def _access_token(self):
        from server.integrations import integrations
        t = integrations.load_token("google")
        return t.get("access_token") if t else None

    def _api(self, url, method="GET", body=None):
        from server.integrations import integrations
        token = self._access_token()
        if not token:
            return None, "Google isn't connected yet, Master — connect it in settings first."

        def _do(tok):
            data = json.dumps(body).encode("utf-8") if body is not None else None
            req = urllib.request.Request(url, data=data, method=method)
            req.add_header("Authorization", f"Bearer {tok}")
            if body is not None:
                req.add_header("Content-Type", "application/json")
            return urllib.request.urlopen(req, timeout=12)

        try:
            resp = _do(token)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                nt = integrations.auto_refresh_google_token()
                if nt and nt.get("access_token"):
                    try:
                        resp = _do(nt["access_token"])
                    except Exception as e2:
                        return None, f"Calendar auth error after refresh: {e2}"
                else:
                    return None, "Google session expired, Master — please reconnect Google."
            elif e.code == 403:
                return None, ("I don't have permission to write to your calendar yet, Master. "
                              "Reconnect Google (it now asks for calendar access) and I can schedule it.")
            else:
                return None, f"Google Calendar error {e.code}: {e.read().decode()[:150]}"
        except Exception as e:
            return None, f"Calendar request failed: {e}"
        try:
            return json.loads(resp.read().decode("utf-8")), None
        except Exception:
            return {}, None

    def get_todays_calendar(self):
        from server.config import mizune_now
        now = mizune_now()
        tmin = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        tmax = now.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()
        url = ("https://www.googleapis.com/calendar/v3/calendars/primary/events"
               f"?timeMin={urllib.parse.quote(tmin)}&timeMax={urllib.parse.quote(tmax)}"
               "&singleEvents=true&orderBy=startTime&maxResults=15")
        data, err = self._api(url)
        if err:
            return err
        items = data.get("items", [])
        if not items:
            return "You have no events on your calendar today, Master."
        lines = []
        for ev in items:
            s = ev.get("start", {})
            when = s["dateTime"][11:16] if s.get("dateTime") else "all day"
            lines.append(f"- {when} {ev.get('summary', '(no title)')}")
        return "Today's calendar:\n" + "\n".join(lines)

    def list_upcoming(self, max_results=10):
        from server.config import mizune_now
        tmin = mizune_now().isoformat()
        url = ("https://www.googleapis.com/calendar/v3/calendars/primary/events"
               f"?timeMin={urllib.parse.quote(tmin)}&singleEvents=true&orderBy=startTime"
               f"&maxResults={int(max_results)}")
        data, err = self._api(url)
        if err:
            return err
        items = data.get("items", [])
        if not items:
            return "Nothing on your upcoming calendar, Master."
        lines = []
        for ev in items:
            s = ev.get("start", {})
            when = s.get("dateTime", s.get("date", ""))[:16].replace("T", " ")
            lines.append(f"- {when} — {ev.get('summary', '(no title)')}")
        return "Upcoming events:\n" + "\n".join(lines)

    def create_event(self, summary, start_iso, end_iso=None, description=""):
        if not summary or not start_iso:
            return "I need a title and a start time to schedule it, Master."
        if not end_iso:
            try:
                st = datetime.datetime.fromisoformat(start_iso)
                end_iso = (st + datetime.timedelta(hours=1)).isoformat()
            except Exception:
                end_iso = start_iso
        body = {
            "summary": summary,
            "description": description or "Scheduled by Mizune",
            "start": {"dateTime": start_iso, "timeZone": _TZ},
            "end": {"dateTime": end_iso, "timeZone": _TZ},
        }
        url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
        data, err = self._api(url, method="POST", body=body)
        if err:
            return err
        link = data.get("htmlLink", "")
        return f"✅ Scheduled '{summary}' on your calendar, Master! {link}"

    def read_unread_emails(self, max_results=5):
        # Real recent mail is served by google_workspace action 'list_emails' (local store).
        return "Ask me to 'show my emails' and I'll list your recent mail, Master."

    def get_morning_briefing(self):
        return self.get_todays_calendar()


global_google_api = GoogleAPIBridge()
