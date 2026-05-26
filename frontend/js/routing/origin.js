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

function _pointInRing(pointLngLat, ringLngLat) {
    const x = pointLngLat[0];
    const y = pointLngLat[1];
    let inside = false;
    for (let i = 0, j = ringLngLat.length - 1; i < ringLngLat.length; j = i++) {
        const xi = ringLngLat[i][0];
        const yi = ringLngLat[i][1];
        const xj = ringLngLat[j][0];
        const yj = ringLngLat[j][1];
        const intersect = ((yi > y) !== (yj > y)) &&
            (x < ((xj - xi) * (y - yi)) / ((yj - yi) || 1e-12) + xi);
        if (intersect) inside = !inside;
    }
    return inside;
}

function _pointInPolygon(pointLngLat, polygonCoords) {
    if (!polygonCoords || polygonCoords.length === 0) return false;
    const outer = polygonCoords[0];
    if (!_pointInRing(pointLngLat, outer)) return false;
    for (let i = 1; i < polygonCoords.length; i++) {
        if (_pointInRing(pointLngLat, polygonCoords[i])) return false;
    }
    return true;
}

function _pointInDistrictBoundary(lat, lng) {
    const gj = window.appState?.boundaryGeoJSON;
    if (!gj) return true;
    const point = [lng, lat];
    const geom = gj.type === 'Feature' ? gj.geometry : (gj.type === 'FeatureCollection' ? gj.features?.[0]?.geometry : gj);
    if (!geom) return true;

    if (geom.type === 'Polygon') {
        return _pointInPolygon(point, geom.coordinates);
    }
    if (geom.type === 'MultiPolygon') {
        return geom.coordinates.some(poly => _pointInPolygon(point, poly));
    }
    return true;
}

function _getDistrict1Viewbox() {
    const gj = window.appState?.boundaryGeoJSON;
    if (gj) {
        const geom = gj.type === 'Feature' ? gj.geometry : (gj.type === 'FeatureCollection' ? gj.features?.[0]?.geometry : gj);
        const coords = [];
        const _push = (c) => { if (Array.isArray(c) && typeof c[0] === 'number' && typeof c[1] === 'number') coords.push(c); };
        const _walk = (arr) => {
            if (!Array.isArray(arr)) return;
            if (typeof arr[0] === 'number' && typeof arr[1] === 'number') {
                _push(arr);
                return;
            }
            arr.forEach(_walk);
        };
        _walk(geom?.coordinates);
        if (coords.length > 0) {
            let west = Infinity, south = Infinity, east = -Infinity, north = -Infinity;
            coords.forEach(([x, y]) => {
                if (x < west) west = x;
                if (x > east) east = x;
                if (y < south) south = y;
                if (y > north) north = y;
            });
            return { west, south, east, north };
        }
    }
    return { west: 120.96, south: 14.63, east: 121.08, north: 14.74 };
}

let _originSearchTimer = null;
let _originSearchAbort = null;

async function _searchOriginAddress(query) {
    const resultsEl = document.getElementById('origin-search-results');
    if (!resultsEl) return;

    const q = (query || '').trim();
    if (q.length < 3) {
        resultsEl.classList.add('hidden');
        resultsEl.innerHTML = '';
        return;
    }

    if (_originSearchAbort) _originSearchAbort.abort();
    _originSearchAbort = new AbortController();

    const vb = _getDistrict1Viewbox();
    const viewbox = `${vb.west},${vb.north},${vb.east},${vb.south}`;

    const url = `https://nominatim.openstreetmap.org/search?format=jsonv2&limit=8&addressdetails=1&bounded=1&viewbox=${encodeURIComponent(viewbox)}&q=${encodeURIComponent(q + ', Quezon City')}`;

    resultsEl.classList.remove('hidden');
    resultsEl.innerHTML = `<div class="addr-item"><div class="addr-item-title">Searching…</div></div>`;

    try {
        const res = await fetch(url, {
            signal: _originSearchAbort.signal,
            headers: { 'Accept': 'application/json' }
        });
        const items = await res.json();

        const filtered = (Array.isArray(items) ? items : [])
            .map(it => ({
                ...it,
                latNum: Number(it.lat),
                lonNum: Number(it.lon)
            }))
            .filter(it => Number.isFinite(it.latNum) && Number.isFinite(it.lonNum))
            .filter(it => _pointInDistrictBoundary(it.latNum, it.lonNum));

        if (filtered.length === 0) {
            resultsEl.innerHTML = `<div class="addr-item"><div class="addr-item-title">No matches in District 1</div></div>`;
            return;
        }

        resultsEl.innerHTML = '';
        filtered.slice(0, 6).forEach(it => {
            const title = (it.display_name || '').split(',').slice(0, 2).join(', ').trim() || 'Result';
            const sub = `${it.latNum.toFixed(5)}, ${it.lonNum.toFixed(5)}`;
            const row = document.createElement('div');
            row.className = 'addr-item';
            row.innerHTML = `<div class="addr-item-title"></div><div class="addr-item-sub"></div>`;
            row.querySelector('.addr-item-title').textContent = title;
            row.querySelector('.addr-item-sub').textContent = sub;
            row.addEventListener('click', () => {
                resultsEl.classList.add('hidden');
                resultsEl.innerHTML = '';
                const input = document.getElementById('origin-search-input');
                if (input) input.value = it.display_name || title;

                const latlng = { lat: it.latNum, lng: it.lonNum };
                handleMapClickForOrigin(latlng);
                if (window.appState?.map) window.appState.map.setView([latlng.lat, latlng.lng], Math.max(window.appState.map.getZoom(), 16));
            });
            resultsEl.appendChild(row);
        });
    } catch (e) {
        if (e && e.name === 'AbortError') return;
        console.error('Origin address search failed:', e);
        resultsEl.innerHTML = `<div class="addr-item"><div class="addr-item-title">Search failed</div></div>`;
    }
}

function _initOriginAddressSearch() {
    const input = document.getElementById('origin-search-input');
    const resultsEl = document.getElementById('origin-search-results');
    if (!input || !resultsEl) return;

    input.addEventListener('input', () => {
        if (_originSearchTimer) window.clearTimeout(_originSearchTimer);
        _originSearchTimer = window.setTimeout(() => _searchOriginAddress(input.value), 320);
    });

    input.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            resultsEl.classList.add('hidden');
            resultsEl.innerHTML = '';
            input.blur();
        }
    });

    document.addEventListener('click', (e) => {
        if (!resultsEl || resultsEl.classList.contains('hidden')) return;
        const target = e.target;
        if (target === input || resultsEl.contains(target)) return;
        resultsEl.classList.add('hidden');
        resultsEl.innerHTML = '';
    });
}

document.addEventListener('DOMContentLoaded', () => {
    _initOriginAddressSearch();
});

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
