# Data pipeline

The scripts that produced everything in `backend/data/`. They run once, in
this order, and are kept because the thesis has to be reproducible — not
because the app needs them at runtime.

| Stage | Directory | What it produces |
|---|---|---|
| 1. Road network | `network/` | `road_nodes.geojson`, `road_edges.geojson`, the district boundary, and the Supabase upload |
| 2. Terrain | `terrain/` | the aligned rasters: elevation, slope, HAND, TWI, flow accumulation, curvature, SPI/STI, land cover, distance to waterways |
| 3. Training | `training/` | the training tables, and the XGBoost models in `backend/data/models/` |
| 4. Evaluation | `evaluation/` | accuracy figures and the confusion matrices behind `docs/model-evaluation.md` |

## Which trainer is the current one

`training/train_xgboost_11features_return_periods.py` is the script that
produced the shipping models (`model_5yr.pkl`, `model_25yr.pkl`,
`model_100yr.pkl`): 3-class, 12 terrain features including HAND, one model per
return period.

The numbered `train_flood_model*.py` and `build_training_table*.py` scripts are
the earlier attempts, in order. They are superseded — do not run them expecting
current results — but they stay in the repo because the thesis reports how the
model got here, and each version is a step in that argument.
