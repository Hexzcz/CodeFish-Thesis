// Stores connector dashed lines per route: [[originSnap, destSnap], ...]
window._connectorLines = [];
window._destMarkers = [];
window._segmentPolylines = []; // [routeIndex][segIdx] → L.polyline (flood-colored)
window._bgPolylines = []; // [routeIndex][segIdx] → background solid line
window._haloPolyline = null; // single shared halo for whichever edge is hovered

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
        const routeStart = firstSeg?.[0];
        const routeEnd = lastSeg?.[lastSeg.length - 1];

        const destLat = props.destination_lat ?? destRoot?.lat;
        const destLon = props.destination_lon ?? destRoot?.lon;
        const userLat = window.appState.originCoords?.lat;
        const userLng = window.appState.originCoords?.lng;

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
        window.appState.map.fitBounds(
            L.featureGroup(allPolys).getBounds(),
            { padding: [60, 60] }
        );
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


function selectRoute(index) {
    window.appState.activeRouteIndex = index;
    updateRouteVisibility();

    // Bottom bar sync
    document.querySelectorAll('.route-tab').forEach((t, i) =>
        t.classList.toggle('active', i === index)
    );

    // Right panel
    if (window.appState.rightPanelOpen) populateRightPanel(index);
}

function updateRouteVisibility() {
    const actIdx = window.appState.activeRouteIndex;
    const isVisible = window.appState.routesVisible;
    const focusMode = window.appState.routeFocusMode || 'selected'; // 'all' | 'selected'

    const btnVis = document.getElementById('btn-toggle-visibility');
    const btnFoc = document.getElementById('btn-toggle-focus');

    const _setLayerOpacity = (layer, opacity) => {
        if (!layer) return;
        // Markers
        if (typeof layer.setOpacity === 'function') {
            layer.setOpacity(opacity);
            return;
        }
        // Polylines / polygons
        if (typeof layer.setStyle === 'function') {
            layer.setStyle({ opacity });
            return;
        }
        // Fallback for DOM-based layers
        if (typeof layer.getElement === 'function') {
            const el = layer.getElement();
            if (el) el.style.opacity = String(opacity);
        }
    };

    // 1. MASTER VISIBILITY
    if (!isVisible) {
        if (btnVis) btnVis.classList.remove('active');
        if (btnVis) btnVis.title = "Show Routes";
        if (btnFoc) {
            btnFoc.style.opacity = '0.3';
            btnFoc.style.pointerEvents = 'none';
        }
        // Important: do NOT force element.style.opacity on polylines, otherwise later setStyle()
        // won't make them visible again.
        [...window._segmentPolylines.flat(), ...window._bgPolylines.flat(),
        ...window._connectorLines.flat(), ...window._destMarkers.flat()]
            .forEach(p => _setLayerOpacity(p, 0));
        return;
    }

    if (btnVis) btnVis.classList.add('active');
    if (btnVis) btnVis.title = "Hide Routes";
    if (btnFoc) {
        btnFoc.style.opacity = '1';
        btnFoc.style.pointerEvents = 'auto';
    }

    // If any previous implementation set `element.style.opacity = 0` on SVG paths,
    // that inline style will override later `setStyle({ opacity })` calls.
    // Clear inline opacity so Leaflet styles can take effect again.
    [...window._segmentPolylines.flat(), ...window._bgPolylines.flat(),
    ...window._connectorLines.flat(), ...window._destMarkers.flat()]
        .forEach(layer => {
            if (!layer || typeof layer.getElement !== 'function') return;
            const el = layer.getElement();
            if (!el) return;
            if (el.style && el.style.opacity === '0') el.style.opacity = '';
        });

    // 2. FOCUS MODE
    if (focusMode === 'selected') {
        if (btnFoc) {
            btnFoc.title = 'Switch to: Show All Routes (Base Colors)';
            btnFoc.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" stroke="currentColor" fill="none" stroke-width="1.5">
                <rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect>
                <rect x="3" y="14" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect>
            </svg>`;
        }
        window._bgPolylines.forEach((segs, i) => {
            segs.forEach(p => p.setStyle({ opacity: i === actIdx ? 0 : 0.1, weight: 3 }));
        });
        window._segmentPolylines.forEach((segs, i) => {
            segs.forEach(p => p.setStyle({ opacity: i === actIdx ? 0.9 : 0, weight: 5 }));
            if (i === actIdx) segs.forEach(p => p.bringToFront());
        });
        window._connectorLines.forEach((conns, i) => {
            conns.forEach(p => p.setStyle({ opacity: i === actIdx ? 0.6 : 0.1 }));
        });
        window._destMarkers.forEach((m, i) => {
            if (!m) return;
            const el = m.getElement();
            if (el) el.style.opacity = i === actIdx ? '1' : '0.1';
        });
    } else { // focusMode === 'all'
        if (btnFoc) {
            btnFoc.title = 'Switch to: Show Selected Route (Risk Colors)';
            btnFoc.innerHTML = `<svg width="14" height="14" viewBox="0 0 24 24" stroke="currentColor" fill="none" stroke-width="1.5">
                <rect x="3" y="3" width="18" height="18" rx="2"></rect>
            </svg>`;
        }
        window._bgPolylines.forEach((segs, i) => {
            segs.forEach(p => p.setStyle({ opacity: 0.9, weight: 5 }));
            if (i === actIdx) segs.forEach(p => p.bringToFront());
        });
        window._segmentPolylines.forEach((segs) => {
            segs.forEach(p => p.setStyle({ opacity: 0 }));
        });
        window._connectorLines.forEach((conns) => {
            conns.forEach(p => p.setStyle({ opacity: 0.6 }));
        });
        window._destMarkers.forEach((m) => {
            if (!m) return;
            const el = m.getElement();
            if (el) el.style.opacity = '1';
        });
    }
}

function toggleRouteVisibility() {
    window.appState.routesVisible = !window.appState.routesVisible;
    updateRouteVisibility();
}

function toggleRouteFocus() {
    window.appState.routeFocusMode = (window.appState.routeFocusMode === 'all') ? 'selected' : 'all';

    // If switching focus while right panel is open, but leaving 'selected' mode, close the panel
    if (window.appState.routeFocusMode === 'all' && window.appState.rightPanelOpen) {
        closeRightPanel();
        const btnAct = document.getElementById('analysis-btn');
        if (btnAct) btnAct.classList.remove('active');
    }

    updateRouteVisibility();
}

function toggleAnalysisPanel() {
    if (window.appState.rightPanelOpen) {
        closeRightPanel();
    } else {
        openRightPanel(window.appState.activeRouteIndex || 0);
    }
}


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
