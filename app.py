from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import logging
import os
from kombu.exceptions import OperationalError
from werkzeug.exceptions import NotFound

from config import Config
from tasks import scrapear
import logging_config

# === NUEVO: Importar modelo predictivo ===
from ml.predict import predict_dumping

app = Flask(__name__)
app.config.from_object(Config)
CORS(app, origins=app.config["ALLOWED_ORIGINS"])

# ==========================================================
# 🧩 1. ENDPOINT EXISTENTE: SCRAPING
# ==========================================================
@app.route("/api/scrape", methods=["POST"])
def scrape():
    data = request.get_json() or {}
    producto = data.get("producto")
    plataforma = data.get("plataforma")

    if not producto or not plataforma:
        logging.warning("Parametros faltantes en solicitud de scraping")
        return jsonify({
            "success": False,
            "message": "Los parámetros 'producto' y 'plataforma' son obligatorios."
        }), 400

    logging.info("Iniciando scraping de %s en %s", producto, plataforma)
    try:
        task = scrapear.delay(producto, plataforma)
    except OperationalError:
        logging.exception("Error al enviar la tarea de scraping")
        return jsonify({
            "success": False,
            "message": "El servicio de mensajería no está disponible."
        }), 503

    return jsonify({"task_id": task.id}), 202

# ==========================================================
# 🧩 2. ENDPOINT EXISTENTE: CONSULTAR RESULTADOS DE SCRAPE
# ==========================================================
@app.route("/api/resultado/<task_id>")
def resultado(task_id):
    task = scrapear.AsyncResult(task_id)
    if task.state == "PENDING":
        return jsonify({"state": task.state}), 200
    if task.state == "SUCCESS":
        return jsonify({"state": task.state, **task.result}), 200
    response = {"state": task.state, "message": str(task.info)}
    if task.state == "FAILURE":
        response["traceback"] = task.traceback
    return jsonify(response), 200

# ==========================================================
# 🧩 3. NUEVO ENDPOINT: PREDICCIÓN DE DUMPING
# ==========================================================
@app.route("/api/predict", methods=["POST"])
def predict():
    """
    Endpoint que recibe datos de precios y devuelve la probabilidad de dumping.
    """
    try:
        data = request.get_json() or {}
        precio_importado = float(data.get("precio_importado", 0))
        precio_local = float(data.get("precio_local", 0))
        plataforma = data.get("plataforma", "AliExpress")

        if not precio_importado or not precio_local:
            return jsonify({
                "success": False,
                "message": "Debe enviar 'precio_importado' y 'precio_local'."
            }), 400

        resultado = predict_dumping(precio_importado, precio_local, plataforma)
        return jsonify({"success": True, **resultado}), 200

    except FileNotFoundError:
        return jsonify({
            "success": False,
            "message": "Modelo no encontrado. Entrene el modelo primero con /ml/training.py."
        }), 500
    except Exception as e:
        logging.exception("Error al predecir dumping")
        return jsonify({"success": False, "message": str(e)}), 500

# ==========================================================
# 🧩 4. DESCARGAR ARCHIVOS
# ==========================================================
@app.route("/api/descargar/<nombre>")
def descargar(nombre):
    safe_name = os.path.basename(nombre)
    try:
        return send_from_directory("data", safe_name, as_attachment=True)
    except NotFound:
        return jsonify({"success": False, "message": "Archivo no encontrado"}), 404

# ==========================================================
# MAIN APP
# ==========================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=app.config["DEBUG"])
