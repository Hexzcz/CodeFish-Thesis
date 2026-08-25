/**
 * Navigation: the thing that runs while somebody is walking.
 *
 * Owns the sequence — permission, first fix, 3D camera, follow, progress,
 * rerouting — and nothing else. The pieces it drives each know one job:
 * live_location.js watches the GPS, map_3d.js draws, follow_camera.js moves
 * the camera, nav_ui.js writes the words on screen.
 *
 * Two rules this file exists to keep:
 *
 *   · Where you are along the route is decided by the backend
 *     (POST /navigation/progress), not by geometry copied into the browser.
 *   · Rerouting calls the same POST /route the app has always used, with the
 *     same criteria. There is no second router here, and no shortest-distance
 *     fallback — a flood-aware route is the only kind this app gives.
 */

// Ask the server where we are on the route no more often than this, and only
// after moving far enough to matter. Walking pace makes that roughly one call
// every ten seconds rather than one per GPS fix.
const PROGRESS_MIN_INTERVAL_MS = 2000;
const PROGRESS_MIN_MOVE_M = 15;

// One stray fix is not a wrong turn. Three in a row is.
const OFF_ROUTE_FIXES_BEFORE_REROUTE = 3;
// ...and never reroute more often than this, however lost someone gets.
const REROUTE_COOLDOWN_MS = 20000;

const session = {
    active: false,
    // '3d' normally; '2d' when this device could not start the 3D view.
    mode: '3d',
    route: null,          // the GeoJSON feature being followed
    coordinates: [],      // [[lon, lat], ...] handed to the progress endpoint
    lastFix: null,
    lastProgressAt: 0,
    lastProgressFix: null,
    offRouteStreak: 0,
    lastRerouteAt: 0,
    rerouting: false,
};

function isNavigating() {
    return session.active;
}

/** Start following the recommended route. */
async function startNavigation() {
    const routes = (window.appState.routeData || {}).routes || [];
    const index = Math.max(0, window.appState.activeRouteIndex || 0);
    const route = routes[index] || routes.find(r => r.properties.recommended) || routes[0];
    if (!route) return;

    session.active = true;
    session.mode = '3d';
    session.route = route;
    session.coordinates = _flatCoordinates(route);
    session.offRouteStreak = 0;
    session.rerouting = false;

    showNavigationPanel(route);
    navStatus('Finding your location…');

    try {
        await enter3DMode();
        show3DRoute(route, destinationName(route.properties));
    } catch (e) {
        // Losing the 3D view must not cost someone live tracking: fall back
        // to following them on the flat map, and say so once.
        console.warn('[nav] 3D unavailable, following in 2D:', e.message);
        session.mode = '2d';
        exit3DMode();
        navError(`${e.message} Following your location on the flat map instead.`);
    }

    setFollowing(true);
    if (!startWatchingPosition()) return;    // its own error event explains why
}

function stopNavigation() {
    session.active = false;
    session.route = null;
    session.coordinates = [];
    session.lastFix = null;
    session.offRouteStreak = 0;

    stopWatchingPosition();
    removeUserMarker();
    removeUserMarker2D();
    hideNavigationPanel();
    exit3DMode();
}

// ── Reacting to the world ───────────────────────────────────────────────────

document.addEventListener('codefish:position', (event) => {
    if (!session.active) return;
    const fix = event.detail;
    session.lastFix = fix;

    // A fix arriving means whatever went wrong before is over — a stale
    // "permission refused" sitting under a working blue dot is just confusing.
    navClearError();

    if (session.mode === '3d') {
        updateUserPosition(get3DMap(), fix);
    } else {
        updateUserPosition2D(window.appState.map, fix, isFollowing());
    }
    navAccuracy(fix.accuracy);
    _maybeCheckProgress(fix);
});

document.addEventListener('codefish:position-error', (event) => {
    if (!session.active) return;
    navError(event.detail.message);
});

document.addEventListener('codefish:map-dragged', () => {
    if (session.active) setFollowing(false);
});

// A phone that sleeps mid-evacuation should not keep the GPS running.
document.addEventListener('pagehide', () => {
    if (session.active) stopWatchingPosition();
});
document.addEventListener('visibilitychange', () => {
    if (!session.active) return;
    if (document.visibilityState === 'visible') startWatchingPosition();
});

// ── Progress, and going the wrong way ───────────────────────────────────────

async function _maybeCheckProgress(fix) {
    const now = Date.now();
    const moved = session.lastProgressFix ? _metresBetween(session.lastProgressFix, fix) : Infinity;
    if (now - session.lastProgressAt < PROGRESS_MIN_INTERVAL_MS) return;
    if (moved < PROGRESS_MIN_MOVE_M && session.lastProgressFix) return;

    session.lastProgressAt = now;
    session.lastProgressFix = fix;

    if (!navigator.onLine) {
        navOfflineProgress();
        return;
    }

    try {
        const res = await fetch(`${API_BASE}/navigation/progress`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lat: fix.lat, lon: fix.lon, route: session.coordinates }),
        });
        const progress = await res.json();
        if (!res.ok) throw new Error(progress.detail || `HTTP ${res.status}`);
        _applyProgress(progress);
    } catch (e) {
        // A failed check is not a wrong turn; say nothing and try the next fix.
        console.warn('[nav] progress check failed:', e.message);
        navOfflineProgress();
    }
}

function _applyProgress(progress) {
    navRemaining(progress.remaining_m);

    if (progress.arrived) {
        navArrived();
        stopWatchingPosition();
        return;
    }

    if (!progress.off_route) {
        session.offRouteStreak = 0;
        navOnRoute();
        return;
    }

    session.offRouteStreak += 1;
    navOffRoute();
    if (session.offRouteStreak >= OFF_ROUTE_FIXES_BEFORE_REROUTE) _reroute();
}

/**
 * Ask for a new safer route from where the person actually is.
 *
 * This is the same endpoint, weights and ranking the app used to choose the
 * first route. Nothing here re-implements routing, and if it fails the old
 * route stays on screen rather than being replaced by something shorter.
 */
async function _reroute() {
    const now = Date.now();
    if (session.rerouting || now - session.lastRerouteAt < REROUTE_COOLDOWN_MS) return;

    if (!navigator.onLine) {
        navRerouteUnavailable();
        return;
    }

    session.rerouting = true;
    session.lastRerouteAt = now;
    navRerouting();

    try {
        const data = await requestRoutes({
            lat: session.lastFix.lat,
            lon: session.lastFix.lon,
            scenario: window.appState.scenario,
            weights: window.appState.weights,
            penaltyFactor: window.appState.penaltyFactor,
        });

        const best = data.routes.find(r => r.properties.recommended) || data.routes[0];
        window.appState.routeData = data;
        window.appState.activeRouteIndex = data.routes.indexOf(best);
        rememberLastRoute(data, { lat: session.lastFix.lat, lng: session.lastFix.lon });

        session.route = best;
        session.coordinates = _flatCoordinates(best);
        session.offRouteStreak = 0;

        drawAllRoutes(data.routes);           // keep the 2D view in step
        if (session.mode === '3d') show3DRoute(best, destinationName(best.properties));
        renderSimpleResult(data.routes);
        navRerouted(best);
    } catch (e) {
        console.error('[nav] reroute failed:', e);
        navRerouteFailed(e.message);
    } finally {
        session.rerouting = false;
    }
}

function recenterNavigation() {
    if (session.mode === '3d') {
        recenterOnUser(get3DMap(), session.lastFix);
        return;
    }
    setFollowing(true);
    if (session.lastFix) updateUserPosition2D(window.appState.map, session.lastFix, true);
}

function _flatCoordinates(route) {
    return ((route.geometry || {}).coordinates || []).flat();
}

function _metresBetween(a, b) {
    const dy = (a.lat - b.lat) * 111320;
    const dx = (a.lon - b.lon) * 107600;
    return Math.sqrt(dx * dx + dy * dy);
}
