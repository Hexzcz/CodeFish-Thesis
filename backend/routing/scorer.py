import numpy as np
import logging
from typing import List, Dict
from backend.graph.builder import Graph
from backend.routing.weights import compute_wsm_weight, HIGHWAY_RANK, MAX_RANK

logger = logging.getLogger(__name__)

def score_routes(routes: List[Dict], g: Graph, scenario: str, weights_map: Dict[str, float], max_edge_length: float, _log: bool = True) -> List[Dict]:
    """
    Score paths using WSM and TOPSIS ranking with detailed logging.
    """
    if not routes:
        return []

    scored = []

    for route_idx, route_data in enumerate(routes):
        path = route_data['path']

        total_length = 0.0
        total_flood_proba = 0.0
        weighted_flood_proba = 0.0
        max_flood_class = 0
        segment_count = 0
        flood_class_counts = {0: 0, 1: 0, 2: 0}
        segments = []

        for i in range(len(path) - 1):
            edge = g.get_edge(path[i], path[i + 1])
            if not edge:
                continue

            length = float(edge.get('length', 0.0))
            flood_class = int(edge.get(f'flood_class_{scenario}', 0) or 0)
            flood_proba = float(edge.get(f'flood_proba_{scenario}', 0.0) or 0.0)
            elevation = float(edge.get('elevation', 0.0) or 0.0)

            flood_proba_array = edge.get(f'flood_proba_array_{scenario}', [1.0, 0.0, 0.0])

            total_length += length
            total_flood_proba += flood_proba
            weighted_flood_proba += flood_proba * length
            max_flood_class = max(max_flood_class, flood_class)
            flood_class_counts[min(flood_class, 2)] += 1
            segment_count += 1

            segment_data = {
                'name': edge.get('name', 'Unnamed Road'),
                'highway': edge.get('highway', 'unclassified'),
                'length': round(length, 2),
                'flood_class': flood_class,
                'flood_proba': round(flood_proba, 4),
                'flood_proba_array': [round(p, 3) for p in flood_proba_array],
                'elevation': round(elevation, 2),
                'wsm_cost': round(compute_wsm_weight(edge, scenario, weights_map, max_edge_length), 4)
            }
            segments.append(segment_data)
            logger.debug(f"Route {route_idx} - Segment {i}: {segment_data['name']} (Flood: {segment_data['flood_proba']})")


        avg_flood_proba = weighted_flood_proba / total_length if total_length > 0 else 0.0

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
    # --- TERMINAL LOGGING (fires after rank is assigned and TOPSIS is done) ---
    if _log:
        _log_routes(scored, scenario, weights_map, max_edge_length)

    return scored

# ---------------------------------------------------------------------------
# Terminal logging helpers
# ---------------------------------------------------------------------------

_RISK_LABELS = {0: 'No Risk', 1: 'Low-Moderate', 2: 'High Risk'}
_DIVIDER     = '=' * 122
_SUB_DIV     = '-' * 122

def _rc_norm_for(highway) -> float:
    hw = highway if not isinstance(highway, list) else highway[0]
    return round(HIGHWAY_RANK.get(str(hw), MAX_RANK) / MAX_RANK, 4)

def _dist_norm_for(length: float, max_edge_length: float) -> float:
    return round(min(length / max_edge_length, 2.0), 6)

def _log_routes(
    scored: list,
    scenario: str,
    weights_map: dict,
    max_edge_length: float,
) -> None:
    wf = weights_map.get('flood',      0.764)
    wd = weights_map.get('distance',   0.112)
    wr = weights_map.get('road_class', 0.124)

    print('\n' + _DIVIDER)
    print(
        f'  ROUTE SCORING BREAKDOWN  |  Scenario: {scenario.upper()}'
        f'  |  Weights: FS={wf}  RC={wr}  Dist={wd}'
        f'  |  max_edge_len={max_edge_length:.1f}m'
    )
    print(_DIVIDER)

    for r in scored:
        dest        = (r.get('destination_info') or {}).get('facility', 'Unknown Destination')
        rank        = r.get('rank', '?')
        topsis      = r.get('topsis_score', 0.0)
        sb          = r.get('topsis_breakdown', {}).get('s_best',  0.0)
        sw          = r.get('topsis_breakdown', {}).get('s_worst', 0.0)
        rec_tag     = '  [RECOMMENDED]' if r.get('recommended') else ''

        print(f'\nROUTE {rank}{rec_tag}  -->  {dest}')
        print(_SUB_DIV)
        print(
            f"  {'Seg':>4}  {'Street Name':<30}  {'HW Type':<14}  {'Risk Class':<14}"
            f"  {'FS Raw':>8}  {'FS Norm':>8}  {'RC Norm':>8}  {'Dist (m)':>10}  {'Dist Norm':>10}  {'WSM Cost':>10}"
        )
        print('  ' + '-' * 120)

        total_wsm = 0.0
        counts = {0: 0, 1: 0, 2: 0}
        
        for idx, seg in enumerate(r['segments'], start=1):
            name        = str(seg['name'])[:30]
            hw_raw      = seg['highway']
            hw          = hw_raw if not isinstance(hw_raw, list) else hw_raw[0]
            fc          = seg['flood_class']
            fs_raw      = seg['flood_proba']
            fs_norm     = fs_raw
            rc_norm     = _rc_norm_for(hw_raw)
            length      = seg['length']
            d_norm      = _dist_norm_for(length, max_edge_length)
            wsm         = seg['wsm_cost']
            risk        = _RISK_LABELS.get(fc, f'Class {fc}')
            total_wsm  += wsm
            counts[min(fc, 2)] += 1

            print(
                f"  {idx:>4}  {name:<30}  {str(hw):<14}  {risk:<14}"
                f"  {fs_raw:>8.4f}  {fs_norm:>8.4f}  {rc_norm:>8.4f}  {length:>10.2f}  {d_norm:>10.6f}  {wsm:>10.4f}"
            )

        print('  ' + '-' * 120)
        print(f"  Total WSM cost (sum)         : {total_wsm:.4f}")
        print(f"  Average FS score             : {r['flood_exposure']:.4f}")
        print(f"  Total distance               : {r['total_length_m']:.2f} m  ({r['total_length_km']:.3f} km)")
        print(f"  Segment Risk Counts          : High Risk: {counts[2]} | Low-Moderate Risk: {counts[1]} | No Risk: {counts[0]}")
        if 'topsis_score' in r:
            print(f"  TOPSIS closeness coefficient : {topsis:.4f}  (S+={sb:.4f}, S-={sw:.4f})")
        print(f"  Dijkstra path cost           : {r.get('wsm_path_cost', r.get('cost', 0.0)):.4f}")
        print()

    print(_DIVIDER + '\n')


def _log_baseline_comparison(
    scored: list,
    baselines: list,
    scenario: str,
    weights_map: dict,
    max_edge_length: float,
) -> None:
    """Print Dijkstra shortest-distance baseline segments and comparison for each route."""
    if not any(baselines):
        return

    print('\n' + _DIVIDER)
    print(f'  DIJKSTRA SHORTEST-DISTANCE BASELINE COMPARISON  |  Scenario: {scenario.upper()}')
    print(_DIVIDER)

    for route, baseline in zip(scored, baselines):
        if baseline is None:
            continue

        rank = route.get('rank', '?')
        dest = (route.get('destination_info') or {}).get('facility', 'Unknown Destination')
        rec_tag = '  [RECOMMENDED]' if route.get('recommended') else ''

        print(f'\nROUTE {rank}{rec_tag}  vs  DIJKSTRA BASELINE  -->  {dest}')
        print(_SUB_DIV)
        print(
            f"  {'Seg':>4}  {'Street Name':<30}  {'HW Type':<14}  {'Risk Class':<14}"
            f"  {'FS Raw':>8}  {'RC Norm':>8}  {'Dist (m)':>10}  {'WSM Cost':>10}"
        )
        print('  ' + '-' * 104)

        b_total_wsm = 0.0
        b_counts = {0: 0, 1: 0, 2: 0}

        for idx, seg in enumerate(baseline.get('segments', []), start=1):
            name    = str(seg['name'])[:30]
            hw_raw  = seg['highway']
            hw      = hw_raw if not isinstance(hw_raw, list) else hw_raw[0]
            fc      = seg['flood_class']
            fs_raw  = seg['flood_proba']
            rc_norm = _rc_norm_for(hw_raw)
            length  = seg['length']
            wsm     = seg['wsm_cost']
            risk    = _RISK_LABELS.get(fc, f'Class {fc}')
            b_total_wsm += wsm
            b_counts[min(fc, 2)] += 1

            print(
                f"  {idx:>4}  {name:<30}  {str(hw):<14}  {risk:<14}"
                f"  {fs_raw:>8.4f}  {rc_norm:>8.4f}  {length:>10.2f}  {wsm:>10.4f}"
            )

        b_dist_km = baseline.get('total_length_km', 0.0)
        b_dist_m  = baseline.get('total_length_m', 0.0)
        b_fe      = baseline.get('flood_exposure', 0.0)

        print('  ' + '-' * 104)
        print(f"  Total WSM cost (sum)         : {b_total_wsm:.4f}")
        print(f"  Average FS score             : {b_fe:.4f}")
        print(f"  Total distance               : {b_dist_m:.2f} m  ({b_dist_km:.3f} km)")
        print(f"  Segment Risk Counts          : High Risk: {b_counts[2]} | Low-Moderate Risk: {b_counts[1]} | No Risk: {b_counts[0]}")

        # --- Comparison summary ---
        r_dist_km  = route.get('total_length_km', 0.0)
        r_fe       = route.get('flood_exposure', 0.0)
        r_total_wsm = sum(s['wsm_cost'] for s in route.get('segments', []))
        r_counts   = route.get('flood_class_counts', {0: 0, 1: 0, 2: 0})

        d_dist = r_dist_km - b_dist_km
        d_fe   = r_fe - b_fe
        d_wsm  = r_total_wsm - b_total_wsm

        print()
        print(f"  {'COMPARISON SUMMARY':^72}")
        print(f"  {'Metric':<28} {'Route ' + str(rank):>14} {'Dijkstra':>14} {'Delta':>14}")
        print('  ' + '-' * 72)
        print(f"  {'Distance (km)':<28} {r_dist_km:>14.3f} {b_dist_km:>14.3f} {d_dist:>+14.3f}")
        print(f"  {'Avg Flood Susceptibility':<28} {r_fe:>14.4f} {b_fe:>14.4f} {d_fe:>+14.4f}")
        print(f"  {'Total WSM Cost':<28} {r_total_wsm:>14.4f} {b_total_wsm:>14.4f} {d_wsm:>+14.4f}")
        print(f"  {'High Risk Segments':<28} {r_counts.get(2,0):>14} {b_counts[2]:>14} {r_counts.get(2,0)-b_counts[2]:>+14}")
        print(f"  {'Low-Moderate Segments':<28} {r_counts.get(1,0):>14} {b_counts[1]:>14} {r_counts.get(1,0)-b_counts[1]:>+14}")
        print(f"  {'No Risk Segments':<28} {r_counts.get(0,0):>14} {b_counts[0]:>14} {r_counts.get(0,0)-b_counts[0]:>+14}")
        print()

    print(_DIVIDER + '\n')
