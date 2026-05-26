// ── CRITERIA WEIGHTS ──
function onWeightInput() {
    const wf = parseFloat(document.getElementById('winput-flood').value) || 0;
    const wd = parseFloat(document.getElementById('winput-distance').value) || 0;
    const wr = parseFloat(document.getElementById('winput-road_class').value) || 0;
    const sum = Math.round((wf + wd + wr) * 1000) / 1000;

    const badge = document.getElementById('weight-sum-badge');
    const warning = document.getElementById('weight-warning');
    const detail = document.getElementById('weight-warning-detail');
    const saveBtn = document.getElementById('save-weights-btn');

    badge.textContent = sum.toFixed(3);
    const valid = Math.abs(sum - 1.0) < 0.0005;

    if (valid) {
        badge.className = 'weight-sum-valid';
        warning.classList.remove('visible');
        saveBtn.disabled = false;
    } else {
        badge.className = 'weight-sum-invalid';
        detail.textContent = 'Current sum: ' + sum.toFixed(3) + ' \u2014 must equal 1.000';
        warning.classList.add('visible');
        saveBtn.disabled = true;
    }
}

function saveWeights() {
    const wf = Math.round(parseFloat(document.getElementById('winput-flood').value) * 1000) / 1000;
    const wd = Math.round(parseFloat(document.getElementById('winput-distance').value) * 1000) / 1000;
    const wr = Math.round(parseFloat(document.getElementById('winput-road_class').value) * 1000) / 1000;
    const penalty = parseFloat(document.getElementById('penalty-factor-input').value);
    if (Math.abs(wf + wd + wr - 1.0) >= 0.0005) return;

    window.appState.weights.flood = wf;
    window.appState.weights.distance = wd;
    window.appState.weights.road_class = wr;
    window.appState.penaltyFactor = penalty > 0 ? penalty : 3.0;

    const saveBtn = document.getElementById('save-weights-btn');
    saveBtn.textContent = 'SAVED!';
    saveBtn.style.background = 'var(--safe)';
    saveBtn.style.color = '#fff';
    setTimeout(() => {
        saveBtn.textContent = 'SAVE WEIGHTS';
        saveBtn.style.background = '';
        saveBtn.style.color = '';
    }, 1600);
}

// Scenario selection
function selectScenario(scenario) {
    window.appState.scenario = scenario;
    document.querySelectorAll('.seg-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.scenario === scenario);
    });
}

// Wire scenario buttons
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.seg-btn').forEach(btn => {
        btn.addEventListener('click', () => selectScenario(btn.dataset.scenario));
    });
});

// Find routes
async function findRoutes() {
    if (!window.appState.originCoords) return;

    const findBtn = document.getElementById('find-routes-btn');
    findBtn.disabled = true;
    findBtn.classList.add('loading');
    findBtn.textContent = 'COMPUTING…';
    setStatus('COMPUTING', true);

    const body = {
        origin_lat: window.appState.originCoords.lat,
        origin_lon: window.appState.originCoords.lng,
        scenario: window.appState.scenario,
        k: K_ROUTES,
        weights: window.appState.weights,
        penalty_factor: window.appState.penaltyFactor
    };
    console.log('[CodeFish] Routing with scenario:', window.appState.scenario, body);

    try {
        const res = await fetch('/route', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        const data = await res.json();
        window.appState.routeData = data;

        drawAllRoutes(data.routes);
        showBottomBar(data.routes);
        updateRoutingSummary(data.routes);
        updateDecisionHeader(data.routes);
        document.getElementById('risk-legend').classList.remove('hidden');

        setStatus('DONE');
    } catch (err) {
        console.error('Route error:', err);
        setStatus('ERROR');
    } finally {
        findBtn.disabled = false;
        findBtn.classList.remove('loading');
        findBtn.textContent = 'FIND ROUTES';
        if (window.appState.originCoords) findBtn.disabled = false;
    }
}

// Clear all routing state
function clearRouting() {
    clearRoutes();         // handles [[seg,seg],[seg,seg]] format
    removeOriginMarker();
    window.appState.originCoords = null;
    window.appState.routeData = null;

    document.getElementById('place-origin-btn').className = 'origin-btn';
    document.getElementById('origin-btn-text').textContent = 'Click map to place';
    document.getElementById('coord-display').classList.remove('visible');
    const originSearch = document.getElementById('origin-search-input');
    if (originSearch) originSearch.value = '';
    const originResults = document.getElementById('origin-search-results');
    if (originResults) {
        originResults.classList.add('hidden');
        originResults.innerHTML = '';
    }
    document.getElementById('find-routes-btn').disabled = true;
    document.getElementById('route-summary').classList.add('hidden');
    document.getElementById('decision-header').classList.add('hidden');
    document.getElementById('risk-legend').classList.add('hidden');

    hideBottomBar();
    if (window.appState.rightPanelOpen) closeRightPanel();
    setStatus('READY');
}

function updateRoutingSummary(routes) {
    const best = routes.find(r => r.properties.recommended) || routes[0];
    const props = best.properties;
    document.getElementById('route-summary').classList.remove('hidden');
    document.getElementById('summary-count').textContent = `${routes.length} routes found`;
    document.getElementById('summary-best').textContent = `Best → ${props.destination_name || 'Evacuation Center'} · ${(props.total_length_km || 0).toFixed(2)} km`;
}

function updateDecisionHeader(routes) {
    const best = routes.find(r => r.properties.recommended) || routes[0];
    const props = best.properties;
    document.getElementById('dh-destination').textContent = props.destination_name || 'Nearest Evacuation Center';
    document.getElementById('dh-meta').textContent = `${(props.total_length_km || 0).toFixed(2)} km · ${Math.round(props.safety_score || 0)}% safe`;
    document.getElementById('decision-header').classList.remove('hidden');
}
