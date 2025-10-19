# -*- coding: utf-8 -*-
"""
Entrenamiento de modelos predictivos: Logística, RandomForest, XGBoost, IsolationForest
"""

import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.metrics import classification_report, roc_auc_score
import xgboost as xgb
from ml.preprocessing import load_and_clean_data

def train_all_models():
    df = load_and_clean_data()

    # ====================== VARIABLES ======================
    features = ["precio", "precio_local", "ratio_precio", "plataforma"]
    X = df[features]
    y = df["dumping_flag"]

    # División entrenamiento / prueba
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42
    )

    # Preprocesamiento
    numeric = ["precio", "precio_local", "ratio_precio"]
    categorical = ["plataforma"]

    preproc = ColumnTransformer([
        ("num", StandardScaler(), numeric),
        ("cat", OneHotEncoder(handle_unknown="ignore"), categorical)
    ])

    results = []

    # ====================== 1. REGRESIÓN LOGÍSTICA ======================
    try:
        model_lr = Pipeline([
            ("prep", preproc),
            ("clf", LogisticRegression(max_iter=1000))
        ])
        model_lr.fit(X_train, y_train)
        y_pred_lr = model_lr.predict(X_test)
        auc_lr = roc_auc_score(y_test, model_lr.predict_proba(X_test)[:, 1])
        results.append(["Regresión Logística", auc_lr])
        joblib.dump(model_lr, "ml/model_logistica.pkl")
        print("\n📊 Regresión Logística:\n", classification_report(y_test, y_pred_lr))
        print("AUC:", round(auc_lr, 3))
    except Exception as e:
        print(f"⚠️ Error en Regresión Logística: {e}")
        results.append(["Regresión Logística (error)", None])

    # ====================== 2. RANDOM FOREST ======================
    try:
        model_rf = Pipeline([
            ("prep", preproc),
            ("clf", RandomForestClassifier(
                n_estimators=200, max_depth=6, random_state=42, class_weight="balanced"))
        ])
        model_rf.fit(X_train, y_train)
        y_pred_rf = model_rf.predict(X_test)
        auc_rf = roc_auc_score(y_test, model_rf.predict_proba(X_test)[:, 1])
        results.append(["Random Forest", auc_rf])
        joblib.dump(model_rf, "ml/model_randomforest.pkl")
        print("\n🌲 Random Forest:\n", classification_report(y_test, y_pred_rf))
        print("AUC:", round(auc_rf, 3))
    except Exception as e:
        print(f"⚠️ Error en Random Forest: {e}")
        results.append(["Random Forest (error)", None])

    # ====================== 3. XGBOOST ======================
    try:
        model_xgb = Pipeline([
            ("prep", preproc),
            ("clf", xgb.XGBClassifier(
                n_estimators=300, learning_rate=0.1, max_depth=5,
                subsample=0.8, colsample_bytree=0.8,
                eval_metric="logloss"))
        ])
        model_xgb.fit(X_train, y_train)
        y_pred_xgb = model_xgb.predict(X_test)
        auc_xgb = roc_auc_score(y_test, model_xgb.predict_proba(X_test)[:, 1])
        results.append(["XGBoost", auc_xgb])
        joblib.dump(model_xgb, "ml/model_xgboost.pkl")
        print("\n⚡ XGBoost:\n", classification_report(y_test, y_pred_xgb))
        print("AUC:", round(auc_xgb, 3))
    except Exception as e:
        print(f"⚠️ Error en XGBoost: {e}")
        results.append(["XGBoost (error)", None])

    # ====================== 4. ISOLATION FOREST ======================
    try:
        iso = IsolationForest(contamination=0.05, random_state=42)
        iso.fit(df[numeric])  # ✅ aplicar sobre todo el dataset
        df["anomalia"] = iso.predict(df[numeric])
        joblib.dump(iso, "ml/model_isolation.pkl")
        results.append(["Isolation Forest (no supervisado)", None])
        print("\n🧩 Isolation Forest entrenado (sin etiquetas supervisadas).")
    except Exception as e:
        print(f"⚠️ Error en IsolationForest: {e}")
        results.append(["Isolation Forest (error)", None])

    # ====================== GUARDAR RESULTADOS ======================
    try:
        results_df = pd.DataFrame(results, columns=["Modelo", "AUC"])
        results_df.to_csv("ml/model_results.csv", index=False)
        print("\n✅ Resultados guardados en ml/model_results.csv")
        print(results_df)
    except Exception as e:
        print(f"❌ Error al guardar resultados: {e}")

if __name__ == "__main__":
    train_all_models()
