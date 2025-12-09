# -*- coding: utf-8 -*-
"""
Script: analisis_relaciones.py
Autor: Anthony Isaac Mendoza Palomino
Descripción:
Analiza las relaciones entre variables de los datos normalizados del proyecto “Detector de Dumping”.
Genera matriz de correlación, gráficos de dispersión, boxplots y un resumen estadístico de relaciones clave.
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
import numpy as np

# ==============================
# 1. CONFIGURACIÓN INICIAL
# ==============================
DATA_DIR = "output"
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

plt.style.use("seaborn-v0_8-muted")

# ==============================
# 2. CARGA DE DATOS
# ==============================
print("📥 Cargando datos normalizados...")

try:
    df = pd.read_csv(os.path.join(DATA_DIR, "productos_normalizados.csv"), sep=";", encoding="utf-8-sig")
except Exception:
    df = pd.read_csv(os.path.join(DATA_DIR, "productos_normalizados.csv"), sep=",", encoding="utf-8-sig")

print(f"✅ Archivo cargado correctamente ({len(df)} filas, {len(df.columns)} columnas).")

# ==============================
# 3. LIMPIEZA BÁSICA
# ==============================
df.replace([np.inf, -np.inf], np.nan, inplace=True)

# Seleccionar solo columnas numéricas para correlación
num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
num_cols = [c for c in num_cols if df[c].notna().sum() > 0]

# ==============================
# 4. MATRIZ DE CORRELACIÓN
# ==============================
print("\n📊 Generando matriz de correlación...")

corr = df[num_cols].corr(method="spearman")  # Spearman es más robusta para escalas no lineales

plt.figure(figsize=(10, 8))
sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", square=True, linewidths=0.5)
plt.title("Matriz de correlación entre variables numéricas")
plt.tight_layout()
plt.savefig(os.path.join(OUTPUT_DIR, "matriz_correlacion.png"))
plt.close()

print("✅ Matriz de correlación guardada como: matriz_correlacion.png")

# ==============================
# 5. RELACIONES CLAVE EN GRÁFICOS
# ==============================

# Precio vs Ventas
if "precio_local" in df.columns and "ventas" in df.columns:
    plt.figure(figsize=(7, 5))
    sns.scatterplot(data=df, x="precio_local", y="ventas", hue="plataforma", alpha=0.7)
    plt.title("Relación entre Precio Local y Ventas")
    plt.xlabel("Precio (S/)")
    plt.ylabel("Ventas estimadas")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "relacion_precio_ventas.png"))
    plt.close()

# Precio por Plataforma
if "precio_local" in df.columns and "plataforma" in df.columns:
    plt.figure(figsize=(7, 5))
    sns.boxplot(data=df, x="plataforma", y="precio_local", palette="Set2")
    plt.title("Distribución de precios por plataforma")
    plt.xlabel("Plataforma")
    plt.ylabel("Precio (S/)")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "boxplot_precios_plataforma.png"))
    plt.close()

# Ratio de precio vs Dumping Flag
if "ratio_precio" in df.columns and "dumping_flag" in df.columns:
    plt.figure(figsize=(6, 5))
    sns.boxplot(data=df, x="dumping_flag", y="ratio_precio", palette=["lightcoral", "lightgreen"])
    plt.title("Relación entre Ratio de Precio y Dumping Detectado")
    plt.xlabel("Dumping (0 = No, 1 = Sí)")
    plt.ylabel("Ratio Precio Internacional / Nacional")
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, "relacion_ratio_dumping.png"))
    plt.close()

# ==============================
# 6. RESUMEN ESTADÍSTICO
# ==============================
print("\n📈 Generando resumen estadístico de correlaciones...")

corr_sorted = (
    corr["dumping_flag"]
    .abs()
    .sort_values(ascending=False)
    .dropna()
)

top_corr = corr_sorted.head(6)
resumen = pd.DataFrame({
    "Variable": top_corr.index,
    "Correlacion_con_Dumping": top_corr.values
})

print("📋 Variables más relacionadas con el dumping:")
print(resumen)

resumen.to_csv(os.path.join(OUTPUT_DIR, "resumen_relaciones.csv"), index=False, encoding="utf-8-sig")

# ==============================
# 7. MENSAJE FINAL
# ==============================
print("\n✅ Análisis de relaciones completado exitosamente.")
print("📂 Archivos generados en la carpeta /output:")
print(" - matriz_correlacion.png")
print(" - relacion_precio_ventas.png")
print(" - boxplot_precios_plataforma.png")
print(" - relacion_ratio_dumping.png")
print(" - resumen_relaciones.csv")
