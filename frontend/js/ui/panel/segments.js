/**
 * The segment tab: every road the route uses, in order.
 */

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
    const colorLegend = `
        <div style="
            font-size:10.5px; color:var(--text-tertiary);
            padding:7px 10px 10px 10px;
            border-bottom:1px solid var(--border-subtle);
            margin-bottom:6px;
            line-height:1.6;
        ">
            <span style="font-weight:600; color:var(--text-secondary);">Flood Susceptibility Score</span><br>
            <span>
                Each segment's score (0–100%) is predicted by the XGBoost model based on the road's
                terrain features — elevation, slope, HAND, TWI, and proximity to waterways.
                A higher score means the road sits in terrain <em>more prone</em> to flood inundation
                under the selected return period. It reflects <strong>spatial hazard susceptibility</strong>,
                not a real-time flood forecast.
            </span>
            <div style="display:flex; align-items:center; gap:6px; flex-wrap:wrap; margin-top:6px;">
                <span style="color:var(--text-tertiary); font-size:10px; margin-right:2px;">Color coding —</span>
                <span style="display:inline-flex;align-items:center;gap:3px;font-size:10px;"><span style="width:9px;height:9px;border-radius:2px;background:#4caf7d;display:inline-block;"></span>Safe (&lt;10%)</span>
                <span style="display:inline-flex;align-items:center;gap:3px;font-size:10px;"><span style="width:9px;height:9px;border-radius:2px;background:#8bc34a;display:inline-block;"></span>Low (10–25%)</span>
                <span style="display:inline-flex;align-items:center;gap:3px;font-size:10px;"><span style="width:9px;height:9px;border-radius:2px;background:#ffc107;display:inline-block;"></span>Moderate (25–45%)</span>
                <span style="display:inline-flex;align-items:center;gap:3px;font-size:10px;"><span style="width:9px;height:9px;border-radius:2px;background:#ff7043;display:inline-block;"></span>High (45–65%)</span>
                <span style="display:inline-flex;align-items:center;gap:3px;font-size:10px;"><span style="width:9px;height:9px;border-radius:2px;background:#e53935;display:inline-block;"></span>Critical (&gt;65%)</span>
            </div>
        </div>`;

    el.innerHTML = colorLegend + segs.map((seg, i) => {
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
