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
let adjacencyList = new Map();
let pathLayer = null;

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
        // Extract unique nodes and build Adjacency List
        const nodes = new Map();
        adjacencyList.clear();

        data.features.forEach(feature => {
            const coords = feature.geometry.coordinates;
            const u = feature.properties.u;
            const v = feature.properties.v;
            const length = feature.properties.length || 1;

            if (coords.length >= 2) {
                const startCoords = coords[0];
                const endCoords = coords[coords.length - 1];

                if (u !== undefined) {
                    nodes.set(u, { id: u, coords: [startCoords[1], startCoords[0]] });
                }
                if (v !== undefined) {
                    nodes.set(v, { id: v, coords: [endCoords[1], endCoords[0]] });
                }
            }

            if (u !== undefined && v !== undefined) {
                if (!adjacencyList.has(u)) adjacencyList.set(u, []);
                if (!adjacencyList.has(v)) adjacencyList.set(v, []);

                adjacencyList.get(u).push({ node: v, weight: length, feature: feature });
                adjacencyList.get(v).push({ node: u, weight: length, feature: feature });
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
                const result = runDijkstra(currentNode, targetNode);
                if (result) {
                    drawPath(result);
                } else {
                    alert("No path found between the selected nodes.");
                }
            } else {
                console.log("Button clicked but nodes not fully selected:", { currentNode, targetNode });
            }
        });
    }

    const clearBtn = document.getElementById('clear-path');
    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            clearSelectionAndPath();
        });
    }
}

function runDijkstra(startNode, endNode) {
    const distances = new Map();
    const previous = new Map();
    const pq = new PriorityQueue();

    // Initialize all nodes
    for (let node of adjacencyList.keys()) {
        distances.set(node, Infinity);
        previous.set(node, null);
    }

    distances.set(startNode, 0);
    pq.enqueue(startNode, 0);

    while (!pq.isEmpty()) {
        const { element: currentNode, priority: currentDist } = pq.dequeue();

        // Skip if we've already found a better path
        if (currentDist > distances.get(currentNode)) continue;

        // Early exit if we reached the target
        if (currentNode === endNode) break;

        const neighbors = adjacencyList.get(currentNode) || [];

        for (let neighbor of neighbors) {
            const nextNode = neighbor.node;
            const edgeWeight = neighbor.weight;
            const newDist = distances.get(currentNode) + edgeWeight;

            if (newDist < distances.get(nextNode)) {
                distances.set(nextNode, newDist);
                previous.set(nextNode, {
                    node: currentNode,
                    feature: neighbor.feature,
                    weight: edgeWeight
                });
                pq.enqueue(nextNode, newDist);
            }
        }
    }

    // Check if path exists
    if (distances.get(endNode) === Infinity) {
        return null;
    }

    // Reconstruct path with proper ordering
    const pathFeatures = [];
    const pathNodes = [];
    let current = endNode;

    while (previous.get(current)) {
        const prev = previous.get(current);
        pathFeatures.unshift(prev.feature); // Add to beginning
        pathNodes.unshift(current);
        current = prev.node;
    }
    pathNodes.unshift(startNode);

    return {
        features: pathFeatures,
        nodes: pathNodes,
        totalDistance: distances.get(endNode)
    };
}


function drawPath(result) {
    if (pathLayer) {
        map.removeLayer(pathLayer);
    }

    const { features, nodes, totalDistance } = result;

    // Build continuous path coordinates
    const pathCoords = [];

    features.forEach((feature, index) => {
        const coords = feature.geometry.coordinates;
        const geometryType = feature.geometry.type;

        if (geometryType === 'LineString') {
            // Determine if we need to reverse the coordinates
            // Check if the line connects properly to previous segment
            const lineCoords = coords.map(c => [c[1], c[0]]);

            if (pathCoords.length > 0) {
                const lastPoint = pathCoords[pathCoords.length - 1];
                const firstPoint = lineCoords[0];
                const lastPoint2 = lineCoords[lineCoords.length - 1];

                // Calculate distances to determine orientation
                const distToFirst = Math.hypot(
                    lastPoint[0] - firstPoint[0],
                    lastPoint[1] - firstPoint[1]
                );
                const distToLast = Math.hypot(
                    lastPoint[0] - lastPoint2[0],
                    lastPoint[1] - lastPoint2[1]
                );

                // If closer to last point, reverse the line
                if (distToLast < distToFirst) {
                    lineCoords.reverse();
                }
            }

            // Add coordinates (skip first if continuing from previous segment)
            const startIdx = pathCoords.length > 0 ? 1 : 0;
            pathCoords.push(...lineCoords.slice(startIdx));

        } else if (geometryType === 'MultiLineString') {
            // Handle MultiLineString (less common in road networks)
            coords.forEach(line => {
                const lineCoords = line.map(c => [c[1], c[0]]);
                const startIdx = pathCoords.length > 0 ? 1 : 0;
                pathCoords.push(...lineCoords.slice(startIdx));
            });
        }
    });

    // Create the path polyline with enhanced styling
    pathLayer = L.polyline(pathCoords, {
        color: '#00D9FF',        // Bright cyan blue
        weight: 6,
        opacity: 0.9,
        lineJoin: 'round',
        lineCap: 'round',
        pane: 'roadPane',
        className: 'path-highlight' // For CSS animations if desired
    }).addTo(map);

    // Add a glow effect with a second, wider line underneath
    const glowLayer = L.polyline(pathCoords, {
        color: '#00D9FF',
        weight: 10,
        opacity: 0.3,
        lineJoin: 'round',
        lineCap: 'round',
        pane: 'roadPane'
    }).addTo(map);

    // Store glow layer for cleanup
    pathLayer._glowLayer = glowLayer;

    // Add markers at start and end with distance info
    if (pathCoords.length > 0) {
        const startMarker = L.circleMarker(pathCoords[0], {
            radius: 8,
            fillColor: '#00ff00',
            color: '#fff',
            weight: 2,
            fillOpacity: 1,
            pane: 'roadPane'
        }).addTo(map);

        const endMarker = L.circleMarker(pathCoords[pathCoords.length - 1], {
            radius: 8,
            fillColor: '#ff0000',
            color: '#fff',
            weight: 2,
            fillOpacity: 1,
            pane: 'roadPane'
        }).addTo(map);

        // Add distance popup
        const distanceKm = (totalDistance / 1000).toFixed(2);
        const distanceM = totalDistance.toFixed(0);

        const popup = L.popup()
            .setLatLng(pathCoords[Math.floor(pathCoords.length / 2)])
            .setContent(`
                <div style="text-align: center;">
                    <strong>Route Found</strong><br>
                    Distance: ${distanceKm} km (${distanceM} m)<br>
                    Segments: ${features.length}
                </div>
            `)
            .openOn(map);

        // Store for cleanup
        pathLayer._startMarker = startMarker;
        pathLayer._endMarker = endMarker;
        pathLayer._popup = popup;
    }

    // Zoom to path with padding
    map.fitBounds(pathLayer.getBounds(), {
        padding: [80, 80],
        maxZoom: 16
    });

    console.log(`Path found: ${totalDistance.toFixed(2)}m over ${features.length} segments`);
}

function clearSelectionAndPath() {
    // Clear node markers
    if (currentNodeMarker) {
        currentNodeMarker.setStyle({
            radius: 4,
            fillColor: '#ffffff',
            weight: 1,
            color: '#000'
        });
    }
    if (targetNodeMarker) {
        targetNodeMarker.setStyle({
            radius: 4,
            fillColor: '#ffffff',
            weight: 1,
            color: '#000'
        });
    }

    // Clear path and associated layers
    if (pathLayer) {
        if (pathLayer._glowLayer) map.removeLayer(pathLayer._glowLayer);
        if (pathLayer._startMarker) map.removeLayer(pathLayer._startMarker);
        if (pathLayer._endMarker) map.removeLayer(pathLayer._endMarker);
        if (pathLayer._popup) map.closePopup(pathLayer._popup);
        map.removeLayer(pathLayer);
        pathLayer = null;
    }

    // Reset state
    currentNode = null;
    targetNode = null;
    currentNodeMarker = null;
    targetNodeMarker = null;

    // Update UI
    document.getElementById('current-node-display').innerText = 'None';
    document.getElementById('target-node-display').innerText = 'None';
    updateSearchButtonState();
}

// Simple Priority Queue implementation for Dijkstra
class PriorityQueue {
    constructor() {
        this.heap = [];
    }

    enqueue(element, priority) {
        this.heap.push({ element, priority });
        this._bubbleUp(this.heap.length - 1);
    }

    dequeue() {
        if (this.isEmpty()) return null;

        const min = this.heap[0];
        const end = this.heap.pop();

        if (this.heap.length > 0) {
            this.heap[0] = end;
            this._bubbleDown(0);
        }

        return min;
    }

    isEmpty() {
        return this.heap.length === 0;
    }

    _bubbleUp(index) {
        const element = this.heap[index];

        while (index > 0) {
            const parentIndex = Math.floor((index - 1) / 2);
            const parent = this.heap[parentIndex];

            if (element.priority >= parent.priority) break;

            this.heap[index] = parent;
            index = parentIndex;
        }

        this.heap[index] = element;
    }

    _bubbleDown(index) {
        const length = this.heap.length;
        const element = this.heap[index];

        while (true) {
            let leftChildIndex = 2 * index + 1;
            let rightChildIndex = 2 * index + 2;
            let swapIndex = null;

            if (leftChildIndex < length) {
                const leftChild = this.heap[leftChildIndex];
                if (leftChild.priority < element.priority) {
                    swapIndex = leftChildIndex;
                }
            }

            if (rightChildIndex < length) {
                const rightChild = this.heap[rightChildIndex];
                if (
                    (swapIndex === null && rightChild.priority < element.priority) ||
                    (swapIndex !== null && rightChild.priority < this.heap[swapIndex].priority)
                ) {
                    swapIndex = rightChildIndex;
                }
            }

            if (swapIndex === null) break;

            this.heap[index] = this.heap[swapIndex];
            index = swapIndex;
        }

        this.heap[index] = element;
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
    if (pathLayer) {
        map.removeLayer(pathLayer);
        pathLayer = null;
    }
    updateSearchButtonState();
});

document.getElementById('clear-target').addEventListener('click', () => {
    if (targetNodeMarker) {
        targetNodeMarker.setStyle({ radius: 4, fillColor: '#ffffff', weight: 1, color: '#000' });
    }
    targetNode = null;
    targetNodeMarker = null;
    document.getElementById('target-node-display').innerText = 'None';
    if (pathLayer) {
        map.removeLayer(pathLayer);
        pathLayer = null;
    }
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
