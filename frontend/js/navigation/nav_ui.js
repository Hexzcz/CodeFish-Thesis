/**
 * What navigation says on screen, and the 2D/3D switch.
 *
 * Every sentence a walking person reads is written here, in the same plain
 * register as the rest of the resident's view — distance remaining, whether
 * they are on the route, what happens when the signal goes. No model
 * vocabulary reaches this file, and no measurement is invented in it: the
 * numbers come from the backend, the wording from plain_language.js.
 */

function showNavigationPanel(route) {
    document.getElementById('nav-panel').classList.remove('hidden');
    document.body.classList.add('navigating');
    document.getElementById('nav-destination').textContent =
        destinationName(route.properties);
    navRemaining((route.properties.total_length_km || 0) * 1000);
    navOnRoute();
}

function hideNavigationPanel() {
    document.getElementById('nav-panel').classList.add('hidden');
    document.body.classList.remove('navigating');
    navClearError();
}

// ── The numbers ─────────────────────────────────────────────────────────────

function navRemaining(metres) {
    const el = document.getElementById('nav-remaining');
    if (!el) return;
    el.textContent = formatDistance((metres || 0) / 1000);
    document.getElementById('nav-remaining-walk').textContent = walkingTime(metres || 0);
}

function navAccuracy(metres) {
    const el = document.getElementById('nav-accuracy');
    if (!el) return;
    // Worth saying only when it is bad enough to explain a jumpy marker.
    const poor = metres && metres > 30;
    el.textContent = poor ? `Location accurate to about ${Math.round(metres)} m` : '';
    el.classList.toggle('hidden', !poor);
}

// ── The status line ─────────────────────────────────────────────────────────

function navStatus(text, kind = 'neutral') {
    const el = document.getElementById('nav-status');
    if (!el) return;
    el.textContent = text;
    el.className = `nav-status nav-status-${kind}`;
}

function navOnRoute() {
    navStatus('Following your location', 'good');
}

function navOffRoute() {
    navStatus('You are off the recommended route', 'warn');
}

function navRerouting() {
    navStatus('Updating your route…', 'warn');
}

function navRerouted(route) {
    navStatus('Safer route updated', 'good');
    navRemaining((route.properties.total_length_km || 0) * 1000);
}

function navRerouteFailed(message) {
    navStatus('Could not update your route — keep following the one shown', 'warn');
    navError(message);
}

function navRerouteUnavailable() {
    navStatus('You are off the route, and offline', 'warn');
    navError('Your route cannot be updated without a connection. The route shown is the last safe one worked out for you.');
}

/**
 * Offline: still following, but no longer checking.
 *
 * Says both halves out loud. Distance remaining and off-route warnings are
 * worked out by the server, so without it they stop — and a silent "you are
 * on track" would be a claim the app cannot make.
 */
function navOfflineProgress() {
    navStatus('Following your location — offline', 'warn');
    const el = document.getElementById('nav-remaining');
    if (el) el.textContent = '—';
    const walk = document.getElementById('nav-remaining-walk');
    if (walk) {
        walk.textContent = 'Distance left and route checks need a connection';
    }
}

function navArrived() {
    navStatus('You have arrived', 'good');
    const walk = document.getElementById('nav-remaining-walk');
    if (walk) walk.textContent = 'Stay safe';
}

function navError(message) {
    const el = document.getElementById('nav-error');
    if (!el) return;
    el.textContent = message;
    el.classList.remove('hidden');
}

function navClearError() {
    const el = document.getElementById('nav-error');
    if (el) el.classList.add('hidden');
}

// ── Switching between the two maps ──────────────────────────────────────────

async function enter3DMode() {
    document.getElementById('map-3d').classList.remove('hidden');
    document.getElementById('map').classList.add('hidden');
    document.body.classList.add('map-3d-active');
    _setModeButtons('3d');

    const map = await ensure3DMap();
    map.resize();
    return map;
}

function exit3DMode() {
    document.getElementById('map-3d').classList.add('hidden');
    document.getElementById('map').classList.remove('hidden');
    document.body.classList.remove('map-3d-active');
    _setModeButtons('2d');
    if (window.appState.map) window.appState.map.invalidateSize();
}

/**
 * The 2D/3D switch outside navigation: 2D stays the view for reading the whole
 * route and the flood picture, 3D for walking it.
 */
async function switchMapMode(mode) {
    if (mode === '3d') {
        try {
            await enter3DMode();
            const routes = (window.appState.routeData || {}).routes || [];
            const route = routes[Math.max(0, window.appState.activeRouteIndex || 0)];
            if (route) {
                show3DRoute(route, destinationName(route.properties));
                const coords = ((route.geometry || {}).coordinates || []).flat();
                if (coords.length) get3DMap().jumpTo({ center: coords[0], zoom: 16.5, pitch: 55 });
            }
        } catch (e) {
            exit3DMode();
            navError(e.message || 'The 3D map could not be loaded.');
        }
        return;
    }
    exit3DMode();
}

function _setModeButtons(mode) {
    const to2d = document.getElementById('map-mode-2d');
    const to3d = document.getElementById('map-mode-3d');
    if (to2d) to2d.classList.toggle('active', mode === '2d');
    if (to3d) to3d.classList.toggle('active', mode === '3d');
}
