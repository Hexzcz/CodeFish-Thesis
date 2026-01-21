/**
 * Application State Module
 */

export const state = {
    // Selection state
    currentNode: null,
    targetNode: null,
    currentNodeMarker: null,
    targetNodeMarker: null,

    // Layers
    floodLayer: null,
    boundaryLayer: null,
    project8BoundaryLayer: null,
    project8RoadLayer: null,
    project8NodeLayer: null,
    pathLayer: null,

    // Data structures
    adjacencyList: new Map(),

    // UI state
    currentFloodOpacity: 0.6
};

// Debug object
window.nodeState = {
    get current() { return state.currentNode; },
    get target() { return state.targetNode; },
    update: null // Will be set in main.js or node-selection.js
};
