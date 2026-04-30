window.appState = {
    map: null,
    scenario: '25yr',
    rainfallMode: 'jaxa',  // 'jaxa' | 'simulation'
    jaxaTab: 'forecast',   // 'forecast' | 'historical'
    forecastRange: 'short', // 'short' | 'medium'
    activeRouteIndex: 0,
    weights: { flood: 0.5, distance: 0.3, road_class: 0.2 },

    // Routing
    originCoords: null,
    originMarker: null,
    placingOrigin: false,
    routePolylines: [],
    routeData: null,
    routesVisible: true,
    routeFocusMode: 'all', // 'selected' | 'all'

    // UI
    rightPanelOpen: false,

    // Layers
    clipEnabled: true,
    config: {
        layers: {
            flood_5yr: { group: 'flood', visible: false, opacity: 0.7, leafletLayer: null },
            flood_25yr: { group: 'flood', visible: false, opacity: 0.7, leafletLayer: null },
            flood_100yr: { group: 'flood', visible: false, opacity: 0.7, leafletLayer: null },
            dist_waterway: { group: 'env', visible: false, opacity: 0.7, leafletLayer: null },
            elevation: { group: 'env', visible: false, opacity: 0.7, leafletLayer: null },
            slope: { group: 'env', visible: false, opacity: 0.7, leafletLayer: null },
            land_cover: { group: 'env', visible: false, opacity: 0.6, leafletLayer: null },
        }
    },
    roadNetworkVisible: false,
    roadLayer: null,
    roadGeoJSON: null,

    centersVisible: true,
    centersLayer: null,
    centersGeoJSON: null,
    boundaryLayer: null,
    boundaryGeoJSON: null,
};
