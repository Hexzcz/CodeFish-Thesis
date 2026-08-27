import os
import joblib
from typing import Dict, Any
from backend.core.config import SCENARIOS, MODEL_PATHS

from backend.core.logging import get_logger

log = get_logger(__name__)

def load_models() -> Dict[str, Any]:
    """Load XGBoost models."""
    models: Dict[str, Any] = {}
    log.info("      Loading XGBoost models...")
    loaded = []
    
    for scenario in SCENARIOS:
        path = MODEL_PATHS.get(scenario)
        if path and os.path.exists(path):
            try:
                models[scenario] = joblib.load(path)
                loaded.append(scenario)
            except Exception as e:
                log.warning(f"      WARNING: failed to load {path}: {e}")
        else:
            log.warning(f"      WARNING: {path} not found")

    if loaded:
        log.info(f"      Models loaded: {', '.join(loaded)}")
    else:
        log.info("      No XGBoost models found — flood predictions unavailable")
        
    return models
