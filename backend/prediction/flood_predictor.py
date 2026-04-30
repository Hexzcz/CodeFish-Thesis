import numpy as np
from typing import Dict, Any
from backend.graph.builder import Graph
from backend.core.config import SCENARIOS

def precompute_predictions(graph: Graph, models: Dict[str, Any]) -> Graph:
    """Pre-compute flood predictions for all edges × scenarios."""
    print("[5/6] Pre-computing flood predictions...")

    if not models:
        print("      Skipped — no models available")
        return graph

    for scenario in SCENARIOS:
        model = models.get(scenario)
        if model is None:
            continue

        count = 0
        for (u, v), edge in list(graph.edges.items()):
            if v < u:
                continue
            feats = edge.get('features')
            if feats is None:
                edge[f'flood_class_{scenario}'] = 0
                edge[f'flood_proba_{scenario}'] = 0.0
                rev = graph.edges.get((v, u))
                if rev:
                    rev[f'flood_class_{scenario}'] = 0
                    rev[f'flood_proba_{scenario}'] = 0.0
                continue

            try:
                X = np.array([[
                    feats['elevation'],
                    feats['slope'],
                    feats['land_cover'],
                    feats['dist_waterway'],
                ]])
                flood_class = int(model.predict(X)[0])
                proba = model.predict_proba(X)[0]
                # Use P(class 3) = high flood probability
                flood_proba = float(proba[3] if len(proba) > 3 else max(proba))
            except Exception:
                flood_class = 0
                flood_proba = 0.0

            edge[f'flood_class_{scenario}'] = flood_class
            edge[f'flood_proba_{scenario}'] = flood_proba
            rev = graph.edges.get((v, u))
            if rev:
                rev[f'flood_class_{scenario}'] = flood_class
                rev[f'flood_proba_{scenario}'] = flood_proba

            count += 1

        print(f"      {scenario}: {count} edges processed")
    
    return graph
