/**
 * Drawing the shortest-distance baseline route on the map.
 *
 * Deliberately separate from the ranked routes: the baseline is a comparison
 * aid with its own dashed styling, its own tooltip, and its own lifetime.
 */

window._baselineOutlinePolylines = []; // [segIdx] → L.polyline (white dashed outline)
window._baselineSegmentPolylines = []; // [segIdx] → L.polyline (flood-colored)


function clearBaselineRoute() {
    // Remove any active halo first
    _removeEdgeHalo();
    if (!window.appState?.map) return;

    window._baselineSegmentPolylines.forEach(p => {
        try { window.appState.map.removeLayer(p); } catch (e) { }
    });
    window._baselineOutlinePolylines.forEach(p => {
        try { window.appState.map.removeLayer(p); } catch (e) { }
    });

    window._baselineSegmentPolylines = [];
    window._baselineOutlinePolylines = [];
}


function showBaselineSegTooltip(e, seg) {
    const color = getRiskColorHex(seg.flood_proba || 0);
    const prob = Math.round((seg.flood_proba || 0) * 100);
    const riskLbl = getRiskLabel(seg.flood_proba || 0);
    const hw = seg.highway || 'unclassified';

    document.getElementById('tt-name').textContent = seg.name || 'Unnamed Road';
    document.getElementById('tt-type').textContent = hw.replace(/_/g, ' ');
    document.getElementById('tt-bar').style.width = prob + '%';
    document.getElementById('tt-bar').style.background = color;
    document.getElementById('tt-prob').textContent = prob + '%';
    document.getElementById('tt-class').textContent = riskLbl;
    document.getElementById('tt-length').textContent = ((seg.length || 0) / 1000).toFixed(3) + ' km';
    document.getElementById('tt-elev').textContent = (seg.elevation || 0).toFixed(1) + ' m';
    document.getElementById('tt-wsm').textContent = (seg.wsm_cost || 0).toFixed(4);
    document.getElementById('tt-formula').textContent = 'Dijkstra Baseline';

    const tt = document.getElementById('seg-tooltip');
    tt.style.left = (e.originalEvent.pageX + 14) + 'px';
    tt.style.top = (e.originalEvent.pageY - 14) + 'px';
    tt.classList.remove('hidden');
}


function drawBaselineRoute(feature) {
    if (!feature || !window.appState?.map) return null;
    clearBaselineRoute();

    const geom = feature.geometry || {};
    const props = feature.properties || {};
    const segments = props.segments || [];

    // Convert geometry to [lat, lng] per-segment
    let latlngsSegments = [];
    if (geom.type === 'MultiLineString') {
        latlngsSegments = geom.coordinates.map(seg => seg.map(c => [c[1], c[0]]));
    } else if (geom.type === 'LineString') {
        latlngsSegments = [geom.coordinates.map(c => [c[1], c[0]])];
    }

    // White broken-line outline underlay to distinguish baseline
    const outlines = latlngsSegments.map((latlngs) =>
        L.polyline(latlngs, {
            color: '#ffffff',
            weight: 10,
            opacity: 0.75,
            dashArray: '10 8',
            lineCap: 'butt',
            interactive: false,
        }).addTo(window.appState.map)
    );
    window._baselineOutlinePolylines = outlines;

    // Flood-risk-colored segments on top (same interaction style)
    const segPolys = latlngsSegments.map((latlngs, segIdx) => {
        const seg = segments[segIdx];
        const segColor = seg ? getRiskColorHex(seg.flood_proba || 0) : '#ffffff';
        const poly = L.polyline(latlngs, {
            color: segColor,
            weight: 6,
            opacity: 0.9,
        }).addTo(window.appState.map);

        if (seg) {
            poly.on('mouseover', e => {
                _showEdgeHalo(latlngs, poly.options.weight);
                showBaselineSegTooltip(e, seg);
            });
            poly.on('mousemove', e => moveRouteSegTooltip(e));
            poly.on('mouseout', () => {
                _removeEdgeHalo();
                hideSegmentTooltip();
            });
        } else {
            poly.on('mouseover', () => _showEdgeHalo(latlngs, poly.options.weight));
            poly.on('mouseout', () => _removeEdgeHalo());
        }

        return poly;
    });
    window._baselineSegmentPolylines = segPolys;

    segPolys.forEach(p => p.bringToFront());
    return L.featureGroup([...outlines, ...segPolys]);
}
