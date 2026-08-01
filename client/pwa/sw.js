/* Mizune PWA service worker.
 *
 * Scope is deliberately narrow: cache the app SHELL so the icon on the home
 * screen always opens something, and get out of the way for everything else.
 * We never cache API responses - a stale /api/vitals would be exactly the kind
 * of confident lie this client is built to avoid.
 */
var CACHE = 'mizune-pwa-v2';
var SHELL = ['./', 'index.html', 'app.js', 'style.css', 'manifest.json',
             'icon-192.png', 'icon-512.png', 'icon-maskable-512.png'];

self.addEventListener('install', function (e) {
  e.waitUntil(
    caches.open(CACHE)
      .then(function (c) { return c.addAll(SHELL); })
      .then(function () { return self.skipWaiting(); })
      .catch(function () { /* a missing shell file must not block install */ })
  );
});

self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.map(function (k) {
        return k === CACHE ? null : caches.delete(k);
      }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') return;

  var url;
  try { url = new URL(req.url); } catch (err) { return; }

  // Never intercept live data or cross-origin calls to the VM.
  if (url.pathname.indexOf('/api/') === 0 ||
      url.pathname === '/health' ||
      url.pathname === '/ws' ||
      url.origin !== self.location.origin) return;

  // Shell: network-first so a redeploy lands immediately, cache as the fallback.
  // `cache:'no-store'` skips the browser's own HTTP cache - FastAPI's StaticFiles
  // sends no Cache-Control, so heuristic caching otherwise pins a stale app.js
  // and a redeploy silently does nothing.
  e.respondWith(
    fetch(req, { cache: 'no-store' }).then(function (res) {
      if (res && res.ok) {
        var copy = res.clone();
        caches.open(CACHE).then(function (c) { c.put(req, copy); });
      }
      return res;
    }).catch(function () {
      return caches.match(req).then(function (hit) {
        return hit || caches.match('index.html');
      });
    })
  );
});
