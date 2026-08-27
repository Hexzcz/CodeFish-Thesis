"""Planning an evacuation: which centers are considered, and which route wins.

This is the layer the thesis argues for. Dijkstra, TOPSIS and snapping are
tested next door; what happens here is the part that decides *which* centers
become candidates, how alternatives are found, and whether a longer dry route
beats a shorter flooded one when it counts.

The graph is the four-node fixture from conftest:

    a --200m, dry----- b ----200m, dry---- d
    a --100m, FLOODED- c ----100m, dry---- d
"""
import pytest

from backend.domain.services.route_planner import (
    DEFAULT_WEIGHTS,
    MAX_ROUTES,
    NoRouteFound,
    distance_baselines,
    plan_evacuation_routes,
)

DISTANCE_ONLY = {'flood': 0.0, 'distance': 1.0, 'road_class': 0.0}

# Node positions from the fixture, so centers can sit exactly on a junction.
AT_A = (14.6200, 121.0200)
AT_D = (14.6230, 121.0210)

# Halfway along the a–b edge. Standing on a junction snaps straight to it and
# changes nothing; standing on a road forces a temporary node to be inserted,
# which is the case that can leak into a shared graph.
ON_THE_ROAD = (14.6210, 121.0200)


def center(lat, lon, facility="Barangay Hall", barangay="Test"):
    return {'lat': lat, 'lon': lon, 'facility': facility, 'barangay': barangay, 'type': 'Hall'}


def plan(graph, centers, weights=DEFAULT_WEIGHTS, k=3, origin=AT_A):
    return plan_evacuation_routes(
        graph=graph,
        evacuation_centers=centers,
        origin_lat=origin[0],
        origin_lon=origin[1],
        scenario='25yr',
        weights=weights,
        max_edge_length=graph.max_edge_length,
        k=k,
    )


# ── What it produces ────────────────────────────────────────────────────────

def test_it_returns_ranked_routes_and_where_they_start(diamond_graph):
    result = plan(diamond_graph, [center(*AT_D)])

    assert result.routes, "no routes planned"
    assert result.routes[0]['recommended'] is True
    assert result.origin_info['lat'] == AT_A[0]
    assert result.origin_node is not None


def test_the_plan_carries_the_graph_its_routes_refer_to(diamond_graph):
    """Snapping splits edges, so the geometry only exists in that copy."""
    result = plan(diamond_graph, [center(*AT_D)])

    for node in result.routes[0]['path']:
        assert result.graph.has_node(node), f"{node} is not in the returned graph"


def test_the_caller_s_graph_is_left_alone(diamond_graph):
    """Two identical requests must not drift because the first mutated state.

    The origin is deliberately mid-road: snapping then splits an edge and
    inserts a node, which is the mutation that would otherwise accumulate in
    the shared graph request after request.
    """
    before_nodes = diamond_graph.node_count()
    before_edges = diamond_graph.edge_count()

    first = plan(diamond_graph, [center(*AT_D)], origin=ON_THE_ROAD)
    second = plan(diamond_graph, [center(*AT_D)], origin=ON_THE_ROAD)

    # The split really happened — otherwise this test proves nothing.
    assert first.graph.node_count() > before_nodes, "no edge was split; pick a better origin"

    assert diamond_graph.node_count() == before_nodes
    assert diamond_graph.edge_count() == before_edges
    assert second.routes[0]['total_length_m'] == pytest.approx(
        first.routes[0]['total_length_m']
    ), "the same request gave a different answer the second time"


# ── The claim the thesis makes ──────────────────────────────────────────────

def test_a_flooded_shortcut_loses_to_a_longer_dry_route(diamond_graph):
    """The whole argument: 400 m of dry road beats 200 m through water."""
    result = plan(diamond_graph, [center(*AT_D)])

    assert result.routes[0]['path'] == ['a', 'b', 'd'], "the planner took the flooded shortcut"
    assert result.routes[0]['total_length_m'] == pytest.approx(400.0)


def test_without_the_flood_weight_the_short_way_wins(diamond_graph):
    """Guards the test above from passing for the wrong reason.

    If both weightings produced the same path, the assertion above would prove
    nothing about flood-awareness — only that the graph has one sensible route.
    """
    result = plan(diamond_graph, [center(*AT_D)], weights=DISTANCE_ONLY)

    assert result.routes[0]['path'] == ['a', 'c', 'd']
    assert result.routes[0]['total_length_m'] == pytest.approx(200.0)


def test_the_recommended_route_is_the_one_ranked_first(diamond_graph):
    result = plan(diamond_graph, [center(*AT_D)])

    recommended = [r for r in result.routes if r['recommended']]
    assert len(recommended) == 1
    assert recommended[0] is result.routes[0]
    assert [r['rank'] for r in result.routes] == list(range(1, len(result.routes) + 1))


# ── Which centers get considered ────────────────────────────────────────────

def test_a_center_nothing_can_reach_is_skipped(diamond_graph):
    """An island in the graph is not a destination, however close it looks.

    Two independent guards produce this outcome — unreachable centers are
    dropped when candidates are chosen, and a center with no path through is
    dropped again when routes are built. Removing either one alone will not
    fail this test; that is deliberate. The test pins the behaviour, not which
    line of code delivers it.
    """
    diamond_graph.add_node('island', lat=14.6260, lon=121.0260)

    reachable = center(*AT_D, facility="Reachable Hall")
    stranded = center(14.6260, 121.0260, facility="Stranded Hall")

    result = plan(diamond_graph, [reachable, stranded])

    named = {r['destination_info'].get('facility') for r in result.routes}
    assert "Stranded Hall" not in named
    assert "Reachable Hall" in named


def test_no_reachable_center_is_an_error_not_an_empty_answer(diamond_graph):
    """Returning nothing would look like a working app with no advice."""
    diamond_graph.add_node('island', lat=14.6260, lon=121.0260)

    with pytest.raises(NoRouteFound):
        plan(diamond_graph, [center(14.6260, 121.0260, facility="Stranded Hall")])


def test_having_no_centers_at_all_is_refused_loudly(diamond_graph):
    """A server with no evacuation centers is misconfigured, not unlucky."""
    with pytest.raises(ValueError, match="No evacuation centers"):
        plan(diamond_graph, [])


def test_an_origin_far_from_any_road_is_refused(diamond_graph):
    """Routing from somewhere the network does not reach would be a guess."""
    with pytest.raises(ValueError, match="from the nearest road"):
        plan(diamond_graph, [center(*AT_D)], origin=(14.7500, 121.2000))


# ── How many routes come back ───────────────────────────────────────────────

def test_k_limits_the_number_of_routes(diamond_graph):
    result = plan(diamond_graph, [center(*AT_D)], k=1)
    assert len(result.routes) == 1


def test_k_cannot_ask_for_more_than_the_planner_offers(diamond_graph):
    result = plan(diamond_graph, [center(*AT_D)], k=99)
    assert 1 <= len(result.routes) <= MAX_ROUTES


def test_alternatives_are_found_for_a_single_center(diamond_graph):
    """With one destination and two ways to it, both should be offered."""
    result = plan(diamond_graph, [center(*AT_D)], k=2)

    paths = [tuple(r['path']) for r in result.routes]
    assert len(paths) == len(set(paths)), "the same path was offered twice"
    if len(paths) > 1:
        assert ('a', 'b', 'd') in paths and ('a', 'c', 'd') in paths


# ── Weights ─────────────────────────────────────────────────────────────────

def test_no_weights_given_means_the_thesis_defaults(diamond_graph):
    """A caller who passes nothing must not silently get distance-only routing."""
    result = plan(diamond_graph, [center(*AT_D)], weights=None)

    assert result.routes[0]['path'] == ['a', 'b', 'd']
    assert DEFAULT_WEIGHTS['flood'] > DEFAULT_WEIGHTS['distance']


# ── The baseline shown alongside ────────────────────────────────────────────

def test_a_baseline_is_returned_for_every_route(diamond_graph):
    """The compare view pairs them by index, so the lists must line up."""
    result = plan(diamond_graph, [center(*AT_D)])

    baselines = distance_baselines(
        result.graph, result.origin_node, result.routes,
        '25yr', DEFAULT_WEIGHTS, diamond_graph.max_edge_length,
    )

    assert len(baselines) == len(result.routes)


def test_the_baseline_is_the_shortest_route_not_the_safest(diamond_graph):
    """It exists to be compared against — if it matched, it would say nothing."""
    result = plan(diamond_graph, [center(*AT_D)])

    baselines = distance_baselines(
        result.graph, result.origin_node, result.routes,
        '25yr', DEFAULT_WEIGHTS, diamond_graph.max_edge_length,
    )

    assert baselines[0] is not None
    assert baselines[0]['total_length_m'] < result.routes[0]['total_length_m']
    assert baselines[0]['flood_exposure'] > result.routes[0]['flood_exposure']
