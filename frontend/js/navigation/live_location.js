/**
 * Where the person actually is, updated as they walk.
 *
 * One watcher for the whole app, started only when navigation starts — a
 * background GPS watch is a battery drain and a permission prompt nobody
 * asked for. Every fix is announced as `codefish:position`; failures are
 * announced as `codefish:position-error` with a sentence a resident can act
 * on, because "PERMISSION_DENIED" is not one.
 *
 * Geolocation needs HTTPS (or localhost). Over plain http from another
 * machine the browser refuses silently, which is why the error path says so.
 */

const GPS_OPTIONS = {
    enableHighAccuracy: true,
    // A fix older than this is not where you are now.
    maximumAge: 5000,
    timeout: 20000,
};

// Below this speed a phone's reported heading is noise, so it is ignored and
// the bearing is derived from movement instead.
const HEADING_MIN_SPEED_MS = 0.5;

let watchId = null;
let lastFix = null;

function isLiveLocationSupported() {
    return 'geolocation' in navigator;
}

function isLiveLocationBlocked() {
    // Secure-context rule: browsers disable geolocation on plain http.
    return !window.isSecureContext;
}

/** Begin watching. Safe to call twice; the second call is ignored. */
function startWatchingPosition() {
    if (watchId !== null) return true;

    if (!isLiveLocationSupported()) {
        _fail(t('location_not_supported'));
        return false;
    }
    if (isLiveLocationBlocked()) {
        _fail(t('location_needs_https'));
        return false;
    }

    watchId = navigator.geolocation.watchPosition(_onFix, _onError, GPS_OPTIONS);
    return true;
}

function stopWatchingPosition() {
    if (watchId === null) return;
    navigator.geolocation.clearWatch(watchId);
    watchId = null;
    lastFix = null;
}

function isWatchingPosition() {
    return watchId !== null;
}

function _onFix(position) {
    const fix = {
        lat: position.coords.latitude,
        lon: position.coords.longitude,
        accuracy: position.coords.accuracy,
        speed: position.coords.speed,
        heading: _headingFor(position),
        at: position.timestamp,
    };
    lastFix = fix;
    document.dispatchEvent(new CustomEvent('codefish:position', { detail: fix }));
}

/**
 * A bearing to point the map along.
 *
 * `coords.heading` is null on most devices unless moving, and on iOS it is
 * often null entirely. Falling back to the direction between the last two
 * fixes gives a usable course whenever someone is actually walking.
 */
function _headingFor(position) {
    const reported = position.coords.heading;
    const speed = position.coords.speed;
    if (reported !== null && !Number.isNaN(reported) && (speed === null || speed > HEADING_MIN_SPEED_MS)) {
        return reported;
    }

    if (!lastFix) return null;
    const moved = _metresBetween(lastFix, {
        lat: position.coords.latitude,
        lon: position.coords.longitude,
    });
    if (moved < 5) return lastFix.heading;   // standing still: hold the last one

    return _bearingBetween(lastFix, {
        lat: position.coords.latitude,
        lon: position.coords.longitude,
    });
}

function _onError(error) {
    const messages = {
        1: t('location_refused'),
        2: t('location_unavailable'),
        3: t('location_slow'),
    };
    _fail(messages[error.code] || t('location_failed'));
}

function _fail(message) {
    document.dispatchEvent(new CustomEvent('codefish:position-error', { detail: { message } }));
}

function _metresBetween(a, b) {
    const dy = (a.lat - b.lat) * 111320;
    const dx = (a.lon - b.lon) * 107600;
    return Math.sqrt(dx * dx + dy * dy);
}

function _bearingBetween(from, to) {
    const y = (to.lon - from.lon) * 107600;
    const x = (to.lat - from.lat) * 111320;
    return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
}
