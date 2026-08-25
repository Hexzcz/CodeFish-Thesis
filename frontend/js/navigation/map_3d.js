/**
 * The 3D navigation map.
 *
 * Leaflet cannot tilt or rotate, so the 3D view is a second map — MapLibre GL
 * — created only when someone switches to it, over the same Esri basemap the
 * 2D map uses and the same route GeoJSON the router returned. The 2D map is
 * left exactly as it was: switching hides one and shows the other, and the
 * app's state lives in neither.
 *
 * Terrain comes from CodeFish's own DEM through /tiles/terrain-rgb, so the 3D
 * view needs no API key and no vector-tile provider. District 1 rises about
 * 20 m across 7 km, so the exaggeration below is what makes any of it visible;
 * the point of this view is the tilted heading-up camera, not the hills.
 */

const NAV_PITCH = 60;
const NAV_ZOOM = 17.5;
const TERRAIN_EXAGGERATION = 3;
// If the first render has not happened by now, something in this environment
// will not run it — a browser without usable WebGL, or a page that is still
// hidden (background tabs suspend the animation frames MapLibre needs).
// Navigation must not hang waiting for a map that is never coming.
const MAP_LOAD_TIMEOUT_MS = 15000;
const MAPLIBRE_JS = 'vendor/maplibre/maplibre-gl.js';
const MAPLIBRE_CSS = 'vendor/maplibre/maplibre-gl.css';

let map3d = null;
let libraryPromise = null;

/** Load MapLibre on first use, so the 2D view never pays for it. */
function loadMapLibre() {
    if (window.maplibregl) return Promise.resolve(window.maplibregl);
    if (libraryPromise) return libraryPromise;

    libraryPromise = new Promise((resolve, reject) => {
        const css = document.createElement('link');
        css.rel = 'stylesheet';
        css.href = MAPLIBRE_CSS;
        document.head.appendChild(css);

        const script = document.createElement('script');
        script.src = MAPLIBRE_JS;
        script.onload = () => resolve(window.maplibregl);
        script.onerror = () => reject(new Error('The 3D map could not be loaded.'));
        document.head.appendChild(script);
    });
    return libraryPromise;
}

function navigationStyle() {
    return {
        version: 8,
        sources: {
            basemap: {
                type: 'raster',
                tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}'],
                tileSize: 256,
                maxzoom: 16,
                attribution: 'Tiles &copy; Esri',
            },
            terrain: {
                type: 'raster-dem',
                tiles: [`${API_BASE}/tiles/terrain-rgb/{z}/{x}/{y}.png`],
                tileSize: 256,
                maxzoom: 15,
                // Mapbox Terrain-RGB packing, which is what the backend writes.
                encoding: 'mapbox',
            },
            route: { type: 'geojson', data: _emptyCollection() },
            destination: { type: 'geojson', data: _emptyCollection() },
        },
        layers: [
            { id: 'basemap', type: 'raster', source: 'basemap' },
            {
                id: 'route-casing',
                type: 'line',
                source: 'route',
                layout: { 'line-join': 'round', 'line-cap': 'round' },
                paint: { 'line-color': '#000000', 'line-opacity': 0.5, 'line-width': 14 },
            },
            {
                id: 'route-line',
                type: 'line',
                source: 'route',
                layout: { 'line-join': 'round', 'line-cap': 'round' },
                // Each segment carries the colour the flood model gave it, so
                // the 3D view shows the same risk the 2D view does.
                paint: { 'line-color': ['get', 'color'], 'line-width': 8 },
            },
            {
                id: 'destination-halo',
                type: 'circle',
                source: 'destination',
                paint: {
                    'circle-radius': 18,
                    'circle-color': '#4caf7d',
                    'circle-opacity': 0.25,
                    'circle-stroke-width': 2,
                    'circle-stroke-color': '#4caf7d',
                },
            },
            {
                id: 'destination-label',
                type: 'symbol',
                source: 'destination',
                layout: {
                    'text-field': ['get', 'name'],
                    'text-size': 13,
                    'text-offset': [0, -2.2],
                    'text-anchor': 'bottom',
                    'text-allow-overlap': true,
                },
                paint: { 'text-color': '#ffffff', 'text-halo-color': '#000000', 'text-halo-width': 1.6 },
            },
        ],
    };
}

async function ensure3DMap() {
    if (map3d) return map3d;

    const maplibregl = await loadMapLibre();
    map3d = new maplibregl.Map({
        container: 'map-3d',
        style: navigationStyle(),
        center: [121.02, 14.645],
        zoom: NAV_ZOOM,
        pitch: NAV_PITCH,
        bearing: 0,
        attributionControl: { compact: true },
    });

    await new Promise((resolve, reject) => {
        const timer = setTimeout(() => {
            reject(new Error('The 3D view could not start on this device.'));
        }, MAP_LOAD_TIMEOUT_MS);

        map3d.on('load', () => {
            clearTimeout(timer);
            resolve();
        });
        map3d.on('error', (e) => {
            // Tile errors are routine (a missing terrain tile is just flat
            // ground); only a failure to build the map itself is fatal.
            if (e && e.error && /webgl|context/i.test(e.error.message || '')) {
                clearTimeout(timer);
                reject(new Error('This device cannot show the 3D view.'));
            }
        });
    }).catch((e) => {
        destroy3DMap();
        throw e;
    });

    map3d.setTerrain({ source: 'terrain', exaggeration: TERRAIN_EXAGGERATION });
    map3d.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');

    // A dragged map should stop chasing the walker until they ask again.
    map3d.on('dragstart', () => document.dispatchEvent(new CustomEvent('codefish:map-dragged')));
    return map3d;
}

function get3DMap() {
    return map3d;
}

/** Put the chosen route and its destination on the 3D map. */
function show3DRoute(routeFeature, destinationName) {
    if (!map3d) return;

    const segments = _segmentFeatures(routeFeature);
    map3d.getSource('route').setData({ type: 'FeatureCollection', features: segments });

    const coordinates = _flatCoordinates(routeFeature);
    const end = coordinates[coordinates.length - 1];
    map3d.getSource('destination').setData({
        type: 'FeatureCollection',
        features: end ? [{
            type: 'Feature',
            geometry: { type: 'Point', coordinates: end },
            properties: { name: destinationName || 'Evacuation center' },
        }] : [],
    });
}

/**
 * Split the route into one feature per drawn segment so each keeps its own
 * flood colour, matching the 2D view rather than inventing a second scheme.
 */
function _segmentFeatures(routeFeature) {
    const lines = (routeFeature.geometry || {}).coordinates || [];
    const segments = (routeFeature.properties || {}).segments || [];

    return lines.map((line, index) => ({
        type: 'Feature',
        geometry: { type: 'LineString', coordinates: line },
        properties: {
            color: getRiskColorHex(segments[index] ? segments[index].flood_proba : 0),
        },
    })).filter(f => f.geometry.coordinates.length > 1);
}

function _flatCoordinates(routeFeature) {
    return ((routeFeature.geometry || {}).coordinates || []).flat();
}

function _emptyCollection() {
    return { type: 'FeatureCollection', features: [] };
}

function destroy3DMap() {
    if (!map3d) return;
    map3d.remove();
    map3d = null;
}
