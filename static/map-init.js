/**
 * Map Initialization Module
 */

import { MAP_CONFIG, PANES } from './config.js';

export let map;

/**
 * Initialize the Leaflet map and base layers
 */
export function initMap() {
    map = L.map('map', {
        zoomControl: false // Disable default to move it
    }).setView(MAP_CONFIG.center, MAP_CONFIG.zoom);

    // Add zoom control to top-right
    L.control.zoom({ position: 'topright' }).addTo(map);

    L.tileLayer(MAP_CONFIG.tileLayer, {
        attribution: MAP_CONFIG.attribution,
        subdomains: MAP_CONFIG.subdomains,
        maxZoom: MAP_CONFIG.maxZoom
    }).addTo(map);

    // Create custom panes
    const roadPane = map.createPane(PANES.roadPane.name);
    roadPane.style.zIndex = PANES.roadPane.zIndex;

    return map;
}
