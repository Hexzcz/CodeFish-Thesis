function toggleOriginPlacement() {
    window.appState.placingOrigin = !window.appState.placingOrigin;
    const btn = document.getElementById('place-origin-btn');
    const txt = document.getElementById('origin-btn-text');
    if (window.appState.placingOrigin) {
        btn.classList.add('placing');
        btn.classList.remove('placed');
        txt.textContent = 'Click map to place…';
        window.appState.map.getContainer().style.cursor = 'crosshair';
    } else {
        btn.classList.remove('placing');
        window.appState.map.getContainer().style.cursor = '';
    }
}

function handleMapClickForOrigin(latlng) {
    window.appState.originCoords = latlng;
    window.appState.placingOrigin = false;
    window.appState.map.getContainer().style.cursor = '';

    const btn = document.getElementById('place-origin-btn');
    const txt = document.getElementById('origin-btn-text');
    btn.classList.remove('placing');
    btn.classList.add('placed');
    txt.textContent = 'Origin placed';

    const coord = document.getElementById('coord-display');
    coord.textContent = `${latlng.lat.toFixed(5)}, ${latlng.lng.toFixed(5)}`;
    coord.classList.add('visible');

    createOriginMarker(latlng);
    document.getElementById('find-routes-btn').disabled = false;

    setStatus('READY');
}

function createOriginMarker(latlng) {
    if (window.appState.originMarker) window.appState.map.removeLayer(window.appState.originMarker);
    const icon = L.divIcon({
        className: '',
        html: `<div style="width:14px;height:14px;border-radius:50%;background:#e8c547;border:2px solid #fff;box-shadow:0 0 8px rgba(232,197,71,0.6);"></div>`,
        iconSize: [14, 14],
        iconAnchor: [7, 7]
    });
    window.appState.originMarker = L.marker(latlng, { icon }).addTo(window.appState.map);
}

function removeOriginMarker() {
    if (window.appState.originMarker) {
        window.appState.map.removeLayer(window.appState.originMarker);
        window.appState.originMarker = null;
    }
}
