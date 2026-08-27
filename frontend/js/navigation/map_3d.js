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
// District 1 has about 20 m of relief across 7 km. Exaggeration is what makes
// any of it readable, but too much warps the streets draped over it into
// something that looks melted — this is the compromise.
const TERRAIN_EXAGGERATION = 1.5;
// If the first render has not happened by now, something in this environment
// will not run it — a browser without usable WebGL, or a page that is still
// hidden (background tabs suspend the animation frames MapLibre needs).
// Navigation must not hang waiting for a map that is never coming.
const MAP_LOAD_TIMEOUT_MS = 15000;
const MAPLIBRE_JS = 'vendor/maplibre/maplibre-gl.js';
const MAPLIBRE_CSS = 'vendor/maplibre/maplibre-gl.css';

let map3d = null;
let libraryPromise = null;
let destinationMarker = null;

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
            // Which provider, and why, is documented on BASEMAP_3D in
            // config.js. The 2D map's Esri basemap is not reused here because
            // it has no tiles above zoom 16, and navigation happens at 17.5.
            basemap: {
                type: 'raster',
                tiles: BASEMAP_3D.tiles,
                tileSize: BASEMAP_3D.tileSize,
                maxzoom: BASEMAP_3D.maxzoom,
                attribution: BASEMAP_3D.attribution,
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
            // Muted to sit under a dark interface rather than fight it.
            { id: 'basemap', type: 'raster', source: 'basemap', paint: BASEMAP_3D.paint },
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
        // Keep whatever the map complained about first: a style that fails to
        // validate never fires `load`, and without this the only symptom is a
        // black rectangle fifteen seconds later.
        let firstError = null;

        const timer = setTimeout(() => {
            reject(new Error(firstError
                ? `The 3D view could not start: ${firstError}`
                : 'The 3D view could not start on this device.'));
        }, MAP_LOAD_TIMEOUT_MS);

        map3d.on('load', () => {
            clearTimeout(timer);
            resolve();
        });

        map3d.on('error', (e) => {
            const message = (e && e.error && e.error.message) || 'unknown map error';
            console.warn('[3d]', message);
            if (!firstError) firstError = message;

            // A missing tile is routine — flat ground, or a gap in the
            // basemap. A broken style or a dead WebGL context is not, and
            // waiting out the timeout for those helps nobody.
            if (/webgl|context lost|style|glyphs|sprite/i.test(message)) {
                clearTimeout(timer);
                reject(new Error(`The 3D view could not start: ${message}`));
            }
        });
    }).catch((e) => {
        destroy3DMap();
        throw e;
    });

    map3d.setTerrain({ source: 'terrain', exaggeration: TERRAIN_EXAGGERATION });

    // No compass widget: it lands on top of the 2D/3D switch, and this view
    // already has the controls a resident needs. Dragging still rotates the
    // map, and "Recenter on me" puts it back.

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
        }] : [],
    });

    if (end) _placeDestinationLabel(end, destinationName || 'Evacuation center');
}

/**
 * The destination's name, as an HTML marker.
 *
 * MapLibre's own text layers need a `glyphs` font source — a URL serving PBF
 * font ranges. Hosting one would add assets for a single label, and pointing
 * at someone else's would break the offline promise. A DOM marker needs
 * neither.
 */
function _placeDestinationLabel(coordinates, name) {
    if (destinationMarker) destinationMarker.remove();

    const element = document.createElement('div');
    element.className = 'nav-destination-marker';
    element.textContent = name;

    destinationMarker = new window.maplibregl.Marker({ element, anchor: 'bottom', offset: [0, -14] })
        .setLngLat(coordinates)
        .addTo(map3d);
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

/**
 * Frame the whole route in the 3D view.
 *
 * Switching to 3D outside navigation should show the walk that was planned,
 * not drop the camera on its first metre. Padding keeps the line clear of the
 * answer sheet, which covers the lower half of a phone screen.
 */
function frame3DRoute(routeFeature) {
    if (!map3d) return;

    const coordinates = _flatCoordinates(routeFeature);
    if (coordinates.length < 2) return;

    const bounds = coordinates.reduce(
        (box, coord) => box.extend(coord),
        new window.maplibregl.LngLatBounds(coordinates[0], coordinates[0])
    );

    const panel = document.getElementById('simple-shell');
    const size = map3d.getContainer().getBoundingClientRect();
    const sheetAtBottom = panel && panel.getBoundingClientRect().width >= size.width * 0.9;
    const rect = panel ? panel.getBoundingClientRect() : null;

    map3d.fitBounds(bounds, {
        padding: sheetAtBottom
            ? { top: 60, bottom: Math.min(size.height - rect.top + 20, size.height * 0.55), left: 40, right: 40 }
            : { top: 60, bottom: 60, left: rect ? Math.min(rect.right + 24, size.width * 0.45) : 60, right: 60 },
        pitch: NAV_PITCH,
        maxZoom: 17,
        duration: 0,
    });
}

function _flatCoordinates(routeFeature) {
    return ((routeFeature.geometry || {}).coordinates || []).flat();
}

function _emptyCollection() {
    return { type: 'FeatureCollection', features: [] };
}

function destroy3DMap() {
    if (destinationMarker) {
        destinationMarker.remove();
        destinationMarker = null;
    }
    if (!map3d) return;
    map3d.remove();
    map3d = null;
}
