import os
import joblib

model_path = r"c:\Users\Hexzc\Documents\Thesis - CodeFish\Compressed File\backend\data\models\model_25yr.pkl"
model = joblib.load(model_path)
print("Classes:", model.classes_)
