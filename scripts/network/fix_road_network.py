"""
fix_road_network.py
───────────────────
Downloads/fixes the District 1 QC road network and exports
clean road_nodes.geojson and road_edges.geojson files.

Usage:
    python fix_road_network.py

Requirements:
    pip install osmnx geopandas networkx shapely
"""

import json
import os
import math
import warnings
warnings.filterwarnings("ignore")

import osmnx as ox
import networkx as nx
import geopandas as gpd
from shapely.geometry import LineString, MultiLineString

# ─── 1. Download ───────────────────────────────────────────────────────────────

print("=" * 52)
print("  District 1 QC Road Network — Download & Fix  ")
print("=" * 52)
print()
print("[1/6] Downloading road network from OpenStreetMap...")
print("      Area: District 1, Quezon City, Metro Manila")
print("      buffer_dist=500 m, retain_all=False (auto-prunes disconnected)")
print()

G = ox.graph_from_place(
    "District 1, Quezon City, Metro Manila, Philippines",
    network_type="drive",
    simplify=True,
    retain_all=False,   # <-- keeps ONLY largest connected subgraph
)

print(f"      Raw download: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# ─── 2. Connectivity Diagnostics ───────────────────────────────────────────────

print()
print("[2/6] Running connectivity diagnostics...")

G_undirected = G.to_undirected()
components = sorted(nx.connected_components(G_undirected), key=len, reverse=True)

print()
print("=== ROAD NETWORK DIAGNOSTICS ===")
print(f"Total nodes: {G.number_of_nodes()}")
print(f"Total edges: {G.number_of_edges()}")
print(f"Connected components: {len(components)}")
print()
print("Component sizes (top 10):")
for i, comp in enumerate(components[:10], 1):
    print(f"  Component {i}: {len(comp)} nodes")

if len(components) == 1:
    print()
    print("Network is fully connected ✅")
else:
    print()
    print(f"WARNING: {len(components)} disconnected components found")
    print(f"Keeping only largest component ({len(components[0])} nodes)")

# ─── 3. Keep Largest Component ─────────────────────────────────────────────────

print()
print("[3/6] Pruning isolated components...")

largest_component = components[0]
nodes_to_remove = [n for n in G.nodes() if n not in largest_component]
G.remove_nodes_from(nodes_to_remove)

print(f"      Removed {len(nodes_to_remove)} isolated nodes")
print(f"      Final network: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# ─── 4. Validate Network Coverage ──────────────────────────────────────────────

print()
print("[4/6] Validating network coverage...")

lats = [data['y'] for _, data in G.nodes(data=True)]
lons = [data['x'] for _, data in G.nodes(data=True)]

print(f"      Network bounds:")
print(f"        North: {max(lats):.6f}")
print(f"        South: {min(lats):.6f}")
print(f"        East:  {max(lons):.6f}")
print(f"        West:  {min(lons):.6f}")

# Expected rough bounds for District 1 QC
ok_n = 14.580 <= max(lats) <= 14.750
ok_s = 14.550 <= min(lats) <= 14.650
ok_e = 121.000 <= max(lons) <= 121.200
ok_w = 120.960 <= min(lons) <= 121.100

if ok_n and ok_s and ok_e and ok_w:
    print("      Bounds look correct ✅")
else:
    print("      WARNING: bounds look unexpected — check if the correct district was downloaded")
    print("      Expected roughly: N≈14.700, S≈14.580, E≈121.130, W≈120.990")

# ─── 5. Export road_nodes.geojson ──────────────────────────────────────────────

print()
print("[5/6] Exporting road_nodes.geojson...")

gdfs = ox.graph_to_gdfs(G)
if isinstance(gdfs, tuple):
    nodes_gdf, _ = gdfs
else:
    nodes_gdf = gdfs  # single return (nodes only requested)

nodes_gdf = nodes_gdf.reset_index()  # osmid becomes a column

# Keep only needed columns
keep_cols = [c for c in ['osmid', 'y', 'x', 'geometry'] if c in nodes_gdf.columns]
nodes_gdf = nodes_gdf[keep_cols].copy()
nodes_gdf = nodes_gdf.rename(columns={'y': 'lat', 'x': 'lon'})

nodes_gdf.to_file('road_nodes.geojson', driver='GeoJSON')
print(f"      Saved {len(nodes_gdf)} nodes → road_nodes.geojson")

# ─── 6. Export road_edges.geojson ──────────────────────────────────────────────

print()
print("[6/6] Exporting road_edges.geojson...")

all_gdfs = ox.graph_to_gdfs(G)
if isinstance(all_gdfs, tuple):
    _, edges_gdf = all_gdfs
else:
    # Newer osmnx: call with fill_edge_geometry
    _, edges_gdf = ox.graph_to_gdfs(G, nodes=True, edges=True)
edges_gdf = edges_gdf.reset_index()  # u, v, key become columns

# --- Fix list-valued columns (common after simplification) ---

def first_or_str(val, default=''):
    if isinstance(val, list):
        return val[0] if val else default
    if val is None or (isinstance(val, float) and math.isnan(float(val))):
        return default
    return val

if 'osmid' in edges_gdf.columns:
    edges_gdf['osmid'] = edges_gdf['osmid'].apply(
        lambda x: str(x[0]) if isinstance(x, list) else str(x)
    )

if 'name' in edges_gdf.columns:
    edges_gdf['name'] = edges_gdf['name'].apply(
        lambda x: first_or_str(x, 'Unnamed Road')
    )
else:
    edges_gdf['name'] = 'Unnamed Road'

if 'highway' in edges_gdf.columns:
    edges_gdf['highway'] = edges_gdf['highway'].apply(
        lambda x: first_or_str(x, 'unclassified')
    )
else:
    edges_gdf['highway'] = 'unclassified'

if 'length' in edges_gdf.columns:
    edges_gdf['length'] = edges_gdf['length'].apply(
        lambda x: float(x) if x is not None else 100.0
    ).fillna(100.0)
else:
    edges_gdf['length'] = 100.0

# Ensure u and v are regular columns (integers stored as strings for JSON compat)
if 'u' in edges_gdf.columns:
    edges_gdf['u'] = edges_gdf['u'].astype(str)
if 'v' in edges_gdf.columns:
    edges_gdf['v'] = edges_gdf['v'].astype(str)

# --- Fix geometry: MultiLineString → LineString ---

def to_linestring(geom):
    if geom is None:
        return None
    if geom.geom_type == 'MultiLineString':
        # Merge if possible, else take longest part
        from shapely.ops import linemerge
        merged = linemerge(geom)
        if merged.geom_type == 'LineString':
            return merged
        return max(geom.geoms, key=lambda g: g.length)
    return geom

edges_gdf['geometry'] = edges_gdf['geometry'].apply(to_linestring)
edges_gdf = edges_gdf[edges_gdf['geometry'].notna()]

# Keep only the columns we care about
keep_edge_cols = [c for c in ['u', 'v', 'osmid', 'name', 'highway', 'length', 'geometry']
                  if c in edges_gdf.columns]
edges_gdf = edges_gdf[keep_edge_cols].copy()

edges_gdf.to_file('road_edges.geojson', driver='GeoJSON')
print(f"      Saved {len(edges_gdf)} edges → road_edges.geojson")

# ─── 7. Validation ─────────────────────────────────────────────────────────────

print()
print("=== VALIDATION ===")

with open('road_nodes.geojson') as f:
    nodes_check = json.load(f)
with open('road_edges.geojson') as f:
    edges_check = json.load(f)

node_count = len(nodes_check['features'])
edge_count = len(edges_check['features'])

print(f"road_nodes.geojson: {node_count} nodes")
print(f"road_edges.geojson: {edge_count} edges")

if edges_check['features']:
    sample = edges_check['features'][0]['properties']
    required = ['u', 'v', 'name', 'highway', 'length']
    missing = [f for f in required if f not in sample]
    if missing:
        print(f"WARNING: missing fields: {missing}")
    else:
        print("All required fields present ✅")
    print(f"Sample edge properties: {sample}")

print()
print("road_nodes.geojson saved ✅")
print("road_edges.geojson saved ✅")
print()
print("Next steps:")
print("  1. Restart uvicorn: uvicorn main_routing:app --reload --port 8000")
print("  2. Check startup log for 'Graph components found: 1'")
print("  3. Visit http://localhost:8000/graph/diagnostics to verify")
