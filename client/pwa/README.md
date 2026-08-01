# Mizune PWA (`client/pwa/`)

A phone client for Mizune that ships over HTTP instead of through an APK rebuild.
Plain HTML + CSS + vanilla JS. **No build step, no npm, no framework** — these files
are served exactly as they sit on disk.

It exists so the phone stops being blocked on Android Studio. In particular it can
hold an auth token, which is what makes it safe to turn on `ws_auth_required` and
close the unauthenticated-`/ws` remote-code-execution hole.

```
client/pwa/
  index.html               app shell
  app.js                   websocket client, reconnect, vitals, settings
  style.css                dark theme, thumb-sized targets, keyboard handling
  manifest.json            installable to the home screen
  sw.js                    caches the shell only; never caches /api or /health
  icon-192.png  icon-512.png  icon-maskable-512.png
```

---

## 1. The server route the lead must add

**One line. Nothing else in this repo is touched by the PWA.**

In the VM's `backend_main.py`, next to the existing `app.mount("/ui", ...)`:

```python
pwa_path = os.path.join(os.path.dirname(__file__), "client", "pwa")
if os.path.isdir(pwa_path):
    app.mount("/app", StaticFiles(directory=pwa_path, html=True), name="pwa")
```

| Property | Value | Why it matters |
|---|---|---|
| Mount path | `/app` | Free today. `/` is the React dist, `/ui` is `public/`. |
| Directory | `client/pwa` relative to `backend_main.py` | Must be deployed alongside the backend. |
| `html=True` | required | Serves `index.html` for `/app` and `/app/`. |
| Auth | **none** | These are static assets. The token lives in the browser, not in the URL. |
| Phone URL | `http://40.123.215.32:8001/app/` | Add to Home Screen from Chrome. |

### Two things that will bite if they are missed

1. **`sw.js` must be served from `/app/`, not from a parent path.** A service worker
   can only control pages at or below its own URL. The mount above puts it at
   `/app/sw.js`, whose scope is `/app/` — correct. Do not relocate `sw.js`.

2. **Install-to-home-screen needs HTTPS**, except on `localhost`. Over plain
   `http://40.123.215.32:8001/app/` Chrome for Android will **load and run the page
   normally, but will not offer "Install"** and will not register the service worker.
   Everything else — chat, quick actions, vitals, reconnect — works over plain HTTP.
   To get the real installable PWA, serve it through the existing `Caddyfile` on a
   hostname with a certificate. When that happens the client switches to `wss://`
   and `https://` automatically; it derives the scheme from `location.protocol`.
   No code change needed.

### Optional, not required

The client falls back to the hard-coded host `40.123.215.32:8001` only when it is
opened from `file://` or `localhost`. Served from the VM it talks to its own origin,
so the same files work unchanged behind a domain later.

---

## 2. What changes when `ws_auth_required` is turned on

Today `config.json` has no `ws_auth_required` key, so `_verify_ws_auth` returns
`(True, "Auth disabled")` and `/ws` accepts everyone. **This client already sends the
token**, so the switch does not require a client change.

Behaviour on each side of the flag:

| | `ws_auth_required: false` (today) | `ws_auth_required: true` |
|---|---|---|
| No token stored | Chat works. Status strip says vitals need a token. | `/ws` closes with **4001**. UI shows "Rejected (4001): server now requires a token. Add one in settings." Send is disabled. |
| Correct token stored | Chat works, `?key=` is sent and ignored. Vitals render. | Chat works. Vitals render. Nothing visibly changes. |
| Wrong token stored | Chat works (auth off). Vitals show "401 - server rejected this token". | `/ws` closes with 4001, same honest message as above. |

**Order of operations for the cutover:**

1. Deploy the `/app` mount, open it on the phone.
2. Paste the token into Settings, press **Test token** — it hits
   `GET /api/vitals` with `X-Mizune-Key` and reports accepted or rejected. Save.
3. Confirm the strip shows a brain and the socket says "Connected (token sent)".
4. Only then set `"ws_auth_required": true` in the VM config and restart.
5. Any client without the token is now refused with code 4001 — which is the point.

On a 4001 the client deliberately **backs off to 15-30s instead of retrying fast**.
A rejected client hammering the socket is just a self-inflicted DoS.

The token is stored in `localStorage` under `mizune_token`, on the device only. It is
sent two ways, matching what the server already accepts: `?key=<token>` on the
WebSocket URL, and the `X-Mizune-Key` header on `/api/vitals`.

---

## 3. Wire protocol this client depends on

Verified live against `40.123.215.32:8001` on 2026-08-01. If any of this changes
server-side, this client needs updating.

**Sends:** `{"type":"chat","text":"...","platform":"pwa"}` — that is all. Quick action
buttons send the same shape with `text` set to `/usage`, `/status`, `/insights`, `/model`.

**Receives:**

| type | Used for |
|---|---|
| `speak` | Her reply. One message per sentence; rendered as separate bubbles. |
| `status` | `"Thinking..."` / `"Idle"` drive the activity line. `Idle` clears it. |
| `user_input` | Echo of any client's input. Only rendered when `platform != "pwa"`. |
| `audio` | ~250 KB base64 mp3 per reply. **Ignored unless "Play her voice" is on.** |
| `state_update`, `emotion_update`, `mode`, `task_list` | Accepted and ignored. |

**`/ws` is a broadcast bus.** The server calls `broadcast_sync`, so this client also
receives traffic caused by his laptop. Input from another device is labelled with its
platform rather than being shown as if he typed it here. Worth knowing before someone
files a bug about "messages I never sent".

`GET /api/vitals` (header `X-Mizune-Key`) returns:

```json
{"brain":{"provider":"cerebras","model":"gpt-oss-120b","tools":"2/3"},
 "providers":{"total":6,"keyed":5,"live":5,"down":[]},
 "devices":["laptop"],"crons":8,"seals_24h":6,"seals_failed_24h":0,"problems":[]}
```

---

## 4. Design rules this client is held to

- **Never show state it has not verified.** "Connected" appears only after `onopen`.
  When the socket closes, the vitals strip is blanked immediately with a stated
  reason — stale numbers from thirty seconds ago are not evidence the VM is healthy.
- **Every failure states its cause**: the close code, the HTTP status, the exception.
  No bare "something went wrong".
- **Send is disabled whenever the socket is not open**, and typed text is never
  silently dropped — it stays in the box with an explanation.
- **Reconnect** backs off 1s -> 2s -> 4s -> 8s -> 15s -> 30s, and counts down visibly.
- **Screen lock / backgrounding**: on resume, a socket claiming `OPEN` after 20s+ away
  is not trusted. The client probes `GET /health` (unauthenticated, works with no
  token) and recycles the socket rather than believing a half-open TCP connection.
- **Keyboard**: the composer is translated up by the `visualViewport` delta, so the
  input is never buried by the on-screen keyboard. Input font is 16px to stop iOS
  auto-zoom. Every tap target is at least 44px.
- **`sw.js` never caches `/api/*`, `/health`, `/ws`, or cross-origin requests.** A
  cached vitals response would be exactly the kind of confident lie this client avoids.
  Shell fetches use `cache: 'no-store'` because FastAPI's `StaticFiles` sends no
  `Cache-Control` and heuristic caching otherwise pins a stale `app.js` after deploys.

## 5. Redeploying

Copy the directory to the VM and reload. Bump `CACHE` in `sw.js` (`mizune-pwa-vN`) on
any change so old shells are evicted; `BUILD` in `app.js` is shown in Settings so the
running version is checkable from the phone.
