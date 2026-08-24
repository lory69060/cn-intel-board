const CACHE_NAME = "cn-intel-board-v1";
const URLS_TO_CACHE = [
  "./",
  "./qa.html",
  "./index.html",
  "./signal-board-structured.json",
  "./manifest.webmanifest",
  "./icons/icon-180.png",
  "./icons/icon-512.png",
  "./vendor/qrcode.min.js"
];

// Install: cache core assets
self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(URLS_TO_CACHE))
  );
  self.skipWaiting();
});

// Activate: clean old caches
self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch: cache-first for static assets, network-first for JSON
self.addEventListener("fetch", event => {
  const url = new URL(event.request.url);
  // JSON data: network-first (freshness matters)
  if (url.pathname.endsWith(".json")) {
    event.respondWith(
      fetch(event.request)
        .then(resp => {
          const clone = resp.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          return resp;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }
  // Everything else: cache-first
  event.respondWith(
    caches.match(event.request).then(cached => {
      return cached || fetch(event.request).then(network => {
        if (network && network.status === 200) {
          const clone = network.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return network;
      }).catch(() => cached);
    })
  );
});
