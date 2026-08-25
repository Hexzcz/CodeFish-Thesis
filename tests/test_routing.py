"""What the router is for: preferring the dry way when it matters."""
import pytest

from backend.domain.routing.dijkstra import dijkstra
from backend.domain.routing.distance import shortest_distance, shortest_distance_path
from backend.domain.routing.scoring import score_routes

FLOOD_FIRST = {'flood': 0.764, 'distance': 0.112, 'road_class': 0.124}
DISTANCE_ONLY = {'flood': 0.0, 'distance': 1.0, 'road_class': 0.0}


def test_distance_search_takes_the_short_way(diamond_graph):
    distance, path = shortest_distance_path(diamond_graph, 'a', 'd')
    assert path == ['a', 'c', 'd']
    assert distance == pytest.approx(200.0)


def test_distance_only_wrapper_agrees_with_the_full_search(diamond_graph):
    assert shortest_distance(diamond_graph, 'a', 'd') == pytest.approx(200.0)


def test_unreachable_target_is_infinite_not_an_error(diamond_graph):
    diamond_graph.add_node('island', lat=14.70, lon=121.10)
    distance, path = shortest_distance_path(diamond_graph, 'a', 'island')
    assert distance == float('inf')
    assert path == []


def test_flood_weighting_avoids_the_flooded_shortcut(diamond_graph):
    """The whole point of the app: the shorter road is the flooded one."""
    _, path = dijkstra(diamond_graph, 'a', 'd', '25yr', FLOOD_FIRST, 200.0)
    assert path == ['a', 'b', 'd'], "router took the flooded shortcut"


def test_distance_weighting_takes_the_flooded_shortcut(diamond_graph):
    """Same graph, flood weight removed — the short way wins again.

    Guards against the flood term being ignored: if both weightings produced
    the same path, the test above would pass for the wrong reason.
    """
    _, path = dijkstra(diamond_graph, 'a', 'd', '25yr', DISTANCE_ONLY, 200.0)
    assert path == ['a', 'c', 'd']


def test_scoring_ranks_the_dry_route_first(diamond_graph):
    routes = [
        {'path': ['a', 'c', 'd'], 'cost': 1.0, 'destination_info': {'facility': 'Short'}, 'dest_node': 'd'},
        {'path': ['a', 'b', 'd'], 'cost': 2.0, 'destination_info': {'facility': 'Dry'}, 'dest_node': 'd'},
    ]
    scored = score_routes(routes, diamond_graph, '25yr', FLOOD_FIRST, 200.0)

    assert scored[0]['destination_info']['facility'] == 'Dry'
    assert scored[0]['recommended'] is True
    assert scored[0]['rank'] == 1
    assert scored[1]['recommended'] is False


def test_scoring_reports_length_and_exposure(diamond_graph):
    scored = score_routes(
        [{'path': ['a', 'b', 'd'], 'cost': 1.0, 'destination_info': {}, 'dest_node': 'd'}],
        diamond_graph, '25yr', FLOOD_FIRST, 200.0,
    )
    route = scored[0]
    assert route['total_length_m'] == pytest.approx(400.0)
    assert route['total_length_km'] == pytest.approx(0.4)
    assert route['segment_count'] == 2
    assert route['flood_exposure'] == pytest.approx(0.01, abs=1e-6)
    assert route['risk_label'] == 'Low'


def test_scoring_empty_input_is_empty_output(diamond_graph):
    assert score_routes([], diamond_graph, '25yr', FLOOD_FIRST, 200.0) == []
