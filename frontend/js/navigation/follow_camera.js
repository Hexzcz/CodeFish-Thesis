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
// Position sits below centre so most of the screen shows what is ahead.
const FOLLOW_OFFSET = [0, 110];
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
        offset: FOLLOW_OFFSET,
        duration: EASE_MS,
        // Do not fight a finger that is already on the map.
        essential: true,
    });

    // Heading-up means the arrow points at the top of the screen.
    _pointMarker(0);
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
