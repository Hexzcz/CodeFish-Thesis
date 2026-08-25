/**
 * The overview tab: how this route scores, and why.
 */

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
