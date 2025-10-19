# -*- coding: utf-8 -*-
"""
Evaluación comparativa y visualización de resultados de los modelos
"""
import pandas as pd
import matplotlib.pyplot as plt

def compare_models():
    results = pd.read_csv("ml/model_results.csv")
    results = results.sort_values(by="AUC", ascending=False)
    print("\n📈 Comparativa de modelos:\n", results)

    plt.barh(results["Modelo"], results["AUC"], color="skyblue")
    plt.xlabel("AUC ROC")
    plt.title("Comparación de desempeño de modelos predictivos")
    plt.gca().invert_yaxis()
    plt.show()

if __name__ == "__main__":
    compare_models()
