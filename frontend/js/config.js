const API_BASE = window.location.origin;

const ROUTE_COLORS_CSS = ['--route-1', '--route-2', '--route-3'];
const ROUTE_COLORS_HEX = ['#29b6f6', '#ce93d8', '#f06292'];

/**
 * The basemap under the 3D navigation view.
 *
 * Requirements, learned the hard way: it must have tiles at walking zoom
 * (~17.5), it must send CORS headers because MapLibre loads tiles into WebGL,
 * and it must not need an API key — Carto now watermarks keyless tiles with
 * "API KEY REQUIRED" straight across the map, and Esri's dark canvas simply
 * stops at zoom 16 and returns "Map data not yet available".
 *
 * OpenStreetMap's own tiles satisfy all three, and the paint below mutes them
 * to match the app rather than shipping a bright map inside a dark one.
 *
 * Before deploying this publicly, read OSM's tile usage policy: their servers
 * are for light use, and distributing an app on them is not that. Swapping to
 * a keyed provider (MapTiler, Carto, Stadia) is a change to this object and
 * nothing else.
 */
const BASEMAP_3D = {
    tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
    tileSize: 256,
    maxzoom: 19,
    attribution: '&copy; OpenStreetMap contributors',
    paint: {
        'raster-saturation': -0.9,
        'raster-brightness-max': 0.38,
        'raster-contrast': 0.15,
    },
};

const SCENARIOS = ['5yr', '25yr', '100yr'];
const K_ROUTES = 3;

function getRiskColor(flood_proba) {
    if (flood_proba < 0.10) return 'var(--safe)';
    if (flood_proba < 0.25) return 'var(--low)';
    if (flood_proba < 0.45) return 'var(--moderate)';
    if (flood_proba < 0.65) return 'var(--high)';
    return 'var(--critical)';
}

function getRiskColorHex(flood_proba) {
    if (flood_proba < 0.10) return '#4caf7d';
    if (flood_proba < 0.25) return '#8bc34a';
    if (flood_proba < 0.45) return '#ffc107';
    if (flood_proba < 0.65) return '#ff7043';
    return '#e53935';
}

function getRiskLabel(flood_proba) {
    if (flood_proba < 0.10) return 'Safe';
    if (flood_proba < 0.25) return 'Low';
    if (flood_proba < 0.45) return 'Moderate';
    if (flood_proba < 0.65) return 'High';
    return 'Critical';
}


/**
 * One colour for a whole route, from its overall flood risk.
 *
 * The resident's view draws each route in a single colour: a line that changes
 * colour every fifty metres is a patchwork, and the thing a person needs from
 * the map is which route is the safe one, not which individual road is wet.
 * The per-road colouring survives in the console, where it is the evidence.
 *
 * The banding comes from routeVerdict() so the line and the sentence beside it
 * can never disagree — green next to "this route crosses flood-prone roads"
 * would be worse than no colour at all.
 */
function getRouteColorHex(props) {
    const level = (typeof routeVerdict === 'function')
        ? routeVerdict(props || {}).level
        : 'safe';

    return {
        safe: '#4caf7d',   // avoids flood-prone roads
        some: '#ffc107',   // some roads on it may flood
        high: '#e53935',   // crosses flood-prone roads
    }[level] || '#4caf7d';
}
