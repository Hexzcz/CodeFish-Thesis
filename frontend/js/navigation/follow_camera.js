/**
 * The camera that walks with you.
 *
 * Keeps the person near the bottom of the screen looking forward, the way a
 * car navigator does, and turns the map to match their heading when one is
 * available. Panning the map by hand stops the following until "Recenter on
 * me" is pressed — a map that fights the user is worse than one that waits.
 */

const FOLLOW_ZOOM = 17.5;
const FOLLOW_PITCH = 60;
// How far down the *visible* map the walker should sit: most of the screen
// should show what is ahead of them, not behind.
const FOLLOW_POSITION_RATIO = 0.62;
const EASE_MS = 900;

let following = true;
let userMarker = null;
let lastBearing = 0;

function setFollowing(value) {
    following = value;
    const button = document.getElementById('nav-recenter-btn');
    if (button) button.classList.toggle('hidden', value);
}

function isFollowing() {
    return following;
}

/** Draw (or move) the "you are here" marker, and follow it if we are meant to. */
function updateUserPosition(map, fix) {
    if (!map) return;

    if (!userMarker) {
        userMarker = _createUserMarker(map, fix);
    } else {
        userMarker.setLngLat([fix.lon, fix.lat]);
    }

    if (fix.heading !== null && fix.heading !== undefined) {
        lastBearing = fix.heading;
        _pointMarker(lastBearing - (map.getBearing() || 0));
    }

    if (!following) return;

    map.easeTo({
        center: [fix.lon, fix.lat],
        zoom: Math.max(map.getZoom(), FOLLOW_ZOOM),
        pitch: FOLLOW_PITCH,
        bearing: fix.heading !== null && fix.heading !== undefined ? fix.heading : map.getBearing(),
        offset: _followOffset(map),
        duration: EASE_MS,
        // Do not fight a finger that is already on the map.
        essential: true,
    });

    // Heading-up means the arrow points at the top of the screen.
    _pointMarker(0);
}

/**
 * Where on screen to put the walker.
 *
 * The answer panel covers the bottom of a phone and the left of a laptop, so
 * centring on the map's midpoint buries the marker underneath it. This aims
 * for the middle of whatever is actually visible.
 */
function _followOffset(map) {
    const panel = document.getElementById('simple-shell');
    const size = map.getContainer().getBoundingClientRect();
    if (!panel) return [0, 0];

    const rect = panel.getBoundingClientRect();
    const isBottomSheet = rect.width >= size.width * 0.9;

    if (isBottomSheet) {
        const visibleHeight = Math.max(rect.top - size.top, size.height * 0.35);
        return [0, visibleHeight * FOLLOW_POSITION_RATIO - size.height / 2];
    }

    // Card on the left: shift the walker right of it, and low in the frame.
    const covered = Math.min(rect.right - size.left, size.width * 0.45);
    return [covered / 2, size.height * (FOLLOW_POSITION_RATIO - 0.5)];
}

function recenterOnUser(map, fix) {
    setFollowing(true);
    if (fix) updateUserPosition(map, fix);
}

function _createUserMarker(map, fix) {
    const element = document.createElement('div');
    element.className = 'nav-user-marker';
    element.innerHTML = `
        <div class="num-accuracy"></div>
        <div class="num-arrow"></div>`;
    return new window.maplibregl.Marker({ element, rotationAlignment: 'map' })
        .setLngLat([fix.lon, fix.lat])
        .addTo(map);
}

function _pointMarker(degrees) {
    if (!userMarker) return;
    const arrow = userMarker.getElement().querySelector('.num-arrow');
    if (arrow) arrow.style.transform = `rotate(${degrees}deg)`;
}

function removeUserMarker() {
    if (!userMarker) return;
    userMarker.remove();
    userMarker = null;
}
