import os
import joblib
from typing import Dict, Any
from backend.core.config import SCENARIOS, MODEL_PATHS

def load_models() -> Dict[str, Any]:
    """Load XGBoost models."""
    models: Dict[str, Any] = {}
    print("[4/6] Loading XGBoost models...")
    loaded = []
    
    for scenario in SCENARIOS:
        path = MODEL_PATHS.get(scenario)
        if path and os.path.exists(path):
            try:
                models[scenario] = joblib.load(path)
                loaded.append(scenario)
            except Exception as e:
                print(f"      WARNING: failed to load {path}: {e}")
        else:
            print(f"      WARNING: {path} not found")

    if loaded:
        print(f"      Models loaded: {', '.join(loaded)}")
    else:
        print("      No XGBoost models found — flood predictions unavailable")
        
    return models
