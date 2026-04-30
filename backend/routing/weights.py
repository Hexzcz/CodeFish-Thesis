from typing import Dict

HIGHWAY_RANK = {
    'motorway': 1, 'motorway_link': 1,
    'trunk': 2, 'trunk_link': 2,
    'primary': 3, 'primary_link': 3,
    'secondary': 4, 'secondary_link': 4,
    'tertiary': 5, 'tertiary_link': 5,
    'residential': 6,
    'unclassified': 7,
    'service': 8,
    'living_street': 8,
    'pedestrian': 9,
    'footway': 9,
    'path': 9,
}
MAX_RANK = 10.0

def compute_wsm_weight(edge_data: Dict, scenario: str, weights: Dict[str, float], max_edge_length: float = 1000.0) -> float:
    """
    Weighted Sum Model (WSM) for edge cost.
    Cost = w1*norm(flood) + w2*norm(length) + w3*norm(road_class)
    Higher cost = less desirable edge.
    """
    # 1. Flood Probability (0 to 1)
    flood_proba = float(edge_data.get(f'flood_proba_{scenario}', 0.0) or 0.0)
    
    # 2. Road Length (Normalised by max_edge_length)
    length = float(edge_data.get('length', 100.0))
    norm_length = min(length / max_edge_length, 2.0) # Cap significantly long edges
    
    # 3. Road Class (Lower rank = better road = lower cost)
    hw = edge_data.get('highway', 'unclassified')
    if isinstance(hw, list): hw = hw[0]
    rank = HIGHWAY_RANK.get(hw, MAX_RANK)
    norm_rank = rank / MAX_RANK
    
    # WSM Calculation
    wf = weights.get('flood', 0.5)
    wd = weights.get('distance', 0.3)
    wr = weights.get('road_class', 0.2)
    
    # Scaling factor (e.g. 100) to keep costs as meaningful numbers for Dijkstra
    wsm_cost = (wf * flood_proba + wd * norm_length + wr * norm_rank) * 100.0
    
    return max(wsm_cost, 0.01)
