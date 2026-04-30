// Raster layer management

function buildTileUrl(layerName) {
    const clip = window.appState.clipEnabled ? 'true' : 'false';
    return `${API_BASE}/tiles/${layerName}/{z}/{x}/{y}.png?clip=${clip}&t=${Date.now()}`;
}

function handleLayerToggle(el) {
    const id = el.dataset.layer;
    const isActive = el.classList.contains('active');
    const cfg = window.appState.config.layers;

    // Flood layers are radio-grouped
    if (cfg[id] && cfg[id].group === 'flood' && !isActive) {
        Object.keys(cfg).forEach(k => {
            if (cfg[k].group === 'flood' && k !== id && cfg[k].visible) {
                const otherEl = document.querySelector(`[data-layer="${k}"]`);
                if (otherEl) otherEl.classList.remove('active');
                removeRasterLayer(k);
                cfg[k].visible = false;
                const opEl = document.getElementById(`opacity-cnt-${k}`);
                if (opEl) opEl.classList.add('hidden');
            }
        });
    }

    if (isActive) {
        el.classList.remove('active');
        removeRasterLayer(id);
        if (cfg[id]) cfg[id].visible = false;
        const opEl = document.getElementById(`opacity-cnt-${id}`);
        if (opEl) opEl.classList.add('hidden');
    } else {
        el.classList.add('active');
        addRasterLayer(id);
        if (cfg[id]) cfg[id].visible = true;
        const opEl = document.getElementById(`opacity-cnt-${id}`);
        if (opEl) opEl.classList.remove('hidden');
    }
}

function addRasterLayer(id) {
    const cfg = window.appState.config.layers[id];
    if (!cfg || cfg.leafletLayer) return;
    const url = buildTileUrl(id);
    const layer = L.tileLayer(url, {
        maxZoom: 22,
        opacity: cfg.opacity
    }).addTo(window.appState.map);
    cfg.leafletLayer = layer;
}

function removeRasterLayer(id) {
    const cfg = window.appState.config.layers[id];
    if (!cfg || !cfg.leafletLayer) return;
    window.appState.map.removeLayer(cfg.leafletLayer);
    cfg.leafletLayer = null;
}

function updateLayerOpacity(id, val) {
    const cfg = window.appState.config.layers[id];
    if (!cfg) return;
    cfg.opacity = val / 100;
    if (cfg.leafletLayer) cfg.leafletLayer.setOpacity(cfg.opacity);
}

// Clip toggle (called from HTML onclick)
function toggleClip() {
    const el = document.getElementById('clip-toggle');
    el.classList.toggle('active');
    window.appState.clipEnabled = el.classList.contains('active');
    // Refresh all active raster layers
    Object.keys(window.appState.config.layers).forEach(id => {
        const cfg = window.appState.config.layers[id];
        if (cfg.visible && cfg.leafletLayer) {
            removeRasterLayer(id);
            addRasterLayer(id);
        }
    });
}
