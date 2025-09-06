from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

from scraper.aliexpress_scraper import obtener_productos_aliexpress
from scraper.temu_scraper import obtener_productos_temu
from scraper.alibaba_scraper import obtener_productos_alibaba
from scraper.madeinchina_scraper import obtener_productos_made_in_china

import pandas as pd
import os

SCRAPERS = {
    "aliexpress": (obtener_productos_aliexpress, "productos_aliexpress.csv"),
    "temu": (obtener_productos_temu, "productos_temu.csv"),
    "alibaba": (obtener_productos_alibaba, "productos_alibaba.csv"),
    "madeinchina": (obtener_productos_made_in_china, "productos_madeinchina.csv"),
}

app = Flask(__name__)
CORS(app)  # Permitir peticiones desde el frontend React

@app.route("/api/scrape", methods=["POST"])
def scrape():
    data = request.get_json() or {}
    producto = data.get("producto")
    plataforma = data.get("plataforma")

    if not producto or not plataforma:
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Los parámetros 'producto' y 'plataforma' son obligatorios.",
                }
            ),
            400,
        )

    scraper_info = SCRAPERS.get(plataforma)
    if scraper_info is None:
        return (
            jsonify({"success": False, "message": "Plataforma no soportada."}),
            400,
        )

    scraper_func, csv_name = scraper_info
    productos = scraper_func(producto)
    archivo_csv = os.path.join("data", csv_name)

    if productos:
        os.makedirs("data", exist_ok=True)
        df = pd.DataFrame(productos)
        df.to_csv(archivo_csv, index=False, encoding="utf-8-sig")
        return jsonify({"success": True, "productos": productos})

    return jsonify({"success": False, "message": "No se encontraron productos."})

@app.route("/api/descargar/<nombre>")
def descargar(nombre):
    path = f"data/{nombre}"
    return send_file(path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
