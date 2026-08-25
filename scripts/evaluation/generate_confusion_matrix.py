import pandas as pd
import numpy as np
import joblib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.metrics import confusion_matrix
import os

def main():
    print("Loading dataset...")
    # Trying the v4 training CSV, which should be the 11-feature one
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
    
    print("Generating Confusion Matrix...")
    cm = confusion_matrix(y_test, y_pred)
    
    # Class labels based on our hazard map: 1=Low, 2=Medium, 3=High
    # If there is a class 0 (No Flood), we include it.
    unique_classes = sorted(list(set(y_test) | set(y_pred)))
    class_names = [f"Class {c}" for c in unique_classes]
    
    if set(unique_classes) == {1, 2, 3}:
        class_names = ["Low (1)", "Medium (2)", "High (3)"]
    elif set(unique_classes) == {0, 1, 2, 3}:
        class_names = ["No Flood (0)", "Low (1)", "Medium (2)", "High (3)"]
        
    plt.figure(figsize=(8, 6))
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                xticklabels=class_names,
                yticklabels=class_names)
                
    plt.title('Confusion Matrix: 11 Features + Optuna (Stable Version)')
    plt.ylabel('Actual Hazard Level')
    plt.xlabel('Predicted Hazard Level')
    plt.tight_layout()
    
    output_png = "confusion_matrix_100yr_fabdem_11features_optuna.png"
    plt.savefig(output_png, dpi=300)
    print(f"\nSuccess! Confusion matrix saved to: {output_png}")

if __name__ == "__main__":
    main()
