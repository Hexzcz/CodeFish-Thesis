async function fetchBoundary() {
    try {
        const res = await fetch('/boundary');
        const data = await res.json();
        window.appState.boundaryGeoJSON = data;
        L.geoJSON(data, {
            style: {
                color: '#e8c547',
                weight: 1.5,
                dashArray: '6 4',
                fillOpacity: 0,
                opacity: 0.35
            }
        }).addTo(window.appState.map);
    } catch (e) {
        console.error('Boundary load error:', e);
    }
}
