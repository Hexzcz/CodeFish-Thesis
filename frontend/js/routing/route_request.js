/**
 * Asking the backend for routes.
 *
 * One function, both views: the admin sidebar and the simple flow differ in
 * what they show, not in what they ask for. Errors arrive as the sentence the
 * server sent — "your pin is 811 m from the nearest road" is worth reading.
 */

const DEFAULT_ROUTE_COUNT = 3;

async function requestRoutes({ lat, lon, scenario, k, weights, penaltyFactor }) {
    const res = await fetch('/route', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            origin_lat: lat,
            origin_lon: lon,
            scenario: scenario || '25yr',
            k: k || DEFAULT_ROUTE_COUNT,
            weights: weights,
            penalty_factor: penaltyFactor,
        }),
    });

    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
    return data;
}
