// QHLN como app: siempre pide primero la versión nueva a internet y guarda una copia.
// Sin señal, muestra la última copia guardada. Así nunca se ven resultados viejos teniendo conexión.
const CACHE = "qhln-v1";
const BASE = ["./", "index.html", "app.html", "dashboard.html", "terminos.html", "privacidad.html", "favicon.svg", "icono-180.png", "icono-192.png", "icono-512.png", "maquina.webp", "bolas.webp"];

self.addEventListener("install", e => {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(BASE)).catch(() => {}));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET" || new URL(req.url).origin !== location.origin) return; // fuentes y librerías externas: directo a internet
  e.respondWith(
    fetch(req).then(res => {
      if (res.ok) { const copia = res.clone(); caches.open(CACHE).then(c => c.put(req, copia)); }
      return res;
    }).catch(() => caches.match(req, { ignoreSearch: true }).then(m => m || (req.mode === "navigate" ? caches.match("index.html") : undefined)))
  );
});
