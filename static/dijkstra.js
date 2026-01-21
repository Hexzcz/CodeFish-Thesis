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
