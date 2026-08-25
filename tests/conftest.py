"""Shared fixtures: a small hand-built graph, so tests need no data files."""
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from backend.domain.graph import Graph


def edge(length: float, flood_proba: float = 0.0, highway: str = "residential") -> dict:
    """An edge with only the attributes routing actually reads."""
    return {
        'osmid': '1',
        'name': 'Test Street',
        'highway': highway,
        'length': length,
        'geometry': [],
        'flood_class_25yr': 0 if flood_proba < 0.25 else 2,
        'flood_proba_25yr': flood_proba,
        'elevation': 10.0,
    }


@pytest.fixture
def diamond_graph() -> Graph:
    """Four nodes, two ways around:

        a --200m, dry--- b ---200m, dry--- d
        a --100m, FLOODED-- c --100m, dry-- d

    The short way is flooded; the long way is not. Which one wins depends on
    the weights, which is exactly what the routing tests are about.
    """
    g = Graph()
    g.add_node('a', lat=14.6200, lon=121.0200)
    g.add_node('b', lat=14.6220, lon=121.0200)
    g.add_node('c', lat=14.6210, lon=121.0210)
    g.add_node('d', lat=14.6230, lon=121.0210)

    g.add_edge('a', 'b', edge(200.0, flood_proba=0.01))
    g.add_edge('b', 'd', edge(200.0, flood_proba=0.01))
    g.add_edge('a', 'c', edge(100.0, flood_proba=0.90))
    g.add_edge('c', 'd', edge(100.0, flood_proba=0.02))
    g.max_edge_length = 200.0
    return g
