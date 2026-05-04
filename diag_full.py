"""
Full diagnostic – traces the flood prediction pipeline end-to-end.
Run from the repo root:  python diag_full.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np
from backend.graph.builder import build_graph
from backend.graph.connectivity import ensure_connected
from backend.prediction.raster_sampler import sample_rasters
from backend.prediction.loader import load_models
from backend.prediction.flood_predictor import predict_scenario_on_the_fly
from backend.routing.weights import compute_wsm_weight

SCENARIO = '25yr'

# ── 1. Build graph ──────────────────────────────────────────────────────────
print("\n[1] Building graph...")
g = build_graph()
g = ensure_connected(g)
print(f"    Nodes: {g.node_count()}, Edges: {g.edge_count()}")

# ── 2. Sample rasters ───────────────────────────────────────────────────────
print("\n[2] Sampling rasters...")
g = sample_rasters(g)

# Count edges with features
with_feats = sum(1 for e in g.edges.values() if e.get('features'))
total_e = len(g.edges)
print(f"    Edges with features: {with_feats}/{total_e}")
if with_feats == 0:
    print("    !! NO FEATURES SAMPLED — rasters may be missing/misaligned")
    sys.exit(1)

# Show a sample feature
sample_edge = next((e for e in g.edges.values() if e.get('features')), None)
print(f"    Sample features: {sample_edge['features']}")

# ── 3. Load models ──────────────────────────────────────────────────────────
print("\n[3] Loading models...")
models = load_models()
print(f"    Loaded scenarios: {list(models.keys())}")
if SCENARIO not in models:
    print(f"    !! Model for '{SCENARIO}' NOT loaded")
    sys.exit(1)

model = models[SCENARIO]
print(f"    Model type: {type(model).__name__}")
print(f"    Model classes: {model.classes_}")
print(f"    Feature names: {getattr(model, 'feature_names_in_', 'N/A')}")

# ── 4. Quick manual prediction check ────────────────────────────────────────
print("\n[4] Manual prediction on sample feature...")
feats = sample_edge['features']
X = np.array([[feats['elevation'], feats['slope'], feats['land_cover'], feats['dist_waterway']]])
print(f"    Input X: {X}")
try:
    pred = model.predict(X)
    proba = model.predict_proba(X)[0]
    expected = sum(i * p for i, p in enumerate(proba)) / (len(proba) - 1)
    print(f"    Predicted class: {pred[0]}")
    print(f"    Probabilities:   {proba}")
    print(f"    flood_proba (expected value): {expected:.4f}")
except Exception as e:
    print(f"    !! Prediction failed: {e}")
    sys.exit(1)

# ── 5. Run on-the-fly inference ─────────────────────────────────────────────
print(f"\n[5] Running predict_scenario_on_the_fly for '{SCENARIO}'...")
predict_scenario_on_the_fly(g, models, SCENARIO)

# ── 6. Check edges after inference ──────────────────────────────────────────
print("\n[6] Checking edges after inference...")
key = f'flood_proba_{SCENARIO}'
has_key = sum(1 for e in g.edges.values() if key in e)
non_zero = sum(1 for e in g.edges.values() if e.get(key, 0) > 0)
all_vals = [e.get(key, 0) for e in g.edges.values() if key in e]
print(f"    Edges with '{key}' key: {has_key}/{total_e}")
print(f"    Edges with non-zero flood_proba: {non_zero}")
if all_vals:
    print(f"    Min: {min(all_vals):.4f}  Max: {max(all_vals):.4f}  Mean: {sum(all_vals)/len(all_vals):.4f}")

# Show a few sample edges
print("\n    Sample edge flood values:")
count = 0
for (u,v), edge in g.edges.items():
    if edge.get('features') and key in edge:
        print(f"      ({u}→{v}) class={edge.get(f'flood_class_{SCENARIO}')} proba={edge.get(key):.4f}")
        count += 1
    if count >= 5:
        break

# ── 7. Simulate scorer reading ───────────────────────────────────────────────
print("\n[7] Simulating scorer read for a few edges...")
count = 0
for (u,v), edge in g.edges.items():
    if edge.get('features'):
        fc  = int(edge.get(f'flood_class_{SCENARIO}', 0) or 0)
        fp  = float(edge.get(f'flood_proba_{SCENARIO}', 0.0) or 0.0)
        wgt = compute_wsm_weight(edge, SCENARIO, {'flood':0.5,'distance':0.3,'road_class':0.2}, g.max_edge_length)
        print(f"      ({u}→{v}) flood_class={fc} flood_proba={fp:.4f} wsm_weight={wgt:.4f}")
        count += 1
    if count >= 5:
        break

print("\n[DONE] Diagnostic complete.")
