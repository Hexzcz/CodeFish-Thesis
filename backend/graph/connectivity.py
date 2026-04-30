from typing import Set, List
from backend.graph.builder import Graph

def _get_connected_component(graph: Graph, start_node) -> Set:
    """BFS from start_node. Returns set of reachable node IDs."""
    visited: Set = set()
    queue = [start_node]
    while queue:
        node = queue.pop(0)
        if node in visited:
            continue
        visited.add(node)
        for neighbor, _ in graph.get_neighbors(node):
            if neighbor not in visited:
                queue.append(neighbor)
    return visited

def ensure_connected(graph: Graph) -> Graph:
    """Find and keep only the largest connected component in graph."""
    all_nodes = set(graph.nodes.keys())
    if not all_nodes:
        return graph
    
    visited_global: Set = set()
    components: List[Set] = []
    
    for node in all_nodes:
        if node not in visited_global:
            comp = _get_connected_component(graph, node)
            components.append(comp)
            visited_global.update(comp)
    
    if not components:
        graph.main_component = all_nodes
        return graph
        
    largest = max(components, key=len)
    total = len(all_nodes)
    
    if len(components) > 1:
        # Remove nodes not in largest component
        nodes_to_remove = [n for n in list(graph.nodes.keys()) if n not in largest]
        for node in nodes_to_remove:
            del graph.nodes[node]
            if node in graph.adj:
                del graph.adj[node]
        
        # Purge stale adjacency entries pointing to removed nodes
        for node in graph.adj:
            graph.adj[node] = [
                (nb, ed) for nb, ed in graph.adj[node]
                if nb in largest
            ]
        
        # Purge stale edge entries
        graph.edges = {
            (u, v): ed
            for (u, v), ed in graph.edges.items()
            if u in largest and v in largest
        }
    
    graph.main_component = largest
    return graph
