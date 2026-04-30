function initMap() {
    const map = L.map('map', { zoomControl: false, maxZoom: 22 }).setView([14.645, 121.02], 14);
    L.control.zoom({ position: 'topright' }).addTo(map);

    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
        attribution: 'Tiles &copy; Esri',
        maxZoom: 22,
        maxNativeZoom: 16
    }).addTo(map);

    window.appState.map = map;

    map.on('click', (e) => {
        if (window.appState.placingOrigin) {
            handleMapClickForOrigin(e.latlng);
        }
    });

    return map;
}
