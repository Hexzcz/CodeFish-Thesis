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

/**
 * Get road risk style based on risk level
 */
export function getRoadRiskStyle(feature) {
    const risk = feature.properties.risk_level || 0;
    let color = '#ffffff'; // Default safe/no data
    let weight = 1.0;
    let opacity = 0.5;

    if (risk === 1) { color = 'yellow'; weight = 2; opacity = 1; }
    else if (risk === 2) { color = 'orange'; weight = 2; opacity = 1; }
    else if (risk === 3) { color = 'red'; weight = 2; opacity = 1; }

    // If we want "safe" roads to be less prominent when risk mode is on
    if (risk === 0) { color = '#cccccc'; weight = 1.5; opacity = 0.7; }

    return {
        color: color,
        weight: weight,
        opacity: opacity
    };
}
