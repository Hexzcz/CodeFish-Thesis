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

let _baselineLayer = null;
let _baselineVisible = false;
let _baselineCacheKey = null;
let _baselineCache = null;

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

function _getHighwayRank(hw) {
    const rankMap = {
        motorway: 1, motorway_link: 1,
        trunk: 2, trunk_link: 2,
        primary: 3, primary_link: 3,
        secondary: 4, secondary_link: 4,
        tertiary: 5, tertiary_link: 5,
        residential: 6,
        unclassified: 7,
        service: 8,
        living_street: 8,
        pedestrian: 9,
        footway: 9,
        path: 9,
    };
    if (Array.isArray(hw)) hw = hw[0];
    return rankMap[String(hw || 'unclassified')] || 10;
}

function _avgRoadClassRankFromSegments(segments) {
    if (!Array.isArray(segments) || segments.length === 0) return null;
    let sum = 0;
    let n = 0;
    segments.forEach(s => {
        const r = _getHighwayRank(s?.highway);
        if (Number.isFinite(r)) {
            sum += r;
            n += 1;
        }
    });
    return n ? (sum / n) : null;
}

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

function _renderBaselineCompare(selectedRouteFeature, baselineData) {
    const bodyEl = document.getElementById('compare-baseline-body');
    const toggleEl = document.getElementById('compare-baseline-toggle');
    if (!bodyEl || !toggleEl) return;

    toggleEl.classList.toggle('on', !!_baselineVisible);
    toggleEl.textContent = _baselineVisible ? 'HIDE ON MAP' : 'SHOW ON MAP';

    if (!selectedRouteFeature) {
        bodyEl.innerHTML = `<div class="compare-baseline-empty">Select a route to compare with the shortest path.</div>`;
        return;
    }

    const sProps = selectedRouteFeature.properties || {};
    const sSegs = sProps.segments || [];
    const sDist = Number(sProps.total_length_km || 0);
    const sFlood = Number(sProps.flood_exposure || 0);
    const sRoadRank = _avgRoadClassRankFromSegments(sSegs);

    const activeIdx = window.appState.activeRouteIndex || 0;
    const routeColors = ['--route-1', '--route-2', '--route-3'];
    const routeColorVar = routeColors[activeIdx] || '--route-1';

    if (!baselineData || !baselineData.feature) {
        bodyEl.innerHTML = `
            <div class="compare-baseline-grid loading">
                <div></div>
                <div class="compare-baseline-cell head route" style="--col-color:var(${routeColorVar})">
                    <span class="cell-tag">SELECTED</span>
                    <span class="cell-title">R${activeIdx + 1}</span>
                </div>
                <div class="compare-baseline-cell head shortest">
                    <span class="cell-tag">SHORTEST</span>
                    <span class="cell-title">Dijkstra</span>
                </div>
            </div>
            <div class="compare-baseline-loading">Computing shortest path…</div>`;
        return;
    }

    const bFeat = baselineData.feature;
    const bProps = bFeat.properties || {};
    const bSegs = bProps.segments || [];
    const bDist = Number(bProps.total_length_km || 0);
    const bFlood = Number(bProps.flood_exposure || 0);
    const bRoadRank = _avgRoadClassRankFromSegments(bSegs);

    const _delta = (selected, baseline, lowerIsBetter, fmt) => {
        if (selected === null || baseline === null || !Number.isFinite(selected) || !Number.isFinite(baseline)) {
            return { text: '', cls: 'neutral' };
        }
        const diff = selected - baseline;
        if (Math.abs(diff) < 1e-9) return { text: '= 0', cls: 'neutral' };
        const better = lowerIsBetter ? (diff < 0) : (diff > 0);
        const cls = better ? 'better' : 'worse';
        const arrow = better ? '▼' : '▲';
        return { text: `${arrow} ${fmt(diff)}`, cls };
    };

    const dDist = _delta(sDist, bDist, true, (v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)} km`);
    const dFlood = _delta(sFlood, bFlood, true, (v) => `${v >= 0 ? '+' : ''}${(v * 100).toFixed(0)}%`);
    const dRoad = _delta(sRoadRank, bRoadRank, true, (v) => `${v >= 0 ? '+' : ''}${v.toFixed(2)}`);

    const _cellWithDelta = (val, delta) => {
        const badge = delta && delta.text
            ? `<span class="delta-badge delta-${delta.cls}">${delta.text}</span>`
            : '';
        return `<div class="compare-baseline-cell value">
            <span class="value-num">${val}</span>${badge}
        </div>`;
    };

    bodyEl.innerHTML = `
        <div class="compare-baseline-grid">
            <div></div>
            <div class="compare-baseline-cell head route" style="--col-color:var(${routeColorVar})">
                <span class="cell-tag">SELECTED</span>
                <span class="cell-title">R${activeIdx + 1}</span>
            </div>
            <div class="compare-baseline-cell head shortest">
                <span class="cell-tag">SHORTEST</span>
                <span class="cell-title">Dijkstra</span>
            </div>

            <div class="compare-baseline-cell label">Distance</div>
            ${_cellWithDelta(`${sDist.toFixed(2)} km`, dDist)}
            <div class="compare-baseline-cell value"><span class="value-num">${bDist.toFixed(2)} km</span></div>

            <div class="compare-baseline-cell label">Flood Susc.</div>
            ${_cellWithDelta(`${Math.round(sFlood * 100)}%`, dFlood)}
            <div class="compare-baseline-cell value"><span class="value-num">${Math.round(bFlood * 100)}%</span></div>

            <div class="compare-baseline-cell label">Road Class</div>
            ${_cellWithDelta(sRoadRank === null ? '—' : sRoadRank.toFixed(2), dRoad)}
            <div class="compare-baseline-cell value"><span class="value-num">${bRoadRank === null ? '—' : bRoadRank.toFixed(2)}</span></div>
        </div>
        <div class="compare-baseline-note">
            <span class="legend-swatch"></span>
            Δ shown vs shortest. Lower = better for distance &amp; flood; lower road rank = higher-class road.
        </div>`;

    if (_baselineVisible) {
        _drawBaselineFeature(bFeat);
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

function populateOverview(routes, activeIndex) {

    // Route pills
    const pillsEl = document.getElementById('route-pills');
    const colors = ['--route-1', '--route-2', '--route-3'];
    pillsEl.innerHTML = routes.map((r, i) => `
        <button class="route-pill ${i === activeIndex ? 'active' : ''}"
                style="--pill-color:var(${colors[i]})"
                onclick="switchActiveRoute(${i})"
                onmouseover="highlightRouteFromTab(${i})"
                onmouseout="unhighlightRouteFromTab()">${i === activeIndex ? '▶ ' : ''}R${i + 1}</button>
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
        const hw = (seg.highway || 'road').replace(/_/g, ' ');
        const mapIdx = (seg._origIdx !== undefined) ? seg._origIdx : i;

        
        const pct = Math.round((seg.flood_proba || 0) * 100);
        const pArr = Array.isArray(seg.flood_proba_array) && seg.flood_proba_array.length
            ? seg.flood_proba_array
            : [1, 0, 0];
        const p0 = Number(pArr[0] || 0);
        const p1 = Number(pArr[1] || 0);
        const p2 = Number(pArr[2] || 0);
        const p3 = Number(pArr[3] || 0);
        const probabilityBlocks = pArr.length >= 4
            ? [
                ['Safe', p0, 'var(--safe)'],
                ['Low Risk', p1, 'var(--low)'],
                ['Moderate Risk', p2, 'var(--moderate)'],
                ['High Risk', p3, 'var(--critical)'],
            ]
            : [
                ['No Risk', p0, 'var(--safe)'],
                ['Low-Moderate Risk', p1, 'var(--moderate)'],
                ['High Risk', p2, 'var(--critical)'],
            ];
        const probabilityBar = probabilityBlocks.map(([title, value, bg]) => {
            const width = (value * 100).toFixed(1);
            return `<div title="${title}: ${width}%" style="width:${width}%; background:${bg}; height:100%;"></div>`;
        }).join('');

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
            
            <div class="seg-bar-wrap" style="display: flex; overflow: hidden; border-radius: 4px; height: 6px; background: #222;">
                ${probabilityBar}
            </div>
            
            <div style="display:flex; justify-content:space-between; font-size:10px; color:var(--text-tertiary); margin-top:4px;">
                <span>XGBoost Probability Distribution</span>
                <span style="color:${color}; font-weight:600;">Exp: ${Math.round((seg.flood_proba || 0) * 100)}%</span>
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


function switchCompareSubTab(tabName) {
    // Update tab buttons
    document.querySelectorAll('.compare-sub-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.tab === tabName);
    });

    // Update content panels
    document.getElementById('compare-tab-baseline').classList.toggle('hidden', tabName !== 'baseline');
    document.getElementById('compare-tab-generated').classList.toggle('hidden', tabName !== 'generated');
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

    const tbl = document.getElementById('compare-table');
    const baseRows = [
        ['Distance (km)', routes.map(r => (r.properties.total_length_km || 0).toFixed(2)), 'min'],
        ['Suitability Score', routes.map(r => Math.round(r.properties.safety_score || 0)), 'max'],
        ['Flood Exp.', routes.map(r => Math.round((r.properties.flood_exposure || 0) * 100) + '%'), 'min'],
        ['TOPSIS Score', routes.map(r => ((r.properties.topsis_score || 0) * 100).toFixed(1) + '%'), 'max'],
        ['WSM Cost', routes.map(r => (r.properties.wsm_path_cost || 0).toFixed(2)), 'min'],
    ];

    const headers = routes.map((_, i) =>
        `<th style="color:var(${colors[i]})">R${i + 1}</th>`
    ).join('');

    const renderRows = (rows) => rows.map(([label, vals, better]) => {
        if (better === 'section') {
            return `<tr class="section-divider"><td colspan="${routes.length + 1}">${label}</td></tr>`;
        }
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

    tbl.innerHTML = `<thead><tr><th></th>${headers}</tr></thead><tbody>${renderRows(baseRows)}</tbody>`;

    _updateInteractiveBaseline(routes);
}
