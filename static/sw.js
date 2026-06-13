const CACHE = 'aether-v3';
const NETWORK_FIRST = ['/', '/app.js', '/style.css', '/index.html'];
const ASSETS = [
  '/',
  '/style.css',
  '/app.js',
  '/manifest.json',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  'https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js',
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
});

self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;

  const url = new URL(e.request.url);
  const isNetFirst = NETWORK_FIRST.some(p => url.pathname === p || url.pathname.endsWith(p));

  if (isNetFirst) {
    e.respondWith(
      fetch(e.request)
        .then(res => {
          const clone = res.clone();
          caches.open(CACHE).then(c => c.put(e.request, clone));
          return res;
        })
        .catch(() => caches.match(e.request))
    );
  } else {
    e.respondWith(
      caches.match(e.request).then((cached) => cached || fetch(e.request))
    );
  }
});

self.addEventListener('push', (e) => {
  let data = { title: 'AETHER', body: '', url: '/' };
  try {
    if (e.data) data = { ...data, ...e.data.json() };
  } catch (_) {}

  const options = {
    body: data.body,
    icon: '/icons/icon-192.png',
    badge: '/icons/icon-192.png',
    data: { url: data.url },
    requireInteraction: true,
  };

  e.waitUntil(self.registration.showNotification(data.title, options));
});

self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  const url = e.notification.data?.url || '/';
  e.waitUntil(clients.matchAll({ type: 'window' }).then((clientsList) => {
    for (const c of clientsList) {
      if (c.url.includes(self.location.origin) && 'focus' in c) return c.focus();
    }
    if (clients.openWindow) return clients.openWindow(url);
  }));
});
