/**
 * Drawing the ranked routes on the map, and deciding which are visible.
 *
 * Each route is drawn twice: a solid background line for contrast, and a
 * flood-coloured line on top of it. Both are kept per segment so a single
 * road can be highlighted without redrawing the route.
 */

// Stores connector dashed lines per route: [[originSnap, destSnap], ...]
window._connectorLines = [];
window._destMarkers = [];
window._segmentPolylines = []; // [routeIndex][segIdx] → L.polyline (flood-colored)
window._bgPolylines = []; // [routeIndex][segIdx] → background solid line
window._haloPolyline = null; // single shared halo for whichever edge is hovered

// Returns whichever endpoint ([lat,lng]) of segPts is closest to [refLat, refLng].
// This guards against edge geometries stored in the reverse direction.
function _closerEndpoint(segPts, refLat, refLng) {
    if (!segPts || segPts.length === 0) return null;
    const first = segPts[0];
    const last  = segPts[segPts.length - 1];
    if (refLat == null || refLng == null) return first;
    const dFirst = (first[0] - refLat) ** 2 + (first[1] - refLng) ** 2;
    const dLast  = (last[0]  - refLat) ** 2 + (last[1]  - refLng) ** 2;
    return dFirst <= dLast ? first : last;
}

/**
 * Keep the fitted route clear of whatever is floating over the map.
 *
 * In the simple view the answer card sits on the left; fitting to the whole
 * viewport put the route underneath it, which is the one thing the person
 * needs to see.
 */
function routeFitPadding() {
    const panel = document.getElementById('simple-shell');
    if (currentMode() !== 'simple' || !panel) {
        return { padding: [60, 60] };
    }

    // Never surrender more than this much of the map to the panel: on a narrow
    // window the card is most of the width, and fitting a route into the sliver
    // that is left zooms in far past anything useful.
    const mapWidth = window.appState.map.getSize().x;
    const covered = Math.min(panel.getBoundingClientRect().right + 24, mapWidth * 0.45);
    return {
        paddingTopLeft: [covered, 60],
        paddingBottomRight: [60, 60],
        maxZoom: 17,
    };
}

/** Zoom to one route, clear of any floating panel. */
function fitToRoute(index) {
    const polys = (window._segmentPolylines[index] || []).filter(p => p.getLatLngs().length > 0);
    if (!polys.length || !window.appState.map) return;
    window.appState.map.fitBounds(L.featureGroup(polys).getBounds(), routeFitPadding());
}

function drawAllRoutes(routes) {
    clearRoutes();

    const data = window.appState.routeData;
    const destRoot = data?.destination;

    routes.forEach((route, index) => {
        const color = ROUTE_COLORS_HEX[index] || '#888';
        const geom = route.geometry;
        const props = route.properties || {};
        const segments = props.segments || [];
        
        // ── 1. Convert geometry to [lat, lng] per-segment ──
        let latlngsSegments = [];
        if (geom.type === 'MultiLineString') {
            latlngsSegments = geom.coordinates.map(seg => seg.map(c => [c[1], c[0]]));
        } else if (geom.type === 'LineString') {
            latlngsSegments = [geom.coordinates.map(c => [c[1], c[0]])];
        }

        // ── 2. Background route-colored polyline (always visible) ──
        const bgPolys = latlngsSegments.map((latlngs) =>
            L.polyline(latlngs, {
                color,
                weight: 3,
                opacity: 0.2,
                interactive: false,
            }).addTo(window.appState.map)
        );
        window._bgPolylines.push(bgPolys);

        // ── 3. Flood-risk-colored segment polylines (on top) ──
        const segPolys = latlngsSegments.map((latlngs, segIdx) => {
            const seg = segments[segIdx];
            const segColor = seg ? getRiskColorHex(seg.flood_proba || 0) : color;
            const poly = L.polyline(latlngs, {
                color: segColor,
                weight: 5,
                opacity: 0,   // handled by updateRouteVisibility
            }).addTo(window.appState.map);

            if (seg) {
                poly.on('mouseover', e => {
                    if (window.appState.routeFocusMode === 'all') {
                        _showEdgeHalo(_getRouteLatLngs(index), 5);
                    } else {
                        _showEdgeHalo(latlngs, poly.options.weight);
                    }
                    showRouteSegTooltip(e, seg, index);
                });
                poly.on('mousemove', e => moveRouteSegTooltip(e));
                poly.on('mouseout', () => {
                    _removeEdgeHalo();
                    hideSegmentTooltip();
                });
            } else {
                poly.on('mouseover', () => {
                    if (window.appState.routeFocusMode === 'all') _showEdgeHalo(_getRouteLatLngs(index), 5);
                });
                poly.on('mouseout', () => _removeEdgeHalo());
            }
            poly.on('click', () => selectRoute(index));

            return poly;
        });
        window._segmentPolylines.push(segPolys);

        // ── 4. Connector lines (dashed, route-colored) ──
        const firstSeg = latlngsSegments[0];
        const lastSeg = latlngsSegments[latlngsSegments.length - 1];

        const destLat = props.destination_lat ?? destRoot?.lat;
        const destLon = props.destination_lon ?? destRoot?.lon;
        const userLat = window.appState.originCoords?.lat;
        const userLng = window.appState.originCoords?.lng;

        // Pick the endpoint of the first/last geometry segment that is
        // closest to the user / destination — guards against edges whose
        // coordinates are stored in reverse traversal order.
        const routeStart = _closerEndpoint(firstSeg, userLat, userLng);
        const routeEnd   = _closerEndpoint(lastSeg,  destLat, destLon);

        const connectors = [];
        
        if (routeStart && userLat != null) {
            const cp = L.polyline(
                [[userLat, userLng], routeStart],
                { color, weight: 1.8, opacity: 0.2, dashArray: '6 5' }
            ).addTo(window.appState.map);
            cp.on('mouseover', () => {
                if (window.appState.routeFocusMode === 'all') _showEdgeHalo(_getRouteLatLngs(index), 5);
            });
            cp.on('mouseout', () => _removeEdgeHalo());
            cp.on('click', () => selectRoute(index));
            connectors.push(cp);
        }

        if (routeEnd && destLat != null && destLon != null) {
            const cp = L.polyline(
                [routeEnd, [destLat, destLon]],
                { color, weight: 1.8, opacity: 0.2, dashArray: '6 5' }
            ).addTo(window.appState.map);
            cp.on('mouseover', () => {
                if (window.appState.routeFocusMode === 'all') _showEdgeHalo(_getRouteLatLngs(index), 5);
            });
            cp.on('mouseout', () => _removeEdgeHalo());
            cp.on('click', () => selectRoute(index));
            connectors.push(cp);
        }
        window._connectorLines.push(connectors);

        // ── 5. Destination marker ──
        if (destLat != null && destLon != null) {
            const destIcon = L.divIcon({
                className: '',
                html: `<div style="width:12px;height:12px;border-radius:2px;background:${color};border:2px solid #fff;box-shadow:0 0 6px ${color}88;transform:rotate(45deg);"></div>`,
                iconSize: [12, 12], iconAnchor: [6, 6]
            });
            const dm = L.marker([destLat, destLon], { icon: destIcon })
                .bindTooltip(props.destination_name || 'Evacuation Center', { permanent: false })
                .addTo(window.appState.map);
            window._destMarkers.push(dm);
        } else {
            window._destMarkers.push(null);
        }
    });

    // ── 6. Fit bounds ──
    const allPolys = [
        ...window._segmentPolylines.flat(),
        ...window._connectorLines.flat()
    ].filter(p => p.getLatLngs().length > 0);

    if (allPolys.length > 0) {
        window.appState.map.fitBounds(L.featureGroup(allPolys).getBounds(), routeFitPadding());
    }

    // Default to "all routes" shown explicitly upon routing
    window.appState.routesVisible = true;
    window.appState.routeFocusMode = 'all';

    // Explicitly hide analysis panel if routes are regenerated
    if (window.appState.rightPanelOpen) {
        closeRightPanel();
        // closeRightPanel() internally sets routeFocusMode = 'all' and calls updateRouteVisibility()
    } else {
        updateRouteVisibility();
    }
}

function clearRoutes() {
    // Remove any active halo first
    _removeEdgeHalo();

    // Clear baseline overlay too (if visible) to avoid leftover segments
    clearBaselineRoute();

    // Segment flood-colored polylines
    window._segmentPolylines.forEach(segs => segs.forEach(p => window.appState.map.removeLayer(p)));
    window._segmentPolylines = [];

    // Background route-colored polylines
    window._bgPolylines.forEach(segs => segs.forEach(p => window.appState.map.removeLayer(p)));
    window._bgPolylines = [];

    // Connector dashes
    window._connectorLines.forEach(conns => conns.forEach(p => window.appState.map.removeLayer(p)));
    window._connectorLines = [];

    // Destination markers
    window._destMarkers.forEach(m => { if (m) window.appState.map.removeLayer(m); });
    window._destMarkers = [];

    window.appState.routePolylines = [];
}
