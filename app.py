from flask import Flask, render_template, request, send_file
from scraper.aliexpress_scraper import obtener_productos_aliexpress
from scraper.temu_scraper import obtener_productos_temu
from scraper.alibaba_scraper import obtener_productos_alibaba
from scraper.madeinchina_scraper import obtener_productos_made_in_china

import pandas as pd
import os

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    productos = []
    archivo_csv = None

    if request.method == "POST":
        producto = request.form["producto"]
        plataforma = request.form["plataforma"]

        if plataforma == "aliexpress":
            productos = obtener_productos_aliexpress(producto)
            archivo_csv = "data/productos_aliexpress.csv"
        elif plataforma == "temu":
            productos = obtener_productos_temu(producto)
            archivo_csv = "data/productos_temu.csv"
        elif plataforma == "alibaba":
            productos = obtener_productos_alibaba(producto)
            archivo_csv = "data/productos_alibaba.csv"
        elif plataforma == "madeinchina":
            productos = obtener_productos_made_in_china(producto)
            archivo_csv = "data/productos_madeinchina.csv"

        if productos:
            os.makedirs("data", exist_ok=True)
            df = pd.DataFrame(productos)
            df.to_csv(archivo_csv, index=False, encoding="utf-8-sig")

    return render_template("index.html", productos=productos)

@app.route("/descargar/<nombre>")
def descargar(nombre):
    path = f"data/{nombre}"
    return send_file(path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
