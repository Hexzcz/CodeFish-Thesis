import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.utils.class_weight import compute_sample_weight
import joblib
import matplotlib.pyplot as plt
import time
import os

def train_model():
    start_time = time.time()
    
    # 1. Load data
    input_file = 'training_5yr.csv'
    print(f"Loading data from {input_file}...")
    df = pd.read_csv(input_file)
    
    # 2. Split into X and y
    X = df[['elevation', 'slope', 'land_cover', 'dist_waterway']]
    y = df['flood_class']
    
    # 3. Train-test split (80/20, stratified)
    print("Splitting data into train and test sets...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    
    # 4. Handle class imbalance
    print("Computing sample weights for class imbalance...")
    sample_weights = compute_sample_weight('balanced', y_train)
    
    # 5. Initialize and train XGBoost classifier
    print("Initializing and training XGBoost classifier...")
    model = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        use_label_encoder=False,
        eval_metric='mlogloss',
        random_state=42,
        n_jobs=-1
    )
    
    model.fit(X_train, y_train, sample_weight=sample_weights)
    
    # 6. Evaluation
    print("Evaluating model...")
    y_pred = model.predict(X_test)
    
    accuracy = accuracy_score(y_test, y_pred)
    print(f"\nOverall Accuracy Score: {accuracy:.4f}")
    
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))
    
    print("\nConfusion Matrix:")
    print(confusion_matrix(y_test, y_pred))
    
    # 7. Feature Importance
    importances = model.feature_importances_
    features = X.columns
    importance_df = pd.DataFrame({
        'Feature': features,
        'Importance': importances
    }).sort_values(by='Importance', ascending=False)
    
    print("\nFeature Importance Ranked Table:")
    print(f"{'Feature':<20} {'Importance':<10}")
    for index, row in importance_df.iterrows():
        print(f"{row['Feature']:<20} {row['Importance']*100:>8.2f}%")
    
    # 8. Save output files
    print("\nSaving model and feature importance data...")
    joblib.dump(model, 'model_5yr.pkl')
    importance_df.to_csv('feature_importance_5yr.csv', index=False)
    
    # 9. Plot feature importance
    plt.figure(figsize=(10, 6))
    plt.barh(importance_df['Feature'], importance_df['Importance'], color='skyblue')
    plt.xlabel('Importance Score')
    plt.ylabel('Feature')
    plt.title('Feature Importance for Flood Hazard Prediction (5yr)')
    plt.gca().invert_yaxis()
    plt.tight_layout()
    plt.savefig('feature_importance_5yr.png')
    plt.close()
    
    end_time = time.time()
    training_duration = end_time - start_time
    print(f"\nTotal training time: {training_duration:.2f} seconds")

if __name__ == "__main__":
    train_model()
