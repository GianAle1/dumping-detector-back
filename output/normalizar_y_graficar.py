# -*- coding: utf-8 -*-
"""
Script: normalizar_y_graficar.py
Autor: [Tu nombre]
Descripción:
Limpia y normaliza los datos de AliExpress, Alibaba y precios nacionales.
Genera imágenes de las variables principales para el análisis de dumping.
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

TIPO_CAMBIO = 3.8  # Tipo de cambio USD → Soles

# ==============================
# 2. FUNCIONES DE LIMPIEZA
# ==============================

def limpiar_precio(valor):
    """Convierte valores tipo 'S/ 23,45' o '$4.5' a float."""
    if pd.isna(valor):
        return np.nan
    valor = str(valor)
    valor = re.sub(r"[^\d.,]", "", valor)
    valor = valor.replace(",", ".")
    try:
        return float(valor)
    except:
        return np.nan

def limpiar_texto(txt):
    """Limpieza básica de texto (minúsculas, sin espacios extras)."""
    if pd.isna(txt):
        return ""
    txt = str(txt).strip().lower()
    txt = re.sub(r"\s+", " ", txt)
    return txt

# ==============================
# 3. CARGA DE DATOS
# ==============================

print("Cargando archivos...")

# Lectura robusta de CSV con comillas y comas internas
ali_exp = pd.read_csv(
    os.path.join(DATA_DIR, "productos_aliexpress.csv"),
    sep=",",
    quotechar='"',
    encoding="utf-8-sig",
    on_bad_lines="skip",
    engine="python"
)

ali_ba = pd.read_csv(
    os.path.join(DATA_DIR, "productos_alibaba.csv"),
    sep=",",
    quotechar='"',
    encoding="utf-8-sig",
    on_bad_lines="skip",
    engine="python"
)

# Archivo Excel nacional
nacionales = pd.read_excel(os.path.join(DATA_DIR, "precios_nacionales.xls"))

print("Archivos cargados correctamente.")

# ==============================
# 4. LIMPIEZA Y NORMALIZACIÓN
# ==============================

for df, name in [(ali_exp, "AliExpress"), (ali_ba, "Alibaba")]:
    df["plataforma"] = name
    df["titulo"] = df["titulo"].apply(limpiar_texto)
    df["precio"] = df["precio"].apply(limpiar_precio)
    df["precio_original"] = df["precio_original"].apply(limpiar_precio)
    df["ventas"] = pd.to_numeric(df["ventas"], errors="coerce").fillna(0)
    df["precio_local"] = df["precio"] * TIPO_CAMBIO
    df["fecha_scraping"] = pd.to_datetime(df["fecha_scraping"], errors="coerce")

# Combinar ambas fuentes
df_internacional = pd.concat([ali_exp, ali_ba], ignore_index=True)

# --- Normalización precios nacionales ---
nacionales["DESCRIPCION_ARTICULO"] = nacionales["DESCRIPCION_ARTICULO"].apply(limpiar_texto)
nacionales["Val_Act"] = (
    nacionales["Val_Act"]
    .astype(str)
    .str.replace(",", ".")
    .apply(limpiar_precio)
)
nacionales = nacionales.dropna(subset=["Val_Act"])
nacionales.rename(columns={"Val_Act": "precio_nacional"}, inplace=True)

# Precio promedio nacional
precio_nac_prom = nacionales["precio_nacional"].mean()

print(f"Precio nacional promedio: S/ {precio_nac_prom:.2f}")

# ==============================
# 5. CÁLCULOS COMPARATIVOS
# ==============================

df_internacional["precio_nacional_prom"] = precio_nac_prom
df_internacional["variacion_pct"] = (
    (df_internacional["precio_nacional_prom"] - df_internacional["precio_local"])
    / df_internacional["precio_nacional_prom"]
) * 100

df_internacional["ratio_precio"] = (
    df_internacional["precio_local"] / df_internacional["precio_nacional_prom"]
)

df_internacional["dumping_flag"] = (df_internacional["variacion_pct"] >= 30).astype(int)

# Guardar dataset limpio
df_internacional.to_csv(os.path.join(OUTPUT_DIR, "productos_normalizados.csv"), index=False, encoding="utf-8-sig")

print("Datos normalizados correctamente. Archivo generado: productos_normalizados.csv")

# ==============================
# 6. VISUALIZACIÓN DE VARIABLES
# ==============================

plt.style.use("seaborn-v0_8-muted")

# --- 1. Comparativa de precios promedio por plataforma ---
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
plt.hist(df_internacional["precio_local"].dropna(), bins=15, color="lightgreen", edgecolor="black")
plt.title("Distribución de precios internacionales normalizados")
plt.xlabel("Precio (S/)")
plt.ylabel("Frecuencia")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "grafico_distribucion_precios.png"))
plt.close()

# --- 3. Casos detectados de dumping ---
plt.figure(figsize=(6, 5))
df_internacional["dumping_flag"].value_counts().plot(
    kind="bar", color=["red", "gray"]
)
plt.title("Casos detectados de dumping (1 = Sí, 0 = No)")
plt.ylabel("Cantidad de productos")
plt.xticks([0, 1], ["Sí", "No"], rotation=0)
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "grafico_dumping_detectado.png"))
plt.close()

print("Gráficos generados exitosamente en la carpeta /output:")
print(" - grafico_precios_plataforma.png")
print(" - grafico_distribucion_precios.png")
print(" - grafico_dumping_detectado.png")

# ==============================
# 7. KPI RESUMEN
# ==============================
total = len(df_internacional)
dumping_count = df_internacional["dumping_flag"].sum()
dumping_rate = (dumping_count / total) * 100

print(f"Total productos analizados: {total}")
print(f"Casos detectados de dumping: {dumping_count} ({dumping_rate:.1f}%)")
print(f"Gráficos disponibles en: {os.path.abspath(OUTPUT_DIR)}")
