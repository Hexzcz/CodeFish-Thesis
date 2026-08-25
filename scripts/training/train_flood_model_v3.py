import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from sklearn.utils.class_weight import compute_sample_weight
import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import time
import argparse

FEATURES = ['elevation', 'slope', 'land_cover', 'dist_waterway',
            'twi', 'flow_accumulation', 'aspect', 'profile_curvature', 'plan_curvature']

def train_model():
    parser = argparse.ArgumentParser(description="Train XGBoost flood model with extended features")
    parser.add_argument("--input_csv", required=True, help="Path to training CSV")
    parser.add_argument("--suffix", required=True, help="Suffix for output files (e.g., 100yr_v2)")
    args = parser.parse_args()

    start_time = time.time()
    
    print(f"Loading data from {args.input_csv}...")
    df = pd.read_csv(args.input_csv)

    # Use all available feature columns
    feature_cols = [f for f in FEATURES if f in df.columns]
    print(f"Features used ({len(feature_cols)}): {feature_cols}")

    X = df[feature_cols]
    y = df['flood_class']

    print(f"Splitting data for {args.suffix}...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    
    print("Computing sample weights...")
    sample_weights = compute_sample_weight('balanced', y_train)
    
    print(f"Training XGBoost model for {args.suffix}...")
    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric='mlogloss',
        random_state=42,
        n_jobs=-1
    )
    
    model.fit(X_train, y_train, sample_weight=sample_weights)
    
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"\n[{args.suffix}] Overall Accuracy Score: {accuracy:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))
    
    importance_df = pd.DataFrame({
        'Feature': feature_cols,
        'Importance': model.feature_importances_
    }).sort_values(by='Importance', ascending=False)
    
    print("\nFeature Importance Table:")
    for _, row in importance_df.iterrows():
        print(f"{row['Feature']:<25} {row['Importance']*100:>8.2f}%")
    
    model_path = f'model_{args.suffix}.pkl'
    csv_path = f'feature_importance_{args.suffix}.csv'
    img_path = f'feature_importance_{args.suffix}.png'
    
    joblib.dump(model, model_path)
    importance_df.to_csv(csv_path, index=False)
    
    plt.figure(figsize=(10, 7))
    plt.barh(importance_df['Feature'], importance_df['Importance'], color='steelblue')
    plt.xlabel('Importance Score')
    plt.ylabel('Feature')
    plt.title(f'Feature Importance - Flood Hazard ({args.suffix})')
    plt.gca().invert_yaxis()
    plt.tight_layout()
    plt.savefig(img_path)
    plt.close()
    
    end_time = time.time()
    print(f"\nTotal training time: {end_time - start_time:.2f} seconds")
    print(f"Model saved: {model_path}")

if __name__ == "__main__":
    train_model()
