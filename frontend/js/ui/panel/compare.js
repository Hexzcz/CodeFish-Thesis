/**
 * The compare tab: this route against the plain shortest-distance route.
 *
 * Rendering only. Getting the baseline is baseline.js.
 */

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
