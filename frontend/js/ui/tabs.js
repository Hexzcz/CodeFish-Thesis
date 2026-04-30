function initTabs(tabBarSelector, panelPrefix) {
    const tabs = document.querySelectorAll(`${tabBarSelector} .tab`);
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            document.querySelectorAll(`.panel[id^="${panelPrefix}"]`)
                .forEach(p => p.classList.remove('active'));
            tab.classList.add('active');
            const panelId = panelPrefix + tab.dataset.panel;
            const panel = document.getElementById(panelId);
            if (panel) panel.classList.add('active');
        });
    });
}

// Sort buttons in segments tab
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.sort-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.sort-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            sortSegments(btn.dataset.sort);
        });
    });
});

function sortSegments(by) {
    if (!window.appState.routeData) return;
    const rIdx = window.appState.activeRouteIndex;
    const route = window.appState.routeData.routes[rIdx];
    if (!route || !route.properties.segments) return;

    // Stamp each segment with its original graph index BEFORE sorting
    // so map highlighting always targets the correct polyline edge
    let segs = route.properties.segments.map((s, i) => ({ ...s, _origIdx: i }));

    if (by === 'risk') segs.sort((a, b) => b.flood_proba - a.flood_proba);
    if (by === 'length') segs.sort((a, b) => b.length - a.length);
    // 'order' keeps original position, so _origIdx === loop i anyway

    populateSegmentList(segs, rIdx);
}
