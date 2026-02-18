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

        let color = '#00D9FF';
        let label = 'Optimal Path';
        if (!isOptimal) {
            if (index === 1) { color = '#555555'; label = 'Alternative 1'; }
            else { color = '#999999'; label = 'Alternative 2'; }
        }

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

        const distanceKm = (totalDistance / 1000).toFixed(2);
        const actualMeterText = result.actualDistance ? `<br>Actual Distance: ${(result.actualDistance / 1000).toFixed(2)} km` : '';
        const popupContent = `
            <div style="text-align: center;">
                <strong>${label}</strong><br>
                To: ${result.targetName || 'Evacuation Site'}<br>
                Weighted Cost: ${distanceKm} units${actualMeterText}
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

    if (state.pathLayers.length > 0) {
        const group = new L.featureGroup(state.pathLayers.map(p => p.group));
        map.fitBounds(group.getBounds(), { padding: [80, 80], maxZoom: 16 });
    }
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
