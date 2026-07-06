const CACHE = 'hgc-v1.5';
const ASSETS = [
  '/hgc-nhap-lieu/',
  '/hgc-nhap-lieu/index.html',
  '/hgc-nhap-lieu/css/app.css',
  '/hgc-nhap-lieu/js/app.js?v=20260627e',
  '/hgc-nhap-lieu/js/lsx_data.js?v=20260627e',
  '/hgc-nhap-lieu/js/plan.js?v=20260627e',
  '/hgc-nhap-lieu/js/entry.js?v=20260706a',
  '/hgc-nhap-lieu/js/summary.js?v=20260627e',
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
  const url = e.request.url;
  // JS files: luôn lấy từ network (không dùng cache cũ)
  if (url.includes('/js/')) {
    e.respondWith(fetch(e.request).catch(() => caches.match(e.request)));
    return;
  }
  e.respondWith(
    caches.match(e.request).then(r => r || fetch(e.request).catch(() =>
      caches.match('/hgc-nhap-lieu/index.html')
    ))
  );
});
