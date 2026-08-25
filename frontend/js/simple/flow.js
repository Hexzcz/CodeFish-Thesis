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
            simpleError('Could not get your location. Tap the map to show where you are.');
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
        toggleEvacCenters(true);
        drawAllRoutes(data.routes);
        renderSimpleResult(data.routes);
        simpleShow('result');
    } catch (err) {
        console.error('Route error:', err);
        simpleShow('asking');
        simpleError(err.message || 'Could not find a route from there.');
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

document.addEventListener('DOMContentLoaded', () => {
    if (currentMode() !== 'simple') return;

    if (!navigator.geolocation) {
        const btn = document.getElementById('simple-locate-btn');
        if (btn) btn.classList.add('hidden');
    }

    simpleShow('asking');
});
