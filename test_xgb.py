import os
import joblib
import numpy as np

model_path = r"c:\Users\Hexzc\Documents\Thesis - CodeFish\Compressed File\backend\data\models\model_25yr.pkl"
try:
    model = joblib.load(model_path)
    print("Model loaded.")
    print("Type:", type(model))
    if hasattr(model, 'feature_names_in_'):
        print("Feature names:", model.feature_names_in_)
    else:
        print("No feature names.")

    X = np.array([[20.0, 2.2, 50.0, 275.0]])
    try:
        preds = model.predict(X)
        print("NumPy Predict:", preds)
    except Exception as e:
        print("NumPy Predict Failed:", e)

    import pandas as pd
    if hasattr(model, 'feature_names_in_'):
        X_df = pd.DataFrame(X, columns=model.feature_names_in_)
        preds_df = model.predict(X_df)
        print("Pandas Predict:", preds_df)

except Exception as e:
    print("Failed to load or test:", e)
