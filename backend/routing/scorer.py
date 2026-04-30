import numpy as np
from typing import List, Dict
from backend.graph.builder import Graph
from backend.routing.weights import compute_wsm_weight, HIGHWAY_RANK, MAX_RANK

def score_routes(routes: List[Dict], g: Graph, scenario: str, weights_map: Dict[str, float], max_edge_length: float) -> List[Dict]:
    """
    Score paths using WSM and TOPSIS ranking.
    """
    if not routes:
        return []

    scored = []

    for route_data in routes:
        path = route_data['path']

        total_length = 0.0
        total_flood_proba = 0.0
        max_flood_class = 0
        segment_count = 0
        flood_class_counts = {0: 0, 1: 0, 2: 0, 3: 0}
        segments = []

        for i in range(len(path) - 1):
            edge = g.get_edge(path[i], path[i + 1])
            if not edge:
                continue

            length = float(edge.get('length', 0.0))
            flood_class = int(edge.get(f'flood_class_{scenario}', 0) or 0)
            flood_proba = float(edge.get(f'flood_proba_{scenario}', 0.0) or 0.0)
            elevation = float(edge.get('elevation', 0.0) or 0.0)

            total_length += length
            total_flood_proba += flood_proba
            max_flood_class = max(max_flood_class, flood_class)
            flood_class_counts[min(flood_class, 3)] += 1
            segment_count += 1

            segments.append({
                'name': edge.get('name', 'Unnamed Road'),
                'highway': edge.get('highway', 'unclassified'),
                'length': round(length, 2),
                'flood_class': flood_class,
                'flood_proba': round(flood_proba, 4),
                'elevation': round(elevation, 2),
                'wsm_cost': round(compute_wsm_weight(edge, scenario, weights_map, max_edge_length), 4)
            })

        avg_flood_proba = total_flood_proba / segment_count if segment_count > 0 else 0.0

        wsm_flood_total = sum(s['flood_proba'] * weights_map['flood'] for s in segments) * 100.0
        wsm_dist_total = sum((min(s['length'] / max_edge_length, 2.0)) * weights_map['distance'] for s in segments) * 100.0
        
        wsm_rank_total = 0.0
        for s in segments:
            hw = s['highway']
            if isinstance(hw, list): hw = hw[0]
            rank = HIGHWAY_RANK.get(hw, MAX_RANK)
            wsm_rank_total += (rank / MAX_RANK) * weights_map['road_class'] * 100.0

        r_final = {
            'path': path,
            'cost': route_data['cost'],
            'similarity_score': route_data.get('similarity_score', 0.0),
            'total_length_m': round(total_length, 2),
            'total_length_km': round(total_length / 1000, 3),
            'flood_exposure': round(avg_flood_proba, 4),
            'max_flood_class': max_flood_class,
            'flood_class_counts': flood_class_counts,
            'segment_count': segment_count,
            'segments': segments,
            'wsm_breakdown': {
                'flood': round(wsm_flood_total, 2),
                'distance': round(wsm_dist_total, 2),
                'road_class': round(wsm_rank_total, 2)
            },
            '_raw_flood': avg_flood_proba,
            '_raw_length': total_length,
            'destination_info': route_data.get('destination_info'),
            'dest_node': route_data.get('dest_node')
        }
        scored.append(r_final)
    
    # --- TOPSIS RANKING ---
    if len(scored) > 0:
        matrix = []
        for r in scored:
            avg_hw_rank = sum(HIGHWAY_RANK.get(s['highway'] if not isinstance(s['highway'], list) else s['highway'][0], MAX_RANK) for s in r['segments'])
            avg_hw_rank /= r['segment_count'] if r['segment_count'] > 0 else 1.0
            matrix.append([r['_raw_flood'], r['_raw_length'], avg_hw_rank])
        
        matrix = np.array(matrix)
        w = np.array([weights_map['flood'], weights_map['distance'], weights_map['road_class']])
        
        norm_matrix = np.zeros_like(matrix)
        for j in range(matrix.shape[1]):
            col_sum_sq = np.sqrt(np.sum(matrix[:, j]**2)) + 1e-9
            norm_matrix[:, j] = matrix[:, j] / col_sum_sq
                
        weighted_matrix = norm_matrix * w
        ideal_best = np.min(weighted_matrix, axis=0)
        ideal_worst = np.max(weighted_matrix, axis=0)
        s_best = np.sqrt(np.sum((weighted_matrix - ideal_best)**2, axis=1))
        s_worst = np.sqrt(np.sum((weighted_matrix - ideal_worst)**2, axis=1))
        closeness = s_worst / (s_best + s_worst + 1e-9)
        
        for i, r in enumerate(scored):
            r['topsis_score'] = round(float(closeness[i]), 4)
            r['topsis_breakdown'] = {
                's_best': round(float(s_best[i]), 4),
                's_worst': round(float(s_worst[i]), 4)
            }
            r['wsm_path_cost'] = round(r['cost'], 2)

    scored.sort(key=lambda x: x.get('topsis_score', 0), reverse=True)

    for i, r in enumerate(scored):
        r['rank'] = i + 1
        r['recommended'] = (i == 0)
        fe = r['flood_exposure']
        if fe < 0.15: r['risk_label'] = 'Low'
        elif fe < 0.40: r['risk_label'] = 'Medium'
        else: r['risk_label'] = 'High'
        r['safety_score'] = round(r.get('topsis_score', 0) * 100, 1)
        if '_raw_flood' in r: del r['_raw_flood']
        if '_raw_length' in r: del r['_raw_length']

    return scored
