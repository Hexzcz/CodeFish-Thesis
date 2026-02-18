/**
 * Application State Module
 */

export const state = {
    // Selection state
    currentNode: null,
    targetNode: null,
    startLatlng: null, // Stores actual click coordinates for start
    currentNodeMarker: null,
    targetNodeMarker: null,

    // Layers
    floodLayer: null,
    boundaryLayer: null,
    district1BoundaryLayer: null,
    district1RoadLayer: null,
    district1NodeLayer: null,
    pathLayer: null,
    pathLayers: [], // To store multiple path layers
    rainfallLayer: null,
    evacuationLayer: null,

    // Data structures
    adjacencyList: new Map(),
    rainfallData: null,
    evacuationSites: [],

    // UI state
    currentFloodOpacity: 0.6,
    rainfallTimeframe: 'now',
    showRainfall: false,
    showPaths: true, // Whether to show/hide path overlays
    showEvacuationSites: true,
    selectedEvacuationSite: null
};

// Debug object
window.nodeState = {
    get current() { return state.currentNode; },
    get target() { return state.targetNode; },
    update: null // Will be set in main.js or node-selection.js
};
