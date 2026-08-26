/**
 * Following the walker on the flat map.
 *
 * The fallback for anything that cannot run the 3D view — an old phone, a
 * browser without usable WebGL, a page that started in the background. Live
 * tracking is the part that matters during an evacuation; the tilt is not,
 * so losing 3D must not cost someone their position on the map.
 */

let userMarker2d = null;

function updateUserPosition2D(map, fix, following) {
    if (!map) return;

    const latlng = [fix.lat, fix.lon];
    if (!userMarker2d) {
        const icon = L.divIcon({
            className: '',
            html: '<div class="nav-user-marker"><div class="num-accuracy"></div><div class="num-arrow"></div></div>',
            iconSize: [26, 26],
            iconAnchor: [13, 13],
        });
        userMarker2d = L.marker(latlng, {
            icon,
            zIndexOffset: 1000,
            title: 'Your current location',
            alt: 'Your current location',
        }).addTo(map);
    } else {
        userMarker2d.setLatLng(latlng);
    }

    const arrow = userMarker2d.getElement()?.querySelector('.num-arrow');
    if (arrow && fix.heading !== null && fix.heading !== undefined) {
        arrow.style.transform = `rotate(${fix.heading}deg)`;
    }

    if (following) map.panTo(latlng, { animate: true, duration: 0.8 });
}

function removeUserMarker2D() {
    if (!userMarker2d) return;
    userMarker2d.remove();
    userMarker2d = null;
}
