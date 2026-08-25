"""The app has to start with no database and no internet.

These read the bundled GeoJSON in `backend/data/` — the same files the
fallback uses — so a broken export fails here rather than at a demo.
"""
import pytest

from backend.adapters.evacuation_centers import load_centers_from_file
from backend.adapters.road_network import build_graph_from_files
from backend.domain.prediction.rainfall_scenario import scenario_for_intensity


@pytest.fixture(scope="module")
def file_graph():
    return build_graph_from_files()


def test_road_network_loads_from_files(file_graph):
    assert file_graph.node_count() > 2000
    assert file_graph.edge_count() > 3000


def test_every_edge_has_a_usable_length(file_graph):
    """A zero-length edge is a free shortcut; the router would abuse it."""
    lengths = [e['length'] for e in file_graph.edges.values()]
    assert all(length > 0 for length in lengths)
    assert file_graph.max_edge_length == pytest.approx(max(lengths))


def test_every_edge_connects_two_known_nodes(file_graph):
    for u, v in file_graph.edges:
        assert file_graph.has_node(u) and file_graph.has_node(v)


def test_evacuation_centers_load_from_file():
    centers = load_centers_from_file()
    assert len(centers) > 50
    assert all(center['facility'] for center in centers)


@pytest.mark.xfail(
    reason="Data defect: 'Salvacion Barangay Hall' (id 49) is geocoded to "
           "(7.319, 125.687) — a Salvacion in Mindanao, ~1000 km from Quezon "
           "City. Barangay Salvacion is in District 1, so the record belongs; "
           "its coordinates do not. Fix the coordinate in "
           "backend/data/geojson/evacuation_centers.geojson (and in Supabase) "
           "and this passes.",
    strict=False,
)
def test_every_center_is_in_metro_manila():
    """A center in the wrong province is a destination nobody can evacuate to.

    Routing never picks it — it is thousands of times too far — but it is
    drawn on the map and it is one row away from being chosen if someone
    routes from near it.
    """
    for center in load_centers_from_file():
        assert 14.0 < center['lat'] < 15.5, f"{center['facility']} is at lat {center['lat']}"
        assert 120.5 < center['lon'] < 121.5, f"{center['facility']} is at lon {center['lon']}"


@pytest.mark.parametrize("mm_per_hour,expected", [
    (0.0, '5yr'),
    (7.49, '5yr'),
    (7.5, '25yr'),      # PAGASA: moderate starts here
    (30.0, '25yr'),
    (30.01, '100yr'),   # ...and intense starts above 30
    (150.0, '100yr'),
])
def test_rainfall_maps_to_the_right_model(mm_per_hour, expected):
    assert scenario_for_intensity(mm_per_hour) == expected
