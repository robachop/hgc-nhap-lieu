const CACHE = 'hgc-v1.0';
const ASSETS = [
  '/hgc-nhap-lieu/',
  '/hgc-nhap-lieu/index.html',
  '/hgc-nhap-lieu/css/app.css',
  '/hgc-nhap-lieu/js/app.js',
  '/hgc-nhap-lieu/js/lsx_data.js',
  '/hgc-nhap-lieu/js/plan.js',
  '/hgc-nhap-lieu/js/entry.js',
  '/hgc-nhap-lieu/js/summary.js',
  'https://cdn.jsdelivr.net/npm/qrcode@1.5.3/build/qrcode.min.js',
  'https://cdn.sheetjs.com/xlsx-0.20.3/package/dist/xlsx.full.min.js'
];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).catch(() => {}));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
  ));
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request).catch(() =>
      caches.match('/hgc-nhap-lieu/index.html')
    ))
  );
});
