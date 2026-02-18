/**
 * UI Event Handlers Module
 */

import { state } from './state.js';
import { map } from './map-init.js';
import { getFloodStyle, getRoadRiskStyle } from './styling.js';
import { STYLES } from './config.js';
import { runDijkstra, findNearestEvacuationPath } from './dijkstra.js';
import { drawPaths, clearSelectionAndPath, togglePathsVisibility } from './path-manager.js';

import { fetchRainfallData, updateRainfallOverlay } from './jaxa-api.js';

/**
 * Initialize all UI control event listeners
 */
export function initSidebarControls() {
    initMobileControls();

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

    // District 1 Boundary Toggle
    document.getElementById('toggle-district1-boundary').addEventListener('change', (e) => {
        if (!state.district1BoundaryLayer) return;
        e.target.checked ? map.addLayer(state.district1BoundaryLayer) : map.removeLayer(state.district1BoundaryLayer);
    });

    // Road Network Toggle
    document.getElementById('toggle-roads').addEventListener('change', (e) => {
        if (!state.district1RoadLayer || !state.district1NodeLayer) return;
        if (e.target.checked) {
            map.addLayer(state.district1RoadLayer);
            map.addLayer(state.district1NodeLayer);
        } else {
            map.removeLayer(state.district1RoadLayer);
            map.removeLayer(state.district1NodeLayer);
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
        if (!state.district1RoadLayer) return;
        if (e.target.checked) {
            state.district1RoadLayer.setStyle(getRoadRiskStyle);
        } else {
            state.district1RoadLayer.setStyle(STYLES.road);
        }
    });

    // JAXA Rainfall Timeframe Selection
    document.getElementById('rainfall-timeframe').addEventListener('change', async (e) => {
        state.rainfallTimeframe = e.target.value;
        await fetchRainfallData(state.rainfallTimeframe);
        updateRainfallOverlay();

        // Refresh road risk styles if enabled, as rainfall affects risk
        if (document.getElementById('toggle-road-risk').checked && state.district1RoadLayer) {
            state.district1RoadLayer.setStyle(getRoadRiskStyle);
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

                const results = findNearestEvacuationPath(state.currentNode, state.evacuationSites, state.adjacencyList);

                if (results && results.length > 0) {
                    const optimal = results[0];
                    state.targetNode = optimal.nodes[optimal.nodes.length - 1];
                    document.getElementById('target-node-display').innerText = optimal.targetName;
                    document.getElementById('clear-target').style.display = 'inline-block';

                    drawPaths(results);
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

    // Path Visibility Toggle
    document.getElementById('toggle-paths')?.addEventListener('change', (e) => {
        togglePathsVisibility(e.target.checked);
    });
}

/**
 * Mobile Sidebar Toggle Logic
 */
function initMobileControls() {
    const toggleBtn = document.getElementById('sidebar-toggle');
    const sidebar = document.getElementById('sidebar');
    const container = document.querySelector('.app-container');

    if (!toggleBtn || !sidebar) return;

    // Initial state: 
    // On mobile, collapse it. On desktop, keep it open and set toggle to active (X).
    if (window.innerWidth <= 768) {
        sidebar.classList.add('collapsed');
        toggleBtn.classList.remove('active');
    } else {
        sidebar.classList.remove('collapsed');
        toggleBtn.classList.add('active'); // Shows 'X' when open
    }

    const toggleSidebar = (shouldCollapse) => {
        if (shouldCollapse === undefined) {
            shouldCollapse = !sidebar.classList.contains('collapsed');
        }

        if (shouldCollapse) {
            sidebar.classList.add('collapsed');
            toggleBtn.classList.remove('active');
            if (container) container.classList.remove('sidebar-open');
        } else {
            sidebar.classList.remove('collapsed');
            toggleBtn.classList.add('active');
            if (container && window.innerWidth <= 768) {
                container.classList.add('sidebar-open');
            }
        }
    };

    toggleBtn.addEventListener('click', () => {
        const currentlyCollapsed = sidebar.classList.contains('collapsed');
        toggleSidebar(!currentlyCollapsed);
    });

    // Close sidebar when clicking on the map or the overlay (on mobile)
    map.on('click', () => {
        if (window.innerWidth <= 768) {
            toggleSidebar(true);
        }
    });

    // Handle clicking the overlay specifically
    // Since we don't have a direct overlay element but use ::after on container,
    // we can check if the click target is the container itself or add a real overlay.
    // For now, map click is usually sufficient. But let's add a window listener for the 'after' overlay.
    container.addEventListener('click', (e) => {
        if (window.innerWidth <= 768 && e.target === container && container.classList.contains('sidebar-open')) {
            toggleSidebar(true);
        }
    });

    // Handle window resize to sync states
    window.addEventListener('resize', () => {
        if (window.innerWidth > 768 && sidebar.classList.contains('collapsed')) {
            // Optional: Auto-expand when going back to desktop
            // toggleSidebar(false);
        }
    });
}
