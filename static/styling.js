/**
 * Dynamic Styling Functions Module
 */

import { state } from './state.js';
import { STYLES } from './config.js';

/**
 * Get flood style based on susceptibility value
 */
export function getFloodStyle(feature) {
    const val = feature.properties.Var || 0;

    // Default transparent style for non-flooded areas
    if (val <= 0) {
        return {
            fillColor: 'transparent',
            color: 'transparent',
            weight: 0,
            fillOpacity: 0,
            opacity: 0
        };
    }

    let color = 'grey'; // Fallback
    if (val === 1) color = 'yellow';
    else if (val === 2) color = 'orange';
    else if (val === 3) color = 'red';

    return {
        fillColor: color,
        color: color,
        weight: 1,
        fillOpacity: state.currentFloodOpacity,
        opacity: state.currentFloodOpacity // Ensure stroke also fades
    };
}

import { getIntensityAt } from './jaxa-api.js';

/**
 * Get road risk style based on risk level and rainfall
 */
export function getRoadRiskStyle(feature) {
    const staticRisk = feature.properties.risk_level || 0;

    // Get rainfall intensity for this edge
    let rainfallIntensity = 0;
    if (state.simulationMode) {
        rainfallIntensity = state.manualRainfall;
    } else {
        const coords = feature.geometry.coordinates;
        const midIdx = Math.floor(coords.length / 2);
        const midPoint = coords[midIdx];
        rainfallIntensity = getIntensityAt(midPoint[1], midPoint[0]);
    }

    // Calculate combined risk or rainfall-only risk
    let rainfallRisk = 0;
    if (rainfallIntensity > 30) rainfallRisk = 3;
    else if (rainfallIntensity > 15) rainfallRisk = 2;
    else if (rainfallIntensity > 5) rainfallRisk = 1;

    let color = '#cccccc';
    let weight = 1.5;
    let opacity = 0.7;

    if (state.colorRoadByRainfall) {
        // Pure rainfall coloring
        if (rainfallRisk === 1) { color = '#b3e5fc'; weight = 2.5; opacity = 1; }
        else if (rainfallRisk === 2) { color = '#03a9f4'; weight = 3; opacity = 1; }
        else if (rainfallRisk === 3) { color = '#01579b'; weight = 4; opacity = 1; }
        if (rainfallIntensity > 30) { color = '#311b92'; } // Deep Purple for extreme
    } else {
        // Combined Risk Logic
        const combinedRisk = Math.max(staticRisk, rainfallRisk);

        if (combinedRisk === 1) { color = 'yellow'; weight = 2.5; opacity = 1; }
        if (combinedRisk === 2) { color = 'orange'; weight = 3; opacity = 1; }
        if (combinedRisk === 3) { color = 'red'; weight = 4; opacity = 1; }

        // Special case: if rainfall is high but static risk is low, use blue hints?
        // Let's stick to the combined risk as requested or simple overrides.
        if (rainfallRisk > staticRisk) {
            if (rainfallRisk === 1) color = '#b3e5fc';
            if (rainfallRisk === 2) color = '#01579b';
            if (rainfallRisk === 3) color = '#311b92';
        }
    }

    return {
        color: color,
        weight: weight,
        opacity: opacity
    };
}
