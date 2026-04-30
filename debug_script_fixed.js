
        // Tab switching logic
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById('panel-' + tab.dataset.panel).classList.add('active');
            });
        });

        

        // ══════════════════════════════════════════
        // Layer Configuration
        // ══════════════════════════════════════════
        const LAYERS = {
            flood_5yr: { group: "flood", visible: false, opacity: 0.7, leafletLayer: null },
            flood_25yr: { group: "flood", visible: false, opacity: 0.7, leafletLayer: null },
            flood_100yr: { group: "flood", visible: false, opacity: 0.7, leafletLayer: null },
            land_cover: { group: "env", visible: false, opacity: 0.7, leafletLayer: null },
            dist_waterway: { group: "env", visible: false, opacity: 0.7, leafletLayer: null },
            elevation: { group: "terrain", visible: false, opacity: 0.7, leafletLayer: null },
            slope: { group: "terrain", visible: false, opacity: 0.7, leafletLayer: null }
        };

        let clipEnabled = true;

        // ── Map Init ──
        const map = L.map('map', { zoomControl: false, maxZoom: 22 }).setView([14.645, 121.02], 14);
        L.control.zoom({ position: 'topright' }).addTo(map);

        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
            attribution: 'Tiles &copy; Esri', maxZoom: 22, maxNativeZoom: 16
        }).addTo(map);

        // ── Boundary ──
        fetch('/boundary')
            .then(r => r.json())
            .then(data => {
                L.geoJSON(data, {
                    style: { color: "#00d4ff", weight: 2, dashArray: "8, 6", fillOpacity: 0, opacity: 0.8 }
                }).addTo(map);
            })
            .catch(e => console.error("Boundary load error:", e));

        // ══════════════════════════════════════════
        // Sidebar Toggle
        // ══════════════════════════════════════════
        const sidebar = document.getElementById('sidebar');
        const toggleBtn = document.getElementById('sidebar-toggle');
        const toggleIcon = document.getElementById('toggle-icon');

        function toggleSidebar() {
            const isOpen = !sidebar.classList.contains('closed');
            sidebar.classList.toggle('closed');
            toggleIcon.innerText = isOpen ? '→' : '←';
            setTimeout(() => map.invalidateSize(), 305);
        }
        toggleBtn.addEventListener('click', toggleSidebar);

        // ══════════════════════════════════════════
        // Raster Layer Management
        // ══════════════════════════════════════════
        function toggleClip(enabled) {
            clipEnabled = enabled;
            const loader = document.getElementById('loader');
            loader.style.display = 'block';
            Object.keys(LAYERS).forEach(id => {
                if (LAYERS[id].visible) { removeLayer(id); addLayer(id); }
            });
            setTimeout(() => { loader.style.display = 'none'; map.invalidateSize(); }, 500);
        }

        function updateLayer(layerId, visible) {
            const config = LAYERS[layerId];
            config.visible = visible;
            if (visible && config.group === 'flood') {
                Object.keys(LAYERS).forEach(id => {
                    if (LAYERS[id].group === 'flood' && id !== layerId) {
                        removeLayer(id); LAYERS[id].visible = false;
                        document.getElementById('check-' + id).checked = false;
                    }
                });
            }
            visible ? addLayer(layerId) : removeLayer(layerId);
        }

        function addLayer(layerId) {
            const config = LAYERS[layerId];
            if (config.leafletLayer) return;
            config.leafletLayer = L.tileLayer(
                `/tiles/${layerId}/{z}/{x}/{y}.png?clip=${clipEnabled}`,
                { opacity: config.opacity, maxZoom: 22, maxNativeZoom: 18 }
            ).addTo(map);
        }

        function removeLayer(layerId) {
            const config = LAYERS[layerId];
            if (config.leafletLayer) { map.removeLayer(config.leafletLayer); config.leafletLayer = null; }
        }

        function updateOpacity(layerId, value) {
            LAYERS[layerId].opacity = value / 100;
            if (LAYERS[layerId].leafletLayer) LAYERS[layerId].leafletLayer.setOpacity(value / 100);
        }

        function toggleGroup(groupId, visible) {
            Object.keys(LAYERS).forEach(id => {
                if (LAYERS[id].group === groupId) {
                    if (groupId === 'flood') {
                        if (visible) {
                            updateLayer('flood_5yr', true);
                            document.getElementById('check-flood_5yr').checked = true;
                        } else {
                            ['flood_5yr', 'flood_25yr', 'flood_100yr'].forEach(f => {
                                updateLayer(f, false);
                                document.getElementById('check-' + f).checked = false;
                            });
                        }
                    } else {
                        updateLayer(id, visible);
                        document.getElementById('check-' + id).checked = visible;
                    }
                }
            });
        }

        function toggleCollapse(groupId) {
            document.getElementById(groupId).classList.toggle('collapsed');
        }

        // ══════════════════════════════════════════
        // Road Network State
        // ══════════════════════════════════════════
        let roadData = null;
        let roadLayer = null;
        let roadVisible = false;
        let classStyleOn = false;
        let floodRiskOn = false;
        let connHighlightOn = false;
        let floodRiskCache = {};   // { "5yr": {osmid: props, ...}, ... }
        let selectedRoadId = null; // osmid of currently selected road
        let selectedRoadName = null; // if connHighlightOn is true, stores the name
        let selectedLayers = []; // leaflet layer references
        const tooltip = document.getElementById('road-tooltip');
        const tooltipName = document.getElementById('road-tooltip-name');
        const tooltipMeta = document.getElementById('road-tooltip-meta');

        // ── Highway style config ──
        const HIGHWAY_STYLES = {
            primary: { color: '#00d4ff', weight: 4 },
            secondary: { color: '#4da6ff', weight: 3 },
            tertiary: { color: '#7ec8e3', weight: 2 },
            residential: { color: '#4a5568', weight: 1.5 },
            service: { color: '#2d3748', weight: 1 },
        };
        const DEFAULT_ROAD_STYLE = { color: '#94a3b8', weight: 1.5 };

        function getClassStyleForHighway(highway) {
            return HIGHWAY_STYLES[highway] || { color: '#2d3748', weight: 1 };
        }

        function formatHighwayName(hw) {
            if (!hw) return 'Road';
            const map = {
                primary: 'Primary Road', secondary: 'Secondary Road',
                tertiary: 'Tertiary Road', residential: 'Residential Road',
                service: 'Service Road', trunk: 'Trunk Road',
                motorway: 'Motorway', unclassified: 'Unclassified Road'
            };
            return map[hw] || hw.charAt(0).toUpperCase() + hw.slice(1) + ' Road';
        }

        // ── Determine current base style for a feature ──
        function getBaseStyle(feature) {
            const props = feature.properties;
            const hw = props.highway;

            if (floodRiskOn) {
                // Override with flood risk colour
                const prob = props.flood_probability || 0;
                let color = '#00ff88';
                if (prob >= 0.6) color = '#ff0000';
                else if (prob >= 0.3) color = '#ffaa00';
                const w = classStyleOn ? (getClassStyleForHighway(hw).weight || 1.5) : 1.5;
                return { color, weight: w, opacity: 0.85, fillOpacity: 0 };
            }
            if (classStyleOn) {
                const cs = getClassStyleForHighway(hw);
                return { color: cs.color, weight: cs.weight, opacity: 0.8, fillOpacity: 0 };
            }
            return { color: DEFAULT_ROAD_STYLE.color, weight: DEFAULT_ROAD_STYLE.weight, opacity: 0.7, fillOpacity: 0 };
        }

        // ─────────────────────────────────────────
        // Road data loading
        // ─────────────────────────────────────────
        function loadRoads() {
            if (roadData) return Promise.resolve(roadData);
            return fetch('/roads')
                .then(r => r.json())
                .then(data => { roadData = data; return data; });
        }

        // ─────────────────────────────────────────
        // Toggle master road visibility
        // ─────────────────────────────────────────
        function toggleRoadMaster(show) {
            roadVisible = show;
            const subtoggleArea = document.getElementById('road-subtoggle-area');
            const switches = ['road-class-switch', 'road-risk-switch', 'road-conn-switch'];

            if (show) {
                subtoggleArea.classList.add('visible');
                switches.forEach(s => document.getElementById(s).classList.remove('disabled'));
                loadRoads().then(_data => {
                    renderRoadLayer();
                }).catch(e => console.error("Road load error:", e));
            } else {
                subtoggleArea.classList.remove('visible');
                switches.forEach(s => document.getElementById(s).classList.add('disabled'));
                if (roadLayer) { map.removeLayer(roadLayer); roadLayer = null; }
                selectedRoadId = null;
                deselectRoad();
            }
        }

        // ─────────────────────────────────────────
        // Render / re-style road layer
        // ─────────────────────────────────────────
        function renderRoadLayer() {
            if (!roadData) return;

            if (roadLayer) { map.removeLayer(roadLayer); roadLayer = null; }

            roadLayer = L.geoJSON(roadData, {
                style: feature => getBaseStyle(feature),
                onEachFeature: attachRoadInteractions
            });

            roadLayer.addTo(map);
        }

        function restyleRoadLayer() {
            if (!roadLayer) return;
            roadLayer.eachLayer(layer => {
                if (layer.feature) {
                    const baseStyle = getBaseStyle(layer.feature);
                    // Don't override selected highlight—just track it
                    const isSelected = layer.feature.properties.osmid == selectedRoadId;
                    if (isSelected) {
                        layer.setStyle({ ...baseStyle, color: '#ffaa00', weight: baseStyle.weight + 2 });
                    } else {
                        layer.setStyle(baseStyle);
                    }
                }
            });
        }

        // ─────────────────────────────────────────
        // Classification Style toggle
        // ─────────────────────────────────────────
        function toggleClassification(on) {
            classStyleOn = on;
            if (!floodRiskOn) restyleRoadLayer();
        }

        // ─────────────────────────────────────────
        // Flood Risk Overlay toggle
        // ─────────────────────────────────────────
        function getActiveFloodScenario() {
            if (LAYERS.flood_5yr.visible) return '5yr';
            if (LAYERS.flood_25yr.visible) return '25yr';
            if (LAYERS.flood_100yr.visible) return '100yr';
            return '25yr'; // default
        }

        async function toggleFloodRisk(on) {
            floodRiskOn = on;
            document.getElementById('road-info-risk-row').style.display = on ? '' : 'none';

            if (!on) { restyleRoadLayer(); return; }

            const scenario = getActiveFloodScenario();
            const spinner = document.getElementById('risk-spinner');

            if (floodRiskCache[scenario]) {
                applyFloodRiskData(floodRiskCache[scenario]);
                return;
            }

            spinner.style.display = 'inline-block';
            try {
                const resp = await fetch(`/roads/flood-risk?scenario=${scenario}`);
                const data = await resp.json();

                // Build lookup by osmid
                const lookup = {};
                data.features.forEach(f => {
                    const id = f.properties.osmid;
                    lookup[id] = f.properties;
                });
                floodRiskCache[scenario] = lookup;
                applyFloodRiskData(lookup);
            } catch (e) {
                console.error("Flood risk fetch error:", e);
            } finally {
                spinner.style.display = 'none';
            }
        }

        function applyFloodRiskData(lookup) {
            if (!roadLayer) return;
            roadLayer.eachLayer(layer => {
                if (!layer.feature) return;
                const osmid = layer.feature.properties.osmid;
                if (lookup[osmid]) {
                    layer.feature.properties.flood_probability = lookup[osmid].flood_probability;
                    layer.feature.properties.flood_class = lookup[osmid].flood_class;
                    layer.feature.properties.risk_label = lookup[osmid].risk_label;
                }
            });
            restyleRoadLayer();
        }

        // ─────────────────────────────────────────
        // Connected Highlight toggle
        // ─────────────────────────────────────────
        function toggleConnectedHighlight(on) {
            connHighlightOn = on;
        }

        // ─────────────────────────────────────────
        // Road interactions
        // ─────────────────────────────────────────
        function attachRoadInteractions(feature, layer) {
            const props = feature.properties;
            const name = props.name || 'Unnamed Road';
            const hw = props.highway || '';
            const len = props.length ? (props.length >= 1000
                ? (props.length / 1000).toFixed(2) + ' km'
                : props.length.toFixed(0) + ' m') : '';

            // ── Mouseover ──
            layer.on('mouseover', function (e) {
                const baseStyle = getBaseStyle(feature);
                if (connHighlightOn && name !== 'Unnamed Road') {
                    // Highlight all roads with same name
                    roadLayer.eachLayer(l => {
                        if (l.feature && l.feature.properties.name === name) {
                            const s = getBaseStyle(l.feature);
                            l.setStyle({ color: '#ffffff', weight: s.weight + 2, opacity: 1 });
                        }
                    });
                } else {
                    this.setStyle({ color: '#ffffff', weight: baseStyle.weight + 2, opacity: 1 });
                }
                this.bringToFront();

                // Tooltip
                tooltipName.textContent = name;
                tooltipMeta.textContent = formatHighwayName(hw) + (len ? '  ·  ' + len : '');
                tooltip.style.display = 'block';
                updateTooltipPos(e.originalEvent);
            });

            // ── Mousemove ──
            layer.on('mousemove', function (e) {
                updateTooltipPos(e.originalEvent);
            });

            // ── Mouseout ──
            layer.on('mouseout', function () {
                tooltip.style.display = 'none';
                if (connHighlightOn && name !== 'Unnamed Road') {
                    roadLayer.eachLayer(l => {
                        if (l.feature && l.feature.properties.name === name) {
                            l.setStyle(getBaseStyle(l.feature));
                        }
                    });
                } else {
                    this.setStyle(getBaseStyle(feature));
                }

                // Re-apply highlight to selected layers
                selectedLayers.forEach(l => {
                    if (l && l.feature) {
                        const s = getBaseStyle(l.feature);
                        l.setStyle({ color: '#ffaa00', weight: s.weight + 2 });
                    }
                });
            });

            // ── Click ──
            layer.on('click', function () {
                const osmid = feature.properties.osmid;
                const isGroupSelect = connHighlightOn && name !== 'Unnamed Road';
                const isAlreadySelected = isGroupSelect ? (name === selectedRoadName) : (osmid === selectedRoadId);

                if (isAlreadySelected) {
                    deselectRoad();
                } else {
                    deselectRoad(); // clear previous

                    selectedRoadId = osmid;
                    selectedRoadName = isGroupSelect ? name : null;

                    let aggregatedProps = {
                        isGroup: isGroupSelect,
                        count: 0,
                        totalLength: 0,
                        highway: hw, // use clicked edge's highway type
                        name: name,
                        osmid: isGroupSelect ? 'Multiple' : osmid,
                        maxFloodClass: 0,
                        maxFloodProb: 0,
                        maxRiskLabel: 'None',
                        segments: []
                    };

                    if (isGroupSelect) {
                        roadLayer.eachLayer(l => {
                            if (l.feature && l.feature.properties.name === name) {
                                selectedLayers.push(l);
                                const s = getBaseStyle(l.feature);
                                l.setStyle({ color: '#ffaa00', weight: s.weight + 2 });
                                l.bringToFront();

                                const p = l.feature.properties;
                                aggregatedProps.count++;
                                aggregatedProps.totalLength += (p.length || 0);
                                if ((p.flood_probability || 0) >= aggregatedProps.maxFloodProb) {
                                    aggregatedProps.maxFloodProb = p.flood_probability || 0;
                                    aggregatedProps.maxFloodClass = p.flood_class || 0;
                                    aggregatedProps.maxRiskLabel = p.risk_label || 'None';
                                }

                                aggregatedProps.segments.push({
                                    osmid: p.osmid,
                                    length: (p.length || 0).toFixed(2),
                                    flood_probability: p.flood_probability,
                                    flood_class: p.flood_class,
                                    risk_label: p.risk_label
                                });
                            }
                        });
                    } else {
                        selectedLayers.push(this);
                        const s = getBaseStyle(feature);
                        this.setStyle({ color: '#ffaa00', weight: s.weight + 2 });
                        this.bringToFront();

                        const p = feature.properties;
                        aggregatedProps.count = 1;
                        aggregatedProps.totalLength = p.length || 0;
                        aggregatedProps.maxFloodProb = p.flood_probability || 0;
                        aggregatedProps.maxFloodClass = p.flood_class || 0;
                        aggregatedProps.maxRiskLabel = p.risk_label || 'None';

                        aggregatedProps.segments.push({
                            osmid: p.osmid,
                            length: (p.length || 0).toFixed(2),
                            flood_probability: p.flood_probability,
                            flood_class: p.flood_class,
                            risk_label: p.risk_label
                        });
                    }

                    updateRoadInfoPanel(aggregatedProps);
                }
            });
        }

        function updateTooltipPos(e) {
            tooltip.style.left = (e.clientX + 14) + 'px';
            tooltip.style.top = (e.clientY - 10) + 'px';
        }

        // ─────────────────────────────────────────
        // Road Info Panel
        // ─────────────────────────────────────────
        function updateRoadInfoPanel(props) {
            document.getElementById('road-info-placeholder').style.display = 'none';
            document.getElementById('road-info-content').style.display = 'block';
            document.getElementById('road-info-close').style.display = 'inline-block';

            document.getElementById('road-info-name').textContent = props.name || 'Unnamed Road';

            let classText = formatHighwayName(props.highway);
            if (props.isGroup && props.count > 1) {
                classText += ` (${props.count} segments)`;
            }
            document.getElementById('road-info-class').textContent = classText;
            document.getElementById('road-info-osmid').textContent = props.osmid || '—';

            const len = props.totalLength !== undefined ? props.totalLength : (props.length || 0);
            document.getElementById('road-info-length').textContent = len
                ? (len >= 1000 ? (len / 1000).toFixed(2) + ' km' : len.toFixed(2) + ' m')
                : '—';

            if (floodRiskOn) {
                document.getElementById('road-info-risk-row').style.display = '';
                const prob = props.maxFloodProb !== undefined ? props.maxFloodProb : (props.flood_probability || 0);
                const label = props.maxRiskLabel !== undefined ? props.maxRiskLabel : (props.risk_label || 'None');
                const floodClass = props.maxFloodClass !== undefined ? props.maxFloodClass : (props.flood_class || 0);

                const pct = Math.round(prob * 100);
                const riskClass = label === 'High' ? 'risk-high' : label === 'Medium' ? 'risk-medium' : label === 'Low' ? 'risk-low' : 'risk-none';
                const riskColor = label === 'High' ? '#ff4444' : label === 'Medium' ? '#ffaa00' : label === 'Low' ? '#00ff88' : '#888';

                document.getElementById('road-risk-badge').textContent = label + (prob > 0 ? ' — ' + Math.min(100, Math.max(0, pct)) + '%' : '');
                document.getElementById('road-risk-badge').className = 'risk-badge ' + riskClass;
                document.getElementById('road-risk-bar-fill').style.width = pct + '%';
                document.getElementById('road-risk-bar-fill').style.background = riskColor;
                document.getElementById('road-info-risk-label').textContent = label === 'None' ? 'No flood classification' : 'Class ' + floodClass + ' Hazard (Max)';
                document.getElementById('road-info-risk-label').className = 'road-info-field-value ' + riskClass;
            } else {
                document.getElementById('road-info-risk-row').style.display = 'none';
            }

            // Breakdown Section
            const breakdownRow = document.getElementById('road-info-breakdown-row');
            if (props.isGroup && props.segments && props.segments.length > 1) {
                breakdownRow.style.display = 'block';
                document.getElementById('road-info-breakdown-count').textContent = props.segments.length;

                const listEl = document.getElementById('road-info-breakdown-list');
                listEl.innerHTML = '';

                props.segments.forEach(seg => {
                    const row = document.createElement('div');
                    row.style.display = 'flex';
                    row.style.justifyContent = 'space-between';
                    row.style.alignItems = 'center';
                    row.style.padding = '0.35rem 0';
                    row.style.borderBottom = '1px solid rgba(226, 232, 240, 0.05)';

                    const idSpan = document.createElement('span');
                    idSpan.style.fontFamily = 'monospace';
                    idSpan.style.color = 'var(--text-muted)';
                    idSpan.textContent = seg.osmid;

                    const infoSpan = document.createElement('span');
                    infoSpan.style.display = 'flex';
                    infoSpan.style.alignItems = 'center';
                    infoSpan.style.gap = '6px';
                    infoSpan.style.color = 'var(--text-color)';

                    let infoHtml = `<span>${seg.length}m</span>`;

                    if (floodRiskOn) {
                        const prob = seg.flood_probability || 0;
                        const label = seg.risk_label || 'None';
                        const riskColor = label === 'High' ? '#ff4444' : label === 'Medium' ? '#ffaa00' : label === 'Low' ? '#00ff88' : '#888';
                        infoHtml += `<span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:${riskColor};" title="${label} risk"></span>`;
                    }
                    infoSpan.innerHTML = infoHtml;

                    row.appendChild(idSpan);
                    row.appendChild(infoSpan);
                    listEl.appendChild(row);
                });
            } else {
                breakdownRow.style.display = 'none';
            }
        }

        function deselectRoad() {
            selectedLayers.forEach(l => {
                if (l && l.feature) l.setStyle(getBaseStyle(l.feature));
            });
            selectedLayers = [];
            selectedRoadId = null;
            selectedRoadName = null;

            document.getElementById('road-info-placeholder').style.display = 'block';
            document.getElementById('road-info-content').style.display = 'none';
            document.getElementById('road-info-close').style.display = 'none';
        }

        // ══════════════════════════════════════════
        // Evacuation centers (markers & clusters)
        // ══════════════════════════════════════════
        const EVAC_TYPE_CONFIG = {
            "Barangay Hall": { key: "barangay-hall", icon: "🏛" },
            "School": { key: "school", icon: "🎓" },
            "Church": { key: "church", icon: "⛪" },
            "Court/Gymnasium": { key: "court-gym", icon: "🏀" },
            "Open Space": { key: "open-space", icon: "🌳" },
            "Hospital": { key: "hospital", icon: "🏥" },
            "Other": { key: "other", icon: "📍" }
        };

        let evacuationData = null;
        let evacClusterGroups = {};
        let evacTypeStates = {};
        let evacCountsByType = {};
        let evacMasterOn = false;
        const evacIconCache = {};

        Object.keys(EVAC_TYPE_CONFIG).forEach(type => {
            evacTypeStates[type] = true;
            evacCountsByType[type] = 0;
        });

        function initEvacuationCenters() {
            if (evacuationData) {
                updateEvacShowingCount();
                return;
            }
            fetch('/evacuation-centers')
                .then(r => r.json())
                .then(data => {
                    evacuationData = data;
                    const features = data.features || [];
                    const totalSpan = document.getElementById('evac-total-count');
                    if (totalSpan) totalSpan.textContent = features.length;

                    // Prepare cluster groups per type
                    Object.keys(EVAC_TYPE_CONFIG).forEach(type => {
                        evacClusterGroups[type] = L.markerClusterGroup({
                            disableClusteringAtZoom: 15,
                            showCoverageOnHover: false,
                            spiderfyOnMaxZoom: true,
                        });
                    });

                    // Build markers
                    features.forEach(f => {
                        if (!f.geometry || f.geometry.type !== 'Point') return;
                        const coords = f.geometry.coordinates || [];
                        if (coords.length < 2) return;
                        const lon = coords[0];
                        const lat = coords[1];
                        const props = f.properties || {};
                        const type = props.type || 'Other';
                        const safeType = EVAC_TYPE_CONFIG[type] ? type : 'Other';

                        const marker = L.marker([lat, lon], {
                            icon: getEvacIcon(safeType),
                        });

                        const popupHtml = buildEvacPopupHtml(props);
                        marker.bindPopup(popupHtml, { className: 'evac-popup' });

                        const group = evacClusterGroups[safeType];
                        group.addLayer(marker);
                        evacCountsByType[safeType] = (evacCountsByType[safeType] || 0) + 1;
                    });

                    refreshEvacLayerVisibility();
                })
                .catch(e => console.error('Evacuation centers load error:', e));
        }

        function getEvacIcon(type) {
            if (evacIconCache[type]) return evacIconCache[type];
            const cfg = EVAC_TYPE_CONFIG[type] || EVAC_TYPE_CONFIG["Other"];
            const classSuffix = cfg.key;
            const html = `<div class="evac-marker evac-type-${classSuffix}"><span>${cfg.icon}</span></div>`;
            const icon = L.divIcon({
                html,
                className: '',
                iconSize: [28, 28],
                iconAnchor: [14, 14],
            });
            evacIconCache[type] = icon;
            return icon;
        }

        function buildEvacPopupHtml(props) {
            const type = props.type || 'Other';
            const barangay = props.barangay || 'Unknown barangay';
            const facility = props.facility || 'Unknown facility';
            let typeLabel = type.toUpperCase();
            let emoji = '📍';
            if (type === 'Barangay Hall') emoji = '🏛';
            else if (type === 'School') emoji = '🎓';
            else if (type === 'Church') emoji = '⛪';
            else if (type === 'Court/Gymnasium') emoji = '🏀';
            else if (type === 'Open Space') emoji = '🌳';
            else if (type === 'Hospital') emoji = '🏥';

            return `
                <div class="evac-popup-body">
                    <div class="evac-popup-title"><span>${emoji}</span>${typeLabel}</div>
                    <div style="margin-top:4px;">
                        <div><strong>${facility}</strong></div>
                        <div>${barangay}</div>
                    </div>
                    <div style="margin-top:6px; font-size:0.78rem;">
                        <div>Type: ${type}</div>
                        <div>Capacity: TBD</div>
                    </div>
                </div>
            `;
        }

        function toggleEvacMaster(on) {
            evacMasterOn = on;
            const area = document.getElementById('evac-subtoggle-area');
            const typeToggles = document.querySelectorAll('.evac-type-toggle');

            if (on) {
                area.classList.add('visible');
                typeToggles.forEach(cb => {
                    cb.disabled = false;
                    cb.parentElement.classList.remove('disabled');
                    cb.checked = true;
                    const type = cb.getAttribute('data-evac-type');
                    evacTypeStates[type] = true;
                });
                if (!evacuationData) {
                    initEvacuationCenters();
                } else {
                    refreshEvacLayerVisibility();
                }
            } else {
                area.classList.remove('visible');
                typeToggles.forEach(cb => {
                    cb.disabled = true;
                    cb.parentElement.classList.add('disabled');
                });
                Object.keys(evacTypeStates).forEach(t => { evacTypeStates[t] = false; });
                refreshEvacLayerVisibility();
            }
        }

        function toggleEvacType(input) {
            const type = input.getAttribute('data-evac-type');
            evacTypeStates[type] = input.checked;
            if (evacMasterOn) {
                refreshEvacLayerVisibility();
            } else {
                updateEvacShowingCount();
            }
        }

        function refreshEvacLayerVisibility() {
            Object.keys(EVAC_TYPE_CONFIG).forEach(type => {
                const group = evacClusterGroups[type];
                if (!group) return;
                const shouldShow = evacMasterOn && evacTypeStates[type];
                const onMap = map.hasLayer(group);
                if (shouldShow && !onMap) {
                    group.addTo(map);
                } else if (!shouldShow && onMap) {
                    map.removeLayer(group);
                }
            });
            updateEvacShowingCount();
        }

        function updateEvacShowingCount() {
            const totalSpan = document.getElementById('evac-total-count');
            const showingSpan = document.getElementById('evac-showing-count');
            if (!totalSpan || !showingSpan) return;

            if (!evacuationData) {
                totalSpan.textContent = '0';
                showingSpan.textContent = '0';
                return;
            }

            const features = evacuationData.features || [];
            totalSpan.textContent = features.length;

            let showing = 0;
            if (evacMasterOn) {
                Object.keys(EVAC_TYPE_CONFIG).forEach(type => {
                    if (evacTypeStates[type]) {
                        showing += evacCountsByType[type] || 0;
                    }
                });
            }
            showingSpan.textContent = showing;
        }

        // Ensure evac type switches are disabled until master is on
        (function initEvacSwitchState() {
            const typeToggles = document.querySelectorAll('.evac-type-toggle');
            typeToggles.forEach(cb => {
                cb.disabled = true;
                cb.parentElement.classList.add('disabled');
            });
        })();

        // ══════════════════════════════════════════
        // Evacuation Routing (Marker Placement & Pathfinding)
        // ══════════════════════════════════════════
        let markerPlacementMode = false;
        let locationMarker = null;
        let routeLayers = [];
        let routeData = [];  // Store route data for toggling

        function toggleMarkerPlacement(enabled) {
            markerPlacementMode = enabled;
            const findBtn = document.getElementById('find-evac-btn');
            const statusEl = document.getElementById('routing-status');

            if (enabled) {
                map.getContainer().style.cursor = 'crosshair';
                statusEl.textContent = 'Click on the map to place your location marker';
                statusEl.className = 'routing-status';
            } else {
                map.getContainer().style.cursor = '';
                if (locationMarker) {
                    map.removeLayer(locationMarker);
                    locationMarker = null;
                    findBtn.disabled = true;
                }
                statusEl.textContent = '';
                clearRoutes();
            }
        }

        function placeLocationMarker(latlng) {
            if (locationMarker) {
                map.removeLayer(locationMarker);
            }

            const markerIcon = L.divIcon({
                html: '<div class="location-marker">📍</div>',
                className: '',
                iconSize: [32, 32],
                iconAnchor: [16, 16]
            });

            locationMarker = L.marker(latlng, { icon: markerIcon }).addTo(map);

            const findBtn = document.getElementById('find-evac-btn');
            findBtn.disabled = false;

            const statusEl = document.getElementById('routing-status');
            statusEl.textContent = 'Location set. Click "Find Evacuation Routes" to calculate paths.';
            statusEl.className = 'routing-status success';
        }

        function clearRoutes() {
            routeLayers.forEach(layer => map.removeLayer(layer));
            routeLayers = [];
            routeData = [];

            // Clear route toggles UI
            const routeTogglesContainer = document.getElementById('route-toggles-container');
            if (routeTogglesContainer) {
                routeTogglesContainer.innerHTML = '';
                routeTogglesContainer.style.display = 'none';
            }
        }

        async function findNearestEvacuations() {
            if (!locationMarker) return;

            const findBtn = document.getElementById('find-evac-btn');
            const statusEl = document.getElementById('routing-status');

            findBtn.disabled = true;
            statusEl.textContent = 'Calculating routes...';
            statusEl.className = 'routing-status';

            clearRoutes();

            const k = parseInt(document.getElementById('k-paths-input').value) || 3;
            const startLat = locationMarker.getLatLng().lat;
            const startLng = locationMarker.getLatLng().lng;

            try {
                const response = await fetch('/find-evacuation-routes', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        start_lat: startLat,
                        start_lng: startLng,
                        k: k
                    })
                });

                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }

                const data = await response.json();

                if (data.routes && data.routes.length > 0) {
                    displayRoutes(data.routes);
                    statusEl.textContent = `Found ${data.routes.length} route(s) to evacuation centers`;
                    statusEl.className = 'routing-status success';
                } else {
                    statusEl.textContent = 'No routes found';
                    statusEl.className = 'routing-status error';
                }
            } catch (error) {
                console.error('Error finding evacuation routes:', error);
                statusEl.textContent = 'Error calculating routes. Please try again.';
                statusEl.className = 'routing-status error';
            } finally {
                findBtn.disabled = false;
            }
        }

        function displayRoutes(routes) {
            const colors = ['#ff4444', '#ff8800', '#ffcc00', '#00ff88', '#00d4ff'];

            // Clear existing routes
            clearRoutes();

            // Create route toggles container if it doesn't exist
            let routeTogglesContainer = document.getElementById('route-toggles-container');
            if (!routeTogglesContainer) {
                routeTogglesContainer = document.createElement('div');
                routeTogglesContainer.id = 'route-toggles-container';
                routeTogglesContainer.style.cssText = 'margin-top: 0.6rem; padding-top: 0.6rem; border-top: 1px solid rgba(226, 232, 240, 0.1);';
                document.getElementById('routing-controls').appendChild(routeTogglesContainer);
            }
            routeTogglesContainer.innerHTML = '';
            routeTogglesContainer.style.display = 'block';

            routes.forEach((route, index) => {
                const color = colors[index % colors.length];
                const routeId = route.id || (index + 1);

                // Store route data
                const routeObj = {
                    id: routeId,
                    color: color,
                    layers: [],
                    visible: true,
                    route: route
                };

                // Draw start connector (dashed line from user marker to route start)
                if (route.start_connector && route.start_connector.length >= 2) {
                    const startConnector = L.polyline(
                        route.start_connector.map(p => [p.lat, p.lng]),
                        {
                            color: color,
                            weight: 3,
                            opacity: 0.6,
                            dashArray: '5, 10'
                        }
                    ).addTo(map);
                    routeObj.layers.push(startConnector);
                }

                // Draw main route path (solid, following road curves)
                if (route.path && route.path.length > 0) {
                    const coordinates = route.path.map(p => [p.lat, p.lng]);
                    const routePath = L.polyline(coordinates, {
                        color: color,
                        weight: 5,
                        opacity: 0.8
                    }).addTo(map);

                    const popupContent = `
                        <div style="font-family: var(--font-heading); font-size: 0.85rem;">
                            <strong style="color: ${color};">Route ${routeId}</strong><br>
                            Destination: ${route.destination.facility}<br>
                            Distance: ${(route.distance / 1000).toFixed(2)} km<br>
                            Type: ${route.destination.type}
                        </div>
                    `;
                    routePath.bindPopup(popupContent);
                    routeObj.layers.push(routePath);
                }

                // Draw end connector (dashed line from route end to evacuation marker)
                if (route.end_connector && route.end_connector.length >= 2) {
                    const endConnector = L.polyline(
                        route.end_connector.map(p => [p.lat, p.lng]),
                        {
                            color: color,
                            weight: 3,
                            opacity: 0.6,
                            dashArray: '5, 10'
                        }
                    ).addTo(map);
                    routeObj.layers.push(endConnector);
                }

                // Add destination marker
                const destIcon = L.divIcon({
                    html: `<div class="evac-marker evac-type-${EVAC_TYPE_CONFIG[route.destination.type]?.key || 'other'}">
                        <span>${EVAC_TYPE_CONFIG[route.destination.type]?.icon || '📍'}</span>
                    </div>`,
                    className: '',
                    iconSize: [28, 28],
                    iconAnchor: [14, 14]
                });

                const destMarker = L.marker([route.destination.lat, route.destination.lng], {
                    icon: destIcon
                }).addTo(map);

                destMarker.bindPopup(`
                    <div style="font-family: var(--font-heading);">
                        <strong>${route.destination.facility}</strong><br>
                        ${route.destination.barangay}<br>
                        Type: ${route.destination.type}
                    </div>
                `);
                routeObj.layers.push(destMarker);

                // Store all layers
                routeLayers.push(...routeObj.layers);
                routeData.push(routeObj);

                // Create toggle UI
                const toggleDiv = document.createElement('div');
                toggleDiv.style.cssText = 'display: flex; align-items: center; justify-content: space-between; padding: 0.4rem 0; font-size: 0.78rem;';
                toggleDiv.innerHTML = `
                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                        <div style="width: 16px; height: 16px; background: ${color}; border-radius: 3px;"></div>
                        <span style="color: var(--text-color);">Route ${routeId} - ${route.destination.facility}</span>
                    </div>
                    <label class="switch">
                        <input type="checkbox" checked onchange="toggleRoute(${index}, this.checked)">
                        <span class="slider"></span>
                    </label>
                `;
                routeTogglesContainer.appendChild(toggleDiv);
            });

            if (routes.length > 0) {
                const allCoords = routes.flatMap(r => r.path.map(p => [p.lat, p.lng]));
                if (allCoords.length > 0) {
                    const bounds = L.latLngBounds(allCoords);
                    map.fitBounds(bounds, { padding: [50, 50] });
                }
            }
        }

        function toggleRoute(routeIndex, visible) {
            if (routeIndex < 0 || routeIndex >= routeData.length) return;

            const route = routeData[routeIndex];
            route.visible = visible;

            route.layers.forEach(layer => {
                if (visible) {
                    if (!map.hasLayer(layer)) {
                        layer.addTo(map);
                    }
                } else {
                    if (map.hasLayer(layer)) {
                        map.removeLayer(layer);
                    }
                }
            });
        }

        map.on('click', function (e) {
            if (markerPlacementMode) {
                placeLocationMarker(e.latlng);
            }
        });

        // ══════════════════════════════════════════
        // Responsive & misc
        // ══════════════════════════════════════════
        window.addEventListener('resize', () => map.invalidateSize());

        // ══════════════════════════════════════════
        // Flood-Aware Routing System
        // ══════════════════════════════════════════

        const routingState = {
            scenario: '25yr',
            originCoords: null,
            originMarker: null,
            routePolylines: [],
            destMarker: null,
            activeRouteIndex: null,
            activeRouteOverlay: null,
            routeVisibility: [],
            placingOrigin: false,
            floodSegmentCache: {}
        };

        // Toast notification system
        function showToast(message, type = 'info') {
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.textContent = message;
            document.body.appendChild(toast);

            setTimeout(() => {
                toast.style.animation = 'slideIn 0.3s ease-out reverse';
                setTimeout(() => toast.remove(), 300);
            }, 4000);
        }

        // Scenario selection
        function selectScenario(scenario) {
            routingState.scenario = scenario;

            // Update tab styling
            document.querySelectorAll('.scenario-tab').forEach(tab => {
                tab.classList.toggle('active', tab.dataset.scenario === scenario);
            });

            // Update flood segment coloring if road network is visible
            if (roadVisible) {
                updateFloodSegmentColoring();
            }
        }

        // Toggle origin placement mode
        function toggleOriginPlacement() {
            routingState.placingOrigin = !routingState.placingOrigin;
            const btn = document.getElementById('place-origin-btn');

            if (routingState.placingOrigin) {
                btn.classList.add('active');
                btn.textContent = '📍 Click map now...';
                map.getContainer().style.cursor = 'crosshair';
            } else {
                btn.classList.remove('active');
                btn.textContent = '📍 Click map to place pin';
                map.getContainer().style.cursor = '';
            }
        }

        // Map click handler for origin placement
        map.on('click', function (e) {
            if (routingState.placingOrigin) {
                placeOriginMarker(e.latlng.lat, e.latlng.lng);
                toggleOriginPlacement();
            }
        });

        // Place origin marker
        function placeOriginMarker(lat, lng) {
            routingState.originCoords = { lat, lng };

            // Remove existing marker
            if (routingState.originMarker) {
                map.removeLayer(routingState.originMarker);
            }

            // Create draggable marker
            const icon = L.divIcon({
                className: 'custom-marker',
                html: '<div style="width: 32px; height: 32px; background: #00d4ff; border: 3px solid white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; color: #0a1628; box-shadow: 0 4px 12px rgba(0, 212, 255, 0.6);">A</div>',
                iconSize: [32, 32],
                iconAnchor: [16, 16]
            });

            routingState.originMarker = L.marker([lat, lng], {
                icon: icon,
                draggable: true
            }).addTo(map);

            // Update on drag
            routingState.originMarker.on('dragend', function (e) {
                const pos = e.target.getLatLng();
                routingState.originCoords = { lat: pos.lat, lng: pos.lng };
                updateOriginDisplay();
                checkRouteButtonState();
            });

            updateOriginDisplay();
            checkRouteButtonState();
        }

        // Update origin coordinates display
        function updateOriginDisplay() {
            const display = document.getElementById('origin-coords-display');
            const latSpan = document.getElementById('origin-lat');
            const lonSpan = document.getElementById('origin-lon');

            if (routingState.originCoords) {
                display.style.display = 'block';
                latSpan.textContent = routingState.originCoords.lat.toFixed(5);
                lonSpan.textContent = routingState.originCoords.lng.toFixed(5);
            } else {
                display.style.display = 'none';
            }
        }

        // Check if find routes button should be enabled
        function checkRouteButtonState() {
            const btn = document.getElementById('find-routes-btn');
            const enabled = routingState.originCoords !== null;
            btn.disabled = !enabled;
        }

        // Find routes
        async function findRoutes() {
            const btn = document.getElementById('find-routes-btn');
            btn.disabled = true;
            btn.innerHTML = '🔄 Finding...';

            try {
                const response = await fetch('/route', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        origin_lat: routingState.originCoords.lat,
                        origin_lon: routingState.originCoords.lng,
                        scenario: routingState.scenario,
                        k: 3
                    })
                });

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }

                const data = await response.json();
                displayRoutes(data);

                // Show destination name in toast if available
                const destName = data.destination_name || 'nearest evacuation center';
                showToast(`Found ${data.routes.length} routes to ${destName} (${data.computation_time_ms}ms)`, 'success');

            } catch (error) {
                console.error('Routing error:', error);
                showToast('Failed to find routes. Please try again.', 'error');
            } finally {
                btn.disabled = false;
                btn.innerHTML = '🔍 FIND ROUTES';
            }
        }

        // Display routes on map

        function displayRoutes(data) {
            // Clear existing routes
            routingState.routePolylines.forEach(p => map.removeLayer(p));
            if (routingState.activeRouteOverlay) map.removeLayer(routingState.activeRouteOverlay);
            if (routingState.destMarker) map.removeLayer(routingState.destMarker);
            routingState.routePolylines = [];
            routingState.activeRouteIndex = null;
            routingState.activeRouteOverlay = null;
            routingState.destMarker = null;

            const routes = data.routes || [];
            // Initialize routeVisibility
            routingState.routeVisibility = routes.map(() => true);

            const colors = ['#00ff88', '#ffaa00', '#a78bfa'];
            const weights = [5, 4, 4];
            const opacities = [0.9, 0.7, 0.7];
            const dashArrays = [null, '8,4', '4,8'];

            // Update Origin marker with Pulse
            if (routingState.originMarker) {
                const icon = routingState.originMarker.options.icon;
                const newHtml = `
                    <div style="position:relative;">
                        <div class="pulse-marker-ring cyan"></div>
                        <div style="width: 32px; height: 32px; background: #00d4ff; border: 3px solid white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; color: #0a1628; box-shadow: 0 4px 12px rgba(0, 212, 255, 0.6); position: relative; z-index: 2;">A</div>
                    </div>
                `;
                const newIcon = L.divIcon({ ...icon.options, html: newHtml });
                routingState.originMarker.setIcon(newIcon);
            }

            // Draw connector lines (dashed lines from user/evac to road network)
            if (data.origin_connector) {
                const coords = data.origin_connector.coordinates;
                const connector = L.polyline(
                    coords.map(c => [c[1], c[0]]),
                    {
                        color: '#00d4ff',
                        weight: 2,
                        opacity: 0.5,
                        dashArray: '5, 10'
                    }
                ).addTo(map);
                routingState.routePolylines.push(connector);
            }

            if (data.destination_connector) {
                const coords = data.destination_connector.coordinates;
                const connector = L.polyline(
                    coords.map(c => [c[1], c[0]]),
                    {
                        color: '#ffaa00',
                        weight: 2,
                        opacity: 0.5,
                        dashArray: '5, 10'
                    }
                ).addTo(map);
                routingState.routePolylines.push(connector);

                // Add pulsate Destination marker at end
                const destCoords = coords[0];
                const destLat = destCoords[1];
                const destLng = destCoords[0];
                const destHtml = `
                    <div style="position:relative;">
                        <div class="pulse-marker-ring amber"></div>
                        <div style="width: 32px; height: 32px; background: #ffaa00; border: 3px solid white; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; color: #0a1628; box-shadow: 0 4px 12px rgba(255, 170, 0, 0.6); position: relative; z-index: 2;">B</div>
                    </div>
                `;
                const destIcon = L.divIcon({ className: '', html: destHtml, iconSize: [32, 32], iconAnchor: [16, 16] });
                routingState.destMarker = L.marker([destLat, destLng], { icon: destIcon }).addTo(map);

                const destName = data.destination_name || 'Evacuation Center';
                const destBarangay = data.destination_barangay || '';
                routingState.destMarker.bindPopup(`
                    <div style="font-family: var(--font-heading);">
                        <strong>🏥 ${destName}</strong><br>
                        ${destBarangay}<br>
                        Evacuation Center
                    </div>
                `, { className: 'evac-popup' });
            }

            routes.forEach((route, idx) => {
                const geom = route.geometry;
                if (!geom || geom.type !== 'MultiLineString') return;

                // Flatten MultiLineString to array of LatLng
                const latlngs = [];
                geom.coordinates.forEach(lineString => {
                    lineString.forEach(coord => {
                        latlngs.push([coord[1], coord[0]]);
                    });
                });

                const polyline = L.polyline(latlngs, {
                    color: colors[idx],
                    weight: weights[idx],
                    opacity: opacities[idx],
                    dashArray: dashArrays[idx]
                }).addTo(map);

                polyline.routeIndex = idx;
                polyline.originalStyle = {
                    weight: weights[idx],
                    opacity: opacities[idx]
                };

                // Store latlngs inside the element to reference later for active marching ants
                polyline.latlngs = latlngs;

                // Tooltip el
                const tooltipEl = document.getElementById('custom-route-tooltip');

                // Hover effects
                polyline.on('mouseover', function (e) {
                    if (!routingState.routeVisibility[idx]) return;
                    this.setStyle({ weight: this.originalStyle.weight + 3, opacity: 1.0 });

                    // Show custom tooltip
                    const rProps = route.properties;
                    const rType = rProps.rank === 1 ? '✅ RECOMMENDED' : '⚠️ ALTERNATIVE';
                    tooltipEl.innerHTML = `
                       <div style="font-weight:bold; color:${colors[idx]};">ROUTE ${rProps.rank}  ${rType}</div>
                       <hr style="border-color:rgba(0,212,255,0.2); margin:4px 0;">
                       <div>📏 ${rProps.total_length_km} km</div>
                       <div>🌊 Risk: ${rProps.risk_label.toUpperCase()} (${rProps.flood_exposure.toFixed(2)})</div>
                       <div>⚠️ Max: Class ${rProps.max_flood_class}</div>
                       <div>🏆 Score: ${(100 - rProps.composite_score * 100).toFixed(0)}/100</div>
                       <div style="margin-top:4px; font-size:0.7rem; color:var(--text-muted); font-style:italic;">Click for details</div>
                    `;
                    tooltipEl.style.display = 'block';
                    tooltipEl.style.left = (e.originalEvent.clientX + 14) + 'px';
                    tooltipEl.style.top = (e.originalEvent.clientY - 10) + 'px';
                });

                polyline.on('mousemove', function (e) {
                    if (tooltipEl.style.display === 'block') {
                        tooltipEl.style.left = (e.originalEvent.clientX + 14) + 'px';
                        tooltipEl.style.top = (e.originalEvent.clientY - 10) + 'px';
                    }
                });

                polyline.on('mouseout', function () {
                    if (!routingState.routeVisibility[idx]) return;
                    if (routingState.activeRouteIndex === idx) {
                        this.setStyle({ weight: this.originalStyle.weight + 4, opacity: 1.0 });
                    } else if (routingState.activeRouteIndex !== null) {
                        this.setStyle({ weight: this.originalStyle.weight - 1, opacity: 0.15 });
                    } else {
                        this.setStyle(this.originalStyle);
                    }
                    tooltipEl.style.display = 'none';
                });

                // Click to highlight
                polyline.on('click', function (e) {
                    if (!routingState.routeVisibility[idx]) return;
                    L.DomEvent.stopPropagation(e);
                    if (routingState.activeRouteIndex === idx) {
                        clearRouteHighlight();
                    } else {
                        highlightRoute(idx);
                    }
                });

                routingState.routePolylines.push(polyline);
            });

            // Fit bounds with padding including sidebar
            if (routingState.routePolylines.length > 0) {
                const group = L.featureGroup(routingState.routePolylines);
                if (routingState.originMarker) group.addLayer(routingState.originMarker);
                map.fitBounds(group.getBounds(), { paddingBottomRight: [80, 80], paddingTopLeft: [350, 80] });
            }

            // Display route cards
            displayRouteCards(routes);
        }

        function clearRouteHighlight() {
            routingState.activeRouteIndex = null;
            if (routingState.activeRouteOverlay) {
                map.removeLayer(routingState.activeRouteOverlay);
                routingState.activeRouteOverlay = null;
            }
            routingState.routePolylines.forEach((poly) => {
                if (poly.routeIndex !== undefined) {
                    if (routingState.routeVisibility[poly.routeIndex]) {
                        poly.setStyle(poly.originalStyle);
                    } else {
                        poly.setStyle({ opacity: 0 });
                    }
                }
            });
            document.querySelectorAll('.route-card').forEach((card, i) => {
                card.classList.remove('highlighted');
            });
        }

        // Display route cards in sidebar
        
        function displayRouteCards(routes) {
            const container = document.getElementById('route-cards-container');
            const resultsSection = document.getElementById('route-results-container');
            
            container.innerHTML = '';
            resultsSection.style.display = routes.length > 0 ? 'block' : 'none';
            
            if (routes.length === 0) return;

            const colors = ['#00ff88', '#ffaa00', '#a78bfa'];
            const statusLabels = ['RECOMMENDED', 'ALTERNATIVE', 'ALTERNATIVE'];

            routes.forEach((route, idx) => {
                const props = route.properties;
                const card = document.createElement('div');
                card.className = 'route-card';
                card.style.borderLeftColor = colors[idx];
                card.dataset.routeIndex = idx;

                let riskColor = '#00ff88';
                if (props.risk_label === 'High') riskColor = '#ff4444';
                else if (props.risk_label === 'Medium') riskColor = '#ffaa00';

                const segments = props.segments || [];
                const classCounts = { 0: 0, 1: 0, 2: 0, 3: 0 };
                let totalLen = 0, sumElev = 0, sumProb = 0;
                let safestSeg = { name: 'Unknown', flood_class: 99, flood_proba: 99 };
                let riskiestSeg = { name: 'Unknown', flood_class: -1, flood_proba: -1 };

                segments.forEach(s => {
                    const fc = s.flood_class || 0;
                    classCounts[fc]++;
                    totalLen += s.length;
                    sumElev += s.elevation !== undefined ? s.elevation : 0;
                    sumProb += s.flood_proba || 0;
                    if (fc < safestSeg.flood_class) safestSeg = s;
                    if (fc > riskiestSeg.flood_class) riskiestSeg = s;
                });

                const f0 = (classCounts[0] / segments.length * 100) || 0;
                const f1 = (classCounts[1] / segments.length * 100) || 0;
                const f2 = (classCounts[2] / segments.length * 100) || 0;
                const f3 = (classCounts[3] / segments.length * 100) || 0;

                card.innerHTML = `
                    <div class="route-card-header">
                        <div class="route-rank-label" style="color:${colors[idx]}">ROUTE ${props.rank}</div>
                        <div style="display:flex; align-items:center; gap:6px;">
                            <div class="status-badge" style="background:rgba(255,255,255,0.05); color:${colors[idx]}">${statusLabels[idx]}</div>
                            <button class="visibility-btn visible" onclick="toggleRouteVisibility(event, ${idx})">HIDE</button>
                        </div>
                    </div>
                    
                    <div class="metrics-grid">
                        <div class="metric-cell">
                            <div class="metric-label">DISTANCE</div>
                            <div class="metric-value">${props.total_length_km} km</div>
                        </div>
                        <div class="metric-cell">
                            <div class="metric-label">RISK LEVEL</div>
                            <div class="metric-value" style="color:${riskColor}">${props.risk_label}</div>
                        </div>
                        <div class="metric-cell">
                            <div class="metric-label">FLOOD EXP.</div>
                            <div class="metric-value">${props.flood_exposure.toFixed(2)}</div>
                        </div>
                        <div class="metric-cell">
                            <div class="metric-label">MAX HAZARD</div>
                            <div class="metric-value">CLASS ${props.max_flood_class}</div>
                        </div>
                    </div>

                    <button class="details-toggle-btn" onclick="toggleSegmentDetails(event, ${idx})">Show Route Details</button>
                    
                    <div class="route-segments-container" id="route-segments-${idx}">
                         <div class="metric-label" style="margin-bottom:6px;">FLOOD CLASS BREAKDOWN</div>
                         <div class="flood-class-bar">
                            <div style="width:${f0}%; background:#00ff88;"></div>
                            <div style="width:${f1}%; background:#ffff00;"></div>
                            <div style="width:${f2}%; background:#ffaa00;"></div>
                            <div style="width:${f3}%; background:#ff4444;"></div>
                         </div>
                         <div style="display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px;">
                            <div style="font-size:9px; color:#334155; display:flex; align-items:center; gap:4px;"><span style="width:5px; height:5px; border-radius:50%; background:#00ff88;"></span>Class 0: ${Math.round(f0)}%</div>
                            <div style="font-size:9px; color:#334155; display:flex; align-items:center; gap:4px;"><span style="width:5px; height:5px; border-radius:50%; background:#ffff00;"></span>Class 1: ${Math.round(f1)}%</div>
                            <div style="font-size:9px; color:#334155; display:flex; align-items:center; gap:4px;"><span style="width:5px; height:5px; border-radius:50%; background:#ffaa00;"></span>Class 2: ${Math.round(f2)}%</div>
                            <div style="font-size:9px; color:#334155; display:flex; align-items:center; gap:4px;"><span style="width:5px; height:5px; border-radius:50%; background:#ff0000;"></span>Class 3: ${Math.round(f3)}%</div>
                         </div>

                         <div class="metric-label" style="margin-bottom:6px;">SEGMENTS (${segments.length})</div>
                         <div class="segment-list">
                            ${segments.map((s, si) => {
                                const c = s.flood_class === 3 ? '#ff0000' : s.flood_class === 2 ? '#ffaa00' : s.flood_class === 1 ? '#ffff00' : '#00ff88';
                                return `
                                <div class="segment-item" style="border-left-color:${c}" onmouseover="hoverSegmentOnMap(${idx}, ${si}, true)" onmouseout="hoverSegmentOnMap(${idx}, ${si}, false)">
                                    <div class="segment-name">${si+1}. ${s.name || 'Road'}</div>
                                    <div class="segment-meta-row">
                                        <span>Class ${s.flood_class}</span>
                                        <span>${(s.length/1000).toFixed(2)} km</span>
                                        <span>Elev: ${s.elevation ? s.elevation.toFixed(1) : '--'}m</span>
                                    </div>
                                </div>`;
                            }).join('')}
                         </div>
                    </div>
                `;
                
                card.addEventListener('click', (e) => {
                    if (e.target.tagName === 'BUTTON') return;
                    if (!routingState.routeVisibility[idx]) return;
                    if (routingState.activeRouteIndex === idx) {
                        clearRouteHighlight();
                    } else {
                        // Ensure details shown if highlighted
                        const segs = document.getElementById('route-segments-' + idx);
                        if (!segs.classList.contains('expanded')) {
                            segs.classList.add('expanded');
                            segs.previousElementSibling.textContent = 'Hide Route Details';
                        }
                        highlightRoute(idx);
                    }
                });

                container.appendChild(card);
            });
        }


        function toggleRouteVisibility(e, idx) {
            e.stopPropagation();
            const btn = e.target;
            const isVisible = routingState.routeVisibility[idx];

            if (isVisible) {
                // Check if it's the last visible route
                const visibleCount = routingState.routeVisibility.filter(v => v).length;
                if (visibleCount <= 1) {
                    showToast('At least one route must remain visible', 'warning');
                    return;
                }

                // Hide
                routingState.routeVisibility[idx] = false;
                btn.textContent = '👁 Show';
                btn.classList.add('hidden-state');

                const card = document.querySelector(`.route-card[data-route-index="${idx}"]`);
                if (card) card.classList.add('route-hidden');

                // Update map
                const poly = routingState.routePolylines.find(p => p.routeIndex === idx);
                if (poly && poly.setStyle) {
                    poly.setStyle({ opacity: 0 });
                }
                if (routingState.activeRouteIndex === idx) clearRouteHighlight();

            } else {
                // Show
                routingState.routeVisibility[idx] = true;
                btn.textContent = '👁 Hide';
                btn.classList.remove('hidden-state');

                const card = document.querySelector(`.route-card[data-route-index="${idx}"]`);
                if (card) card.classList.remove('route-hidden');

                // Update map
                const poly = routingState.routePolylines.find(p => p.routeIndex === idx);
                if (poly && poly.setStyle) {
                    if (routingState.activeRouteIndex !== null) {
                        poly.setStyle({ opacity: 0.15, weight: poly.originalStyle.weight - 1 });
                    } else {
                        poly.setStyle(poly.originalStyle);
                    }
                }
            }
        }

        // Toggle segment details
        function toggleSegmentDetails(e, idx) {
            e.stopPropagation();
            const segments = document.getElementById(`route-segments-${idx}`);
            const btn = segments.previousElementSibling;

            if (segments.classList.contains('expanded')) {
                segments.classList.remove('expanded');
                btn.textContent = '▼ Show Route Details';
            } else {
                segments.classList.add('expanded');
                btn.textContent = '▲ Hide Route Details';
            }
        }

        // Segment hovering on Map
        let hoverSegmentLayer = null;
        function hoverSegmentOnMap(routeIdx, segIdx, isHover) {
            if (!routingState.routeVisibility[routeIdx]) return;
            const route = routingState.routePolylines.find(p => p.routeIndex === routeIdx);
            if (!route || !route.latlngs) return;

            if (isHover) {
                // In a highly simplified implementation, we'll just emphasize the entire route on hover
                // To do exactly the segment we'd need segment-specific coordinates which we don't have broken down in latlngs easily.
                // We'll highlight the route polyline slightly more
                route.setStyle({ color: '#ffffff', weight: route.originalStyle.weight + 2, opacity: 1 });
                route.bringToFront();
            } else {
                // Mouseout 
                if (routingState.activeRouteIndex === routeIdx) {
                    route.setStyle({ color: [...['#00ff88', '#ffaa00', '#a78bfa']][routeIdx], weight: route.originalStyle.weight + 4, opacity: 1 });
                } else if (routingState.activeRouteIndex !== null) {
                    route.setStyle({ color: [...['#00ff88', '#ffaa00', '#a78bfa']][routeIdx], weight: route.originalStyle.weight - 1, opacity: 0.15 });
                } else {
                    route.setStyle({ color: [...['#00ff88', '#ffaa00', '#a78bfa']][routeIdx], weight: route.originalStyle.weight, opacity: route.originalStyle.opacity });
                }
            }
        }

        // Highlight route
        function highlightRoute(idx) {
            routingState.activeRouteIndex = idx;
            const colors = ['#00ff88', '#ffaa00', '#a78bfa'];

            // Handle map polylines
            routingState.routePolylines.forEach((poly) => {
                if (poly.routeIndex === undefined) return;

                if (poly.routeIndex === idx) {
                    poly.setStyle({ weight: poly.originalStyle.weight + 4, opacity: 1.0 });
                    poly.bringToFront();

                    // Add animated marching ants overlay
                    if (routingState.activeRouteOverlay) map.removeLayer(routingState.activeRouteOverlay);

                    routingState.activeRouteOverlay = L.polyline(poly.latlngs, {
                        color: 'white',
                        weight: 2,
                        opacity: 0.6,
                        dashArray: '8, 12',
                        className: 'marching-ants-polyline'
                    }).addTo(map);

                } else {
                    if (routingState.routeVisibility[poly.routeIndex]) {
                        poly.setStyle({ weight: Math.max(1, poly.originalStyle.weight - 1), opacity: 0.15 });
                    }
                }
            });

            // Handle cards
            document.querySelectorAll('.route-card').forEach((card) => {
                const cIdx = parseInt(card.dataset.routeIndex);
                if (cIdx === idx) {
                    card.classList.add('highlighted');
                    card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                } else {
                    card.classList.remove('highlighted');
                }
            });
        }


        // Clear routing
        function clearRouting() {
            // Remove origin marker
            if (routingState.originMarker) {
                map.removeLayer(routingState.originMarker);
                routingState.originMarker = null;
            }

            // Remove routes
            routingState.routePolylines.forEach(p => map.removeLayer(p));
            routingState.routePolylines = [];

            // Reset state
            routingState.originCoords = null;
            routingState.activeRouteIndex = null;
            routingState.placingOrigin = false;

            // Reset UI
            document.getElementById('origin-coords-display').style.display = 'none';
            document.getElementById('route-results-container').style.display = 'none';
            document.getElementById('place-origin-btn').classList.remove('active');
            document.getElementById('place-origin-btn').textContent = '📍 Click map to place pin';
            map.getContainer().style.cursor = '';

            // Reset scenario to 25yr
            selectScenario('25yr');

            checkRouteButtonState();
        }

        // Update flood segment coloring
        function updateFloodSegmentColoring() {
            const scenario = routingState.scenario;

            // Show legend if road network is visible
            const legend = document.getElementById('flood-legend');
            if (legend) {
                legend.style.display = roadVisible ? 'block' : 'none';
            }

            if (!roadVisible || !roadLayer) return;

            // Fetch flood segments for current scenario
            fetch(`/flood-segments?scenario=${scenario}`)
                .then(r => r.json())
                .then(data => {
                    routingState.floodSegmentCache[scenario] = data;
                    applyFloodSegmentColors(data);
                })
                .catch(e => console.error('Error loading flood segments:', e));
        }

        // Apply flood segment colors to road layer
        function applyFloodSegmentColors(geojson) {
            if (!roadLayer) return;

            const floodColors = {
                0: '#00ff88',
                1: '#ffff00',
                2: '#ffaa00',
                3: '#ff0000'
            };

            roadLayer.eachLayer(layer => {
                const props = layer.feature.properties;
                const osmid = props.osmid;

                // Find matching flood segment
                const floodFeature = geojson.features.find(f => f.properties.osmid === osmid);

                if (floodFeature) {
                    const floodClass = floodFeature.properties.flood_class || 0;
                    const color = floodColors[floodClass];
                    layer.setStyle({ color: color, weight: 2, opacity: 0.8 });
                }
            });
        }

    