# -*- coding: utf-8 -*-
"""
Preprocessing para unir datasets internacionales (Alibaba, AliExpress)
con precios nacionales y generar dataset de entrenamiento limpio.
"""

import pandas as pd
import numpy as np
import re


def load_and_clean_data():
    # === Cargar datos ===
    ali_baba = pd.read_csv("data/productos_alibaba.csv", sep=";")
    ali_express = pd.read_csv("data/productos_aliexpress.csv", sep=";")
    nacional = pd.read_excel("data/precios_nacionales.xls")

    # === Limpieza mínima ===
    for df in [ali_baba, ali_express]:
        df["titulo"] = df["titulo"].astype(str).str.lower()
        df["precio"] = pd.to_numeric(df["precio"], errors="coerce")
        df["plataforma"] = df["plataforma"].fillna("Desconocida")

    # Calcular precio local promedio (soles)
    nacional["precio_local"] = nacional["Val_Act"] / nacional["St_Act"].replace(0, np.nan)
    nacional["DESCRIPCION_ARTICULO"] = nacional["DESCRIPCION_ARTICULO"].astype(str).str.lower()

    # === Filtrar solo camisas/pantalones (ejemplo textil) ===
    filtro = "camisa|shirt|pantalon|pants|trouser"
    ali_baba = ali_baba[ali_baba["titulo"].str.contains(filtro, na=False)]
    ali_express = ali_express[ali_express["titulo"].str.contains(filtro, na=False)]
    nacional = nacional[nacional["DESCRIPCION_ARTICULO"].str.contains("camisa|pantalon", na=False)]

    # === Unir ambos internacionales ===
    intl = pd.concat([ali_baba, ali_express], ignore_index=True)

    # === Categorizar tipo de prenda ===
    intl["categoria"] = intl["titulo"].apply(lambda x: "camisa" if "shirt" in x or "camisa" in x else "pantalon")
    nacional["categoria"] = nacional["DESCRIPCION_ARTICULO"].apply(lambda x: "camisa" if "camisa" in x else "pantalon")

    # === Merge por categoría ===
    df = pd.merge(intl, nacional[["categoria", "precio_local"]], on="categoria", how="left")

    # === Calcular ratio_precio de forma segura ===
    df["ratio_precio"] = df["precio"] / df["precio_local"]

    # === Limpieza de valores inválidos ===
    # Reemplazar infinitos o NaN
    df.replace([np.inf, -np.inf], np.nan, inplace=True)
    df.dropna(subset=["precio", "precio_local", "ratio_precio"], inplace=True)

    # Eliminar valores con precio local o internacional <= 0
    df = df[(df["precio"] > 0) & (df["precio_local"] > 0)]

    # Limitar ratios extremadamente grandes (outliers)
    df["ratio_precio"] = df["ratio_precio"].clip(lower=0, upper=10)

    # === Etiquetar posible dumping ===
    df["dumping_flag"] = (df["ratio_precio"] < 0.7).astype(int)

    # === Verificación final ===
    if df.empty:
        raise ValueError("El dataset final está vacío después de la limpieza. Revisa los datos de entrada.")

    print(f"✅ Dataset preparado: {len(df)} registros limpios, {df['dumping_flag'].sum()} posibles dumping.")
    return df
