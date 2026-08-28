/**
 * "Show me the way": the streets to walk, in order.
 *
 * Built from the segment names the router already returns. Consecutive
 * segments on the same street are merged — a road split into six graph edges
 * is still one road to walk down, and listing it six times reads as noise.
 *
 * Not turn-by-turn: the app does not compute bearings, and inventing
 * "turn left" from coordinates we have not checked would be worse than a
 * street list a person can follow on the map.
 */

function renderSimpleDirections(route) {
    const list = document.getElementById('simple-steps');
    const segments = (route.properties || {}).segments || [];
    list.innerHTML = '';

    const streets = _mergeConsecutiveStreets(segments);
    if (!streets.length) {
        list.innerHTML = `<li class="step-empty">${t('follow_route_on_map')}</li>`;
        return;
    }

    streets.forEach((street, index) => {
        const item = document.createElement('li');
        item.className = 'simple-step';
        item.innerHTML = `
            <span class="step-number">${index + 1}</span>
            <span class="step-street">${street.name}</span>
            <span class="step-distance">${formatDistance(street.metres / 1000)}</span>`;
        list.appendChild(item);
    });
}

function toggleSimpleDirections() {
    const panel = document.getElementById('simple-directions');
    const opening = panel.classList.contains('hidden');
    panel.classList.toggle('hidden', !opening);

    const btn = document.getElementById('simple-directions-btn');
    if (btn) btn.textContent = opening ? t('hide_the_way') : t('show_me_the_way');

    if (opening && window.appState.map && window.appState.routeData) {
        const routes = window.appState.routeData.routes || [];
        const index = Math.max(0, window.appState.activeRouteIndex || 0);
        if (routes[index]) fitToRoute(index);
    }
}

function _mergeConsecutiveStreets(segments) {
    const streets = [];
    segments.forEach(seg => {
        const name = _streetName(seg);
        const previous = streets[streets.length - 1];
        if (previous && previous.name === name) {
            previous.metres += seg.length || 0;
        } else {
            streets.push({ name, metres: seg.length || 0 });
        }
    });
    return streets;
}

function _streetName(seg) {
    const raw = Array.isArray(seg.name) ? seg.name[0] : seg.name;
    return raw && raw !== 'Unnamed Road' ? raw : t('unnamed_road');
}
