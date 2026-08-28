/**
 * The simple view, as a small state machine.
 *
 *   asking → locating → routing → result
 *              │           │
 *              └─ error ───┘  (back to asking, with a reason)
 *
 * One question on screen at a time. The rainfall scenario is chosen for the
 * person from the latest JAXA reading rather than asked about, because
 * "5-year vs 100-year return period" is not a question a resident can answer.
 */

const SIMPLE_STEPS = ['asking', 'locating', 'routing', 'result'];

function simpleShow(step) {
    if (!SIMPLE_STEPS.includes(step)) return;
    SIMPLE_STEPS.forEach(name => {
        const el = document.getElementById(`simple-${name}`);
        if (el) el.classList.toggle('hidden', name !== step);
    });
    window.appState.simpleStep = step;
}

function simpleError(message) {
    const el = document.getElementById('simple-error');
    if (!el) return;
    el.textContent = message;
    el.classList.remove('hidden');
}

function simpleClearError() {
    const el = document.getElementById('simple-error');
    if (el) el.classList.add('hidden');
}

/** Ask the browser where we are. Only offered when the browser supports it. */
function simpleUseMyLocation() {
    simpleClearError();
    if (!navigator.geolocation) {
        simpleError('This browser cannot share your location. Tap the map instead.');
        return;
    }

    simpleShow('locating');
    navigator.geolocation.getCurrentPosition(
        (position) => {
            const latlng = { lat: position.coords.latitude, lng: position.coords.longitude };
            window.appState.map.setView([latlng.lat, latlng.lng], 17);
            setOrigin(latlng);
        },
        () => {
            simpleShow('asking');
            simpleError(t('could_not_get_location'));
        },
        { enableHighAccuracy: true, timeout: 10000 }
    );
}

/** Arm the map so the next click sets the origin. */
function simpleTapTheMap() {
    simpleClearError();
    window.appState.placingOrigin = true;
    if (window.appState.map) window.appState.map.getContainer().style.cursor = 'crosshair';
    const hint = document.getElementById('simple-tap-hint');
    if (hint) hint.classList.remove('hidden');
}

/** Start over: forget the origin and the routes, ask the question again. */
function simpleStartOver() {
    clearRoutes();
    clearBaselineRoute();
    removeOriginMarker();
    window.appState.originCoords = null;
    window.appState.routeData = null;
    simpleClearError();
    toggleEvacCenters(false);
    const hint = document.getElementById('simple-tap-hint');
    if (hint) hint.classList.add('hidden');
    simpleShow('asking');
}

async function simpleFindRoute() {
    simpleShow('routing');
    const origin = window.appState.originCoords;

    try {
        const data = await requestRoutes({
            lat: origin.lat,
            lon: origin.lng,
            scenario: window.appState.scenario,
            weights: window.appState.weights,
            penaltyFactor: window.appState.penaltyFactor,
        });

        window.appState.routeData = data;
        rememberLastRoute(data, { lat: origin.lat, lng: origin.lng });
        toggleEvacCenters(true);
        drawAllRoutes(data.routes);
        // Show the panel before fitting the map: the result panel is taller
        // than the spinner it replaces, and fitting to the smaller one leaves
        // the route half-hidden under the sheet on a phone.
        simpleShow('result');
        renderSimpleResult(data.routes);
    } catch (err) {
        console.error('Route error:', err);
        simpleShow('asking');
        simpleError(navigator.onLine
            ? (err.message || t('no_route_from_there'))
            : t('offline_no_new_route'));
        offerLastRoute();
    }
}

// In simple mode, placing the origin is the whole question — so answering it
// starts the search immediately, with no second button to press.
document.addEventListener('codefish:origin-set', () => {
    if (currentMode() !== 'simple') return;
    const hint = document.getElementById('simple-tap-hint');
    if (hint) hint.classList.add('hidden');
    simpleFindRoute();
});

/**
 * Show the route this browser was last given.
 *
 * Only ever offered when a fresh one cannot be worked out, and always labelled
 * with its age — a route from this morning is not advice about right now.
 */
function offerLastRoute() {
    const saved = recallLastRoute();
    const button = document.getElementById('simple-last-route-btn');
    if (!button) return;

    if (!saved) {
        button.classList.add('hidden');
        return;
    }
    button.textContent = `Show my last route (${describeAge(saved.savedAt)})`;
    button.classList.remove('hidden');
}

function showLastRoute() {
    const saved = recallLastRoute();
    if (!saved) return;

    window.appState.routeData = { routes: saved.routes, destination: saved.destination };
    if (saved.origin) createOriginMarker(saved.origin);
    drawAllRoutes(saved.routes);
    simpleShow('result');
    renderSimpleResult(saved.routes);

    const stamp = document.getElementById('simple-stale');
    if (stamp) {
        stamp.textContent = `Worked out ${describeAge(saved.savedAt)}, before you went offline. Conditions may have changed.`;
        stamp.classList.remove('hidden');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    if (currentMode() !== 'simple') return;

    if (!navigator.geolocation) {
        const btn = document.getElementById('simple-locate-btn');
        if (btn) btn.classList.add('hidden');
    }

    // Offline on arrival: there is nothing to ask for, so lead with what we
    // already know rather than a button that cannot work.
    if (!navigator.onLine) {
        simpleError(t('offline_no_new_route'));
        offerLastRoute();
    }

    simpleShow('asking');
});
