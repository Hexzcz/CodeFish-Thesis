/**
 * Node Selection Logic Module
 */

import { state } from './state.js';
import { map } from './map-init.js';

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
        state.currentNodeMarker.setStyle({ radius: 4, fillColor: '#ffffff', weight: 1, color: '#000' });
    }

    state.currentNode = nodeId;
    state.currentNodeMarker = layer;
    layer.setStyle({ radius: 8, fillColor: '#00ff00', weight: 2, color: '#fff' });
    document.getElementById('current-node-display').innerText = nodeId;

    updateSearchButtonState();
}

/**
 * Update the "Find Shortest Path" button state
 */
export function updateSearchButtonState() {
    const btn = document.getElementById('find-path');
    if (!btn) return;

    if (state.currentNode) {
        btn.disabled = false;
        btn.style.pointerEvents = 'auto';
        btn.style.opacity = '1';
    } else {
        btn.disabled = true;
        btn.style.pointerEvents = 'none';
        btn.style.opacity = '0.6';
    }
}

/**
 * Initialize node clear button handlers
 */
export function initNodeClearHandlers(clearSelectionAndPath) {
    document.getElementById('clear-current').addEventListener('click', () => {
        if (state.currentNodeMarker) {
            state.currentNodeMarker.setStyle({ radius: 4, fillColor: '#ffffff', weight: 1, color: '#000' });
        }
        state.currentNode = null;
        state.currentNodeMarker = null;
        document.getElementById('current-node-display').innerText = 'None';

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

    document.getElementById('clear-target').addEventListener('click', () => {
        if (state.targetNodeMarker) {
            state.targetNodeMarker.setStyle({ radius: 4, fillColor: '#ffffff', weight: 1, color: '#000' });
        }
        state.targetNode = null;
        state.targetNodeMarker = null;
        document.getElementById('target-node-display').innerText = 'None';
        document.getElementById('clear-target').style.display = 'none';

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
