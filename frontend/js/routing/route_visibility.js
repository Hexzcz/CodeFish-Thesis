/**
 * Which routes are on screen: focus, dimming, and the active selection.
 *
 * Drawing them is route_layer.js; this only changes what is shown of what is
 * already drawn.
 */

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
            segs.forEach(p => p.setStyle({ opacity: 0, weight: 3 }));
        });
        window._segmentPolylines.forEach((segs, i) => {
            segs.forEach(p => p.setStyle({ opacity: i === actIdx ? 0.9 : 0, weight: 5 }));
            if (i === actIdx) segs.forEach(p => p.bringToFront());
        });
        window._connectorLines.forEach((conns, i) => {
            conns.forEach(p => p.setStyle({ opacity: i === actIdx ? 0.6 : 0 }));
        });
        window._destMarkers.forEach((m, i) => {
            if (!m) return;
            const el = m.getElement();
            if (el) el.style.opacity = i === actIdx ? '1' : '0';
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

function selectRoute(index) {
    const routes = window.appState?.routeData?.routes || [];
    if (!routes[index]) return;

    window.appState.activeRouteIndex = index;
    window.appState.routesVisible = true;
    window.appState.routeFocusMode = 'selected';
    updateRouteVisibility();

    document.querySelectorAll('.route-tab').forEach((t, i) =>
        t.classList.toggle('active', i === index)
    );

    if (window.appState.rightPanelOpen && typeof populateRightPanel === 'function') {
        populateRightPanel(index);
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
