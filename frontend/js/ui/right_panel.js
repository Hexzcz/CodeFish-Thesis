function openRightPanel(routeIndex) {
    document.getElementById('app').classList.add('right-panel-open');
    window.appState.rightPanelOpen = true;

    if (window.appState.routeFocusMode !== 'selected') {
        window.appState.routeFocusMode = 'selected';
    }

    const btnAct = document.getElementById('analysis-btn');
    if (btnAct) btnAct.classList.add('active');

    if (typeof updateRouteVisibility === 'function') updateRouteVisibility();

    populateRightPanel(routeIndex);
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
    window.appState.activeRouteIndex = routeIndex;

    populateOverview(routes, routeIndex);

    // Stamp _origIdx so map hover always targets the correct polyline edge
    const rawSegs = routes[routeIndex]?.properties?.segments || [];
    const stampedSegs = rawSegs.map((s, i) => ({ ...s, _origIdx: i }));
    populateSegmentList(stampedSegs, routeIndex);

    populateCompare(routes);
}

// Called from both Overview pills and bottom-bar tabs
function switchActiveRoute(index) {
    selectRoute(index);        // highlight on map
    populateRightPanel(index); // refresh side panel
}

function populateOverview(routes, activeIndex) {

    // Route pills
    const pillsEl = document.getElementById('route-pills');
    const colors = ['--route-1', '--route-2', '--route-3'];
    pillsEl.innerHTML = routes.map((r, i) => `
        <button class="route-pill ${i === activeIndex ? 'active' : ''}"
                style="--pill-color:var(${colors[i]})"
                onclick="switchActiveRoute(${i})">${i === activeIndex ? '▶ ' : ''}R${i + 1}</button>
    `).join('');


    const route = routes[activeIndex];
    const props = route?.properties || {};

    // Recommendation
    document.getElementById('recommendation-text').textContent =
        props.recommended
            ? `Route ${activeIndex + 1} is the optimal path based on TOPSIS analysis — balancing flood safety, distance, and road class.`
            : `Route ${activeIndex + 1} is an alternative evacuation path. The recommended route may offer better overall safety.`;

    // Metrics
    document.getElementById('m-distance').textContent = (props.total_length_km || 0).toFixed(2);
    document.getElementById('m-safety').textContent = Math.round(props.safety_score || 0);
    document.getElementById('m-flood').textContent = Math.round((props.flood_exposure || 0) * 100) + '%';
    document.getElementById('m-hazard').textContent = getRiskLabel(props.flood_exposure || 0);

    // Hazard bar
    const segs = props.segments || [];
    const safe = segs.filter(s => s.flood_proba < 0.10).length;
    const low = segs.filter(s => s.flood_proba >= 0.10 && s.flood_proba < 0.25).length;
    const mod = segs.filter(s => s.flood_proba >= 0.25 && s.flood_proba < 0.45).length;
    const high = segs.filter(s => s.flood_proba >= 0.45 && s.flood_proba < 0.65).length;
    const crit = segs.filter(s => s.flood_proba >= 0.65).length;
    const total = segs.length || 1;

    const barEl = document.getElementById('hazard-bar');
    barEl.innerHTML = [
        ['#4caf7d', safe], ['#8bc34a', low], ['#ffc107', mod],
        ['#ff7043', high], ['#e53935', crit]
    ].map(([color, count]) =>
        `<div style="width:${(count / total * 100).toFixed(1)}%;background:${color};"></div>`
    ).join('');

    const legEl = document.getElementById('hazard-legend');
    legEl.innerHTML = [
        ['#4caf7d', 'Safe', safe], ['#8bc34a', 'Low', low], ['#ffc107', 'Moderate', mod],
        ['#ff7043', 'High', high], ['#e53935', 'Critical', crit]
    ].filter(([, , c]) => c > 0).map(([color, label, count]) =>
        `<div class="hazard-legend-item"><div class="rl-dot" style="background:${color}"></div>${label} (${count})</div>`
    ).join('');

    // Criteria rows
    const criteriaEl = document.getElementById('criteria-rows');
    const topsis = props.topsis_score || 0;
    const wsm = props.wsm_path_cost || 0;
    const dist = props.total_length_km || 0;
    criteriaEl.innerHTML = `
        <div class="criteria-row">
            <span class="criteria-row-label">TOPSIS</span>
            <div class="criteria-row-bar"><div class="criteria-row-fill" style="width:${(topsis * 100).toFixed(1)}%"></div></div>
            <span class="criteria-row-score">${(topsis * 100).toFixed(1)}%</span>
        </div>
        <div class="criteria-row">
            <span class="criteria-row-label">WSM Cost</span>
            <div class="criteria-row-bar"><div class="criteria-row-fill" style="width:${Math.min(100, wsm * 10).toFixed(1)}%;background:var(--moderate)"></div></div>
            <span class="criteria-row-score">${wsm.toFixed(2)}</span>
        </div>
        <div class="criteria-row criteria-total">
            <span class="criteria-row-label">Distance</span>
            <div class="criteria-row-bar"><div class="criteria-row-fill" style="width:${Math.min(100, dist * 5).toFixed(1)}%;background:var(--text-tertiary)"></div></div>
            <span class="criteria-row-score">${dist.toFixed(2)} km</span>
        </div>
    `;
}

function populateSegmentList(segs, routeIndex) {
    // _origIdx is stamped on each segment by the caller, so map hover
    // always targets the correct polyline edge regardless of sort order.
    const rIdx = (routeIndex !== undefined && routeIndex !== null)
        ? routeIndex
        : window.appState.activeRouteIndex;
    const el = document.getElementById('segment-list');
    if (!segs || segs.length === 0) {
        el.innerHTML = '<div style="color:var(--text-tertiary);font-size:11px;padding:var(--sp-2)">No segment data.</div>';
        return;
    }
    el.innerHTML = segs.map((seg, i) => {
        const color = getRiskColorHex(seg.flood_proba || 0);
        const label = getRiskLabel(seg.flood_proba || 0);
        const dist = ((seg.length || 0) / 1000).toFixed(3);
        const pct = Math.round((seg.flood_proba || 0) * 100);
        const hw = (seg.highway || 'road').replace(/_/g, ' ');
        const mapIdx = (seg._origIdx !== undefined) ? seg._origIdx : i;
        return `
        <div class="segment-item"
             style="border-left-color:${color}"
             data-index="${mapIdx}"
             onmouseenter="highlightSegmentOnMap(${rIdx}, ${mapIdx})"
             onmouseleave="unhighlightSegmentOnMap(${rIdx}, ${mapIdx})"
             onclick="focusSegmentOnMap(${rIdx}, ${mapIdx})">
            <div class="seg-top">
                <span class="seg-name">${seg.name || 'Unnamed Road'}</span>
                <span class="seg-length">${dist} km</span>
            </div>
            <div class="seg-bar-wrap">
                <div class="seg-bar-fill" style="width:${pct}%;background:${color}"></div>
            </div>
            <div class="seg-meta">
                <span style="color:${color}">${label}</span>
                <span>${hw}</span>
                <span>P: ${pct}%</span>
                <span>elev ${(seg.elevation || 0).toFixed(1)}m</span>
            </div>
        </div>`;
    }).join('');

    const totalLen = segs.reduce((a, s) => a + (s.length || 0), 0);
    const avgFlood = segs.reduce((a, s) => a + (s.flood_proba || 0), 0) / (segs.length || 1);
    const maxClass = Math.max(...segs.map(s => s.flood_class || 0));
    const totalWsm = segs.reduce((a, s) => a + (s.wsm_cost || 0), 0);
    document.getElementById('segment-summary').innerHTML = `
        <div class="summary-row"><span>Total segments</span><span>${segs.length}</span></div>
        <div class="summary-row"><span>Total length</span><span>${(totalLen / 1000).toFixed(2)} km</span></div>
        <div class="summary-row"><span>Avg flood P</span><span>${Math.round(avgFlood * 100)}%</span></div>
        <div class="summary-row"><span>Max flood class</span><span>Class ${maxClass}</span></div>
        <div class="summary-row"><span>Total WSM cost</span><span>${totalWsm.toFixed(3)}</span></div>
    `;
}


function populateCompare(routes) {
    const colors = ['--route-1', '--route-2', '--route-3'];

    // Pills
    const selEl = document.getElementById('compare-selector');
    selEl.innerHTML = routes.map((_, i) => `
        <button class="compare-pill included"
                style="--pill-color:var(${colors[i]})"
                data-route="${i}">R${i + 1}</button>
    `).join('');

    // Table
    const tbl = document.getElementById('compare-table');
    const rows = [
        ['Distance (km)', routes.map(r => (r.properties.total_length_km || 0).toFixed(2)), 'min'],
        ['Suitability Score', routes.map(r => Math.round(r.properties.safety_score || 0)), 'max'],
        ['Flood Exp.', routes.map(r => Math.round((r.properties.flood_exposure || 0) * 100) + '%'), 'min'],
        ['TOPSIS Score', routes.map(r => ((r.properties.topsis_score || 0) * 100).toFixed(1) + '%'), 'max'],
        ['WSM Cost', routes.map(r => (r.properties.wsm_path_cost || 0).toFixed(2)), 'min'],
    ];

    const headers = routes.map((_, i) =>
        `<th style="color:var(${colors[i]})">R${i + 1}</th>`
    ).join('');

    const tableRows = rows.map(([label, vals, better]) => {
        const nums = vals.map(v => parseFloat(v));
        const best = better === 'min' ? Math.min(...nums) : Math.max(...nums);
        const worst = better === 'min' ? Math.max(...nums) : Math.min(...nums);
        const cells = vals.map((v, i) => {
            const n = nums[i];
            const cls = n === best ? 'best' : (n === worst && routes.length > 1 ? 'worst' : '');
            return `<td class="${cls}">${v}</td>`;
        }).join('');
        return `<tr><td>${label}</td>${cells}</tr>`;
    }).join('');

    tbl.innerHTML = `<thead><tr><th></th>${headers}</tr></thead><tbody>${tableRows}</tbody>`;
}
