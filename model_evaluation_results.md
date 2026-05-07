# XGBoost 3-Class 12-Feature Flood Model Evaluation with HAND

Models were trained as 3-class classifiers: 0=no risk, 1=low to moderate risk, 2=high risk.
Relabeling was applied before train/test splitting: original 0 -> 0, original 1/2 -> 1, original 3 -> 2.
Feature rasters were read from the same aligned map layers used by the backend/current layer stack.
HAND was derived from the DEM using fill depressions, D8 flow direction, D8 flow accumulation, stream extraction by thresholding, and elevation above stream.
Class-weighted training was removed; no `sample_weight` was passed to XGBoost.
All XGBoost hyperparameters, train/test split settings, and random seeds were kept identical to the prior baseline experiments.

Features: `elevation`, `slope`, `land_cover`, `dist_waterway`, `twi`, `flow_accumulation`, `aspect`, `profile_curvature`, `plan_curvature`, `spi`, `sti`, `HAND`

## 5yr

- Training rows: 19,008
- Class distribution: 0=9,795, 1=5,908, 2=3,305
- **Accuracy:** 0.7672
- **Macro Precision:** 0.7726
- **Macro Recall:** 0.7457
- **Macro F1-Score:** 0.7541
- **Weighted Precision:** 0.7621
- **Weighted Recall:** 0.7672
- **Weighted F1-Score:** 0.7591
- **Macro AUC OVR:** 0.9002
- Training used no `sample_weight`.
- Backend model: `backend\data\models\model_5yr.pkl`
- Confusion matrix image: `backend\data\model_reports\confusion_matrix_5yr_12features_hand_3class.png`
- Feature importance: `backend\data\model_reports\feature_importance_5yr_12features_hand_3class.csv`
- Feature importance PNG: `backend\data\model_reports\feature_importance_5yr_12features_hand_3class.png`
- HAND importance rank: `2` of `12` with importance `0.124856`.

### Summary Comparison Against Previous 4-Class HAND Baseline

| Metric | Collapsed Previous 4-Class HAND | New 3-Class HAND | Delta |
|---|---:|---:|---:|
| Accuracy | 0.7488 | 0.7672 | +0.0184 |
| Macro Precision | 0.7575 | 0.7726 | +0.0150 |
| Macro Recall | 0.7231 | 0.7457 | +0.0226 |
| Macro F1 | 0.7231 | 0.7541 | +0.0310 |
| Weighted Precision | 0.7450 | 0.7621 | +0.0172 |
| Weighted Recall | 0.7488 | 0.7672 | +0.0184 |
| Weighted F1 | 0.7287 | 0.7591 | +0.0305 |
| Macro AUC OVR | n/a from confusion matrix | 0.9002 | n/a |

### Confusion Matrix

| Actual \ Predicted | No Risk (0) | Low to Moderate Risk (1) | High Risk (2) |
|---|---:|---:|---:|
| No Risk (0) | 1,751 | 194 | 14 |
| Low to Moderate Risk (1) | 471 | 631 | 80 |
| High Risk (2) | 41 | 85 | 535 |

### Per-Class Metrics

| Class | Precision | Recall | F1-Score | Support | AUC OVR |
|---|---:|---:|---:|---:|---:|
| No Risk (0) | 0.7738 | 0.8938 | 0.8295 | 1,959 | 0.8919 |
| Low to Moderate Risk (1) | 0.6934 | 0.5338 | 0.6033 | 1,182 | 0.8316 |
| High Risk (2) | 0.8506 | 0.8094 | 0.8295 | 661 | 0.9770 |

### F1 Comparison Against Collapsed 4-Class HAND Baseline

| Class | Collapsed Previous 4-Class F1 | New 3-Class F1 | Delta | Flag |
|---|---:|---:|---:|---|
| No Risk (0) | 0.8216 | 0.8295 | +0.0079 | no significant degradation |
| Low to Moderate Risk (1) | 0.5186 | 0.6033 | +0.0847 | improved |
| High Risk (2) | 0.8291 | 0.8295 | +0.0004 | no significant degradation |

Merged intermediate class improved: **yes**.
High-risk class avoided significant degradation (threshold `0.020` F1): **yes**.

### Feature Importance

![5yr feature importance](backend/data/model_reports/feature_importance_5yr_12features_hand_3class.png)

| Rank | Feature | Importance |
|---:|---|---:|
| 1 | dist_waterway | 0.218413 |
| 2 | HAND | 0.124856 |
| 3 | elevation | 0.120236 |
| 4 | land_cover | 0.077400 |
| 5 | aspect | 0.062883 |
| 6 | slope | 0.061240 |
| 7 | flow_accumulation | 0.060586 |
| 8 | twi | 0.059057 |
| 9 | plan_curvature | 0.056744 |
| 10 | sti | 0.054403 |
| 11 | profile_curvature | 0.054227 |
| 12 | spi | 0.049955 |

## 25yr

- Training rows: 19,008
- Class distribution: 0=8,088, 1=6,295, 2=4,625
- **Accuracy:** 0.7546
- **Macro Precision:** 0.7626
- **Macro Recall:** 0.7579
- **Macro F1-Score:** 0.7592
- **Weighted Precision:** 0.7525
- **Weighted Recall:** 0.7546
- **Weighted F1-Score:** 0.7524
- **Macro AUC OVR:** 0.9016
- Training used no `sample_weight`.
- Backend model: `backend\data\models\model_25yr.pkl`
- Confusion matrix image: `backend\data\model_reports\confusion_matrix_25yr_12features_hand_3class.png`
- Feature importance: `backend\data\model_reports\feature_importance_25yr_12features_hand_3class.csv`
- Feature importance PNG: `backend\data\model_reports\feature_importance_25yr_12features_hand_3class.png`
- HAND importance rank: `1` of `12` with importance `0.182855`.

### Summary Comparison Against Previous 4-Class HAND Baseline

| Metric | Collapsed Previous 4-Class HAND | New 3-Class HAND | Delta |
|---|---:|---:|---:|
| Accuracy | 0.7412 | 0.7546 | +0.0134 |
| Macro Precision | 0.7494 | 0.7626 | +0.0132 |
| Macro Recall | 0.7410 | 0.7579 | +0.0169 |
| Macro F1 | 0.7350 | 0.7592 | +0.0242 |
| Weighted Precision | 0.7394 | 0.7525 | +0.0131 |
| Weighted Recall | 0.7412 | 0.7546 | +0.0134 |
| Weighted F1 | 0.7295 | 0.7524 | +0.0229 |
| Macro AUC OVR | n/a from confusion matrix | 0.9016 | n/a |

### Confusion Matrix

| Actual \ Predicted | No Risk (0) | Low to Moderate Risk (1) | High Risk (2) |
|---|---:|---:|---:|
| No Risk (0) | 1,315 | 272 | 31 |
| Low to Moderate Risk (1) | 402 | 764 | 93 |
| High Risk (2) | 38 | 97 | 790 |

### Per-Class Metrics

| Class | Precision | Recall | F1-Score | Support | AUC OVR |
|---|---:|---:|---:|---:|---:|
| No Risk (0) | 0.7493 | 0.8127 | 0.7797 | 1,618 | 0.8917 |
| Low to Moderate Risk (1) | 0.6743 | 0.6068 | 0.6388 | 1,259 | 0.8337 |
| High Risk (2) | 0.8643 | 0.8541 | 0.8592 | 925 | 0.9794 |

### F1 Comparison Against Collapsed 4-Class HAND Baseline

| Class | Collapsed Previous 4-Class F1 | New 3-Class F1 | Delta | Flag |
|---|---:|---:|---:|---|
| No Risk (0) | 0.7826 | 0.7797 | -0.0029 | no significant degradation |
| Low to Moderate Risk (1) | 0.5735 | 0.6388 | +0.0653 | improved |
| High Risk (2) | 0.8489 | 0.8592 | +0.0103 | no significant degradation |

Merged intermediate class improved: **yes**.
High-risk class avoided significant degradation (threshold `0.020` F1): **yes**.

### Feature Importance

![25yr feature importance](backend/data/model_reports/feature_importance_25yr_12features_hand_3class.png)

| Rank | Feature | Importance |
|---:|---|---:|
| 1 | HAND | 0.182855 |
| 2 | dist_waterway | 0.174631 |
| 3 | elevation | 0.118738 |
| 4 | land_cover | 0.077389 |
| 5 | aspect | 0.064809 |
| 6 | flow_accumulation | 0.061726 |
| 7 | slope | 0.059112 |
| 8 | twi | 0.055793 |
| 9 | plan_curvature | 0.053997 |
| 10 | sti | 0.052357 |
| 11 | profile_curvature | 0.050122 |
| 12 | spi | 0.048472 |

## 100yr

- Training rows: 19,008
- Class distribution: 0=7,067, 1=6,491, 2=5,450
- **Accuracy:** 0.7609
- **Macro Precision:** 0.7649
- **Macro Recall:** 0.7671
- **Macro F1-Score:** 0.7655
- **Weighted Precision:** 0.7588
- **Weighted Recall:** 0.7609
- **Weighted F1-Score:** 0.7594
- **Macro AUC OVR:** 0.9069
- Training used no `sample_weight`.
- Backend model: `backend\data\models\model_100yr.pkl`
- Confusion matrix image: `backend\data\model_reports\confusion_matrix_100yr_12features_hand_3class.png`
- Feature importance: `backend\data\model_reports\feature_importance_100yr_12features_hand_3class.csv`
- Feature importance PNG: `backend\data\model_reports\feature_importance_100yr_12features_hand_3class.png`
- HAND importance rank: `1` of `12` with importance `0.190115`.

### Summary Comparison Against Previous 4-Class HAND Baseline

| Metric | Collapsed Previous 4-Class HAND | New 3-Class HAND | Delta |
|---|---:|---:|---:|
| Accuracy | 0.7562 | 0.7609 | +0.0047 |
| Macro Precision | 0.7653 | 0.7649 | -0.0004 |
| Macro Recall | 0.7615 | 0.7671 | +0.0056 |
| Macro F1 | 0.7542 | 0.7655 | +0.0114 |
| Weighted Precision | 0.7587 | 0.7588 | +0.0001 |
| Weighted Recall | 0.7562 | 0.7609 | +0.0047 |
| Weighted F1 | 0.7479 | 0.7594 | +0.0115 |
| Macro AUC OVR | n/a from confusion matrix | 0.9069 | n/a |

### Confusion Matrix

| Actual \ Predicted | No Risk (0) | Low to Moderate Risk (1) | High Risk (2) |
|---|---:|---:|---:|
| No Risk (0) | 1,097 | 284 | 33 |
| Low to Moderate Risk (1) | 347 | 832 | 119 |
| High Risk (2) | 33 | 93 | 964 |

### Per-Class Metrics

| Class | Precision | Recall | F1-Score | Support | AUC OVR |
|---|---:|---:|---:|---:|---:|
| No Risk (0) | 0.7427 | 0.7758 | 0.7589 | 1,414 | 0.8991 |
| Low to Moderate Risk (1) | 0.6882 | 0.6410 | 0.6637 | 1,298 | 0.8471 |
| High Risk (2) | 0.8638 | 0.8844 | 0.8740 | 1,090 | 0.9744 |

### F1 Comparison Against Collapsed 4-Class HAND Baseline

| Class | Collapsed Previous 4-Class F1 | New 3-Class F1 | Delta | Flag |
|---|---:|---:|---:|---|
| No Risk (0) | 0.7654 | 0.7589 | -0.0065 | no significant degradation |
| Low to Moderate Risk (1) | 0.6221 | 0.6637 | +0.0416 | improved |
| High Risk (2) | 0.8750 | 0.8740 | -0.0010 | no significant degradation |

Merged intermediate class improved: **yes**.
High-risk class avoided significant degradation (threshold `0.020` F1): **yes**.

### Feature Importance

![100yr feature importance](backend/data/model_reports/feature_importance_100yr_12features_hand_3class.png)

| Rank | Feature | Importance |
|---:|---|---:|
| 1 | HAND | 0.190115 |
| 2 | dist_waterway | 0.173694 |
| 3 | elevation | 0.120325 |
| 4 | land_cover | 0.073163 |
| 5 | aspect | 0.064032 |
| 6 | flow_accumulation | 0.060584 |
| 7 | twi | 0.059854 |
| 8 | slope | 0.057271 |
| 9 | profile_curvature | 0.051924 |
| 10 | plan_curvature | 0.051893 |
| 11 | sti | 0.049722 |
| 12 | spi | 0.047422 |
