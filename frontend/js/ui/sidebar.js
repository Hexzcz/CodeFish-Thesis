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
        weights: window.appState.weights
    };

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
