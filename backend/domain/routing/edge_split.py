"""Inserting a temporary node partway along an edge.

When the closest point on the network is the middle of a road rather than an
intersection, the router needs a node there. This makes one: it splits the edge
in two, divides the length and the drawn geometry at the same fraction, and
returns the new node's id.

The new node lives only in the caller's copy of the graph — every request
clones the graph before snapping, so these never accumulate.
"""
from __future__ import annotations

import math
import uuid
from typing import Any, Dict, Tuple

from backend.domain.graph import Graph


def materialise_split(
    graph: Graph,
    edge: Tuple[Any, Any],
    t: float,
) -> Any:
    """
    Insert midpoint node M onto edge (u, v) at parameter t, split the edge,
    and return M's node_id.  Mutates graph in-place.
    """
    u, v = edge
    nu = graph.nodes[u]
    nv = graph.nodes[v]
    orig_edge_data: Dict = dict(graph.edges[(u, v)])

    # Interpolate M's position
    m_lat = nu['lat'] + t * (nv['lat'] - nu['lat'])
    m_lon = nu['lon'] + t * (nv['lon'] - nu['lon'])

    # Unique, stable ID that won't clash with integer OSM node IDs
    m_id = f"snap_{uuid.uuid4().hex[:12]}"
    graph.add_node(m_id, lat=m_lat, lon=m_lon)

    # Split the original edge length proportionally
    orig_len: float = orig_edge_data.get('length', 0.0)
    len_um = orig_len * t
    len_mc = orig_len * (1.0 - t)

    # Split the original geometry at the snap point
    orig_geom = orig_edge_data.get('geometry', [])
    m_coord = [m_lon, m_lat]
    geom_um = []
    geom_mv = []

    if orig_geom and len(orig_geom) >= 2:
        # Accumulate lengths along the geometry to find the split position
        seg_lengths = []
        total_geom_len = 0.0
        for gi in range(len(orig_geom) - 1):
            dx = orig_geom[gi + 1][0] - orig_geom[gi][0]
            dy = orig_geom[gi + 1][1] - orig_geom[gi][1]
            sl = math.sqrt(dx * dx + dy * dy)
            seg_lengths.append(sl)
            total_geom_len += sl

        target_len = t * total_geom_len
        accum = 0.0
        split_idx = len(orig_geom) - 1  # fallback: end

        for gi, sl in enumerate(seg_lengths):
            if accum + sl >= target_len and sl > 0:
                split_idx = gi
                break
            accum += sl

        geom_um = orig_geom[:split_idx + 1] + [m_coord]
        geom_mv = [m_coord] + orig_geom[split_idx + 1:]
    else:
        nu_coord = [nu['lon'], nu['lat']]
        nv_coord = [nv['lon'], nv['lat']]
        geom_um = [nu_coord, m_coord]
        geom_mv = [m_coord, nv_coord]

    # Helper to build a split-edge data dict
    def _split_data(seg_len: float, geom: list) -> Dict:
        d = dict(orig_edge_data)
        d['length'] = max(seg_len, 0.1)   # never zero
        d['geometry'] = geom
        return d

    # Remove old edge (both directions)
    graph.edges.pop((u, v), None)
    graph.edges.pop((v, u), None)
    graph.adj[u] = [(nb, ed) for nb, ed in graph.adj[u] if nb != v]
    graph.adj[v] = [(nb, ed) for nb, ed in graph.adj[v] if nb != u]

    # Add the two new half-edges
    graph.add_edge(u, m_id, _split_data(len_um, geom_um))
    graph.add_edge(m_id, v,  _split_data(len_mc, geom_mv))

    return m_id


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
