/**
 * The service worker: what CodeFish can still do with no signal.
 *
 * Be honest about what offline means here. Routing is a POST to the server —
 * it cannot work without a connection, and no cache can fake it. What this
 * buys is real but narrower:
 *
 *   · the app opens instantly, and opens at all, when the network is gone
 *   · the district boundary, roads and centers are already there
 *   · basemap tiles you have already looked at still draw
 *
 * The last route you were given is kept by the page itself, in localStorage,
 * so someone who asked before losing signal can still read their directions.
 */

const VERSION = 'v1';
const SHELL_CACHE = `codefish-shell-${VERSION}`;
const DATA_CACHE = `codefish-data-${VERSION}`;
const TILE_CACHE = `codefish-tiles-${VERSION}`;

// Basemap tiles are unbounded; keep a working set, not the whole city.
const MAX_TILES = 300;

// Everything index.html loads. Hand-maintained, and guarded by
// tests/test_pwa_assets.py — rename a file without touching this list and the
// test fails rather than the app quietly losing its offline copy.
const SHELL = [
    '/',
    '/index.html',
    '/manifest.webmanifest',
    '/vendor/leaflet/leaflet.js',
    '/vendor/leaflet/leaflet.css',
    '/icons/icon-192.png',
    '/icons/icon-512.png',
    '/icons/apple-touch-icon.png',
    '/css/base.css',
    '/css/sidebar.css',
    '/css/routing_panel.css',
    '/css/layer_controls.css',
    '/css/rainfall_controls.css',
    '/css/bottom_bar.css',
    '/css/analysis_panel.css',
    '/css/segments_tab.css',
    '/css/compare_tab.css',
    '/css/decision_matrix.css',
    '/css/map.css',
    '/css/simple.css',
    '/css/simple_result.css',
    '/css/simple_phone.css',
    '/css/admin_phone.css',
    '/css/navigation.css',
    '/js/mode.js',
    '/js/i18n.js',
    '/js/config.js',
    '/js/state.js',
    '/js/ui/utils.js',
    '/js/map/init.js',
    '/js/map/boundary.js',
    '/js/layers/raster_layers.js',
    '/js/layers/road_layer.js',
    '/js/centers/evacuation_centers.js',
    '/js/routing/origin.js',
    '/js/routing/route_request.js',
    '/js/routing/route_layer.js',
    '/js/routing/route_visibility.js',
    '/js/routing/baseline_layer.js',
    '/js/routing/segment_highlight.js',
    '/js/routing/segment_hover.js',
    '/js/ui/a11y.js',
    '/js/ui/tabs.js',
    '/js/ui/sidebar.js',
    '/js/ui/rainfall.js',
    '/js/ui/bottom_bar.js',
    '/js/ui/panel/panel.js',
    '/js/ui/panel/overview.js',
    '/js/ui/panel/segments.js',
    '/js/ui/panel/baseline.js',
    '/js/ui/panel/compare.js',
    '/js/simple/plain_language.js',
    '/js/simple/result_card.js',
    '/js/simple/directions.js',
    '/js/simple/flow.js',
    '/js/navigation/live_location.js',
    '/js/navigation/map_3d.js',
    '/js/navigation/follow_camera.js',
    '/js/navigation/follow_2d.js',
    '/js/navigation/rainfall_watch.js',
    '/js/navigation/nav_ui.js',
    '/js/navigation/nav_session.js',
    '/js/pwa.js',
    '/js/app.js',
];

// Data the map needs to draw anything at all.
const DATA_PATHS = ['/boundary', '/roads', '/evacuation-centers'];

self.addEventListener('install', (event) => {
    event.waitUntil((async () => {
        const cache = await caches.open(SHELL_CACHE);
        // addAll fails the whole install if one file 404s, which would leave
        // the app with no worker at all. Take what we can get.
        await Promise.all(SHELL.map(url =>
            cache.add(url).catch(err => console.warn('[sw] skipped', url, err))
        ));
        self.skipWaiting();
    })());
});

self.addEventListener('activate', (event) => {
    event.waitUntil((async () => {
        const keep = [SHELL_CACHE, DATA_CACHE, TILE_CACHE];
        const names = await caches.keys();
        await Promise.all(names.filter(n => !keep.includes(n)).map(n => caches.delete(n)));
        await self.clients.claim();
    })());
});

self.addEventListener('fetch', (event) => {
    const { request } = event;
    if (request.method !== 'GET') return;   // /route is a POST: always live.

    const url = new URL(request.url);

    if (url.origin !== self.location.origin) {
        // Basemap tiles from either provider: keep what has been seen so the
        // map still draws where the signal does not.
        if (/tile|arcgis|basemaps|cartocdn/i.test(url.href)) event.respondWith(cacheFirstTile(request));
        return;
    }

    if (request.mode === 'navigate') {
        event.respondWith(networkFirst(request, SHELL_CACHE));
        return;
    }

    if (DATA_PATHS.some(path => url.pathname === path)) {
        event.respondWith(staleWhileRevalidate(request, DATA_CACHE));
        return;
    }

    if (url.pathname.startsWith('/tiles/')) {
        event.respondWith(cacheFirstTile(request));
        return;
    }

    // The 3D map library and its terrain: not precached (800 KB that a
    // resident who never opens 3D should not download), but kept once used,
    // so the second time works offline.
    if (url.pathname.startsWith('/vendor/maplibre/')) {
        event.respondWith(cacheFirst(request, SHELL_CACHE));
        return;
    }

    // Leaflet, icons and the manifest never change without a filename change:
    // serve them from cache and skip the network entirely.
    if (/^\/(vendor|icons)\//.test(url.pathname) || url.pathname === '/manifest.webmanifest') {
        event.respondWith(cacheFirst(request, SHELL_CACHE));
        return;
    }

    // Everything else — the app's own JS and CSS — is network-first.
    //
    // These are requested with a ?v= cache-buster that the precache does not
    // have, and matching loosely enough to find them would also match an
    // *older* version after a deploy. Going to the network when there is one
    // sidesteps that: the cache is the offline copy, not the fast path.
    event.respondWith(networkFirst(request, SHELL_CACHE));
});

/** Fresh page when online; the cached one rather than a dinosaur when not. */
async function networkFirst(request, cacheName) {
    try {
        const response = await fetch(request);
        if (response.ok) {
            const cache = await caches.open(cacheName);
            cache.put(request, response.clone());
        }
        return response;
    } catch (e) {
        // Offline. `ignoreSearch` is what lets a request for app.js?v=6 find
        // the app.js the install step stored without a version.
        const cached = await caches.match(request, { ignoreSearch: true });
        if (cached) return cached;
        if (request.mode === 'navigate') {
            const shell = await caches.match('/index.html');
            if (shell) return shell;
        }
        throw e;
    }
}

async function cacheFirst(request, cacheName) {
    const cached = await caches.match(request, { ignoreSearch: true });
    if (cached) return cached;

    const response = await fetch(request);
    if (response.ok) {
        const cache = await caches.open(cacheName);
        cache.put(request, response.clone());
    }
    return response;
}

/** Draw immediately from cache, refresh in the background for next time. */
async function staleWhileRevalidate(request, cacheName) {
    const cache = await caches.open(cacheName);
    const cached = await cache.match(request);

    const network = fetch(request).then(response => {
        if (response.ok) cache.put(request, response.clone());
        return response;
    }).catch(() => cached);

    return cached || network;
}

async function cacheFirstTile(request) {
    const cache = await caches.open(TILE_CACHE);
    const cached = await cache.match(request);
    if (cached) return cached;

    try {
        const response = await fetch(request);
        if (response.ok || response.type === 'opaque') {
            cache.put(request, response.clone());
            trimCache(TILE_CACHE, MAX_TILES);
        }
        return response;
    } catch (e) {
        // A missing tile leaves a grey square; the route still draws over it.
        return new Response('', { status: 504, statusText: 'tile unavailable offline' });
    }
}

/** Oldest-first eviction. Crude, but the alternative is an unbounded cache. */
async function trimCache(cacheName, maxEntries) {
    const cache = await caches.open(cacheName);
    const keys = await cache.keys();
    if (keys.length <= maxEntries) return;
    await Promise.all(keys.slice(0, keys.length - maxEntries).map(key => cache.delete(key)));
}
