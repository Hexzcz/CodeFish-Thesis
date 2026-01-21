/**
 * Path Visualization & Management Module
 */

import { state } from './state.js';
import { map } from './map-init.js';
import { updateSearchButtonState } from './node-selection.js';

/**
 * Draw the calculated path on the map
 */
export function drawPath(result) {
    if (state.pathLayer) {
        clearPathOverlay();
    }

    const { features, totalDistance } = result;

    // Build continuous path coordinates
    const pathCoords = [];

    features.forEach((feature) => {
        const coords = feature.geometry.coordinates;
        const geometryType = feature.geometry.type;

        if (geometryType === 'LineString') {
            const lineCoords = coords.map(c => [c[1], c[0]]);

            if (pathCoords.length > 0) {
                const lastPoint = pathCoords[pathCoords.length - 1];
                const firstPoint = lineCoords[0];
                const lastPointOfNew = lineCoords[lineCoords.length - 1];

                const distToFirst = Math.hypot(lastPoint[0] - firstPoint[0], lastPoint[1] - firstPoint[1]);
                const distToLast = Math.hypot(lastPoint[0] - lastPointOfNew[0], lastPoint[1] - lastPointOfNew[1]);

                if (distToLast < distToFirst) {
                    lineCoords.reverse();
                }
            }

            const startIdx = pathCoords.length > 0 ? 1 : 0;
            pathCoords.push(...lineCoords.slice(startIdx));

        } else if (geometryType === 'MultiLineString') {
            coords.forEach(line => {
                const lineCoords = line.map(c => [c[1], c[0]]);
                const startIdx = pathCoords.length > 0 ? 1 : 0;
                pathCoords.push(...lineCoords.slice(startIdx));
            });
        }
    });

    // Create the path polyline
    state.pathLayer = L.polyline(pathCoords, {
        color: '#00D9FF',
        weight: 6,
        opacity: 0.9,
        lineJoin: 'round',
        lineCap: 'round',
        pane: 'roadPane',
        className: 'path-highlight'
    }).addTo(map);

    // Add glow effect
    const glowLayer = L.polyline(pathCoords, {
        color: '#00D9FF',
        weight: 10,
        opacity: 0.3,
        lineJoin: 'round',
        lineCap: 'round',
        pane: 'roadPane'
    }).addTo(map);

    state.pathLayer._glowLayer = glowLayer;

    // Add start and end markers
    if (pathCoords.length > 0) {
        const startMarker = L.circleMarker(pathCoords[0], {
            radius: 8, fillColor: '#00ff00', color: '#fff', weight: 2, fillOpacity: 1, pane: 'roadPane'
        }).addTo(map);

        const endMarker = L.circleMarker(pathCoords[pathCoords.length - 1], {
            radius: 8, fillColor: '#ff0000', color: '#fff', weight: 2, fillOpacity: 1, pane: 'roadPane'
        }).addTo(map);

        const distanceKm = (totalDistance / 1000).toFixed(2);
        const distanceM = totalDistance.toFixed(0);

        const popup = L.popup()
            .setLatLng(pathCoords[Math.floor(pathCoords.length / 2)])
            .setContent(`
                <div style="text-align: center;">
                    <strong>Route Found</strong><br>
                    Distance: ${distanceKm} km (${distanceM} m)<br>
                    Segments: ${features.length}
                </div>
            `)
            .openOn(map);

        state.pathLayer._startMarker = startMarker;
        state.pathLayer._endMarker = endMarker;
        state.pathLayer._popup = popup;
    }

    map.fitBounds(state.pathLayer.getBounds(), {
        padding: [80, 80],
        maxZoom: 16
    });

    console.log(`Path found: ${totalDistance.toFixed(2)}m over ${features.length} segments`);
}

/**
 * Clear the current selection and path
 */
export function clearSelectionAndPath(resetMarkers = true) {
    if (resetMarkers) {
        if (state.currentNodeMarker) {
            state.currentNodeMarker.setStyle({ radius: 4, fillColor: '#ffffff', weight: 1, color: '#000' });
        }
        if (state.targetNodeMarker) {
            state.targetNodeMarker.setStyle({ radius: 4, fillColor: '#ffffff', weight: 1, color: '#000' });
        }
        state.currentNode = null;
        state.targetNode = null;
        state.currentNodeMarker = null;
        state.targetNodeMarker = null;

        document.getElementById('current-node-display').innerText = 'None';
        document.getElementById('target-node-display').innerText = 'None';
    }

    clearPathOverlay();
    updateSearchButtonState();
}

/**
 * Internal helper to clear only the path overlay
 */
function clearPathOverlay() {
    if (state.pathLayer) {
        if (state.pathLayer._glowLayer) map.removeLayer(state.pathLayer._glowLayer);
        if (state.pathLayer._startMarker) map.removeLayer(state.pathLayer._startMarker);
        if (state.pathLayer._endMarker) map.removeLayer(state.pathLayer._endMarker);
        if (state.pathLayer._popup) map.closePopup(state.pathLayer._popup);
        map.removeLayer(state.pathLayer);
        state.pathLayer = null;
    }
}
