// Service worker InstaShoot — volontairement minimal.
// Objectif : rendre le site installable (PWA), sans jamais servir de données
// périmées (profils, demandes, messages...). Seuls les fichiers statiques
// (CSS, JS, icônes) sont mis en cache ; toutes les pages passent par le réseau.

const CACHE_NAME = "instashoot-static-v1";
const FICHIERS_STATIQUES = [
  "/static/css/style.css",
  "/static/js/main.js",
  "/static/icons/icon-192.png",
  "/static/icons/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(FICHIERS_STATIQUES)).catch(() => {})
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((noms) =>
      Promise.all(noms.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Uniquement les fichiers statiques passent par le cache (cache d'abord, réseau en secours).
  // Tout le reste (pages HTML, données) va toujours chercher le réseau en premier.
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.match(event.request).then((reponse) => reponse || fetch(event.request))
    );
  }
});
