/**
 * Watching the rain while somebody walks.
 *
 * The scenario is chosen once, when the page loads. An evacuation takes half
 * an hour, and the whole premise of this app is that conditions change — a
 * walk that begins under the 5-year model can end under the 100-year one, and
 * the safest route under one is not always the safest under another.
 *
 * So during navigation the rainfall reading is re-checked, and if it now maps
 * to a different flood model the session is told. Deciding what to do about
 * that is nav_session's job; this only reports.
 *
 * GSMaP publishes every half hour, so checking more often than this would ask
 * the same question of JAXA's FTP server repeatedly and get the same answer.
 */

const RAINFALL_CHECK_INTERVAL_MS = 5 * 60 * 1000;

// Rainfall is a nice-to-have during a walk; routing is not. After this many
// failures in a row the watcher gives up rather than retrying into a hole.
const MAX_CONSECUTIVE_FAILURES = 3;

let timer = null;
let failures = 0;

function startRainfallWatch() {
    if (timer !== null) return;
    failures = 0;
    timer = setInterval(checkRainfallNow, RAINFALL_CHECK_INTERVAL_MS);
}

function stopRainfallWatch() {
    if (timer === null) return;
    clearInterval(timer);
    timer = null;
}

function isWatchingRainfall() {
    return timer !== null;
}

/** Read the rain now. Announces a change of model; says nothing otherwise. */
async function checkRainfallNow() {
    if (!navigator.onLine) return null;

    let reading;
    try {
        const res = await fetch(`${API_BASE}/rainfall/jaxa?mode=forecast&step=1`);
        reading = await res.json();
        if (!res.ok) throw new Error(reading.detail || `HTTP ${res.status}`);
        failures = 0;
    } catch (e) {
        failures += 1;
        console.warn('[rain] could not read rainfall:', e.message);
        if (failures >= MAX_CONSECUTIVE_FAILURES) stopRainfallWatch();
        return null;
    }

    const before = window.appState.scenario;
    if (!reading.mapping || reading.mapping === before) return reading;

    document.dispatchEvent(new CustomEvent('codefish:scenario-changed', {
        detail: {
            from: before,
            to: reading.mapping,
            intensity: reading.intensity,
            heavier: _isHeavier(reading.mapping, before),
        },
    }));
    return reading;
}

// 5yr → 25yr → 100yr, in order of how much rain they stand for.
const SCENARIO_ORDER = ['5yr', '25yr', '100yr'];

function _isHeavier(next, previous) {
    return SCENARIO_ORDER.indexOf(next) > SCENARIO_ORDER.indexOf(previous);
}
