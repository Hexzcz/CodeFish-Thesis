/**
 * Data Fetching & Layer Management Module
 */

import { state } from './state.js';
import { map } from './map-init.js';
import { API_ENDPOINTS, STYLES } from './config.js';
import { getFloodStyle, getRoadRiskStyle } from './styling.js';
import { handleNodeClick, updateSearchButtonState } from './node-selection.js';
import { clearSelectionAndPath } from './path-manager.js';
import { evacuationSitesData } from './evacuation-sites.js';

/**
 * Fetch all required GeoJSON data and initialize layers
 */
export async function loadData() {
    const timestamp = new Date().getTime();

    // Fetch Flood Data
    fetch(`${API_ENDPOINTS.flood}?t=${timestamp}`)
        .then(response => response.json())
        .then(data => {
            state.floodLayer = L.geoJSON(data, {
                style: getFloodStyle,
                onEachFeature: (feature, layer) => {
                    if (feature.properties && feature.properties.Var) {
                        layer.bindTooltip(`Flood Level: ${feature.properties.Var}`);
                    }
                }
            });

            if (document.getElementById('toggle-flood').checked) {
                state.floodLayer.addTo(map);
            }
        })
        .catch(err => console.error("Error loading flood data:", err));

    // Fetch QC Boundary Data
    fetch(`${API_ENDPOINTS.boundary}?t=${timestamp}`)
        .then(response => response.json())
        .then(data => {
            state.boundaryLayer = L.geoJSON(data, {
                style: STYLES.boundary
            });

            if (document.getElementById('toggle-boundary').checked) {
                state.boundaryLayer.addTo(map);
            }
        })
        .catch(err => console.error("Error loading boundary data:", err));

    // Fetch District 1 Boundary Data
    fetch(`${API_ENDPOINTS.district1Boundary}?t=${timestamp}`)
        .then(response => response.json())
        .then(data => {
            state.district1BoundaryLayer = L.geoJSON(data, {
                style: STYLES.district1Boundary
            });

            if (document.getElementById('toggle-district1-boundary').checked) {
                state.district1BoundaryLayer.addTo(map);
            }
        })
        .catch(err => console.error("Error loading District 1 boundary data:", err));

    // Fetch District 1 Road Data
    fetch(`${API_ENDPOINTS.roads}?t=${timestamp}`)
        .then(response => response.json())
        .then(data => {
            const nodes = new Map();
            state.adjacencyList.clear();

            data.features.forEach(feature => {
                const coords = feature.geometry.coordinates;
                const u = feature.properties.u;
                const v = feature.properties.v;
                const length = feature.properties.length || 1;

                if (coords.length >= 2) {
                    const startCoords = coords[0];
                    const endCoords = coords[coords.length - 1];
                    if (u !== undefined) nodes.set(u, { id: u, coords: [startCoords[1], startCoords[0]] });
                    if (v !== undefined) nodes.set(v, { id: v, coords: [endCoords[1], endCoords[0]] });
                }

                if (u !== undefined && v !== undefined) {
                    if (!state.adjacencyList.has(u)) state.adjacencyList.set(u, []);
                    if (!state.adjacencyList.has(v)) state.adjacencyList.set(v, []);
                    state.adjacencyList.get(u).push({ node: v, weight: length, feature: feature });
                    state.adjacencyList.get(v).push({ node: u, weight: length, feature: feature });
                }
            });

            // Create Roads Layer
            state.district1RoadLayer = L.geoJSON(data, {
                pane: 'roadPane',
                interactive: true,
                style: STYLES.road,
                onEachFeature: (feature, layer) => {
                    const length = feature.properties.length ? feature.properties.length.toFixed(2) : 'N/A';
                    layer.bindTooltip(`Road: ${feature.properties.name || 'Unnamed'}<br>Length: ${length}m`, { sticky: true });
                    layer.on({
                        mouseover: (e) => {
                            e.target.setStyle({ weight: 4, color: '#4facfe', opacity: 1 });
                            e.target.bringToFront();
                        },
                        mouseout: (e) => {
                            if (document.getElementById('toggle-road-risk').checked) {
                                e.target.setStyle(getRoadRiskStyle(feature));
                            } else {
                                e.target.setStyle(STYLES.road);
                            }
                        }
                    });
                }
            });

            // Create Nodes Layer (Circular markers)
            const nodeFeatures = Array.from(nodes.values()).map(node => ({
                type: 'Feature',
                geometry: { type: 'Point', coordinates: [node.coords[1], node.coords[0]] },
                properties: { id: node.id }
            }));

            state.district1NodeLayer = L.geoJSON(nodeFeatures, {
                pane: 'roadPane',
                interactive: true,
                pointToLayer: (feature, latlng) => L.circleMarker(latlng, {
                    radius: 4, fillColor: "#ffffff", color: "#000", weight: 1, opacity: 1, fillOpacity: 0.8
                }),
                onEachFeature: (feature, layer) => {
                    layer.bindTooltip(`Node ID: ${feature.properties.id}`);
                    layer.on({
                        mouseover: (e) => e.target.setStyle({ radius: 7, fillColor: '#4facfe' }),
                        mouseout: (e) => {
                            const id = feature.properties.id;
                            if (state.currentNode !== id && state.targetNode !== id) {
                                e.target.setStyle({ radius: 4, fillColor: '#ffffff' });
                            }
                        },
                        click: (e) => {
                            L.DomEvent.stopPropagation(e);
                            handleNodeClick(feature.properties.id, layer, clearSelectionAndPath);
                        }
                    });
                }
            });

            state.nodes = nodes; // Store for nearest node search

            if (document.getElementById('toggle-roads').checked) {
                state.district1RoadLayer.addTo(map);
                state.district1NodeLayer.addTo(map);
            }

            initEvacuationSites();
            updateSearchButtonState();
        })
        .catch(err => console.error("Error loading road data:", err));
}

/**
 * Initialize evacuation sites layer
 */
export function initEvacuationSites() {
    if (!state.nodes) return;

    state.evacuationSites = evacuationSitesData.map(site => ({
        ...site,
        nodeId: findNearestNode(site.lat, site.lng)
    }));

    const markers = state.evacuationSites.map(site => {
        const nearestNodeId = site.nodeId;

        // Custom icon for evacuation site
        const evacIcon = L.divIcon({
            html: `<div style="background-color: #ff9500; width: 20px; height: 20px; border-radius: 50%; border: 2px solid white; display: flex; align-items: center; justify-content: center; color: white; font-size: 12px; font-weight: bold; box-shadow: 0 0 10px rgba(255,149,0,0.5);">E</div>`,
            className: 'evac-icon',
            iconSize: [20, 20],
            iconAnchor: [10, 10]
        });

        const marker = L.marker([site.lat, site.lng], { icon: evacIcon });
        marker.bindTooltip(`<b>${site.name}</b><br>Barangay: ${site.barangay}`);

        return marker;
    });

    state.evacuationLayer = L.layerGroup(markers);

    if (document.getElementById('toggle-evacuation').checked) {
        state.evacuationLayer.addTo(map);
    }
}

/**
 * Find the nearest road node to a given lat/lng
 */
export function findNearestNode(lat, lng) {
    let minDistance = Infinity;
    let nearestNodeId = null;

    state.nodes.forEach((node, id) => {
        // Simple Euclidean distance for selection
        const dist = Math.sqrt(Math.pow(node.coords[0] - lat, 2) + Math.pow(node.coords[1] - lng, 2));
        if (dist < minDistance) {
            minDistance = dist;
            nearestNodeId = id;
        }
    });

    return nearestNodeId;
}
