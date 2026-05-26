"""
backend/graph/snap.py
=====================
Spatial snap: given an arbitrary lat/lon point A, find the geometrically
correct attachment point in the graph, enforcing:

    Rule 1 — Nearest-neighbour check
        Never skip a closer existing node to connect to a farther one.

    Rule 2 — Edge-split check
        If the perpendicular drop from A onto any existing edge is closer
        than *every* existing node, insert a midpoint node M on that edge,
        split the edge B→C into B→M and M→C, and connect A to M.

Priority: whichever candidate (node or edge midpoint) is geometrically
closest to A wins.  Both checks are performed within a configurable
search radius; beyond the radius the plain nearest-node fallback is used.

Public API
----------
snap_point_to_graph(graph, lat, lon,
                    search_radius_m=200.0,
                    max_snap_m=500.0) -> (node_id, snap_dist_m)

The function mutates *graph* in-place only when a new midpoint node M is
inserted (edge-split case).  The caller owns the graph and is responsible
for any serialisation / caching concerns.
"""

from __future__ import annotations

import math
import uuid
from typing import Any, Dict, Optional, Tuple

from backend.graph.builder import Graph

# ---------------------------------------------------------------------------
# Coordinate-system constants (matches nearest_node.py)
# ---------------------------------------------------------------------------
LAT_TO_M: float = 111_320.0        # metres per degree latitude
LON_TO_M: float = 107_600.0        # metres per degree longitude at ~14.6 °N


# ---------------------------------------------------------------------------
# Internal geometry helpers
# ---------------------------------------------------------------------------

def _dist_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Flat-Earth Euclidean distance in metres."""
    dlat = (lat2 - lat1) * LAT_TO_M
    dlon = (lon2 - lon1) * LON_TO_M
    return math.hypot(dlat, dlon)


def _project_onto_segment(
    ax: float, ay: float,   # query point (projected Cartesian)
    bx: float, by: float,   # segment start
    cx: float, cy: float,   # segment end
) -> Tuple[float, float, float]:
    """
    Return (mx, my, t) where (mx, my) is the closest point on segment BC to A,
    and t ∈ [0, 1] is the parameter along BC.  All units are metres.
    """
    bcx = cx - bx
    bcy = cy - by
    seg_len_sq = bcx * bcx + bcy * bcy
    if seg_len_sq == 0.0:
        return bx, by, 0.0  # degenerate segment
    t = max(0.0, min(1.0, ((ax - bx) * bcx + (ay - by) * bcy) / seg_len_sq))
    return bx + t * bcx, by + t * bcy, t


def _to_cartesian(lat: float, lon: float) -> Tuple[float, float]:
    """Convert lat/lon to a flat-Earth Cartesian point in metres."""
    return lon * LON_TO_M, lat * LAT_TO_M


# ---------------------------------------------------------------------------
# Core snap logic
# ---------------------------------------------------------------------------

class SnapResult:
    """
    Represents the winning snap candidate.

    kind    : 'node'  — connect to an existing node
              'split' — insert midpoint M on an existing edge, connect to M
    node_id : the (existing or newly created) node ID to connect A to
    dist_m  : Euclidean distance from A to the snap point
    """
    __slots__ = ('kind', 'node_id', 'dist_m', '_edge', '_t')

    def __init__(self, kind: str, node_id: Any, dist_m: float):
        self.kind = kind
        self.node_id = node_id
        self.dist_m = dist_m
        self._edge = None   # set only for 'split' candidates
        self._t: float = 0.0


def _best_node_candidate(
    graph: Graph,
    ax: float, ay: float,           # A in Cartesian metres
    a_lat: float, a_lon: float,
    search_radius_m: float,
) -> Optional[SnapResult]:
    """Rule 1 — find the nearest existing node within search_radius_m."""
    best_dist = float('inf')
    best_id: Any = None

    for nid, nd in graph.nodes.items():
        d = _dist_m(a_lat, a_lon, nd['lat'], nd['lon'])
        if d <= search_radius_m and d < best_dist:
            best_dist = d
            best_id = nid

    if best_id is None:
        return None
    return SnapResult('node', best_id, best_dist)


def _best_edge_candidate(
    graph: Graph,
    ax: float, ay: float,           # A in Cartesian metres
    a_lat: float, a_lon: float,
    search_radius_m: float,
) -> Optional[SnapResult]:
    """
    Rule 2 — find the nearest perpendicular drop point onto any edge within
    search_radius_m.  Returns None if no edge midpoint beats the radius.

    We iterate over edges (u, v) once by only considering canonical pairs
    where u < v (edges are stored bidirectionally).
    """
    best_perp_dist = float('inf')
    best_edge: Optional[Tuple[Any, Any]] = None   # (u, v)
    best_t: float = 0.0

    seen: set = set()
    for (u, v) in graph.edges:
        key = frozenset((u, v))   # frozenset handles mixed int/str node IDs safely
        if key in seen:
            continue
        seen.add(key)

        nu = graph.nodes.get(u)
        nv = graph.nodes.get(v)
        if nu is None or nv is None:
            continue

        bx, by = _to_cartesian(nu['lat'], nu['lon'])
        cx, cy = _to_cartesian(nv['lat'], nv['lon'])

        mx, my, t = _project_onto_segment(ax, ay, bx, by, cx, cy)

        perp_dist = math.hypot(ax - mx, ay - my)
        if perp_dist <= search_radius_m and perp_dist < best_perp_dist:
            best_perp_dist = perp_dist
            best_edge = (u, v)
            best_t = t

    if best_edge is None:
        return None

    # Tag the winning edge/t for later materialisation
    result = SnapResult('split', None, best_perp_dist)  # node_id filled later
    result._edge = best_edge   # type: ignore[attr-defined]
    result._t = best_t         # type: ignore[attr-defined]
    return result


def _materialise_split(
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

def snap_point_to_graph(
    graph: Graph,
    lat: float,
    lon: float,
    search_radius_m: float = 200.0,
    max_snap_m: float = 500.0,
) -> Tuple[Any, float]:
    """
    Snap point A=(lat, lon) to the graph, enforcing Rule 1 and Rule 2.

    Parameters
    ----------
    graph           : the live Graph object (may be mutated on edge-split)
    lat, lon        : coordinates of the new point A
    search_radius_m : radius within which both rules are checked
    max_snap_m      : hard maximum — raises ValueError if nothing is found
                      within this distance

    Returns
    -------
    (node_id, dist_m)
        node_id is always a node that exists in graph.nodes after the call.
        dist_m  is the Euclidean snap distance in metres.

    Raises
    ------
    ValueError  if graph is empty or nothing is within max_snap_m.
    """
    if not graph.nodes:
        raise ValueError("Road network graph is empty.")

    ax, ay = _to_cartesian(lat, lon)

    # --- Rule 1: nearest node within search radius ---
    node_cand = _best_node_candidate(graph, ax, ay, lat, lon, search_radius_m)

    # --- Rule 2: nearest perpendicular drop onto any edge ---
    edge_cand = _best_edge_candidate(graph, ax, ay, lat, lon, search_radius_m)

    # --- Choose winner ---
    if node_cand is None and edge_cand is None:
        # Nothing inside search radius — fall back to global nearest node
        return _global_nearest_node(graph, lat, lon, max_snap_m)

    if edge_cand is not None and (
        node_cand is None or edge_cand.dist_m < node_cand.dist_m
    ):
        # Rule 2 wins — materialise the split and connect to M
        m_id = _materialise_split(graph, edge_cand._edge, edge_cand._t)  # type: ignore[attr-defined]
        return m_id, edge_cand.dist_m

    # Rule 1 wins (or equal — node preferred for stability)
    return node_cand.node_id, node_cand.dist_m


def _global_nearest_node(
    graph: Graph,
    lat: float,
    lon: float,
    max_dist_m: float,
) -> Tuple[Any, float]:
    """Plain nearest-node fallback used when point is outside search radius."""
    best_dist = float('inf')
    best_id: Any = None

    for nid, nd in graph.nodes.items():
        d = _dist_m(lat, lon, nd['lat'], nd['lon'])
        if d < best_dist:
            best_dist = d
            best_id = nid

    if best_id is None or best_dist > max_dist_m:
        raise ValueError(
            f"Point is {best_dist:.0f} m from the nearest road node "
            f"(max allowed: {max_dist_m:.0f} m). "
            "Please place your pin closer to a road."
        )
    return best_id, best_dist
