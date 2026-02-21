/**
 * Pathfinding Algorithm Module
 */

/**
 * Priority Queue implementation using a min-heap
 */
export class PriorityQueue {
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

import { state } from './state.js';
import { getIntensityAt } from './jaxa-api.js';

/**
 * Normalizes a value between 0 and 1
 */
function normalize(val, min, max, isCost = true) {
    if (max === min) return 0.5;
    const norm = (val - min) / (max - min);
    return isCost ? norm : (1 - norm);
}

/**
 * Pre-calculates WSM and TOPSIS scores for all edges
 */
export function calculateMCWeights(adjacencyList) {
    const weights = state.mcWeights;
    const manualRainfall = state.manualRainfall;

    // 1. Gather all values for normalization
    let allEdges = [];
    adjacencyList.forEach((neighbors, u) => {
        neighbors.forEach(neighbor => {
            const feature = neighbor.feature;
            const length = feature.properties.length || 1;
            const risk = feature.properties.risk_level || 0;
            const coords = feature.geometry.coordinates;
            const midPoint = coords[Math.floor(coords.length / 2)];
            const rainfall = state.simulationMode ? manualRainfall : getIntensityAt(midPoint[1], midPoint[0]);

            allEdges.push({
                u,
                v: neighbor.node,
                length,
                risk,
                rainfall,
                neighbor
            });
        });
    });

    if (allEdges.length === 0) return;

    const minMax = {
        length: { min: Math.min(...allEdges.map(e => e.length)), max: Math.max(...allEdges.map(e => e.length)) },
        risk: { min: 0, max: 3 },
        rainfall: { min: 0, max: Math.max(10, ...allEdges.map(e => e.rainfall)) }
    };

    // 2. TOPSIS Step 1: Decision Matrix and Normalization
    // We'll calculate WSM and TOPSIS simultaneously

    // TOPSIS: Calculate denominator for vector normalization: sqrt(sum(x^2))
    const denoms = {
        length: Math.sqrt(allEdges.reduce((sum, e) => sum + Math.pow(e.length, 2), 0)),
        risk: Math.sqrt(allEdges.reduce((sum, e) => sum + Math.pow(e.risk, 2), 0)),
        rainfall: Math.sqrt(allEdges.reduce((sum, e) => sum + Math.pow(e.rainfall, 2), 0))
    };

    // TOPSIS: Weight normalized matrix and find PIS/NIS
    // Since all criteria are COSTS (lower is better):
    // PIS (Ideal) = min values
    // NIS (Negative Ideal) = max values

    // For TOPSIS, we need the weighted normalized values first to find PIS/NIS
    const weightedNorms = allEdges.map(e => ({
        length: (e.length / (denoms.length || 1)) * weights.length,
        risk: (e.risk / (denoms.risk || 1)) * weights.risk,
        rainfall: (e.rainfall / (denoms.rainfall || 1)) * weights.rainfall
    }));

    const PIS = {
        length: Math.min(...weightedNorms.map(w => w.length)),
        risk: Math.min(...weightedNorms.map(w => w.risk)),
        rainfall: Math.min(...weightedNorms.map(w => w.rainfall))
    };

    const NIS = {
        length: Math.max(...weightedNorms.map(w => w.length)),
        risk: Math.max(...weightedNorms.map(w => w.risk)),
        rainfall: Math.max(...weightedNorms.map(w => w.rainfall))
    };

    // 3. Final calculation for each edge
    allEdges.forEach((e, i) => {
        // WSM: Weighted Sum of Normalized Values (0-1 scale)
        const nLen = normalize(e.length, minMax.length.min, minMax.length.max);
        const nRisk = normalize(e.risk, minMax.risk.min, minMax.risk.max);
        const nRain = normalize(e.rainfall, minMax.rainfall.min, minMax.rainfall.max);

        const wsmScore = (nLen * weights.length) + (nRisk * weights.risk) + (nRain * weights.rainfall);

        // TOPSIS: Closeness to Ideal
        const w = weightedNorms[i];
        const distPIS = Math.sqrt(
            Math.pow(w.length - PIS.length, 2) +
            Math.pow(w.risk - PIS.risk, 2) +
            Math.pow(w.rainfall - PIS.rainfall, 2)
        );
        const distNIS = Math.sqrt(
            Math.pow(w.length - NIS.length, 2) +
            Math.pow(w.risk - NIS.risk, 2) +
            Math.pow(w.rainfall - NIS.rainfall, 2)
        );

        // Closeness Coefficient: Di- / (Di+ + Di-)
        // Higher is better in TOPSIS (closer to ideal), but we want a STICK/COST for Dijkstra.
        // So we use (1 - CC) or just the distance to PIS? 
        // Let's use 1 - CC as the weight.
        const closeness = (distPIS + distNIS) === 0 ? 0 : distNIS / (distPIS + distNIS);
        const topsisScore = 1 - closeness;

        // Store for breakdown
        const breakdown = {
            length: e.length,
            risk: e.risk,
            rainfall: e.rainfall,
            wsm: wsmScore,
            topsis: closeness
        };

        e.neighbor.mcBreakdown = breakdown;
        e.neighbor.feature.mcBreakdown = breakdown; // Attach to feature for table display

        // The baked weight for Dijkstra will be the combined multi-criteria weight
        // Normalized and scaled by original length to keep it in a reasonable "distance" range
        // This ensures the pathfinding follows the "lowest cost" based on WSM
        e.neighbor.currentBakedWeight = e.length * (1 + wsmScore * 5);
    });
}

/**
 * Calculates the dynamic weight of an edge based on static risk and current rainfall
 */
function getEffectedWeight(neighbor) {
    if (state.simulationMode && neighbor.currentBakedWeight !== undefined) {
        return neighbor.currentBakedWeight;
    }

    const feature = neighbor.feature;
    const staticRisk = feature.properties.risk_level || 0;
    const coords = feature.geometry.coordinates;
    const midIdx = Math.floor(coords.length / 2);
    const midPoint = coords[midIdx];

    const rainfallIntensity = getIntensityAt(midPoint[1], midPoint[0]);

    let riskMultiplier = 1.0;
    const combinedRisk = Math.max(staticRisk, rainfallIntensity > 30 ? 3 : (rainfallIntensity > 15 ? 2 : (rainfallIntensity > 5 ? 1 : 0)));

    if (combinedRisk === 1) riskMultiplier = 1.5;
    else if (combinedRisk === 2) riskMultiplier = 3.0;
    else if (combinedRisk === 3) riskMultiplier = 10.0;

    return neighbor.weight * riskMultiplier;
}

/**
 * Dijkstra's shortest path algorithm
 * Updated to support single target OR multiple target Set
 */
export function runDijkstra(startNode, target, adjacencyList, excludedNodes = new Set(), excludedEdges = new Set()) {
    const distances = new Map();
    const previous = new Map();
    const pq = new PriorityQueue();

    if (excludedNodes.has(startNode)) return null;

    distances.set(startNode, 0);
    pq.enqueue(startNode, 0);

    const isTarget = (node) => {
        if (target instanceof Set) return target.has(node);
        return node === target;
    };

    while (!pq.isEmpty()) {
        const { element: currentNode, priority: currentDist } = pq.dequeue();

        if (currentDist > (distances.get(currentNode) ?? Infinity)) continue;

        // Success condition: reached a target node
        if (isTarget(currentNode)) {
            const pathFeatures = [];
            const finalPathNodes = [];
            let trace = currentNode;

            while (trace !== startNode) {
                finalPathNodes.unshift(trace);
                const p = previous.get(trace);
                if (!p) break;
                pathFeatures.unshift(p.feature);
                trace = p.node;
            }
            finalPathNodes.unshift(startNode);

            return {
                features: pathFeatures,
                nodes: finalPathNodes,
                targetNode: currentNode,
                totalDistance: distances.get(currentNode),
                actualDistance: pathFeatures.reduce((sum, f) => sum + (f.properties.length || 0), 0)
            };
        }

        const neighbors = adjacencyList.get(currentNode);
        if (!neighbors) continue;

        for (let i = 0; i < neighbors.length; i++) {
            const neighbor = neighbors[i];
            const nextNode = neighbor.node;
            if (excludedNodes.has(nextNode)) continue;

            const edgeId = `${currentNode}->${nextNode}`;
            if (excludedEdges.has(edgeId)) continue;

            const weight = neighbor.currentBakedWeight ?? getEffectedWeight(neighbor);
            const newDist = currentDist + weight;

            if (newDist < (distances.get(nextNode) ?? Infinity)) {
                distances.set(nextNode, newDist);
                previous.set(nextNode, {
                    node: currentNode,
                    feature: neighbor.feature,
                    weight: weight
                });
                pq.enqueue(nextNode, newDist);
            }
        }
    }

    return null;
}

/**
 * Yen's algorithm for K-shortest paths
 * Optimized with multi-target support
 */
export function runYensAlgorithm(startNode, target, adjacencyList, K = 3) {
    // Bake weights once
    for (let neighbors of adjacencyList.values()) {
        for (let j = 0; j < neighbors.length; j++) {
            neighbors[j].currentBakedWeight = getEffectedWeight(neighbors[j]);
        }
    }

    const A = []; // The K shortest paths
    const B = new PriorityQueue(); // Potential paths
    const B_hashes = new Set();

    const p0 = runDijkstra(startNode, target, adjacencyList);
    if (!p0) {
        for (let neighbors of adjacencyList.values()) {
            for (let j = 0; j < neighbors.length; j++) delete neighbors[j].currentBakedWeight;
        }
        return [];
    }
    A.push(p0);

    for (let k = 1; k < K; k++) {
        const previousPath = A[k - 1];

        for (let i = 0; i < previousPath.nodes.length - 1; i++) {
            const spurNode = previousPath.nodes[i];
            const rootPathNodes = previousPath.nodes.slice(0, i + 1);
            const rootPathFeatures = previousPath.features.slice(0, i);

            let rootPathWeight = 0;
            for (let j = 0; j < i; j++) {
                const u = previousPath.nodes[j];
                const v = previousPath.nodes[j + 1];
                const edge = adjacencyList.get(u).find(n => n.node === v);
                rootPathWeight += edge.currentBakedWeight;
            }

            const excludedEdges = new Set();
            const excludedNodes = new Set();

            for (let pIdx = 0; pIdx < A.length; pIdx++) {
                const path = A[pIdx];
                if (path.nodes.length > i && rootPathNodes.every((n, idx) => n === path.nodes[idx])) {
                    excludedEdges.add(`${path.nodes[i]}->${path.nodes[i + 1]}`);
                    excludedEdges.add(`${path.nodes[i + 1]}->${path.nodes[i]}`);
                }
            }

            for (let j = 0; j < i; j++) {
                excludedNodes.add(rootPathNodes[j]);
            }

            const spurPath = runDijkstra(spurNode, target, adjacencyList, excludedNodes, excludedEdges);

            if (spurPath) {
                const totalPathNodes = [...rootPathNodes.slice(0, -1), ...spurPath.nodes];
                const totalFeatures = [...rootPathFeatures, ...spurPath.features];
                const totalDist = rootPathWeight + spurPath.totalDistance;

                const pathHash = totalPathNodes.join(',');
                if (!B_hashes.has(pathHash)) {
                    B.enqueue({
                        nodes: totalPathNodes,
                        features: totalFeatures,
                        targetNode: spurPath.targetNode,
                        totalDistance: totalDist,
                        actualDistance: totalFeatures.reduce((sum, f) => sum + (f.properties.length || 0), 0)
                    }, totalDist);
                    B_hashes.add(pathHash);
                }
            }
        }

        if (B.isEmpty()) break;

        let potentialPath;
        while (!B.isEmpty()) {
            const item = B.dequeue();
            const p = item.element;
            const pHash = p.nodes.join(',');
            if (!A.some(existing => existing.nodes.join(',') === pHash)) {
                potentialPath = p;
                break;
            }
        }

        if (!potentialPath) break;
        A.push(potentialPath);
    }

    // Cleanup
    for (let neighbors of adjacencyList.values()) {
        for (let neighbor of neighbors) delete neighbor.currentBakedWeight;
    }

    return A;
}

/**
 * Find the path to the nearest reachable evacuation site
 */
export function findNearestEvacuationPath(startNode, evacuationSites, adjacencyList) {
    const targetNodeIds = new Set(evacuationSites.map(s => s.nodeId));

    // 1. Find 3 paths with lowest total WSM cost
    const rawPaths = runYensAlgorithm(startNode, targetNodeIds, adjacencyList, 3);
    if (!rawPaths || rawPaths.length === 0) return [];

    // 2. Add metadata and path-level metrics for TOPSIS
    const results = rawPaths.map((p) => {
        const siteInfo = evacuationSites.find(s => s.nodeId === p.targetNode);

        // Calculate total raw metrics for the path
        const totalRisk = p.features.reduce((sum, f) => sum + (f.properties.risk_level || 0), 0);
        const totalRainfall = p.features.reduce((sum, f) => {
            const coords = f.geometry.coordinates;
            const mid = coords[Math.floor(coords.length / 2)];
            return sum + getIntensityAt(mid[1], mid[0]);
        }, 0);

        return {
            ...p,
            targetName: siteInfo ? siteInfo.name : "Evacuation Site",
            targetLatlng: siteInfo ? { lat: siteInfo.lat, lng: siteInfo.lng } : null,
            metrics: {
                length: p.actualDistance,
                risk: totalRisk,
                rainfall: totalRainfall
            }
        };
    });

    // 3. Rank the 3 paths using TOPSIS at the path level
    const rankedResults = rankPathsByTOPSIS(results);

    // 4. Set final isOptimal flag and return
    return rankedResults;
}

/**
 * Performs TOPSIS ranking on a set of completed paths
 */
function rankPathsByTOPSIS(paths) {
    if (!paths || paths.length === 0) return [];

    // Reset all paths to non-optimal first
    paths.forEach(p => p.isOptimal = false);

    if (paths.length === 1) {
        paths[0].isOptimal = true;
        paths[0].topsisRankScore = 1.0;
        return paths;
    }

    const weights = state.mcWeights;
    const criteria = ['length', 'risk', 'rainfall'];

    // 1. Vector Normalization
    const denoms = {};
    criteria.forEach(c => {
        const sumSq = paths.reduce((sum, p) => sum + Math.pow(p.metrics[c] || 0, 2), 0);
        denoms[c] = Math.sqrt(sumSq) || 0.0001;
    });

    // 2. Weight Normalized Matrix and PIS/NIS
    const weightedNorms = paths.map(p => {
        const wn = {};
        criteria.forEach(c => {
            wn[c] = ((p.metrics[c] || 0) / denoms[c]) * (weights[c] || 0);
        });
        return wn;
    });

    const PIS = {};
    const NIS = {};
    criteria.forEach(c => {
        const vals = weightedNorms.map(w => w[c]);
        PIS[c] = Math.min(...vals);
        NIS[c] = Math.max(...vals);
    });

    // 3. Closeness Coefficient
    let maxCloseness = -1;
    let winnerIndex = 0;

    paths.forEach((p, i) => {
        const w = weightedNorms[i];
        const dPIS = Math.sqrt(criteria.reduce((sum, c) => sum + Math.pow(w[c] - PIS[c], 2), 0));
        const dNIS = Math.sqrt(criteria.reduce((sum, c) => sum + Math.pow(w[c] - NIS[c], 2), 0));

        const closeness = (dPIS + dNIS) === 0 ? 0 : dNIS / (dPIS + dNIS);
        p.topsisRankScore = closeness;

        if (closeness > maxCloseness) {
            maxCloseness = closeness;
            winnerIndex = i;
        }
    });

    // 4. Mark the official winner
    paths[winnerIndex].isOptimal = true;

    return paths;
}
