# /ml/predict.py
import joblib
import pandas as pd
import os

MODEL_PATH = os.path.join("ml", "model_xgboost.pkl")

def load_model():
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError("El modelo predictivo no está entrenado aún.")
    return joblib.load(MODEL_PATH)

def predict_dumping(precio_importado: float, precio_local: float, plataforma: str):
    model = load_model()
    ratio = precio_importado / precio_local

    X = pd.DataFrame([{
        "precio": precio_importado,
        "precio_local": precio_local,
        "ratio_precio": ratio,
        "plataforma": plataforma
    }])

    proba = model.predict_proba(X)[0, 1]
    resultado = {
        "probabilidad_dumping": round(float(proba), 3),
        "decision": "Dumping probable" if proba >= 0.7 else "Precio competitivo"
    }
    return resultado
