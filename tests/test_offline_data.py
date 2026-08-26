"""The app has to start with no database and no internet.

These read the bundled GeoJSON in `backend/data/` — the same files the
fallback uses — so a broken export fails here rather than at a demo.
"""
import json

import pytest

from backend.adapters.evacuation_centers import load_centers_from_file
from backend.core.config import GEOJSON_DIR
from backend.domain.geo import point_in_boundary
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


def test_every_center_is_inside_district_1():
    """A center in the wrong place is a destination nobody can evacuate to.

    This caught "Salvacion Barangay Hall" sitting at (7.319, 125.687) — a
    Salvacion in Mindanao, about 1,000 km from Quezon City, from a geocoding
    pass that matched the wrong one. Routing never picked it, because it was
    thousands of times too far, but it was drawn on the map and it was one row
    away from being chosen by someone routing from near it.

    Checked against the real boundary rather than a bounding box: the wrong
    Salvacion was in the Philippines, and a box around Metro Manila would not
    have caught a mistake one city over.
    """
    boundary = json.loads((GEOJSON_DIR / "district1_boundary.geojson").read_text())
    feature = boundary["features"][0]

    outside = [
        center["facility"]
        for center in load_centers_from_file()
        if not point_in_boundary(center["lat"], center["lon"], feature)
    ]
    assert not outside, f"evacuation centers outside District 1: {outside}"


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
