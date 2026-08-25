/**
 * Highlighting one road segment — from the map, or from the sidebar list.
 *
 * The halo is a single shared polyline that moves to whichever segment is
 * hovered, rather than one halo per segment.
 */

// ── Halo helpers ──
function _getRouteLatLngs(routeIndex) {
    const latlngs = [];
    if (window._segmentPolylines[routeIndex]) {
        window._segmentPolylines[routeIndex].forEach(p => latlngs.push(p.getLatLngs()));
    }
    if (window._connectorLines[routeIndex]) {
        window._connectorLines[routeIndex].forEach(p => latlngs.push(p.getLatLngs()));
    }
    return latlngs;
}

function _showEdgeHalo(latlngs, baseWeight) {
    _removeEdgeHalo();
    // White outline slightly thicker than the edge
    window._haloPolyline = L.polyline(latlngs, {
        color: '#ffffff',
        weight: (baseWeight || 5) + 8,
        opacity: 0.40,
        interactive: false,
    }).addTo(window.appState.map);
    // Also a bright color inner ring
    window._haloInner = L.polyline(latlngs, {
        color: '#ffffff',
        weight: (baseWeight || 5) + 2,
        opacity: 0.7,
        interactive: false,
    }).addTo(window.appState.map);
}

function _removeEdgeHalo() {
    if (window._haloPolyline) {
        window.appState.map.removeLayer(window._haloPolyline);
        window._haloPolyline = null;
    }
    if (window._haloInner) {
        window.appState.map.removeLayer(window._haloInner);
        window._haloInner = null;
    }
}

// ── Map segment highlighting from sidebar ──
function highlightSegmentOnMap(routeIndex, segIndex) {
    const segs = window._segmentPolylines[routeIndex];
    if (!segs || !segs[segIndex]) return;
    const poly = segs[segIndex];
    _showEdgeHalo(poly.getLatLngs(), poly.options.weight);
    poly.bringToFront();
}

function unhighlightSegmentOnMap(routeIndex, segIndex) {
    _removeEdgeHalo();
}

function focusSegmentOnMap(routeIndex, segIndex) {
    const segs = window._segmentPolylines[routeIndex];
    if (!segs || !segs[segIndex]) return;
    _removeEdgeHalo();
    const bounds = segs[segIndex].getBounds();
    if (bounds.isValid()) {
        window.appState.map.fitBounds(bounds, { padding: [100, 100], maxZoom: 18 });
    }
}

// ── Tooltip for map-hovered route segments ──
function showRouteSegTooltip(e, seg, routeIndex) {
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
    document.getElementById('tt-formula').textContent = `Class ${seg.flood_class || 0}  ·  Route ${routeIndex + 1}`;

    const tt = document.getElementById('seg-tooltip');
    tt.style.left = (e.originalEvent.pageX + 14) + 'px';
    tt.style.top = (e.originalEvent.pageY - 14) + 'px';
    tt.classList.remove('hidden');
}

function moveRouteSegTooltip(e) {
    const tt = document.getElementById('seg-tooltip');
    tt.style.left = (e.originalEvent.pageX + 14) + 'px';
    tt.style.top = (e.originalEvent.pageY - 14) + 'px';
}
