"""
train_flood_model_v6_ensemble.py
================================
Stacking Ensemble: XGBoost + Random Forest → Logistic Regression meta-learner.

NOTE: This script is for RESEARCH/COMPARISON ONLY.
      The model output (.pkl) is saved separately and is NOT used by the live system
      until explicitly swapped in backend/core/config.py.

Architecture:
  Base Learner 1: XGBoost (best Optuna params from previous run)
  Base Learner 2: Random Forest Classifier
  Meta-Learner:   Logistic Regression (simple, prevents overfitting)
"""

import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.ensemble import StackingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from sklearn.utils.class_weight import compute_sample_weight
import sklearn
sklearn.set_config(enable_metadata_routing=True)
import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import time
import argparse

FEATURES = ['elevation', 'slope', 'land_cover', 'dist_waterway',
            'twi', 'flow_accumulation', 'aspect', 'profile_curvature',
            'plan_curvature', 'spi', 'sti']

def main():
    parser = argparse.ArgumentParser(description="[RESEARCH ONLY] Stacking Ensemble flood model")
    parser.add_argument("--input_csv", required=True, help="Path to training CSV (11 features)")
    parser.add_argument("--suffix", required=True, help="Suffix for output files")
    args = parser.parse_args()

    start_time = time.time()

    print(f"[RESEARCH ONLY] Stacking Ensemble Training")
    print(f"Loading data from {args.input_csv}...")
    df = pd.read_csv(args.input_csv)

    feature_cols = [f for f in FEATURES if f in df.columns]
    print(f"Features used ({len(feature_cols)}): {feature_cols}")

    X = df[feature_cols]
    y = df['flood_class']

    # 80/20 split — same seed as all other models for fair comparison
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    sample_weights = compute_sample_weight('balanced', y_train)

    # ─── Base Learner 1: XGBoost ──────────────────────────────────────────────
    # Using the best Optuna params discovered in previous run
    xgb_model = xgb.XGBClassifier(
        n_estimators=600,
        max_depth=8,
        learning_rate=0.05,
        min_child_weight=3,
        subsample=0.8,
        colsample_bytree=0.75,
        gamma=0.5,
        eval_metric='mlogloss',
        random_state=42,
        n_jobs=-1
    )
    # Enable metadata routing so sample_weight can be passed through the stack
    xgb_model.set_fit_request(sample_weight=True)

    # ─── Base Learner 2: Random Forest ───────────────────────────────────────
    rf_model = RandomForestClassifier(
        n_estimators=300,
        max_depth=20,
        min_samples_split=5,
        min_samples_leaf=2,
        class_weight='balanced',  # RF's own class balancing mechanism
        random_state=42,
        n_jobs=-1
    )
    # RF uses class_weight internally, so tell sklearn to ignore sample_weight for RF
    rf_model.set_fit_request(sample_weight=False)

    # ─── Meta-Learner: Logistic Regression ────────────────────────────────────
    # Simple meta-learner. It receives the output probabilities from both base
    # models and learns the best weighted combination.
    # passthrough=True also gives the meta-learner the original features,
    # which can help it understand context.
    meta_learner = LogisticRegression(
        max_iter=1000,
        class_weight='balanced',
        random_state=42
    )

    # ─── Stacking Classifier ─────────────────────────────────────────────────
    # stack_method='predict_proba' passes class probabilities (not just the
    # winning class) to the meta-learner, giving it much richer information.
    ensemble = StackingClassifier(
        estimators=[
            ('xgb', xgb_model),
            ('rf', rf_model)
        ],
        final_estimator=meta_learner,
        stack_method='predict_proba',
        passthrough=False,       # Only pass base model outputs to meta-learner
        cv=3,                    # 3-fold CV to train the meta-learner (prevents overfitting)
        n_jobs=-1
    )

    print("Training Stacking Ensemble (XGBoost + Random Forest -> Logistic Regression)...")
    print("  This trains with 3-fold cross-validation internally. Please wait...")
    ensemble.fit(X_train, y_train, sample_weight=sample_weights)

    # ─── Evaluation ──────────────────────────────────────────────────────────
    y_pred = ensemble.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)

    print(f"\n[ENSEMBLE RESULT - {args.suffix}] Overall Accuracy: {accuracy:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))

    # ─── Feature Importance (from XGBoost base model only) ───────────────────
    xgb_fitted = ensemble.named_estimators_['xgb']
    rf_fitted  = ensemble.named_estimators_['rf']

    xgb_importance = xgb_fitted.feature_importances_
    rf_importance  = rf_fitted.feature_importances_

    importance_df = pd.DataFrame({
        'Feature':         feature_cols,
        'XGBoost_Imp':     xgb_importance,
        'RF_Imp':          rf_importance,
        'Average_Imp':     (xgb_importance + rf_importance) / 2
    }).sort_values(by='Average_Imp', ascending=False)

    print("\nFeature Importance (Averaged across XGBoost & Random Forest):")
    for _, row in importance_df.iterrows():
        print(f"  {row['Feature']:<25} XGB: {row['XGBoost_Imp']*100:>5.1f}%  |  RF: {row['RF_Imp']*100:>5.1f}%  |  Avg: {row['Average_Imp']*100:>5.1f}%")

    # ─── Save Results ─────────────────────────────────────────────────────────
    model_path = f'model_{args.suffix}.pkl'
    csv_path   = f'feature_importance_{args.suffix}.csv'
    img_path   = f'feature_importance_{args.suffix}.png'

    # NOTE: This saves the FULL ensemble (all 3 models) as one object
    joblib.dump(ensemble, model_path)
    importance_df.to_csv(csv_path, index=False)

    plt.figure(figsize=(12, 7))
    x = np.arange(len(feature_cols))
    width = 0.35
    bars1 = plt.barh(x - width/2, importance_df['XGBoost_Imp'], width, label='XGBoost', color='steelblue')
    bars2 = plt.barh(x + width/2, importance_df['RF_Imp'],      width, label='Random Forest', color='seagreen')
    plt.yticks(x, importance_df['Feature'])
    plt.xlabel('Importance Score')
    plt.title(f'Feature Importance Comparison - Ensemble ({args.suffix})')
    plt.legend()
    plt.tight_layout()
    plt.savefig(img_path)
    plt.close()

    end_time = time.time()
    print(f"\nTotal training time: {(end_time - start_time) / 60:.2f} minutes")
    print(f"[RESEARCH ONLY] Ensemble model saved: {model_path}")
    print("  -> To use in production, update backend/core/config.py with the new model path.")

if __name__ == "__main__":
    main()
