/**
 * Node Selection Logic Module
 */

import { state } from './state.js';
import { map } from './map-init.js';
import { findNearestNode } from './data-loader.js';

/**
 * Handle clicking anywhere on the map to set starting point
 */
export function handleMapClick(latlng, clearSelectionAndPath) {
    if (!state.nodes) return;

    const lat = latlng.lat;
    const lng = latlng.lng;
    const nearestNodeId = findNearestNode(lat, lng);

    if (nearestNodeId === null) return;

    // If a path exists, clear it
    if (state.pathLayer) {
        clearSelectionAndPath(false);
    }

    // Set arbitrary click coords
    state.startLatlng = latlng;

    // Clear previous starting marker
    if (state.currentNodeMarker) {
        if (state.currentNodeMarker.options.isCustomStart) {
            map.removeLayer(state.currentNodeMarker);
        } else {
            state.currentNodeMarker.setStyle({ radius: 4, fillColor: '#ffffff', weight: 1, color: '#000' });
        }
    }

    state.currentNode = nearestNodeId;

    // Create or move a custom marker for the exact click location
    const customMarker = L.circleMarker(latlng, {
        radius: 8,
        fillColor: '#00D9FF', // Sky blue for arbitrary start
        weight: 2,
        color: '#fff',
        opacity: 1,
        fillOpacity: 1,
        isCustomStart: true
    }).addTo(map);

    state.currentNodeMarker = customMarker;
    document.getElementById('current-node-display').innerText = `Near Node ${nearestNodeId}`;

    updateSearchButtonState();
}

/**
 * Handle clicking on a road node
 */
export function handleNodeClick(nodeId, layer, clearSelectionAndPath) {
    // If a path exists, clear it when selection changes
    if (state.pathLayer) {
        clearSelectionAndPath(false);
    }

    // Always set as Current (Starting Point)
    // Clear previous marker if exists
    if (state.currentNodeMarker) {
        if (state.currentNodeMarker.options.isCustomStart) {
            map.removeLayer(state.currentNodeMarker);
        } else {
            state.currentNodeMarker.setStyle({ radius: 4, fillColor: '#ffffff', weight: 1, color: '#000' });
        }
    }

    state.currentNode = nodeId;
    state.startLatlng = null; // Direct node click resets arbitrary start
    state.currentNodeMarker = layer;
    layer.setStyle({ radius: 8, fillColor: '#00ff00', weight: 2, color: '#fff' });
    document.getElementById('current-node-display').innerText = nodeId;

    updateSearchButtonState();
}

/**
 * Update the "Find Shortest Path" button state
 */
export function updateSearchButtonState() {
    const simBtn = document.getElementById('find-optimal-path');

    const isSelected = !!state.currentNode;

    [simBtn].forEach(b => {
        if (!b) return;
        b.disabled = !isSelected;
        b.style.pointerEvents = isSelected ? 'auto' : 'none';
        b.style.opacity = isSelected ? '1' : '0.6';
    });

    // Update Simulation Sidebar display
    const simDisplay = document.getElementById('sim-current-node-display');
    const mainDisplay = document.getElementById('current-node-display');
    const mainDisplayText = mainDisplay ? mainDisplay.innerText : 'None';
    if (simDisplay) simDisplay.innerText = mainDisplayText;
}

/**
 * Initialize node clear button handlers
 */
export function initNodeClearHandlers(clearSelectionAndPath) {
    document.getElementById('clear-current')?.addEventListener('click', () => {
        if (state.currentNodeMarker) {
            if (state.currentNodeMarker.options.isCustomStart) {
                map.removeLayer(state.currentNodeMarker);
            } else {
                state.currentNodeMarker.setStyle({ radius: 4, fillColor: '#ffffff', weight: 1, color: '#000' });
            }
        }
        state.currentNode = null;
        state.startLatlng = null;
        state.currentNodeMarker = null;
        const display = document.getElementById('current-node-display');
        if (display) display.innerText = 'None';

        // Remove path if one of the nodes is cleared
        if (state.pathLayer) {
            map.removeLayer(state.pathLayer);
            if (state.pathLayer._glowLayer) map.removeLayer(state.pathLayer._glowLayer);
            if (state.pathLayer._startMarker) map.removeLayer(state.pathLayer._startMarker);
            if (state.pathLayer._endMarker) map.removeLayer(state.pathLayer._endMarker);
            if (state.pathLayer._popup) map.closePopup(state.pathLayer._popup);
            state.pathLayer = null;
        }
        updateSearchButtonState();
    });

    document.getElementById('clear-target')?.addEventListener('click', () => {
        if (state.targetNodeMarker) {
            state.targetNodeMarker.setStyle({ radius: 4, fillColor: '#ffffff', weight: 1, color: '#000' });
        }
        state.targetNode = null;
        state.targetNodeMarker = null;
        const display = document.getElementById('target-node-display');
        if (display) display.innerText = 'None';
        const clearTargetBtn = document.getElementById('clear-target');
        if (clearTargetBtn) clearTargetBtn.style.display = 'none';

        // Remove path if one of the nodes is cleared
        if (state.pathLayer) {
            map.removeLayer(state.pathLayer);
            if (state.pathLayer._glowLayer) map.removeLayer(state.pathLayer._glowLayer);
            if (state.pathLayer._startMarker) map.removeLayer(state.pathLayer._startMarker);
            if (state.pathLayer._endMarker) map.removeLayer(state.pathLayer._endMarker);
            if (state.pathLayer._popup) map.closePopup(state.pathLayer._popup);
            state.pathLayer = null;
        }
        updateSearchButtonState();
    });
}
