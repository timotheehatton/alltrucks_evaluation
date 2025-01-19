const CACHE_NAME = "myapp-cache-v1";
const urlsToCache = [
    "/", // Cache the homepage
    "/static/manifest.json", // Cache the manifest file
    "/static/icons/icon-192x192.png", // Cache app icons
    "/static/icons/icon-512x512.png"
];

self.addEventListener("install", (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            return cache.addAll(urlsToCache);
        })
    );
});

self.addEventListener("fetch", (event) => {
    event.respondWith(
        caches.match(event.request).then((response) => {
            return response || fetch(event.request);
        })
    );
});