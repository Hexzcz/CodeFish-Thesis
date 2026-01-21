/**
 * UI Event Handlers Module
 */

import { state } from './state.js';
import { map } from './map-init.js';
import { getFloodStyle, getRoadRiskStyle } from './styling.js';
import { STYLES } from './config.js';
import { runDijkstra } from './dijkstra.js';
import { drawPath, clearSelectionAndPath } from './path-manager.js';

/**
 * Initialize all UI control event listeners
 */
export function initSidebarControls() {
    // Flood Layer Toggle
    document.getElementById('toggle-flood').addEventListener('change', (e) => {
        if (!state.floodLayer) return;
        e.target.checked ? map.addLayer(state.floodLayer) : map.removeLayer(state.floodLayer);
    });

    // QC Boundary Toggle
    document.getElementById('toggle-boundary').addEventListener('change', (e) => {
        if (!state.boundaryLayer) return;
        e.target.checked ? map.addLayer(state.boundaryLayer) : map.removeLayer(state.boundaryLayer);
    });

    // Project 8 Boundary Toggle
    document.getElementById('toggle-project8-boundary').addEventListener('change', (e) => {
        if (!state.project8BoundaryLayer) return;
        e.target.checked ? map.addLayer(state.project8BoundaryLayer) : map.removeLayer(state.project8BoundaryLayer);
    });

    // Road Network Toggle
    document.getElementById('toggle-roads').addEventListener('change', (e) => {
        if (!state.project8RoadLayer || !state.project8NodeLayer) return;
        if (e.target.checked) {
            map.addLayer(state.project8RoadLayer);
            map.addLayer(state.project8NodeLayer);
        } else {
            map.removeLayer(state.project8RoadLayer);
            map.removeLayer(state.project8NodeLayer);
        }
    });

    // Flood Opacity Slider
    document.getElementById('flood-opacity').addEventListener('input', (e) => {
        state.currentFloodOpacity = parseFloat(e.target.value);
        if (state.floodLayer) {
            state.floodLayer.setStyle(getFloodStyle);
        }
    });

    // Road Risk Mode Toggle
    document.getElementById('toggle-road-risk').addEventListener('change', (e) => {
        if (!state.project8RoadLayer) return;
        if (e.target.checked) {
            state.project8RoadLayer.setStyle(getRoadRiskStyle);
        } else {
            state.project8RoadLayer.setStyle(STYLES.road);
        }
    });
}

/**
 * Initialize Pathfinding Button
 */
export function initSearchButton() {
    const btn = document.getElementById('find-path');
    if (btn) {
        btn.addEventListener('click', () => {
            if (state.currentNode && state.targetNode) {
                console.log(`ACTION: Finding path from Node ${state.currentNode} to Node ${state.targetNode}...`);
                const result = runDijkstra(state.currentNode, state.targetNode, state.adjacencyList);
                if (result) {
                    drawPath(result);
                } else {
                    alert("No path found between the selected nodes.");
                }
            }
        });
    }

    const clearBtn = document.getElementById('clear-path');
    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            clearSelectionAndPath();
        });
    }
}
