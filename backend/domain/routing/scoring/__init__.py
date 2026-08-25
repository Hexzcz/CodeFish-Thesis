"""Turning candidate paths into ranked, labelled routes.

Two steps, deliberately separate: `metrics.measure_route` says what a single
route costs, `topsis.rank_routes` decides which of them wins. Printing the
result is somebody else's job — `adapters/reporting/route_report.py`.
"""
from typing import Dict, List

from backend.domain.graph import Graph
from backend.domain.routing.scoring.metrics import measure_route
from backend.domain.routing.scoring.topsis import rank_routes

__all__ = ["score_routes", "measure_route", "rank_routes"]


def score_routes(
    routes: List[Dict],
    g: Graph,
    scenario: str,
    weights_map: Dict[str, float],
    max_edge_length: float,
) -> List[Dict]:
    """Measure every candidate route, then rank them. Best first."""
    if not routes:
        return []

    measured = [
        measure_route(route, g, scenario, weights_map, max_edge_length)
        for route in routes
    ]
    return rank_routes(measured, weights_map)
