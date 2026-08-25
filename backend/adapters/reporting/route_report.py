"""Printing the scoring breakdown to the terminal.

This is an output adapter, not a routing rule: the engine computes the
numbers, this decides how they look on a console. Kept out of
`domain/routing/scoring/` so the engine stays free of side effects.
"""
from backend.domain.routing.weights import HIGHWAY_RANK, MAX_RANK


_RISK_LABELS = {0: 'No Risk', 1: 'Low-Moderate', 2: 'High Risk'}
_DIVIDER     = '=' * 122
_SUB_DIV     = '-' * 122

def _rc_norm_for(highway) -> float:
    hw = highway if not isinstance(highway, list) else highway[0]
    return round(HIGHWAY_RANK.get(str(hw), MAX_RANK) / MAX_RANK, 4)

def _dist_norm_for(length: float, max_edge_length: float) -> float:
    return round(min(length / max_edge_length, 2.0), 6)

def print_route_breakdown(
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


def print_baseline_comparison(
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
