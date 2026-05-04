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
            if str(v) < str(u):   # normalise — node IDs can be int or str
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

def predict_scenario_on_the_fly(graph: Graph, models: Dict[str, Any], scenario: str) -> None:
    """Fast batch inference for a single scenario on-the-fly."""
    model = models.get(scenario)
    if not model:
        return

    edges_to_update = []
    X_batch = []
    
    # 1. Gather features
    for (u, v), edge in list(graph.edges.items()):
        if str(v) < str(u):   # normalise to str — node IDs can be int or str
            continue
        feats = edge.get('features')
        if feats:
            edges_to_update.append((u, v, edge))
            X_batch.append([
                feats['elevation'],
                feats['slope'],
                feats['land_cover'],
                feats['dist_waterway']
            ])
        else:
            edge[f'flood_class_{scenario}'] = 0
            edge[f'flood_proba_{scenario}'] = 0.0
            edge[f'flood_proba_array_{scenario}'] = [1.0, 0.0, 0.0, 0.0]
            rev = graph.edges.get((v, u))
            if rev:
                rev[f'flood_class_{scenario}'] = 0
                rev[f'flood_proba_{scenario}'] = 0.0
                rev[f'flood_proba_array_{scenario}'] = [1.0, 0.0, 0.0, 0.0]

    if not X_batch:
        return

    # 2. Batch predict
    try:
        X_array = np.array(X_batch)
        predictions = model.predict(X_array)
        probabilities = model.predict_proba(X_array)
        
        # 3. Apply back to edges
        for idx, (u, v, edge) in enumerate(edges_to_update):
            flood_class = int(predictions[idx])
            proba = probabilities[idx]
            
            # Fix: Calculate a continuous risk score (0 to 1) based on the expected class
            if len(proba) > 1:
                expected_class = sum(i * p for i, p in enumerate(proba))
                flood_proba = float(expected_class / (len(proba) - 1))
            else:
                flood_proba = float(max(proba))
            
            edge[f'flood_class_{scenario}'] = flood_class
            edge[f'flood_proba_{scenario}'] = flood_proba
            edge[f'flood_proba_array_{scenario}'] = proba.tolist()
            
            rev = graph.edges.get((v, u))
            if rev:
                rev[f'flood_class_{scenario}'] = flood_class
                rev[f'flood_proba_{scenario}'] = flood_proba
                rev[f'flood_proba_array_{scenario}'] = proba.tolist()
    except Exception as e:
        print(f"On-the-fly inference failed for {scenario}: {e}")
