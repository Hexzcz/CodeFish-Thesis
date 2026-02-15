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
 * Dijkstra's shortest path algorithm
 */
export function runDijkstra(startNode, endNode, adjacencyList) {
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
            const feature = neighbor.feature;

            // Calculate dynamic weight multiplier based on risk and rainfall
            const staticRisk = feature.properties.risk_level || 0;
            const coords = feature.geometry.coordinates;
            const midIdx = Math.floor(coords.length / 2);
            const midPoint = coords[midIdx];
            const rainfallIntensity = getIntensityAt(midPoint[1], midPoint[0]);

            // Weight multiplier logic:
            // Risk 1: +50% cost
            // Risk 2: +200% cost
            // Risk 3: +1000% cost (practically impassable but still possible if no other choice)
            let riskMultiplier = 1.0;
            const combinedRisk = Math.max(staticRisk, rainfallIntensity > 30 ? 3 : (rainfallIntensity > 15 ? 2 : (rainfallIntensity > 5 ? 1 : 0)));

            if (combinedRisk === 1) riskMultiplier = 1.5;
            else if (combinedRisk === 2) riskMultiplier = 3.0;
            else if (combinedRisk === 3) riskMultiplier = 10.0;

            const dynamicWeight = neighbor.weight * riskMultiplier;
            const newDist = distances.get(currentNode) + dynamicWeight;

            if (newDist < distances.get(nextNode)) {
                distances.set(nextNode, newDist);
                previous.set(nextNode, {
                    node: currentNode,
                    feature: neighbor.feature,
                    weight: dynamicWeight
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
        totalDistance: distances.get(endNode),
        actualDistance: pathFeatures.reduce((sum, f) => sum + (f.properties.length || 0), 0)
    };
}

/**
 * Find the path to the nearest reachable evacuation site
 */
export function findNearestEvacuationPath(startNode, evacuationSites, adjacencyList) {
    const distances = new Map();
    const previous = new Map();
    const pq = new PriorityQueue();

    for (let node of adjacencyList.keys()) {
        distances.set(node, Infinity);
        previous.set(node, null);
    }

    distances.set(startNode, 0);
    pq.enqueue(startNode, 0);

    // Keep track of which evacuation site nodes we are looking for
    const targetNodeIds = new Set(evacuationSites.map(s => s.nodeId));
    let bestTargetNode = null;
    let minTargetDist = Infinity;

    while (!pq.isEmpty()) {
        const { element: currentNode, priority: currentDist } = pq.dequeue();

        if (currentDist > distances.get(currentNode)) continue;

        // If this node is an evacuation site and it's better than what we've found
        if (targetNodeIds.has(currentNode)) {
            // In Dijkstra, the first time we encounter a target node, it is the shortest path to IT.
            // But we want the shortest path among ALL target nodes.
            // Actually, because Dijkstra extracts nodes in increasing order of distance,
            // the first target node we DEQUEUE is guaranteed to be the nearest target node.
            bestTargetNode = currentNode;
            minTargetDist = currentDist;
            break;
        }

        const neighbors = adjacencyList.get(currentNode) || [];
        for (let neighbor of neighbors) {
            const nextNode = neighbor.node;
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

            const dynamicWeight = neighbor.weight * riskMultiplier;
            const newDist = currentDist + dynamicWeight;

            if (newDist < distances.get(nextNode)) {
                distances.set(nextNode, newDist);
                previous.set(nextNode, {
                    node: currentNode,
                    feature: neighbor.feature,
                    weight: dynamicWeight
                });
                pq.enqueue(nextNode, newDist);
            }
        }
    }

    if (!bestTargetNode) return null;

    // Reconstruct path to the best target
    const pathFeatures = [];
    const pathNodes = [];
    let current = bestTargetNode;

    while (previous.get(current)) {
        const prev = previous.get(current);
        pathFeatures.unshift(prev.feature);
        pathNodes.unshift(current);
        current = prev.node;
    }
    pathNodes.unshift(startNode);

    const siteInfo = evacuationSites.find(s => s.nodeId === bestTargetNode);

    return {
        features: pathFeatures,
        nodes: pathNodes,
        totalDistance: distances.get(bestTargetNode), // This is the weighted distance
        actualDistance: pathFeatures.reduce((sum, f) => sum + (f.properties.length || 0), 0),
        targetName: siteInfo ? siteInfo.name : "Evacuation Site"
    };
}
