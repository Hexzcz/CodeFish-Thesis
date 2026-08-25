"""Ranking the candidate routes against each other (TOPSIS).

TOPSIS scores each route by how close it sits to the ideal route and how far
from the worst one, across three criteria: flood exposure, length, and road
class. Flood exposure carries most of the weight — see
`docs/decisions/0003-topsis-weights.md`.
"""
import logging
from typing import Dict, List

import numpy as np

from backend.domain.routing.weights import HIGHWAY_RANK, MAX_RANK

logger = logging.getLogger(__name__)

# Flood exposure thresholds that turn a probability into a word the UI shows.
_LOW_RISK_BELOW = 0.15
_MEDIUM_RISK_BELOW = 0.40


def rank_routes(scored: List[Dict], weights_map: Dict[str, float]) -> List[Dict]:
    """Score, sort and label routes. Best route first; `rank` is 1-based."""
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
            logger.info(f"Route {i} Topsis Score: {r['topsis_score']} | S_Best: {r['topsis_breakdown']['s_best']} | S_Worst: {r['topsis_breakdown']['s_worst']}")

    scored.sort(key=lambda x: (
        -float(x.get('topsis_score', 0.0) or 0.0),
        float(x.get('flood_exposure', 0.0) or 0.0),
        float(x.get('total_length_m', 0.0) or 0.0),
        str(x.get('destination_info', {}).get('facility', '')),
        tuple(str(node) for node in x.get('path', [])),
    ))

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

    scored.sort(key=lambda x: (
        -float(x.get('topsis_score', 0.0) or 0.0),
        float(x.get('flood_exposure', 0.0) or 0.0),
        float(x.get('total_length_m', 0.0) or 0.0),
        str(x.get('destination_info', {}).get('facility', '')),
        tuple(str(node) for node in x.get('path', [])),
    ))

    for i, r in enumerate(scored):
        r['rank'] = i + 1
        r['recommended'] = (i == 0)
        fe = r['flood_exposure']
        if fe < _LOW_RISK_BELOW:
            r['risk_label'] = 'Low'
        elif fe < _MEDIUM_RISK_BELOW:
            r['risk_label'] = 'Medium'
        else:
            r['risk_label'] = 'High'
        r['safety_score'] = round(r.get('topsis_score', 0) * 100, 1)
        # Raw values exist only to build the decision matrix above.
        r.pop('_raw_flood', None)
        r.pop('_raw_length', None)

    return scored
