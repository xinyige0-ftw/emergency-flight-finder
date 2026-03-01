const CACHE = 'evac-v5';
const STATIC = ['/manifest.json', '/icon.svg'];

self.addEventListener('install', e => {
  // Pre-cache static assets only (NOT the HTML page itself)
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(STATIC)));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  // Delete all old caches on activation
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  const url = e.request.url;

  // API calls: network first, fall back to cache
  if (url.includes('/api/')) {
    e.respondWith(
      fetch(e.request)
        .then(r => {
          if (r.ok) {
            const clone = r.clone();
            caches.open(CACHE).then(c => c.put(e.request, clone));
          }
          return r;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }

  // HTML pages (including '/'): always network first, never serve stale HTML
  if (e.request.mode === 'navigate' || url.endsWith('/') || url.endsWith('.html')) {
    e.respondWith(
      fetch(e.request).catch(() => caches.match('/'))
    );
    return;
  }

  // Everything else: cache first
  e.respondWith(caches.match(e.request).then(r => r || fetch(e.request)));
});
