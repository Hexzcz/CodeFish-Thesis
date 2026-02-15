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

    // Get rainfall intensity for this edge (average of start and end nodes)
    const coords = feature.geometry.coordinates;
    const midIdx = Math.floor(coords.length / 2);
    const midPoint = coords[midIdx];
    const rainfallIntensity = getIntensityAt(midPoint[1], midPoint[0]);

    // Calculate combined risk
    // Rainfall categories (roughly): 1-5 (Low), 5-15 (Med), 15-30 (High), >30 (Extreme)
    let rainfallRisk = 0;
    if (rainfallIntensity > 30) rainfallRisk = 3;
    else if (rainfallIntensity > 15) rainfallRisk = 2;
    else if (rainfallIntensity > 5) rainfallRisk = 1;

    const combinedRisk = Math.max(staticRisk, rainfallRisk);

    let color = '#ffffff';
    let weight = 1.0;
    let opacity = 0.5;

    if (combinedRisk === 1) { color = '#b3e5fc'; weight = 2.5; opacity = 1; } // Rainfall light blue
    if (staticRisk === 1) { color = 'yellow'; }

    if (combinedRisk === 2) { color = '#01579b'; weight = 3; opacity = 1; } // Rainfall dark blue
    if (staticRisk === 2) { color = 'orange'; }

    if (combinedRisk === 3) { color = '#311b92'; weight = 4; opacity = 1; } // Rainfall deep purple
    if (staticRisk === 3) { color = 'red'; }

    // If no risk, subtle road
    if (combinedRisk === 0) { color = '#cccccc'; weight = 1.5; opacity = 0.7; }

    return {
        color: color,
        weight: weight,
        opacity: opacity
    };
}
