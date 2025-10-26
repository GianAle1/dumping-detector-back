# -*- coding: utf-8 -*-
"""
Script: normalizar_y_graficar.py
Autor: Anthony Mendoza
Descripción:
Limpia, normaliza y analiza precios de AliExpress, Alibaba y datos nacionales.
Detecta dumping y genera gráficos comparativos.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import re
import os

# ==============================
# 1. CONFIGURACIÓN INICIAL
# ==============================
DATA_DIR = "data"
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

TIPO_CAMBIO = 3.8  # USD → Soles

# ==============================
# 2. FUNCIONES DE LIMPIEZA
# ==============================

def limpiar_precio(valor):
    """Convierte textos tipo '$4.50', 'S/ 23,45', '18.51', etc. a float."""
    if pd.isna(valor):
        return np.nan
    valor = str(valor).strip()
    valor = valor.replace("PEN", "").replace("S/", "").replace("$", "")
    valor = valor.replace("US", "").replace("USD", "")
    valor = re.sub(r"[^\d,.-]", "", valor)
    if valor == "":
        return np.nan
    # Detectar separador decimal
    if "," in valor and "." in valor:
        if valor.rfind(",") > valor.rfind("."):
            valor = valor.replace(".", "").replace(",", ".")
        else:
            valor = valor.replace(",", "")
    elif "," in valor:
        partes = valor.split(",")
        if len(partes[-1]) in (1, 2):
            valor = valor.replace(",", ".")
        else:
            valor = valor.replace(",", "")
    try:
        return float(valor)
    except ValueError:
        return np.nan


def limpiar_texto(txt):
    """Limpieza básica de texto."""
    if pd.isna(txt):
        return ""
    txt = str(txt).strip().lower()
    txt = re.sub(r"\s+", " ", txt)
    return txt


def cargar_csv_puntoycoma(path):
    """Lee CSV delimitado por punto y coma, limpia encabezados y columnas vacías."""
    df = pd.read_csv(
        path,
        sep=";",
        quotechar='"',
        encoding="utf-8-sig",
        on_bad_lines="skip",
        engine="python"
    )
    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("﻿", "", regex=False)
    )
    df = df.dropna(axis=1, how="all")
    return df

# ==============================
# 3. CARGA DE DATOS
# ==============================
print("Cargando archivos...")

ali_exp = cargar_csv_puntoycoma(os.path.join(DATA_DIR, "productos_aliexpress.csv"))
ali_ba = cargar_csv_puntoycoma(os.path.join(DATA_DIR, "productos_alibaba.csv"))

# Carga de precios nacionales
excel_path = os.path.join(DATA_DIR, "precios_nacionales.xls")
try:
    nacionales = pd.read_excel(excel_path, engine="xlrd")
except Exception:
    nacionales = pd.read_excel(excel_path, engine="openpyxl")

print("Archivos cargados correctamente.")

# ==============================
# 4. LIMPIEZA Y NORMALIZACIÓN
# ==============================

def preparar_dataframe(df, name):
    """Estandariza columnas y calcula precios locales."""
    df["plataforma"] = name
    df["titulo"] = df.get("titulo", "").apply(limpiar_texto)
    df["precio"] = df.get("precio", 0).apply(limpiar_precio)
    df["precio_original"] = df.get("precio_original", 0).apply(limpiar_precio)
    df["ventas"] = pd.to_numeric(df.get("ventas", 0), errors="coerce").fillna(0)
    df["precio_local"] = df["precio"].fillna(0) * TIPO_CAMBIO
    df["fecha_scraping"] = pd.to_datetime(df.get("fecha_scraping", ""), errors="coerce")
    return df[["titulo", "precio", "precio_local", "plataforma", "ventas", "fecha_scraping"]]

ali_exp = preparar_dataframe(ali_exp, "AliExpress")
ali_ba = preparar_dataframe(ali_ba, "Alibaba")

# Combinar datasets
df_internacional = pd.concat([ali_exp, ali_ba], ignore_index=True)
df_internacional = df_internacional.dropna(subset=["precio_local"])
df_internacional = df_internacional[df_internacional["precio_local"] > 0]

# --- Normalización precios nacionales ---
nacionales.columns = (
    nacionales.columns.str.strip()
    .str.lower()
    .str.replace(" ", "_")
)

if "val_act" in nacionales.columns:
    nacionales["precio_nacional"] = nacionales["val_act"].astype(str).apply(limpiar_precio)
else:
    raise ValueError("No se encontró la columna 'Val_Act' en precios_nacionales.xls")

nacionales = nacionales.dropna(subset=["precio_nacional"])
precio_nac_prom = nacionales["precio_nacional"].mean()

print(f"Precio nacional promedio: S/ {precio_nac_prom:.2f}")

# ==============================
# 5. CÁLCULOS COMPARATIVOS
# ==============================
df_internacional["precio_nacional_prom"] = precio_nac_prom
df_internacional["variacion_pct"] = (
    (precio_nac_prom - df_internacional["precio_local"]) / precio_nac_prom
) * 100
df_internacional["ratio_precio"] = df_internacional["precio_local"] / precio_nac_prom
df_internacional["dumping_flag"] = (df_internacional["variacion_pct"] >= 30).astype(int)

# Guardar dataset limpio
output_path = os.path.join(OUTPUT_DIR, "productos_normalizados.csv")
df_internacional.to_csv(output_path, index=False, encoding="utf-8-sig")

print("Datos normalizados correctamente. Archivo generado: productos_normalizados.csv")

# ==============================
# 6. VISUALIZACIÓN DE VARIABLES
# ==============================
plt.style.use("seaborn-v0_8-muted")

# --- 1. Comparativa de precios promedio ---
plt.figure(figsize=(8, 5))
df_internacional.groupby("plataforma")["precio_local"].mean().plot(kind="bar", color="skyblue")
plt.title("Precio promedio internacional por plataforma")
plt.ylabel("Precio en Soles (S/)")
plt.xlabel("Plataforma")
plt.grid(axis="y")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "grafico_precios_plataforma.png"))
plt.close()

# --- 2. Distribución de precios ---
plt.figure(figsize=(8, 5))
plt.hist(df_internacional["precio_local"], bins=20, color="lightgreen", edgecolor="black")
plt.title("Distribución de precios internacionales normalizados")
plt.xlabel("Precio (S/)")
plt.ylabel("Frecuencia")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "grafico_distribucion_precios.png"))
plt.close()

# --- 3. Dumping detectado ---
plt.figure(figsize=(6, 5))
df_internacional["dumping_flag"].value_counts().plot(kind="bar", color=["red", "gray"])
plt.title("Casos detectados de dumping (1 = Sí, 0 = No)")
plt.ylabel("Cantidad de productos")
plt.xticks([0, 1], ["Sí", "No"], rotation=0)
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "grafico_dumping_detectado.png"))
plt.close()

print("Gráficos generados en carpeta /output.")

# ==============================
# 7. KPI RESUMEN
# ==============================
total = len(df_internacional)
dumping_count = df_internacional["dumping_flag"].sum()
dumping_rate = (dumping_count / total) * 100

print(f"Total productos analizados: {total}")
print(f"Casos detectados de dumping: {dumping_count} ({dumping_rate:.1f}%)")
print(f"Gráficos disponibles en: {os.path.abspath(OUTPUT_DIR)}")
