/**
 * The shortest-distance baseline: fetching it, and drawing it on the map.
 *
 * The baseline is what the route would have been with flood risk ignored. It
 * is requested lazily — only when someone opens the compare tab or toggles
 * the baseline on — and cached per route.
 */

let _baselineLayer = null;
let _baselineVisible = false;
let _baselineCacheKey = null;
let _baselineCache = null;

function _clearBaselineLayer() {
    // Back-compat: previous implementation used a Leaflet GeoJSON layer.
    // Current implementation uses drawBaselineRoute() which manages its own layers.
    if (typeof clearBaselineRoute === 'function') {
        clearBaselineRoute();
    }
    if (_baselineLayer && window.appState?.map) {
        try {
            if (typeof _baselineLayer.getLayers === 'function') {
                _baselineLayer.getLayers().forEach(l => {
                    try { window.appState.map.removeLayer(l); } catch (e) { }
                });
            }
            window.appState.map.removeLayer(_baselineLayer);
        } catch (e) { }
    }
    _baselineLayer = null;
}

function _drawBaselineFeature(feature) {
    if (!feature || !window.appState?.map) return;
    _clearBaselineLayer();

    if (typeof drawBaselineRoute === 'function') {
        _baselineLayer = drawBaselineRoute(feature);
        return;
    }

    // Fallback if drawBaselineRoute is not loaded for some reason
    const dashed = L.geoJSON(feature, {
        style: { color: '#e8c547', weight: 4, opacity: 0.9, dashArray: '8 6' }
    }).addTo(window.appState.map);
    _baselineLayer = dashed;
}

async function _fetchShortestPathBaselineForRoute(routeFeature) {
    if (!routeFeature || !window.appState?.originCoords) return null;
    const props = routeFeature.properties || {};
    const origin = window.appState.originCoords;
    const scenario = window.appState?.scenario || props.scenario || '25yr';
    const dLat = Number(props.destination_lat);
    const dLon = Number(props.destination_lon);
    if (!Number.isFinite(dLat) || !Number.isFinite(dLon)) return null;

    const cacheKey = `${origin.lat.toFixed(6)},${origin.lng.toFixed(6)}|${dLat.toFixed(6)},${dLon.toFixed(6)}|${scenario}`;
    if (_baselineCacheKey === cacheKey && _baselineCache) return _baselineCache;

    const body = {
        origin_lat: origin.lat,
        origin_lon: origin.lng,
        destination_lat: dLat,
        destination_lon: dLon,
        scenario,
    };

    try {
        const res = await fetch('/route/shortest-path', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        if (!res.ok) return null;
        const data = await res.json();
        _baselineCacheKey = cacheKey;
        _baselineCache = data;
        return data;
    } catch (e) {
        console.error('Shortest path baseline fetch failed:', e);
        return null;
    }
}

async function _updateInteractiveBaseline(routes) {
    const idx = window.appState.activeRouteIndex || 0;
    const selected = routes?.[idx];
    const selectedFeature = selected || null;
    const data = await _fetchShortestPathBaselineForRoute(selectedFeature);
    _renderBaselineCompare(selectedFeature, data);
}

async function toggleBaselineRoute() {
    _baselineVisible = !_baselineVisible;
    if (!_baselineVisible) {
        _clearBaselineLayer();
    }
    const routes = window.appState?.routeData?.routes || [];
    await _updateInteractiveBaseline(routes);

    if (_baselineVisible && _baselineLayer && window.appState?.map) {
        try {
            if (typeof _baselineLayer.getBounds === 'function') {
                const b = _baselineLayer.getBounds();
                if (b && b.isValid && b.isValid()) window.appState.map.fitBounds(b, { padding: [40, 40] });
            }
        } catch (e) { }
    }
}

async function _fetchShortestDistanceBaselines(routes) {
    if (!window.appState.originCoords) return null;
    const origin = window.appState.originCoords;

    const destinations = routes.map(r => ({
        lat: Number(r?.properties?.destination_lat),
        lon: Number(r?.properties?.destination_lon),
    })).filter(d => Number.isFinite(d.lat) && Number.isFinite(d.lon));

    if (destinations.length === 0) return null;

    try {
        const res = await fetch('/route/shortest-distance', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                origin_lat: origin.lat,
                origin_lon: origin.lng,
                destinations
            })
        });
        if (!res.ok) return null;
        const data = await res.json();
        return data?.baselines || null;
    } catch (e) {
        console.error('Baseline fetch failed:', e);
        return null;
    }
}

// Called from both Overview pills and bottom-bar tabs
