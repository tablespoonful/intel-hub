/**
 * PWA support for the dashboard (dev-spec section 5): web app manifest, service
 * worker and icons. Everything is served same-origin by this Worker.
 *
 * Caching strategy is network-first for every same-origin GET, so an online
 * dashboard always shows fresh data; the cache is only an offline fallback.
 * Responses served from cache carry `X-Intel-Hub-Offline: 1` so the page can
 * tell the user the data is stale.
 */

import ICON_SVG from "./assets/icon.svg";
import ICON_192 from "./assets/icon-192.png";
import ICON_512 from "./assets/icon-512.png";
import APPLE_TOUCH_ICON from "./assets/apple-touch-icon.png";

/** Bump to drop every cached response on the next service worker activation. */
const CACHE_NAME = "intel-hub-v1";

const SHELL_PATHS = ["/", "/manifest.webmanifest", "/icon.svg", "/icon-192.png", "/icon-512.png", "/apple-touch-icon.png"];

const MANIFEST = {
  name: "intel-hub",
  short_name: "intel-hub",
  description: "AI・テクノロジーと金融市場のインテリジェンス",
  lang: "ja",
  start_url: "/",
  scope: "/",
  display: "standalone",
  background_color: "#0d1117",
  theme_color: "#161b22",
  icons: [
    { src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
    { src: "/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
    { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
    { src: "/icon-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
  ],
};

const SERVICE_WORKER_JS = `"use strict";
var CACHE = ${JSON.stringify(CACHE_NAME)};
var SHELL = ${JSON.stringify(SHELL_PATHS)};

self.addEventListener("install", function (event) {
  event.waitUntil(
    caches.open(CACHE)
      .then(function (cache) { return cache.addAll(SHELL); })
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener("activate", function (event) {
  event.waitUntil(
    caches.keys()
      .then(function (keys) {
        return Promise.all(keys.filter(function (k) {
          return k.indexOf("intel-hub-") === 0 && k !== CACHE;
        }).map(function (k) { return caches.delete(k); }));
      })
      .then(function () { return self.clients.claim(); })
  );
});

function offline(response) {
  var headers = new Headers(response.headers);
  headers.set("X-Intel-Hub-Offline", "1");
  return response.blob().then(function (body) {
    return new Response(body, { status: response.status, statusText: response.statusText, headers: headers });
  });
}

function noCache() {
  return new Response(JSON.stringify({ ok: false, error: "offline" }), {
    status: 503,
    headers: { "Content-Type": "application/json; charset=utf-8", "X-Intel-Hub-Offline": "1" },
  });
}

self.addEventListener("fetch", function (event) {
  var req = event.request;
  if (req.method !== "GET") return;
  var url = new URL(req.url);
  if (url.origin !== self.location.origin || url.pathname === "/sw.js") return;

  event.respondWith(
    fetch(req)
      .then(function (res) {
        if (res.ok) {
          var copy = res.clone();
          event.waitUntil(caches.open(CACHE).then(function (cache) { return cache.put(req, copy); }));
        }
        return res;
      })
      .catch(function () {
        var key = req.mode === "navigate" ? "/" : req;
        return caches.match(key).then(function (hit) { return hit ? offline(hit) : noCache(); });
      })
  );
});
`;

const ICON_HEADERS = { "Cache-Control": "public, max-age=86400" };

/** Returns the PWA response for `path`, or null when the path is not a PWA asset. */
export function handlePwa(path: string): Response | null {
  switch (path) {
    case "/manifest.webmanifest":
      return new Response(JSON.stringify(MANIFEST), {
        headers: { "Content-Type": "application/manifest+json; charset=utf-8" },
      });
    case "/sw.js":
      return new Response(SERVICE_WORKER_JS, {
        headers: { "Content-Type": "text/javascript; charset=utf-8", "Cache-Control": "no-cache" },
      });
    case "/icon.svg":
      return new Response(ICON_SVG, { headers: { "Content-Type": "image/svg+xml", ...ICON_HEADERS } });
    case "/icon-192.png":
      return new Response(ICON_192, { headers: { "Content-Type": "image/png", ...ICON_HEADERS } });
    case "/icon-512.png":
      return new Response(ICON_512, { headers: { "Content-Type": "image/png", ...ICON_HEADERS } });
    case "/apple-touch-icon.png":
      return new Response(APPLE_TOUCH_ICON, { headers: { "Content-Type": "image/png", ...ICON_HEADERS } });
    default:
      return null;
  }
}
