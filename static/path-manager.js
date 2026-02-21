/**
 * Path Visualization & Management Module
 */

import { state } from './state.js';
import { map } from './map-init.js';
import { updateSearchButtonState } from './node-selection.js';

/**
 * Draw the calculated paths on the map
 */
export function drawPaths(results) {
    if (!Array.isArray(results)) {
        results = [results];
    }

    if (state.pathLayers) {
        clearPathOverlay();
    }

    state.pathLayers = [];
    const controlsContainer = document.getElementById('individual-path-controls');
    if (controlsContainer) {
        controlsContainer.innerHTML = '';
        controlsContainer.style.display = 'block';
    }

    // Store results for the breakdown overlay
    state.lastAnalysisResults = results;
    setupBreakdownListeners();

    // Process paths in forward order (0 = Optimal, 1 = Alt1, 2 = Alt2)
    results.forEach((result, index) => {
        const { features, totalDistance, isOptimal } = result;
        const pathCoords = [];

        features.forEach((feature) => {
            const coords = feature.geometry.coordinates;
            if (feature.geometry.type === 'LineString') {
                const lineCoords = coords.map(c => [c[1], c[0]]);
                if (pathCoords.length > 0) {
                    const last = pathCoords[pathCoords.length - 1];
                    const firstOfNew = lineCoords[0];
                    const lastOfNew = lineCoords[lineCoords.length - 1];
                    if (Math.hypot(last[0] - firstOfNew[0], last[1] - firstOfNew[1]) >
                        Math.hypot(last[0] - lastOfNew[0], last[1] - lastOfNew[1])) {
                        lineCoords.reverse();
                    }
                }
                pathCoords.push(...(pathCoords.length > 0 ? lineCoords.slice(1) : lineCoords));
            } else if (feature.geometry.type === 'MultiLineString') {
                coords.forEach(line => {
                    const lineCoords = line.map(c => [c[1], c[0]]);
                    pathCoords.push(...(pathCoords.length > 0 ? lineCoords.slice(1) : lineCoords));
                });
            }
        });

        if (pathCoords.length === 0) return;

        let label = `Path ${index + 1}`;
        if (isOptimal) label += ' (Optimal)';

        let color = '#00D9FF'; // Path 1
        if (index === 1) color = '#BF40BF'; // Path 2
        else if (index === 2) color = '#FFCC00'; // Path 3

        const weight = isOptimal ? 6 : 4;
        const opacity = isOptimal ? 0.9 : 0.6;
        const pathGroup = L.layerGroup();

        if (state.showPaths) pathGroup.addTo(map);

        // Main Path Polyline
        L.polyline(pathCoords, {
            color, weight, opacity, lineJoin: 'round', lineCap: 'round', pane: 'roadPane'
        }).addTo(pathGroup);

        // Connections to start/end points
        if (state.startLatlng) {
            L.polyline([[state.startLatlng.lat, state.startLatlng.lng], pathCoords[0]], {
                color, weight: weight - 2, opacity, dashArray: '8, 8', pane: 'roadPane'
            }).addTo(pathGroup);
        }
        if (result.targetLatlng) {
            L.polyline([pathCoords[pathCoords.length - 1], [result.targetLatlng.lat, result.targetLatlng.lng]], {
                color, weight: weight - 2, opacity, dashArray: '8, 8', pane: 'roadPane'
            }).addTo(pathGroup);
        }

        const distanceKm = (result.metrics?.length / 1000 || totalDistance / 1000).toFixed(2);
        const actualMeterText = result.actualDistance ? `<br>Actual Distance: ${(result.actualDistance / 1000).toFixed(2)} km` : '';
        const popupContent = `
            <div style="text-align: center;">
                <strong>${label}</strong><br>
                To: ${result.targetName || 'Evacuation Site'}<br>
                TOPSIS Rank Score: ${result.topsisRankScore ? result.topsisRankScore.toFixed(4) : 'N/A'}
            </div>
        `;

        // Interaction: Hover to see details for any path
        pathGroup.on('mouseover', (e) => {
            if (state.showPaths && pathData.visible) {
                L.popup().setLatLng(e.latlng).setContent(popupContent).openOn(map);
            }
        });

        if (isOptimal) {
            // Visual enhancements for Optimal path
            L.polyline(pathCoords, { color, weight: weight + 4, opacity: 0.3, pane: 'roadPane' }).addTo(pathGroup);
            const startP = state.startLatlng ? [state.startLatlng.lat, state.startLatlng.lng] : pathCoords[0];
            const endP = result.targetLatlng ? [result.targetLatlng.lat, result.targetLatlng.lng] : pathCoords[pathCoords.length - 1];
            L.circleMarker(startP, { radius: 8, fillColor: '#00ff00', color: '#fff', weight: 2, fillOpacity: 1, pane: 'roadPane' }).addTo(pathGroup);
            L.circleMarker(endP, { radius: 8, fillColor: '#ff0000', color: '#fff', weight: 2, fillOpacity: 1, pane: 'roadPane' }).addTo(pathGroup);

            // Auto-open optimal popup
            if (state.showPaths) {
                L.popup().setLatLng(pathCoords[Math.floor(pathCoords.length / 2)]).setContent(popupContent).openOn(map);
            }
        }

        const pathData = { group: pathGroup, id: index, type: label, visible: true };
        state.pathLayers.push(pathData);

        // Sidebar Individual Toggle
        if (controlsContainer) {
            const toggleDiv = document.createElement('div');
            toggleDiv.className = 'individual-toggle';
            toggleDiv.style.display = 'flex';
            toggleDiv.style.justifyContent = 'space-between';
            toggleDiv.style.alignItems = 'center';
            toggleDiv.style.marginBottom = '6px';

            toggleDiv.innerHTML = `
                <span style="font-size: 11px; color: ${color}; font-weight: ${isOptimal ? 'bold' : '500'};">
                    ${isOptimal ? '⭐ ' : ''}${label}
                </span>
                <label class="switch" style="transform: scale(0.7); margin: 0;">
                    <input type="checkbox" id="path-toggle-${index}" checked>
                    <span class="slider round"></span>
                </label>
            `;
            controlsContainer.appendChild(toggleDiv);

            document.getElementById(`path-toggle-${index}`).addEventListener('change', (e) => {
                pathData.visible = e.target.checked;
                updatePathLayerVisibility();
            });
        }
    });

    if (state.simulationMode && results.length > 0) {
        populateAnalysisTable(results[0].features);
    }

    if (state.pathLayers.length > 0) {
        const group = new L.featureGroup(state.pathLayers.map(p => p.group));
        map.fitBounds(group.getBounds(), { padding: [80, 80], maxZoom: 16 });
    }
}

/**
 * Populate the analysis results table with breakdown data
 */
export function populateAnalysisTable(pathFeatures) {
    const tableBody = document.querySelector('#results-table tbody');
    const container = document.getElementById('analysis-results');
    if (!tableBody || !container) return;

    tableBody.innerHTML = '';
    container.style.display = 'block';

    pathFeatures.forEach((feature, index) => {
        const breakdown = feature.mcBreakdown || {}; // Added in dijkstra.js
        const row = document.createElement('tr');

        row.innerHTML = `
            <td>${index + 1}</td>
            <td>${breakdown.wsm ? breakdown.wsm.toFixed(4) : 'N/A'}</td>
            <td>${breakdown.topsis ? breakdown.topsis.toFixed(4) : 'N/A'}</td>
        `;

        // Highlight road on map on row hover
        row.onmouseover = () => {
            // We could find the layer and highlight it
        };

        tableBody.appendChild(row);
    });
}

/**
 * Update visibility based on both the global and individual toggles
 */
export function updatePathLayerVisibility() {
    if (!state.pathLayers) return;

    state.pathLayers.forEach(pathObj => {
        if (state.showPaths && pathObj.visible) {
            pathObj.group.addTo(map);
        } else {
            map.removeLayer(pathObj.group);
        }
    });
}

/**
 * Clear the current selection and path
 */
export function clearSelectionAndPath(resetMarkers = true) {
    if (resetMarkers) {
        if (state.currentNodeMarker) {
            if (state.currentNodeMarker.options.isCustomStart) {
                map.removeLayer(state.currentNodeMarker);
            } else {
                state.currentNodeMarker.setStyle({ radius: 4, fillColor: '#ffffff', weight: 1, color: '#000' });
            }
        }
        if (state.targetNodeMarker) {
            state.targetNodeMarker.setStyle({ radius: 4, fillColor: '#ffffff', weight: 1, color: '#000' });
        }
        state.currentNode = null;
        state.targetNode = null;
        state.startLatlng = null;
        state.currentNodeMarker = null;
        state.targetNodeMarker = null;

        document.getElementById('current-node-display').innerText = 'None';
        document.getElementById('target-node-display').innerText = 'None';
        document.getElementById('clear-target').style.display = 'none';

        const controlsContainer = document.getElementById('individual-path-controls');
        if (controlsContainer) {
            controlsContainer.innerHTML = '';
            controlsContainer.style.display = 'none';
        }
    }

    clearPathOverlay();

    const analysisResults = document.getElementById('analysis-results');
    if (analysisResults) analysisResults.style.display = 'none';
    const tableBody = document.querySelector('#results-table tbody');
    if (tableBody) tableBody.innerHTML = '';

    updateSearchButtonState();
}

/**
 * Toggle the visibility of the path layers (Global Switch)
 */
export function togglePathsVisibility(visible) {
    state.showPaths = visible;
    updatePathLayerVisibility();
}

/**
 * Set up listeners for the breakdown modal
 */
function setupBreakdownListeners() {
    const showBtn = document.getElementById('show-breakdown-btn');
    const closeBtn = document.getElementById('close-breakdown');
    const overlay = document.getElementById('breakdown-overlay');

    if (showBtn && !showBtn.dataset.listenerSet) {
        showBtn.addEventListener('click', () => {
            if (state.lastAnalysisResults) {
                showBreakdownOverlay(state.lastAnalysisResults);
            }
        });
        showBtn.dataset.listenerSet = 'true';
    }

    if (closeBtn && !closeBtn.dataset.listenerSet) {
        closeBtn.addEventListener('click', () => {
            if (overlay) overlay.style.display = 'none';
        });
        closeBtn.dataset.listenerSet = 'true';
    }

    if (overlay && !overlay.dataset.listenerSet) {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) overlay.style.display = 'none';
        });
        overlay.dataset.listenerSet = 'true';
    }
}

/**
 * Show the full breakdown overlay
 */
function showBreakdownOverlay(results) {
    const overlay = document.getElementById('breakdown-overlay');
    const tabsContainer = document.getElementById('path-tabs');
    const cardsContainer = document.getElementById('breakdown-cards-container');

    if (!overlay || !tabsContainer || !cardsContainer) return;

    overlay.style.display = 'flex';
    tabsContainer.innerHTML = '';
    cardsContainer.innerHTML = '';

    // --- 1. Create General Summary Tab & Card ---
    const summaryTab = document.createElement('button');
    summaryTab.className = 'path-tab active';
    summaryTab.innerText = '📊 General Summary';
    tabsContainer.appendChild(summaryTab);

    const summaryCard = document.createElement('div');
    summaryCard.className = 'breakdown-card active';
    summaryCard.id = 'path-card-summary';

    // Calculate Rankings
    const rankings = results.map((r, i) => {
        const avgWSM = r.features.reduce((sum, f) => sum + (f.mcBreakdown?.wsm || 0), 0) / r.features.length;
        return {
            index: i,
            id: i + 1,
            name: `Path ${i + 1}`,
            wsm: avgWSM,
            topsis: r.topsisRankScore || 0, // Use the actual Path-Level Decision Score
            cost: r.totalDistance,
            isOptimal: r.isOptimal
        };
    });

    const wsmRanked = [...rankings].sort((a, b) => a.wsm - b.wsm);
    const topsisRanked = [...rankings].sort((a, b) => b.topsis - a.topsis);

    const rankingChanged = wsmRanked[0].id !== topsisRanked[0].id;

    summaryCard.innerHTML = `
        <div class="card-grid" style="grid-template-columns: 1fr; margin-bottom: 25px;">
            <div class="analysis-section">
                <div class="section-header"><h3>Direct Path Comparison</h3></div>
                <div class="collapsible-content" style="padding: 20px;">
                    <table class="modal-table">
                        <thead>
                            <tr>
                                <th>Metric</th>
                                ${rankings.map(r => `<th style="color: ${r.id === 1 ? '#00D9FF' : (r.id === 2 ? '#BF40BF' : '#FFCC00')}">${r.name}${r.isOptimal ? ' (Optimal)' : ''}</th>`).join('')}
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>Weighted Total Cost</td>
                                ${results.map(r => `<td>${r.totalDistance.toFixed(2)}</td>`).join('')}
                            </tr>
                            <tr>
                                <td>Physical Distance (km)</td>
                                ${results.map(r => `<td>${(r.actualDistance / 1000).toFixed(2)}</td>`).join('')}
                            </tr>
                            <tr>
                                <td>Target Site</td>
                                ${results.map(r => `<td>${r.targetName || 'N/A'}</td>`).join('')}
                            </tr>
                            <tr>
                                <td>Avg. WSM Score</td>
                                ${rankings.map(r => `<td>${r.wsm.toFixed(4)}</td>`).join('')}
                            </tr>
                            <tr>
                                <td>Path Rank Score (TOPSIS)</td>
                                ${rankings.map(r => `<td>${r.topsis.toFixed(4)}</td>`).join('')}
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <div class="card-grid">
            <div class="analysis-section">
                <div class="section-header">
                    <h3>Ranking by WSM (Cost Based)</h3>
                    <span style="font-size: 10px; color: #888;">Lowest = Better</span>
                </div>
                <div style="padding: 15px;">
                    ${wsmRanked.map((r, i) => `
                        <div style="display: flex; justify-content: space-between; padding: 10px; background: ${i === 0 ? 'rgba(0, 217, 255, 0.1)' : '#1a1a1a'}; border-radius: 4px; margin-bottom: 8px; border-left: 4px solid ${r.id === 1 ? '#00D9FF' : (r.id === 2 ? '#BF40BF' : '#FFCC00')}">
                            <span>#${i + 1} ${r.name} ${i === 0 ? '<strong style="color: #00D9FF; margin-left:10px;">🏆 TOP COST</strong>' : ''}</span>
                            <span style="font-family: monospace;">Score: ${r.wsm.toFixed(4)}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
            <div class="analysis-section">
                <div class="section-header">
                    <h3>Ranking by TOPSIS (Ideal Based)</h3>
                    <span style="font-size: 10px; color: #888;">Highest = Better</span>
                </div>
                <div style="padding: 15px;">
                    ${topsisRanked.map((r, i) => `
                        <div style="display: flex; justify-content: space-between; padding: 10px; background: ${i === 0 ? 'rgba(0, 242, 254, 0.1)' : '#1a1a1a'}; border-radius: 4px; margin-bottom: 8px; border-left: 4px solid ${r.id === 1 ? '#00D9FF' : (r.id === 2 ? '#BF40BF' : '#FFCC00')}">
                            <span>#${i + 1} ${r.name} ${r.isOptimal ? '<strong style="color: #00f2fe; margin-left:10px;">🌟 OPTIMAL</strong>' : ''}</span>
                            <span style="font-family: monospace;">Score: ${r.topsis.toFixed(4)}</span>
                        </div>
                    `).join('')}
                    ${rankingChanged ? `
                        <div style="margin-top: 15px; padding: 10px; background: rgba(255, 149, 0, 0.1); border-radius: 4px; border: 1px dashed #FF9500; font-size: 11px; color: #FF9500;">
                            <strong>🔄 Decision Shift:</strong> TOPSIS re-ranked ${topsisRanked[0].name} as the best decision compared to the WSM leader.
                        </div>
                    ` : ''}
                </div>
            </div>
        </div>
    `;
    cardsContainer.appendChild(summaryCard);

    summaryTab.onclick = () => {
        document.querySelectorAll('.path-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.breakdown-card').forEach(c => c.classList.remove('active'));
        summaryTab.classList.add('active');
        summaryCard.classList.add('active');
    };

    // --- 2. Create Individual Path Tabs ---
    results.forEach((result, pathIndex) => {
        const pathID = pathIndex + 1;
        const pathName = `Path ${pathID}`;
        const isActive = false; // Summary is active first

        // Create Tab
        const tab = document.createElement('button');
        tab.className = `path-tab ${isActive ? 'active' : ''}`;
        tab.innerText = pathName;
        tab.onclick = () => {
            document.querySelectorAll('.path-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.breakdown-card').forEach(c => c.classList.remove('active'));
            tab.classList.add('active');
            card.classList.add('active');
        };
        tabsContainer.appendChild(tab);

        // Create Card
        const card = document.createElement('div');
        card.className = `breakdown-card ${isActive ? 'active' : ''}`;
        card.id = `path-card-${pathIndex}`;

        // Card Grid for Tables
        const cardGrid = document.createElement('div');
        cardGrid.className = 'card-grid';

        // WSM Section
        const wsmSection = createAnalysisSection('Weighted Sum Model (WSM)', result.features, 'wsm', pathIndex);
        // TOPSIS Section
        const topsisSection = createAnalysisSection('TOPSIS Analysis', result.features, 'topsis', pathIndex);

        cardGrid.appendChild(wsmSection);
        cardGrid.appendChild(topsisSection);
        card.appendChild(cardGrid);

        // Computation Breakdown
        const compDiv = document.createElement('div');
        compDiv.className = 'computation-details';
        compDiv.innerHTML = `
            <h4>Computation Summary (${pathName})</h4>
            <div class="comp-grid">
                <div class="comp-item">
                    <span class="comp-label">Total Weighted Cost</span>
                    <span class="comp-value">${result.totalDistance.toFixed(2)} units</span>
                </div>
                <div class="comp-item">
                    <span class="comp-label">Actual Distance</span>
                    <span class="comp-value">${(result.actualDistance / 1000).toFixed(2)} km</span>
                </div>
                <div class="comp-item">
                    <span class="comp-label">Edges in Path</span>
                    <span class="comp-value">${result.features.length} segments</span>
                </div>
                <div class="comp-item">
                    <span class="comp-label">Target Site</span>
                    <span class="comp-value">${result.targetName || 'N/A'}</span>
                </div>
            </div>
            <div style="margin-top: 15px; font-size: 12px; color: #aaa; line-height: 1.6;">
                <p><strong>Methodology:</strong> This path was calculated using a combination of Dijkstra's algorithm and Multi-Criteria Decision Analysis (WSM/TOPSIS). 
                The edge weights were adjusted based on the specified criteria: 
                Length (w=${state.mcWeights.length}), Risk (w=${state.mcWeights.risk}), and Rainfall (w=${state.mcWeights.rainfall}).</p>
            </div>
        `;
        card.appendChild(compDiv);

        cardsContainer.appendChild(card);
    });
}

/**
 * Creates a collapsible analysis section with a table
 */
function createAnalysisSection(title, features, type, pathIndex) {
    const section = document.createElement('div');
    section.className = 'analysis-section';

    const header = document.createElement('div');
    header.className = 'section-header';
    header.innerHTML = `
        <h3>${title}</h3>
        <button class="secondary-btn" style="font-size: 10px; padding: 2px 6px;">Collapse</button>
    `;

    const content = document.createElement('div');
    content.className = 'collapsible-content';

    const table = document.createElement('table');
    table.className = 'modal-table';
    table.innerHTML = `
        <thead>
            <tr>
                <th>Step</th>
                <th>Raw Data (L, R, Rf)</th>
                <th>${type.toUpperCase()} Score</th>
            </tr>
        </thead>
        <tbody></tbody>
    `;

    content.appendChild(table);

    // Pagination
    const pagination = document.createElement('div');
    pagination.className = 'pagination-controls';
    let currentPage = 0;
    const pageSize = 8;
    const totalPages = Math.ceil(features.length / pageSize);

    const updateTable = () => {
        const tbody = table.querySelector('tbody');
        tbody.innerHTML = '';
        const start = currentPage * pageSize;
        const end = Math.min(start + pageSize, features.length);

        for (let i = start; i < end; i++) {
            const f = features[i];
            const b = f.mcBreakdown || {};
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${i + 1}</td>
                <td style="color: #888;">${(b.length || 0).toFixed(0)}m, ${b.risk || 0}, ${(b.rainfall || 0).toFixed(1)}</td>
                <td style="font-weight: bold; color: ${type === 'wsm' ? '#4facfe' : '#00f2fe'};">${(b[type] || 0).toFixed(4)}</td>
            `;
            tbody.appendChild(row);
        }

        pagination.querySelector('.page-info').innerText = `Page ${currentPage + 1} of ${totalPages}`;
        pagination.querySelector('.prev-btn').disabled = currentPage === 0;
        pagination.querySelector('.next-btn').disabled = currentPage >= totalPages - 1;
    };

    pagination.innerHTML = `
        <button class="secondary-btn prev-btn" style="padding: 2px 8px;"><</button>
        <span class="page-info" style="font-size: 11px; color: #888;"></span>
        <button class="secondary-btn next-btn" style="padding: 2px 8px;">></button>
    `;

    pagination.querySelector('.prev-btn').onclick = () => { if (currentPage > 0) { currentPage--; updateTable(); } };
    pagination.querySelector('.next-btn').onclick = () => { if (currentPage < totalPages - 1) { currentPage++; updateTable(); } };

    content.appendChild(pagination);
    updateTable();

    header.querySelector('button').onclick = () => {
        if (content.style.display === 'none') {
            content.style.display = 'block';
            header.querySelector('button').innerText = 'Collapse';
        } else {
            content.style.display = 'none';
            header.querySelector('button').innerText = 'Expand';
        }
    };

    section.appendChild(header);
    section.appendChild(content);
    return section;
}

/**
 * Internal helper to clear only the path overlay
 */
function clearPathOverlay() {
    if (state.pathLayers) {
        state.pathLayers.forEach(pathData => map.removeLayer(pathData.group));
        state.pathLayers = [];
    }
    // Backward compatibility
    if (state.pathLayer) {
        map.removeLayer(state.pathLayer);
        state.pathLayer = null;
    }
}
