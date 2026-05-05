# Flood Susceptibility Prediction: Model Evaluation Report

Based on the predictions made by the optimized XGBoost model (`model_100yr_fabdem_11features_optuna.pkl`) on the 20% hold-out test set, here are the requested evaluation metrics.

## 1. Confusion Matrix
*Raw counts in a 4x4 matrix. Rows represent the **Actual** class, and columns represent the **Predicted** class.*

| | Predicted No Risk (0) | Predicted Low (1) | Predicted Moderate (2) | Predicted High (3) |
|---|:---:|:---:|:---:|:---:|
| **Actual No Risk (0)** | 9,367 | 2,682 | 1,039 | 444 |
| **Actual Low (1)** | 2,449 | 2,108 | 939 | 404 |
| **Actual Moderate (2)** | 1,125 | 1,199 | 3,440 | 1,788 |
| **Actual High (3)** | 361 | 254 | 1,762 | 9,893 |

<br>

## 2. Per Class Metrics

| Class | Precision | Recall | F1-Score | Support |
| :--- | :---: | :---: | :---: | :---: |
| **No Risk (0)** | 0.7042 | 0.6922 | 0.6981 | 13,532 |
| **Low (1)** | 0.3377 | 0.3573 | 0.3472 | 5,900 |
| **Moderate (2)** | 0.4791 | 0.4555 | 0.4670 | 7,552 |
| **High (3)** | 0.7896 | 0.8063 | 0.7979 | 12,270 |

<br>

## 3. Macro-Averaged Metrics
*Averaged equally across all 4 classes, treating each class identically regardless of its support.*

- **Macro Precision:** 0.5776
- **Macro Recall:** 0.5778
- **Macro F1-Score:** 0.5776

<br>

## 4. Overall Accuracy
- **Accuracy:** **0.6320** (63.20%)

<br>

## 5. AUC-ROC (One-vs-Rest)

**AUC per class:**
- **No Risk (0):** 0.8835
- **Low (1):** 0.7652
- **Moderate (2):** 0.7993
- **High (3):** 0.9459

**Macro-averaged AUC:**
- **Overall Macro AUC:** **0.8485**
