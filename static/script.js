// Initialize Map
const map = L.map('map').setView([14.65, 121.08], 12);

// Add Base Layer (Dark Matter for better contrast)
const tiles = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 20
}).addTo(map);

// Layers
let floodLayer = null;
let boundaryLayer = null;


// Style for Boundary
const boundaryStyle = {
    fillColor: 'transparent',
    color: '#00ffcc', // Cyan neon border
    weight: 2,
    dashArray: '5, 5',
    fillOpacity: 0
};

// Style for Roads (White and Thicker)
const roadStyle = {
    color: '#ffffff',
    weight: 1.5, // Thicker
    opacity: 0.8
};

// Global opacity variable for flood layer
let currentFloodOpacity = 0.6;

// Style for Flood Polygons
// Style for Flood Polygons
function getFloodStyle(feature) {
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
        fillOpacity: currentFloodOpacity,
        opacity: currentFloodOpacity // Ensure stroke also fades
    };
}

// Fetch and Add Flood Data
fetch('/flood_clipped.geojson?t=' + new Date().getTime())
    .then(response => response.json())
    .then(data => {
        floodLayer = L.geoJSON(data, {
            style: getFloodStyle,
            onEachFeature: function (feature, layer) {
                if (feature.properties && feature.properties.Var) {
                    layer.bindTooltip(`Flood Level: ${feature.properties.Var}`);
                }
            }
        }).addTo(map);
    })
    .catch(err => console.error("Error loading flood data:", err));

// Fetch and Add Boundary Data
fetch('/qc_boundary.geojson?t=' + new Date().getTime())
    .then(response => response.json())
    .then(data => {
        boundaryLayer = L.geoJSON(data, {
            style: boundaryStyle
        }).addTo(map);
    })
    .catch(err => console.error("Error loading boundary data:", err));

// Style for Project 8 Boundary (Different color to distinguish from QC)
const project8BoundaryStyle = {
    fillColor: 'transparent',
    color: '#ff9500', // Orange neon border
    weight: 3,
    dashArray: '10, 5',
    fillOpacity: 0
};

// Fetch and Add Project 8 Boundary Data
let project8BoundaryLayer = null;
fetch('/project8_boundary.geojson?t=' + new Date().getTime())
    .then(response => response.json())
    .then(data => {
        project8BoundaryLayer = L.geoJSON(data, {
            style: project8BoundaryStyle
        });
        // Don't add to map by default (checkbox is unchecked)
    })
    .catch(err => console.error("Error loading Project 8 boundary data:", err));

// Node Selection State
let currentNode = null;
let targetNode = null;
let currentNodeMarker = null;
let targetNodeMarker = null;
let project8NodeLayer = null;

// Expose to window for debugging
window.nodeState = {
    get current() { return currentNode; },
    get target() { return targetNode; },
    update: updateSearchButtonState
};

// Create a custom pane for roads and nodes to ensure they stay on top of flood polygons
map.createPane('roadPane');
map.getPane('roadPane').style.zIndex = 650;

// Fetch Project 8 Road Data (Filtered to Project 8 area only)
let project8RoadLayer = null;
fetch('/project8_roads.geojson?t=' + new Date().getTime())
    .then(response => response.json())
    .then(data => {
        // Extract unique nodes
        const nodes = new Map();
        data.features.forEach(feature => {
            const coords = feature.geometry.coordinates;
            // LineStrings should have at least 2 points
            if (coords.length >= 2) {
                const startCoords = coords[0];
                const endCoords = coords[coords.length - 1];

                if (feature.properties.u !== undefined) {
                    nodes.set(feature.properties.u, { id: feature.properties.u, coords: [startCoords[1], startCoords[0]] });
                }
                if (feature.properties.v !== undefined) {
                    nodes.set(feature.properties.v, { id: feature.properties.v, coords: [endCoords[1], endCoords[0]] });
                }
            }
        });

        // Create Roads Layer
        project8RoadLayer = L.geoJSON(data, {
            pane: 'roadPane',
            interactive: true,
            style: roadStyle,
            onEachFeature: function (feature, layer) {
                const length = feature.properties.length ? feature.properties.length.toFixed(2) : 'N/A';
                layer.bindTooltip(`Road: ${feature.properties.name || 'Unnamed'}<br>Length: ${length}m`, { sticky: true });

                layer.on({
                    mouseover: function (e) {
                        const l = e.target;
                        l.setStyle({ weight: 4, color: '#4facfe', opacity: 1 });
                        l.bringToFront();
                    },
                    mouseout: function (e) {
                        const l = e.target;
                        if (document.getElementById('toggle-road-risk').checked) {
                            l.setStyle(getRoadRiskStyle(feature));
                        } else {
                            l.setStyle(roadStyle);
                        }
                    }
                });
            }
        });

        // Create Nodes Layer
        const nodeFeatures = Array.from(nodes.values()).map(node => ({
            type: 'Feature',
            geometry: { type: 'Point', coordinates: [node.coords[1], node.coords[0]] },
            properties: { id: node.id }
        }));

        project8NodeLayer = L.geoJSON(nodeFeatures, {
            pane: 'roadPane',
            interactive: true,
            pointToLayer: function (feature, latlng) {
                return L.circleMarker(latlng, {
                    radius: 4,
                    fillColor: "#ffffff",
                    color: "#000",
                    weight: 1,
                    opacity: 1,
                    fillOpacity: 0.8
                });
            },
            onEachFeature: function (feature, layer) {
                layer.bindTooltip(`Node ID: ${feature.properties.id}`);
                layer.on({
                    mouseover: function (e) {
                        e.target.setStyle({ radius: 7, fillColor: '#4facfe' });
                    },
                    mouseout: function (e) {
                        const id = feature.properties.id;
                        if (currentNode !== id && targetNode !== id) {
                            e.target.setStyle({ radius: 4, fillColor: '#ffffff' });
                        }
                    },
                    click: function (e) {
                        L.DomEvent.stopPropagation(e); // Prevent map click if any
                        handleNodeClick(feature.properties.id, layer);
                    }
                });
            }
        });

        // Check if toggle was already checked before data arrived
        if (document.getElementById('toggle-roads').checked) {
            project8RoadLayer.addTo(map);
            project8NodeLayer.addTo(map);
        }
        updateSearchButtonState();
    })
    .catch(err => console.error("Error loading Project 8 road data:", err));

function handleNodeClick(nodeId, layer) {
    if (!currentNode) {
        // Set as Current
        currentNode = nodeId;
        currentNodeMarker = layer;
        layer.setStyle({ radius: 8, fillColor: '#00ff00', weight: 2, color: '#fff' });
        document.getElementById('current-node-display').innerText = nodeId;
    } else if (!targetNode && nodeId !== currentNode) {
        // Set as Target
        targetNode = nodeId;
        targetNodeMarker = layer;
        layer.setStyle({ radius: 8, fillColor: '#ff0000', weight: 2, color: '#fff' });
        document.getElementById('target-node-display').innerText = nodeId;
    } else {
        // If both exist or clicking same as current, maybe do nothing or allow replacement logic
        // For simplicity: If clicking a NEW node when both exist, maybe reset?
        // User said: "1 must exist each at a time"
        console.log("Both nodes already set. Clear them first to change selection.");
    }
    console.log("Calling updateSearchButtonState from handleNodeClick");
    updateSearchButtonState();
}

function updateSearchButtonState() {
    const btn = document.getElementById('find-path');
    console.log("Updating button state:", { currentNode, targetNode });
    if (currentNode && targetNode) {
        btn.disabled = false;
        btn.style.pointerEvents = 'auto';
        btn.style.opacity = '1';
        console.log("Button should be enabled now");
    } else {
        btn.disabled = true;
        btn.style.pointerEvents = 'none';
        btn.style.opacity = '0.6';
        console.log("Button should be disabled now");
    }
}

// Search Button Action
function initSearchButton() {
    const btn = document.getElementById('find-path');
    if (btn) {
        btn.addEventListener('click', () => {
            console.log("Button clicked event fired");
            if (currentNode && targetNode) {
                console.log(`ACTION: Finding path from Node ${currentNode} to Node ${targetNode}...`);
            } else {
                console.log("Button clicked but nodes not fully selected:", { currentNode, targetNode });
            }
        });
    }
}
initSearchButton();

// Clear Buttons Logic
document.getElementById('clear-current').addEventListener('click', () => {
    if (currentNodeMarker) {
        currentNodeMarker.setStyle({ radius: 4, fillColor: '#ffffff', weight: 1, color: '#000' });
    }
    currentNode = null;
    currentNodeMarker = null;
    document.getElementById('current-node-display').innerText = 'None';
    updateSearchButtonState();
});

document.getElementById('clear-target').addEventListener('click', () => {
    if (targetNodeMarker) {
        targetNodeMarker.setStyle({ radius: 4, fillColor: '#ffffff', weight: 1, color: '#000' });
    }
    targetNode = null;
    targetNodeMarker = null;
    document.getElementById('target-node-display').innerText = 'None';
    updateSearchButtonState();
});


// QC-wide road network removed - only Project 8 roads are used

// Toggle Logic
document.getElementById('toggle-flood').addEventListener('change', function (e) {
    if (floodLayer) {
        if (e.target.checked) {
            map.addLayer(floodLayer);
        } else {
            map.removeLayer(floodLayer);
        }
    }
});

document.getElementById('toggle-boundary').addEventListener('change', function (e) {
    if (boundaryLayer) {
        if (e.target.checked) {
            map.addLayer(boundaryLayer);
        } else {
            map.removeLayer(boundaryLayer);
        }
    }
});

document.getElementById('toggle-project8-boundary').addEventListener('change', function (e) {
    if (project8BoundaryLayer) {
        if (e.target.checked) {
            map.addLayer(project8BoundaryLayer);
        } else {
            map.removeLayer(project8BoundaryLayer);
        }
    }
});

document.getElementById('toggle-roads').addEventListener('change', function (e) {
    // Use Project 8 roads (filtered to the three barangays) instead of full QC roads
    if (project8RoadLayer && project8NodeLayer) {
        if (e.target.checked) {
            map.addLayer(project8RoadLayer);
            map.addLayer(project8NodeLayer);
        } else {
            map.removeLayer(project8RoadLayer);
            map.removeLayer(project8NodeLayer);
        }
    }
});

// Opacity Slider Logic
document.getElementById('flood-opacity').addEventListener('input', function (e) {
    currentFloodOpacity = parseFloat(e.target.value);
    if (floodLayer) {
        floodLayer.setStyle(getFloodStyle);
    }
});

// Road Risk Coloring Logic
function getRoadRiskStyle(feature) {
    const risk = feature.properties.risk_level || 0;
    let color = '#ffffff'; // Default safe/no data
    let weight = 1.0;
    let opacity = 0.5;

    if (risk === 1) { color = 'yellow'; weight = 2; opacity = 1; }
    else if (risk === 2) { color = 'orange'; weight = 2; opacity = 1; }
    else if (risk === 3) { color = 'red'; weight = 2; opacity = 1; }

    // If we want "safe" roads to be less prominent when risk mode is on
    // Use a lighter grey so it is still visible against the dark map
    if (risk === 0) { color = '#cccccc'; weight = 1.5; opacity = 0.7; }

    return {
        color: color,
        weight: weight,
        opacity: opacity
    };
}

document.getElementById('toggle-road-risk').addEventListener('change', function (e) {
    if (project8RoadLayer) {
        if (e.target.checked) {
            // Apply Risk Style
            project8RoadLayer.setStyle(getRoadRiskStyle);
        } else {
            // Revert to Standard Style
            project8RoadLayer.setStyle(roadStyle);
        }
    }
});
