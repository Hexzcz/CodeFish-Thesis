/**
 * JAXA Rainfall Data Module
 * Handles fetching (or simulating) GSMaP/NEXRA rainfall grid data.
 */

import { state } from './state.js';
import { map } from './map-init.js';

/**
 * Fetches real JAXA rainfall data from the backend.
 */
export async function fetchRainfallData(timeframe = 'now') {
    console.log(`FETCH: Getting REAL JAXA rainfall data for timeframe: ${timeframe}`);

    try {
        const response = await fetch(`/jaxa_rainfall_latest?t=${new Date().getTime()}`);
        const data = await response.json();

        if (data.error) {
            console.warn("Real JAXA data not available, falling back to simulation.");
            return simulateRainfall(timeframe);
        }

        state.rainfallData = data;

        // Pre-process for performance
        state.rainfallGrid = data.features.map(f => {
            const coords = f.geometry.coordinates[0];
            return {
                minLon: coords[0][0],
                maxLon: coords[2][0],
                minLat: coords[0][1],
                maxLat: coords[2][1],
                intensity: f.properties.intensity
            };
        });

        // Log the retrieved statistics
        const intensities = data.features.map(f => f.properties.intensity);
        const maxRain = Math.max(...intensities);
        const avgRain = intensities.reduce((a, b) => a + b, 0) / intensities.length;

        console.log(`REAL RAINFALL DATA LOADED:`, {
            features: data.features.length,
            maxIntensity: maxRain.toFixed(2) + " mm/h",
            avgIntensity: avgRain.toFixed(2) + " mm/h",
            timestamp: data.timestamp,
            rawData: data
        });

        return state.rainfallData;
    } catch (err) {
        console.error("Error fetching real JAXA data:", err);
        return simulateRainfall(timeframe);
    }
}

/**
 * Original simulation logic (kept as fallback)
 */
function simulateRainfall(timeframe) {
    const gridResolution = 0.05;
    const features = [];
    const centers = {
        'now': [{ lat: 14.68, lon: 121.05, intensity: 25 }],
        '1h': [{ lat: 14.70, lon: 121.08, intensity: 40 }],
        '3h': [{ lat: 14.75, lon: 121.12, intensity: 15 }],
        '6h': [{ lat: 14.65, lon: 121.00, intensity: 5 }]
    };

    const activeCenters = centers[timeframe] || centers.now;

    for (let lat = 14.60; lat <= 14.76; lat += gridResolution) {
        for (let lon = 121.00; lon <= 121.16; lon += gridResolution) {
            let intensity = 0;
            activeCenters.forEach(c => {
                const dist = Math.sqrt(Math.pow(lat - c.lat, 2) + Math.pow(lon - c.lon, 2));
                intensity += c.intensity * Math.exp(-dist * 20);
            });
            intensity = Math.max(0, intensity);
            features.push({
                type: 'Feature',
                geometry: {
                    type: 'Polygon',
                    coordinates: [[
                        [lon, lat],
                        [lon + gridResolution, lat],
                        [lon + gridResolution, lat + gridResolution],
                        [lon, lat + gridResolution],
                        [lon, lat]
                    ]]
                },
                properties: { intensity: intensity, timeframe: timeframe }
            });
        }
    }
    state.rainfallData = { type: 'FeatureCollection', features: features };

    // Pre-process simulated grid for performance
    state.rainfallGrid = features.map(f => {
        const coords = f.geometry.coordinates[0];
        return {
            minLon: coords[0][0],
            maxLon: coords[2][0],
            minLat: coords[0][1],
            maxLat: coords[2][1],
            intensity: f.properties.intensity
        };
    });

    return state.rainfallData;
}

/**
 * Updates the rainfall layer on the map
 */
export function updateRainfallOverlay() {
    if (state.rainfallLayer) {
        map.removeLayer(state.rainfallLayer);
    }

    if (!state.showRainfall || !state.rainfallData) return;

    state.rainfallLayer = L.geoJSON(state.rainfallData, {
        style: (feature) => {
            const intensity = feature.properties.intensity;
            let color = 'transparent';

            // Adjust visualization thresholds to be more sensitive to real-world data
            if (intensity > 30) color = '#311b92';      // Extreme
            else if (intensity > 15) color = '#01579b'; // High
            else if (intensity > 5) color = '#03a9f4';  // Medium
            else if (intensity > 0.1) color = '#b3e5fc'; // Low/Light rain (Changed from 1 to 0.1)

            return {
                fillColor: color,
                fillOpacity: color === 'transparent' ? 0 : 0.5,
                color: '#ffffff', // Generic white border for the JAXA grid
                weight: 0.5,      // Always show the grid lines
                opacity: 0.2
            };
        },
        onEachFeature: (feature, layer) => {
            const intensity = feature.properties.intensity.toFixed(2);
            layer.bindTooltip(`JAXA Rain: ${intensity} mm/h`, { sticky: true });
        },
        interactive: true
    }).addTo(map);
}

/**
 * Gets rainfall intensity for a specific coordinate
 */
export function getIntensityAt(lat, lon) {
    if (!state.rainfallGrid) return 0;

    for (let i = 0; i < state.rainfallGrid.length; i++) {
        const cell = state.rainfallGrid[i];
        if (lon >= cell.minLon && lon <= cell.maxLon && lat >= cell.minLat && lat <= cell.maxLat) {
            return cell.intensity;
        }
    }
    return 0;
}
