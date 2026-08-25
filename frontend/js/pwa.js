/**
 * Installing the app, and behaving sensibly when the signal goes.
 *
 * Three jobs:
 *   1. register the service worker (and reload once when a new one takes over)
 *   2. say plainly when routing is unavailable, rather than failing silently
 *   3. remember the last route, so someone who asked before losing signal can
 *      still read where they were told to go
 *
 * Service workers need HTTPS or localhost. On plain http from another machine
 * registration simply does not happen, and the app carries on as a website.
 */

const LAST_ROUTE_KEY = 'codefish.lastRoute';
const LAST_ROUTE_MAX_AGE_MS = 12 * 60 * 60 * 1000;   // half a day

if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js').catch(err =>
            console.warn('[pwa] service worker not registered:', err.message));
    });

    let reloading = false;
    navigator.serviceWorker.addEventListener('controllerchange', () => {
        if (reloading) return;
        reloading = true;
        window.location.reload();
    });
}

// ── Offline state ───────────────────────────────────────────────────────────

function updateOfflineBanner() {
    const banner = document.getElementById('offline-banner');
    if (!banner) return;
    banner.classList.toggle('hidden', navigator.onLine);
}

window.addEventListener('online', updateOfflineBanner);
window.addEventListener('offline', updateOfflineBanner);
document.addEventListener('DOMContentLoaded', updateOfflineBanner);

// ── The last route you were given ───────────────────────────────────────────

/** Keep the answer, not the whole response: enough to redraw the card. */
function rememberLastRoute(data, origin) {
    try {
        localStorage.setItem(LAST_ROUTE_KEY, JSON.stringify({
            savedAt: Date.now(),
            origin: origin,
            routes: data.routes,
            destination: data.destination,
        }));
    } catch (e) {
        // Storage full or blocked: losing the memory is not worth an error.
    }
}

function recallLastRoute() {
    try {
        const raw = localStorage.getItem(LAST_ROUTE_KEY);
        if (!raw) return null;
        const saved = JSON.parse(raw);
        if (Date.now() - saved.savedAt > LAST_ROUTE_MAX_AGE_MS) return null;
        return saved;
    } catch (e) {
        return null;
    }
}

function describeAge(savedAt) {
    const minutes = Math.round((Date.now() - savedAt) / 60000);
    if (minutes < 1) return 'just now';
    if (minutes < 60) return `${minutes} min ago`;
    const hours = Math.round(minutes / 60);
    return hours === 1 ? 'an hour ago' : `${hours} hours ago`;
}
