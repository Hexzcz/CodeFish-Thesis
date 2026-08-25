/**
 * The analysis panel: opening it, closing it, and switching route tabs.
 *
 * What goes inside each tab lives next door — overview.js, segments.js,
 * compare.js.
 */

function openRightPanel(routeIndex) {
    const nextIndex = Number.isInteger(routeIndex) ? routeIndex : (window.appState.activeRouteIndex || 0);
    window.appState.activeRouteIndex = nextIndex;
    document.getElementById('app').classList.add('right-panel-open');
    window.appState.rightPanelOpen = true;

    if (window.appState.routeFocusMode !== 'selected') {
        window.appState.routeFocusMode = 'selected';
    }

    const btnAct = document.getElementById('analysis-btn');
    if (btnAct) btnAct.classList.add('active');

    if (typeof updateRouteVisibility === 'function') updateRouteVisibility();

    populateRightPanel(nextIndex);
}

function closeRightPanel() {
    document.getElementById('app').classList.remove('right-panel-open');
    window.appState.rightPanelOpen = false;

    if (window.appState.routeFocusMode !== 'all') {
        window.appState.routeFocusMode = 'all';
    }

    const btnAct = document.getElementById('analysis-btn');
    if (btnAct) btnAct.classList.remove('active');

    if (typeof updateRouteVisibility === 'function') updateRouteVisibility();
}

function populateRightPanel(routeIndex) {
    if (!window.appState.routeData) return;
    const routes = window.appState.routeData.routes;
    const safeIndex = Math.max(0, Math.min(routes.length - 1, Number.isInteger(routeIndex) ? routeIndex : 0));
    window.appState.activeRouteIndex = safeIndex;

    populateOverview(routes, safeIndex);

    // Stamp _origIdx so map hover always targets the correct polyline edge
    const rawSegs = routes[safeIndex]?.properties?.segments || [];
    const stampedSegs = rawSegs.map((s, i) => ({ ...s, _origIdx: i }));
    populateSegmentList(stampedSegs, safeIndex);

    populateCompare(routes);
}

function switchActiveRoute(index) {
    selectRoute(index);        // highlight on map
    populateRightPanel(index); // refresh side panel
}

function highlightRouteFromTab(index) {
    // In selected mode, only highlight the active route
    if (window.appState.routeFocusMode === 'selected' && index !== window.appState.activeRouteIndex) {
        return;
    }
    if (typeof _getRouteLatLngs === 'function' && typeof _showEdgeHalo === 'function') {
        const latlngs = _getRouteLatLngs(index);
        if (latlngs && latlngs.length > 0) {
            _showEdgeHalo(latlngs, 5);
        }
    }
}

function unhighlightRouteFromTab() {
    if (typeof _removeEdgeHalo === 'function') {
        _removeEdgeHalo();
    }
}
