import pandas as pd
import numpy as np
import joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score, roc_auc_score
import os

def main():
    print("Loading dataset...")
    csv_file = "training_100yr_fabdem_v4.csv"
    if not os.path.exists(csv_file):
        print(f"Error: {csv_file} not found.")
        return
        
    df = pd.read_csv(csv_file)
    
    FEATURES = ['elevation', 'slope', 'land_cover', 'dist_waterway',
                'twi', 'flow_accumulation', 'aspect', 'profile_curvature', 'plan_curvature', 'spi', 'sti']
                
    feature_cols = [f for f in FEATURES if f in df.columns]
    X = df[feature_cols]
    y = df['flood_class']
    
    print(f"Performing exact same 80/20 split (random_state=42) on {len(df)} rows...")
    _, X_test, _, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    
    model_file = "model_100yr_fabdem_11features_optuna.pkl"
    print(f"Loading model: {model_file}...")
    model = joblib.load(model_file)
    
    print("Predicting on the 20% test set...")
    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)
    
    print("\n--- CONFUSION MATRIX ---")
    cm = confusion_matrix(y_test, y_pred)
    print("Rows: Actual (0 to 3), Cols: Predicted (0 to 3)")
    print(cm)
    
    print("\n--- CLASSIFICATION REPORT ---")
    # Using digits=4 for better precision
    report = classification_report(y_test, y_pred, digits=4)
    print(report)
    
    acc = accuracy_score(y_test, y_pred)
    print(f"\n--- OVERALL ACCURACY ---")
    print(f"{acc:.4f}")
    
    print("\n--- ROC AUC (One-vs-Rest) ---")
    unique_classes = sorted(list(set(y_test)))
    
    # Calculate AUC per class
    for i, cls in enumerate(unique_classes):
        # Create binary true labels for this class
        y_test_bin = (y_test == cls).astype(int)
        # Use probability of this class
        y_prob_cls = y_prob[:, i]
        auc_cls = roc_auc_score(y_test_bin, y_prob_cls)
        class_name = {0: "No Risk (0)", 1: "Low (1)", 2: "Moderate (2)", 3: "High (3)"}.get(cls, f"Class {cls}")
        print(f"AUC for {class_name}: {auc_cls:.4f}")
        
    macro_auc = roc_auc_score(y_test, y_prob, multi_class='ovr', average='macro')
    print(f"Macro-averaged AUC: {macro_auc:.4f}")

if __name__ == "__main__":
    main()
