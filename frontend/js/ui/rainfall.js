/**
 * Rainfall Scenario Logic for CodeFish
 */

function setRainfallMode(mode) {
    window.appState.rainfallMode = mode;
    document.getElementById('mode-jaxa-btn').classList.toggle('active', mode === 'jaxa');
    document.getElementById('mode-sim-btn').classList.toggle('active', mode === 'simulation');
    document.getElementById('jaxa-panel').style.display = mode === 'jaxa' ? 'block' : 'none';
    document.getElementById('sim-panel').style.display = mode === 'simulation' ? 'block' : 'none';

    if (mode === 'jaxa') {
        fetchJaxaRainfall();
    }
    updateScenarioBadge();
}

function setJaxaTab(tab) {
    window.appState.jaxaTab = tab;
    document.getElementById('jaxa-tab-forecast').classList.toggle('active', tab === 'forecast');
    document.getElementById('jaxa-tab-historical').classList.toggle('active', tab === 'historical');
    document.getElementById('jaxa-forecast-controls').style.display = tab === 'forecast' ? 'block' : 'none';
    document.getElementById('jaxa-historical-controls').style.display = tab === 'historical' ? 'block' : 'none';
    fetchJaxaRainfall();
    updateScenarioBadge();
}

function setSimulation(level) {
    const mapping = { 'low': '5yr', 'medium': '25yr', 'high': '100yr' };
    window.appState.scenario = mapping[level];
    document.getElementById('sim-btn-low').classList.toggle('active', level === 'low');
    document.getElementById('sim-btn-medium').classList.toggle('active', level === 'medium');
    document.getElementById('sim-btn-high').classList.toggle('active', level === 'high');
    updateScenarioBadge();
}

function setForecastRange(range) {
    window.appState.forecastRange = range;
    document.getElementById('range-short-btn').classList.toggle('active', range === 'short');
    document.getElementById('range-medium-btn').classList.toggle('active', range === 'medium');

    // Show/hide the step selector panels (use 'flex' — .rf-step-block is a flex container)
    document.getElementById('jaxa-short-selector').style.display = range === 'short' ? 'flex' : 'none';
    document.getElementById('jaxa-medium-selector').style.display = range === 'medium' ? 'flex' : 'none';
}

/**
 * Set a specific forecast step (hour for short, day for medium).
 * @param {'short'|'medium'} range
 * @param {number} step
 */
function setForecastStep(range, step) {
    window.appState.forecastStep = step;

    const pillsId = range === 'short' ? 'short-hour-pills' : 'medium-day-pills';
    const container = document.getElementById(pillsId);
    if (container) {
        container.querySelectorAll('.rf-step-btn').forEach(btn => btn.classList.remove('active'));
        // Activate by index (step is 1-based)
        const btns = container.querySelectorAll('.rf-step-btn');
        if (btns[step - 1]) btns[step - 1].classList.add('active');
    }
}

function updateScenarioBadge() {
    const badge = document.getElementById('scenario-status');
    if (!badge || !window.appState) return;

    if (window.appState.rainfallMode === 'jaxa') {
        const sub = (window.appState.jaxaTab || 'forecast').toUpperCase();
        badge.textContent = `JAXA | ${sub}`;
    } else {
        const s = window.appState.scenario;
        let lbl = 'MED';
        if (s === '5yr') lbl = 'LOW';
        if (s === '100yr') lbl = 'HIGH';
        badge.textContent = `SIM | ${lbl}`;
    }
}

// ── Spinner helpers ──────────────────────────────────────────────────────────
function _showJaxaSpinner() {
    const spinner = document.getElementById('jaxa-fetch-spinner');
    const intEl = document.getElementById('jaxa-intensity');
    if (spinner) spinner.style.display = 'inline-block';
    if (intEl) intEl.textContent = '';
}

function _hideJaxaSpinner() {
    const spinner = document.getElementById('jaxa-fetch-spinner');
    if (spinner) spinner.style.display = 'none';
}

// ── FTP fetch ────────────────────────────────────────────────────────────────
async function fetchJaxaFromFTP() {
    const btn = document.getElementById('jaxa-ftp-btn');
    if (btn) { btn.disabled = true; btn.classList.add('loading'); }

    _showJaxaSpinner();

    const mode = window.appState.jaxaTab || 'forecast';
    const range = window.appState.forecastRange || 'short';
    const step = window.appState.forecastStep || 1;
    const timestamp = (mode === 'historical')
        ? document.getElementById('jaxa-historical-time').value
        : null;

    const intensityEl = document.getElementById('jaxa-intensity');
    const mappingEl = document.getElementById('jaxa-mapping');

    try {
        let url = `/rainfall/jaxa/ftp?mode=${mode}&range=${range}&step=${step}`;
        if (timestamp) url += `&timestamp=${timestamp}`;

        const res = await fetch(url);
        const data = await res.json();

        if (intensityEl) intensityEl.textContent = data.intensity.toFixed(2);
        if (mappingEl) mappingEl.textContent = data.mapping.replace('yr', '-Year');
        window.appState.scenario = data.mapping;

        console.log('JAXA FTP Data Received:', data);
    } catch (e) {
        if (intensityEl) intensityEl.textContent = 'Err';
        console.error('JAXA FTP Fetch Error:', e);
    } finally {
        _hideJaxaSpinner();
        if (btn) { btn.disabled = false; btn.classList.remove('loading'); }
    }
    updateScenarioBadge();
}

// ── Regular auto-fetch ───────────────────────────────────────────────────────
async function fetchJaxaRainfall() {
    const mode = window.appState.jaxaTab || 'forecast';
    const range = window.appState.forecastRange || 'short';
    const step = window.appState.forecastStep || 1;
    const timestamp = (mode === 'historical')
        ? document.getElementById('jaxa-historical-time').value
        : null;

    const intensityEl = document.getElementById('jaxa-intensity');
    const mappingEl = document.getElementById('jaxa-mapping');

    if (!intensityEl) return;

    _showJaxaSpinner();

    try {
        let url = `/rainfall/jaxa?mode=${mode}&range=${range}&step=${step}`;
        if (timestamp) url += `&timestamp=${timestamp}`;

        const res = await fetch(url);
        const data = await res.json();

        if (intensityEl) intensityEl.textContent = data.intensity.toFixed(2);
        if (mappingEl) mappingEl.textContent = data.mapping.replace('yr', '-Year');
        window.appState.scenario = data.mapping;

        console.log('JAXA Data Received:', data);
    } catch (e) {
        if (intensityEl) intensityEl.textContent = 'Err';
        console.error('JAXA Fetch Error:', e);
    } finally {
        _hideJaxaSpinner();
    }
}

// ── Init ─────────────────────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
    // Set default date for historical
    const histInput = document.getElementById('jaxa-historical-time');
    if (histInput) {
        const now = new Date();
        now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
        histInput.value = now.toISOString().slice(0, 16);
    }

    // Default step values
    if (!window.appState.forecastStep) window.appState.forecastStep = 1;
    if (!window.appState.forecastRange) window.appState.forecastRange = 'short';

    if (window.appState.rainfallMode === 'jaxa') {
        fetchJaxaRainfall();
    }
    updateScenarioBadge();
});
