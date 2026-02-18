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

import { getIntensityAt } from './jaxa-api.js';

/**
 * Calculates the dynamic weight of an edge based on static risk and current rainfall
 */
function getEffectedWeight(neighbor) {
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

    // Find K-shortest paths to ANY of the evacuation sites
    const paths = runYensAlgorithm(startNode, targetNodeIds, adjacencyList, 3);

    return paths.map((p, index) => {
        const siteInfo = evacuationSites.find(s => s.nodeId === p.targetNode);
        return {
            ...p,
            isOptimal: index === 0,
            targetName: siteInfo ? siteInfo.name : "Evacuation Site",
            targetLatlng: siteInfo ? { lat: siteInfo.lat, lng: siteInfo.lng } : null
        };
    });
}
