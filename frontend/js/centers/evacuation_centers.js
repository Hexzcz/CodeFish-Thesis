function handleCentersToggle(el) {
    el.classList.toggle('active');
    const visible = el.classList.contains('active');
    toggleEvacCenters(visible);
}

function toggleEvacCenters(visible) {
    window.appState.centersVisible = visible;
    if (!visible) {
        if (window.appState.centersLayer) window.appState.map.removeLayer(window.appState.centersLayer);
    } else {
        if (!window.appState.centersGeoJSON) fetchCenters();
        else drawCenters(window.appState.centersGeoJSON);
    }
}

async function fetchCenters() {
    try {
        const response = await fetch('/evacuation-centers');
        const data = await response.json();
        window.appState.centersGeoJSON = data;
        drawCenters(data);
        const count = data.features ? data.features.length : 0;
        const el = document.getElementById('centers-showing');
        if (el) el.textContent = `${count} centers loaded`;
    } catch (e) {
        console.error('Error fetching centers:', e);
    }
}

function drawCenters(data) {
    if (window.appState.centersLayer) window.appState.map.removeLayer(window.appState.centersLayer);

    // Custom cluster icon — small, dark glass, slate-accented
    const cluster = L.markerClusterGroup({
        maxClusterRadius: 35,
        iconCreateFunction: function (cluster) {
            const count = cluster.getChildCount();
            return L.divIcon({
                className: '',
                html: `<div style="
                    width: 20px; height: 20px;
                    border-radius: 50%;
                    background: rgba(18,18,18,0.88);
                    border: 1.5px solid rgba(144,164,174,0.55);
                    color: #90a4ae;
                    font-size: 9px;
                    font-family: 'IBM Plex Mono', monospace;
                    display: flex; align-items: center; justify-content: center;
                    font-weight: 500;
                    box-shadow: 0 0 0 1px rgba(144,164,174,0.18),
                                0 2px 6px rgba(0,0,0,0.5);
                ">${count}</div>`,
                iconSize: [20, 20],
                iconAnchor: [10, 10]
            });
        }
    });

    L.geoJSON(data, {
        pointToLayer: (feature, latlng) => {
            // Individual center: small slate-blue square dot
            const icon = L.divIcon({
                className: '',
                html: `<div style="
                    width: 6px; height: 6px;
                    border-radius: 1px;
                    background: #90a4ae;
                    border: 1px solid rgba(255,255,255,0.35);
                    box-shadow: 0 0 4px rgba(144,164,174,0.5);
                "></div>`,
                iconSize: [6, 6],
                iconAnchor: [3, 3]
            });
            return L.marker(latlng, { icon });
        },
        onEachFeature: (feature, layer) => {
            const p = feature.properties;
            layer.bindPopup(
                `<strong>${p.facility || p.name || 'Center'}</strong><br>` +
                `<span style="font-size:11px;color:#909090;">${p.barangay || ''}</span>`
            );
        }
    }).addTo(cluster);

    cluster.addTo(window.appState.map);
    window.appState.centersLayer = cluster;
}
