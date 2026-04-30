import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import accuracy_score, classification_report
from sklearn.utils.class_weight import compute_sample_weight
import optuna
import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import time
import argparse

FEATURES = ['elevation', 'slope', 'land_cover', 'dist_waterway',
            'twi', 'flow_accumulation', 'aspect', 'profile_curvature', 'plan_curvature', 'spi', 'sti']

def main():
    parser = argparse.ArgumentParser(description="Optuna tuning for XGBoost flood model")
    parser.add_argument("--input_csv", required=True, help="Path to training CSV")
    parser.add_argument("--suffix", required=True, help="Suffix for output files")
    parser.add_argument("--trials", type=int, default=50, help="Number of Optuna trials")
    args = parser.parse_args()

    start_time = time.time()
    
    print(f"Loading data from {args.input_csv}...")
    df = pd.read_csv(args.input_csv)

    feature_cols = [f for f in FEATURES if f in df.columns]
    X = df[feature_cols]
    y = df['flood_class']

    # Split: 80% for training/validation (CV) during Optuna, 20% absolute holdout for final test
    X_train_val, X_test, y_train_val, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    def objective(trial):
        # Hyperparameters to tune
        param = {
            'n_estimators': trial.suggest_int('n_estimators', 200, 800, step=100),
            'max_depth': trial.suggest_int('max_depth', 5, 12),
            'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.2, log=True),
            'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
            'subsample': trial.suggest_float('subsample', 0.6, 1.0),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
            'gamma': trial.suggest_float('gamma', 0, 5),
            'eval_metric': 'mlogloss',
            'random_state': 42,
            'n_jobs': -1
        }

        # 3-Fold Cross Validation for robust evaluation
        cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
        cv_scores = []

        for train_idx, val_idx in cv.split(X_train_val, y_train_val):
            X_tr, X_va = X_train_val.iloc[train_idx], X_train_val.iloc[val_idx]
            y_tr, y_va = y_train_val.iloc[train_idx], y_train_val.iloc[val_idx]

            # Re-compute sample weights for each fold
            weights_tr = compute_sample_weight('balanced', y_tr)

            model = xgb.XGBClassifier(**param)
            model.fit(X_tr, y_tr, sample_weight=weights_tr, eval_set=[(X_va, y_va)], verbose=False)

            preds = model.predict(X_va)
            acc = accuracy_score(y_va, preds)
            cv_scores.append(acc)

        # Optuna aims to maximize the mean CV accuracy
        return np.mean(cv_scores)

    print(f"Starting Optuna hyperparameter tuning ({args.trials} trials)...")
    optuna.logging.set_verbosity(optuna.logging.WARNING) # Reduce console spam
    study = optuna.create_study(direction='maximize')
    study.optimize(objective, n_trials=args.trials, show_progress_bar=True)

    print("\nOptuna Tuning Complete!")
    print(f"Best CV Accuracy: {study.best_value:.4f}")
    print("Best Parameters:")
    for key, value in study.best_params.items():
        print(f"  {key}: {value}")

    # Retrain final model on the ENTIRE train/val set using the best parameters
    print("\nRetraining final model on full 80% split using best parameters...")
    final_params = study.best_params
    final_params['eval_metric'] = 'mlogloss'
    final_params['random_state'] = 42
    final_params['n_jobs'] = -1

    weights_train_val = compute_sample_weight('balanced', y_train_val)
    
    final_model = xgb.XGBClassifier(**final_params)
    final_model.fit(X_train_val, y_train_val, sample_weight=weights_train_val)

    # Final Evaluation on the untouched 20% test set
    y_pred = final_model.predict(X_test)
    final_accuracy = accuracy_score(y_test, y_pred)
    
    print(f"\n[FINAL MODEL - {args.suffix}] Overall Accuracy Score on Test Set: {final_accuracy:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))

    # Feature Importance
    importance_df = pd.DataFrame({
        'Feature': feature_cols,
        'Importance': final_model.feature_importances_
    }).sort_values(by='Importance', ascending=False)
    
    print("\nFeature Importance Table:")
    for _, row in importance_df.iterrows():
        print(f"{row['Feature']:<25} {row['Importance']*100:>8.2f}%")

    # Save artifacts
    model_path = f'model_{args.suffix}.pkl'
    csv_path = f'feature_importance_{args.suffix}.csv'
    img_path = f'feature_importance_{args.suffix}.png'
    
    joblib.dump(final_model, model_path)
    importance_df.to_csv(csv_path, index=False)
    
    plt.figure(figsize=(10, 7))
    plt.barh(importance_df['Feature'], importance_df['Importance'], color='purple')
    plt.xlabel('Importance Score')
    plt.ylabel('Feature')
    plt.title(f'Feature Importance - Optuna Tuned ({args.suffix})')
    plt.gca().invert_yaxis()
    plt.tight_layout()
    plt.savefig(img_path)
    plt.close()

    end_time = time.time()
    print(f"\nTotal script execution time: {(end_time - start_time) / 60:.2f} minutes")
    print(f"Model saved: {model_path}")

if __name__ == "__main__":
    main()
