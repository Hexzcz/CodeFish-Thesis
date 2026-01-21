/**
 * Configuration & Constants Module
 */

export const MAP_CONFIG = {
    center: [14.65, 121.08],
    zoom: 12,
    tileLayer: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 20
};

export const STYLES = {
    boundary: {
        fillColor: 'transparent',
        color: '#00ffcc', // Cyan neon border
        weight: 2,
        dashArray: '5, 5',
        fillOpacity: 0
    },
    road: {
        color: '#ffffff',
        weight: 1.5,
        opacity: 0.8
    },
    project8Boundary: {
        fillColor: 'transparent',
        color: '#ff9500', // Orange neon border
        weight: 3,
        dashArray: '10, 5',
        fillOpacity: 0
    },
    path: {
        color: '#00D9FF',        // Bright cyan blue
        weight: 6,
        opacity: 0.9,
        lineJoin: 'round',
        lineCap: 'round'
    }
};

export const API_ENDPOINTS = {
    flood: '/flood_clipped.geojson',
    boundary: '/qc_boundary.geojson',
    project8Boundary: '/project8_boundary.geojson',
    roads: '/project8_roads.geojson'
};

export const PANES = {
    roadPane: {
        name: 'roadPane',
        zIndex: 650
    }
};
