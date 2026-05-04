import os
import time
from backend.graph.builder import build_graph
from backend.prediction.raster_sampler import sample_rasters
from backend.prediction.loader import load_models
from backend.prediction.flood_predictor import predict_scenario_on_the_fly

print("Building graph...")
g = build_graph()
print(f"Graph nodes: {g.node_count()}, edges: {g.edge_count()}")
print("Sampling rasters...")
g = sample_rasters(g)
print("Loading models...")
models = load_models()
print("Predicting on the fly for 25yr...")
t0 = time.time()
predict_scenario_on_the_fly(g, models, '25yr')
print(f"Done in {time.time()-t0:.2f}s")

# Check a few edges
count = 0
for (u, v), edge in list(g.edges.items()):
    if 'flood_proba_25yr' in edge:
        print(f"Edge {u}-{v}: class={edge.get('flood_class_25yr')}, proba={edge.get('flood_proba_25yr')}")
        count += 1
    if count >= 10:
        break
