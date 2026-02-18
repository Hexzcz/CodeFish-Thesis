/**
 * Application Entry Point
 */

import { initMap } from './map-init.js';
import { loadData } from './data-loader.js';
import { initSidebarControls, initSearchButton } from './ui-controls.js';
import { initNodeClearHandlers, updateSearchButtonState, handleMapClick } from './node-selection.js';
import { clearSelectionAndPath } from './path-manager.js';
import { state } from './state.js';

/**
 * Main application initialization
 */
document.addEventListener('DOMContentLoaded', async () => {
    console.log("Initializing Flooding Pathfinding App...");

    try {
        // 1. Initialize Map
        const map = initMap();

        // 2. Setup window.nodeState for debugging (completing the binding)
        window.nodeState.update = updateSearchButtonState;

        // 3. Initialize UI Controls
        initSidebarControls();
        initSearchButton();
        initNodeClearHandlers(clearSelectionAndPath);

        // Map Click for arbitrary start point
        map.on('click', (e) => {
            handleMapClick(e.latlng, clearSelectionAndPath);
        });

        // 4. Load GeoJSON Data
        await loadData();

        // 5. Fetch Initial Rainfall Data
        const { fetchRainfallData } = await import('./jaxa-api.js');
        await fetchRainfallData('now');

        console.log("Application successfully initialized.");
    } catch (error) {
        console.error("Failed to initialize application:", error);
    }
});
