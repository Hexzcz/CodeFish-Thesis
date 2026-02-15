/**
 * UI Event Handlers Module
 */

import { state } from './state.js';
import { map } from './map-init.js';
import { getFloodStyle, getRoadRiskStyle } from './styling.js';
import { STYLES } from './config.js';
import { runDijkstra, findNearestEvacuationPath } from './dijkstra.js';
import { drawPath, clearSelectionAndPath } from './path-manager.js';

import { fetchRainfallData, updateRainfallOverlay } from './jaxa-api.js';

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

    // Evacuation Sites Toggle
    document.getElementById('toggle-evacuation').addEventListener('change', (e) => {
        if (!state.evacuationLayer) return;
        e.target.checked ? map.addLayer(state.evacuationLayer) : map.removeLayer(state.evacuationLayer);
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

    // JAXA Rainfall Timeframe Selection
    document.getElementById('rainfall-timeframe').addEventListener('change', async (e) => {
        state.rainfallTimeframe = e.target.value;
        await fetchRainfallData(state.rainfallTimeframe);
        updateRainfallOverlay();

        // Refresh road risk styles if enabled, as rainfall affects risk
        if (document.getElementById('toggle-road-risk').checked && state.project8RoadLayer) {
            state.project8RoadLayer.setStyle(getRoadRiskStyle);
        }
    });

    // JAXA Rainfall Visibility Toggle
    document.getElementById('toggle-rainfall')?.addEventListener('change', (e) => {
        state.showRainfall = e.target.checked;
        updateRainfallOverlay();
    });

    // JAXA Data Mode Switch
    document.getElementById('jaxa-mode')?.addEventListener('change', (e) => {
        const mode = e.target.value;
        const liveSection = document.getElementById('section-live-forecast');
        const historicalSection = document.getElementById('section-historical');
        if (liveSection && historicalSection) {
            liveSection.style.display = mode === 'live' ? 'block' : 'none';
            historicalSection.style.display = mode === 'historical' ? 'block' : 'none';
        }
    });

    // FTP Menu Toggle (Advanced Settings)
    const ftpBtn = document.getElementById('toggle-ftp-menu');
    const ftpMenu = document.getElementById('ftp-credentials-menu');
    if (ftpBtn && ftpMenu) {
        ftpBtn.addEventListener('click', () => {
            const isHidden = ftpMenu.style.display === 'none';
            ftpMenu.style.display = isHidden ? 'block' : 'none';
            ftpBtn.innerText = isHidden ? 'Hide Advanced Settings' : 'Advanced FTP Settings';
        });
    }

    // Save/Sync Button
    document.getElementById('save-ftp-creds')?.addEventListener('click', async () => {
        const mode = document.getElementById('jaxa-mode').value;
        const host = document.getElementById('ftp-host').value;
        const user = document.getElementById('ftp-user').value;
        const pass = document.getElementById('ftp-pass').value;
        const timeframe = document.getElementById('rainfall-timeframe').value;

        // Conditional Date/Hour based on mode
        const date = mode === 'historical' ? document.getElementById('ftp-date').value : "";
        const hour = mode === 'historical' ? document.getElementById('ftp-hour').value : "";

        console.log(`SYNC REQUEST: Mode=${mode}, Date=${date || 'LATEST'}, Hour=${hour || 'LATEST'}`);

        const btn = document.getElementById('save-ftp-creds');
        if (btn) {
            btn.disabled = true;
            btn.innerText = "Syncing... ⏳";
        }

        try {
            const response = await fetch('/sync_jaxa_ftp', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ host, user, password: pass, date, hour })
            });

            const result = await response.json();
            if (result.status === 'success') {
                alert("Success: " + result.message);
                await fetchRainfallData(timeframe);
                updateRainfallOverlay();
            } else {
                alert("Error: " + result.message);
            }
        } catch (err) {
            console.error(err);
            alert("Failed to connect to backend server.");
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.innerText = "Sync JAXA Data 🔄";
            }
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
            if (state.currentNode) {
                console.log(`ACTION: Finding nearest evacuation site from Node ${state.currentNode}...`);

                const result = findNearestEvacuationPath(state.currentNode, state.evacuationSites, state.adjacencyList);

                if (result) {
                    state.targetNode = result.nodes[result.nodes.length - 1];
                    document.getElementById('target-node-display').innerText = result.targetName;
                    document.getElementById('clear-target').style.display = 'inline-block';

                    drawPath(result);
                } else {
                    alert("No reachable evacuation centers found from this location.");
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
