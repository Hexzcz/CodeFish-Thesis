"""Attaching a dropped pin to the road network."""
import pytest

from backend.domain.routing.snapping import snap_point_to_graph


def test_pin_on_a_node_snaps_to_that_node(diamond_graph):
    node_id, distance = snap_point_to_graph(diamond_graph, 14.6200, 121.0200)
    assert node_id == 'a'
    assert distance < 1.0


def test_pin_beside_a_road_splits_the_edge(diamond_graph):
    """A pin halfway along a road gets its own node, and the road is split."""
    before = diamond_graph.edge_count()
    node_id, _ = snap_point_to_graph(diamond_graph, 14.6210, 121.02005)

    assert str(node_id).startswith('snap_')
    assert diamond_graph.edge_count() == before + 1, "edge was not split in two"
    assert diamond_graph.has_node(node_id)


def test_pin_far_from_any_road_is_refused(diamond_graph):
    """Silently routing from the wrong place is worse than saying no."""
    with pytest.raises(ValueError, match="from the nearest road"):
        snap_point_to_graph(diamond_graph, 14.7500, 121.2000)


def test_split_does_not_change_total_road_length(diamond_graph):
    """Splitting an edge divides its length; it must not invent or lose any."""
    total_before = sum(
        e['length'] for (u, v), e in diamond_graph.edges.items() if u < v
    )
    snap_point_to_graph(diamond_graph, 14.6210, 121.02005)
    total_after = sum(
        e['length'] for (u, v), e in diamond_graph.edges.items() if u < v
    )
    assert total_after == pytest.approx(total_before, rel=1e-6)
