// ─────────────────────────────────────────────────────────────────────────────
// Evacuation Centers – Clustering + Visualization
// Mirrors the backend `cluster_evacuation_centers()` logic in geojson_builder.py
// ─────────────────────────────────────────────────────────────────────────────

const EVAC_CLUSTER_RADIUS_M = 50; // must match backend DEFAULT_DESTINATION_CLUSTER_RADIUS_M
const LAT_TO_M = 111320.0;
const LON_TO_M = 107600.0;

// ── Global marker registry so popup inline handlers can reference markers ────
// Cleared on every drawCenters() call to avoid stale references.
window._evacMemberMarkers = {};

// Called from popup HTML: onmouseenter="highlightEvacMember('id')"
function highlightEvacMember(id) {
    const m = window._evacMemberMarkers[id];
    if (!m) return;
    m.setRadius(9);
    m.setStyle({ fillColor: '#ffffff', color: '#4caf7d', weight: 2.5, fillOpacity: 1 });
    m.bringToFront();
}

// Called from popup HTML: onmouseleave="unhighlightEvacMember('id')"
function unhighlightEvacMember(id) {
    const m = window._evacMemberMarkers[id];
    if (!m) return;
    m.setRadius(5);
    m.setStyle({ fillColor: '#4caf7d', color: '#ffffff', weight: 1.5, fillOpacity: 0.9 });
}

// ── Flat euclidean approximation (same as backend) ──────────────────────────
function _distM(a, b) {
    const dlat = (a.lat - b.lat) * LAT_TO_M;
    const dlon = (a.lon - b.lon) * LON_TO_M;
    return Math.sqrt(dlat * dlat + dlon * dlon);
}

// ── Mirror of backend cluster_evacuation_centers() ──────────────────────────
function clusterCenters(features) {
    const centers = features.map(f => ({
        lat: Number(f.geometry.coordinates[1]),
        lon: Number(f.geometry.coordinates[0]),
        feature: f
    }));

    const remaining = [...centers];
    const clusters = [];

    while (remaining.length > 0) {
        const seed = remaining.shift();
        const members = [seed];
        const queue = [seed];

        while (queue.length > 0) {
            const current = queue.shift();
            const toRemove = [];
            remaining.forEach((c, i) => {
                if (_distM(current, c) <= EVAC_CLUSTER_RADIUS_M) {
                    toRemove.push(i);
                    members.push(c);
                    queue.push(c);
                }
            });
            for (let i = toRemove.length - 1; i >= 0; i--) {
                remaining.splice(toRemove[i], 1);
            }
        }

        // Centroid
        const centroidLat = members.reduce((s, c) => s + c.lat, 0) / members.length;
        const centroidLon = members.reduce((s, c) => s + c.lon, 0) / members.length;

        // Enclosing radius = max dist from centroid to any member + padding
        let maxDist = 0;
        members.forEach(c => {
            const d = _distM({ lat: centroidLat, lon: centroidLon }, c);
            if (d > maxDist) maxDist = d;
        });

        clusters.push({
            members,
            centroidLat,
            centroidLon,
            enclosingRadius: members.length > 1 ? Math.max(maxDist + 22, 40) : 0,
            isCluster: members.length > 1
        });
    }

    return clusters;
}

// ── Toggle handler (called from HTML) ───────────────────────────────────────
function handleCentersToggle(el) {
    el.classList.toggle('active');
    const visible = el.classList.contains('active');
    toggleEvacCenters(visible);
}

function toggleEvacCenters(visible) {
    window.appState.centersVisible = visible;
    if (!visible) {
        if (window.appState.centersLayer) window.appState.map.removeLayer(window.appState.centersLayer);
    } else {
        if (!window.appState.centersGeoJSON) fetchCenters();
        else drawCenters(window.appState.centersGeoJSON);
    }
}

// ── Fetch from backend ───────────────────────────────────────────────────────
async function fetchCenters() {
    try {
        const response = await fetch('/evacuation-centers');
        const data = await response.json();
        window.appState.centersGeoJSON = data;
        drawCenters(data);

        const totalCount = data.features ? data.features.length : 0;
        const clusterCount = clusterCenters(data.features || []).length;
        const el = document.getElementById('centers-showing');
        if (el) {
            el.textContent = `${totalCount} centers · ${clusterCount} routing destinations`;
        }
    } catch (e) {
        console.error('Error fetching centers:', e);
    }
}

// ── Main draw function ───────────────────────────────────────────────────────
function drawCenters(data) {
    if (window.appState.centersLayer) window.appState.map.removeLayer(window.appState.centersLayer);

    // Clear stale marker references from previous render
    window._evacMemberMarkers = {};

    const features = data && data.features ? data.features : [];
    const clusters = clusterCenters(features);
    const group = L.featureGroup();

    // Use a monotonic counter for stable unique IDs within a render pass
    let markerSeq = 0;

    clusters.forEach(cluster => {
        const { members, centroidLat, centroidLon, enclosingRadius, isCluster } = cluster;

        if (isCluster) {
            // ── 1. Dashed enclosing ring (bottom layer) ───────────────────────
            L.circle([centroidLat, centroidLon], {
                radius: enclosingRadius,
                color: '#e8c547',
                weight: 1.5,
                opacity: 0.65,
                fillColor: '#e8c547',
                fillOpacity: 0.06,
                dashArray: '5 5',
                interactive: false
            }).addTo(group);

            // ── 2. Centroid marker — popup lists members with hover effect ─────
            // Build marker IDs first so popup HTML can reference them
            const memberIds = members.map(() => `evm_${markerSeq++}`);

            const nameRows = members.map((m, i) => {
                const name = m.feature.properties.facility || 'Center';
                const id = memberIds[i];
                return (
                    `<div style="` +
                        `padding:3px 6px;` +
                        `margin:1px 0;` +
                        `border-radius:3px;` +
                        `cursor:default;` +
                        `transition:background 0.15s;` +
                        `font-size:10px;color:#b0b0b0;` +
                    `" ` +
                    `onmouseenter="this.style.background='rgba(76,175,125,0.15)';highlightEvacMember('${id}')" ` +
                    `onmouseleave="this.style.background='transparent';unhighlightEvacMember('${id}')">` +
                        `<span style="color:#4caf7d;margin-right:4px;">●</span>${name}` +
                    `</div>`
                );
            }).join('');

            const popupHTML =
                `<div style="min-width:165px;">` +
                `<strong style="font-size:12px;display:block;margin-bottom:2px;">` +
                `Cluster of ${members.length} Centers</strong>` +
                `<span style="font-size:10px;color:#e8c547;display:block;margin-bottom:6px;">` +
                `⊕ Routing destination</span>` +
                `<div style="border-top:1px solid rgba(255,255,255,0.1);padding-top:4px;">` +
                `<div style="font-size:9px;color:#555;letter-spacing:0.5px;margin-bottom:3px;">` +
                `HOVER TO LOCATE</div>` +
                `${nameRows}` +
                `</div></div>`;

            L.circleMarker([centroidLat, centroidLon], {
                radius: 8,
                fillColor: '#e8c547',
                color: '#ffffff',
                weight: 2.5,
                opacity: 1,
                fillOpacity: 1
            }).bindPopup(popupHTML, { maxWidth: 220 }).addTo(group);

            // ── 3. Individual member dots (top layer, registered in registry) ──
            members.forEach((m, i) => {
                const p = m.feature.properties;
                const marker = L.circleMarker([m.lat, m.lon], {
                    radius: 5,
                    fillColor: '#4caf7d',
                    color: '#ffffff',
                    weight: 1.5,
                    opacity: 1,
                    fillOpacity: 0.9
                }).bindPopup(
                    `<strong>${p.facility || 'Center'}</strong><br>` +
                    `<span style="font-size:11px;color:#909090;">${p.barangay || ''}</span><br>` +
                    `<span style="font-size:10px;color:#e8c547;">Part of a cluster</span>`
                ).addTo(group);

                // Register so highlight functions can find it
                window._evacMemberMarkers[memberIds[i]] = marker;
            });

        } else {
            // ── Solo center ───────────────────────────────────────────────────
            const p = members[0].feature.properties;
            L.circleMarker([members[0].lat, members[0].lon], {
                radius: 7,
                fillColor: '#4caf7d',
                color: '#ffffff',
                weight: 2,
                opacity: 1,
                fillOpacity: 0.9
            }).bindPopup(
                `<strong>${p.facility || 'Center'}</strong><br>` +
                `<span style="font-size:11px;color:#909090;">${p.barangay || ''}</span>`
            ).addTo(group);
        }
    });

    group.addTo(window.appState.map);
    window.appState.centersLayer = group;
}
