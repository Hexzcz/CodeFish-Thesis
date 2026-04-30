function handleRoadToggle(el) {
    el.classList.toggle('active');
    const visible = el.classList.contains('active');
    window.appState.roadNetworkVisible = visible;
    if (visible) {
        if (!window.appState.roadGeoJSON) { fetchRoads(); }
        else if (window.appState.roadLayer) { window.appState.roadLayer.addTo(window.appState.map); }
    } else {
        if (window.appState.roadLayer) { window.appState.map.removeLayer(window.appState.roadLayer); }
    }
}

// Keep these for backward compat (called by old toggle handlers)
function toggleRoadMaster(visible) {
    window.appState.roadNetworkVisible = visible;
    if (visible) {
        if (!window.appState.roadGeoJSON) fetchRoads();
        else if (window.appState.roadLayer) window.appState.roadLayer.addTo(window.appState.map);
    } else {
        if (window.appState.roadLayer) window.appState.map.removeLayer(window.appState.roadLayer);
    }
}

async function fetchRoads() {
    try {
        const response = await fetch('/roads');
        const data = await response.json();
        window.appState.roadGeoJSON = data;
        drawRoadNetwork(data);
    } catch (e) {
        console.error('Error fetching roads:', e);
    }
}

function drawRoadNetwork(data) {
    if (window.appState.roadLayer) {
        window.appState.map.removeLayer(window.appState.roadLayer);
    }
    const layer = L.geoJSON(data, {
        style: () => ({ color: '#3b82f6', weight: 1.5, opacity: 0.5 }),
        onEachFeature: (feature, layer) => {
            layer.on('mouseover', e => showSegmentTooltip(e, feature.properties));
            layer.on('mouseout', hideSegmentTooltip);
        }
    });
    window.appState.roadLayer = layer;
    if (window.appState.roadNetworkVisible) layer.addTo(window.appState.map);
}
