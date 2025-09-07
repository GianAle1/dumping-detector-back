from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import logging
import os
from kombu.exceptions import OperationalError

from config import Config
from tasks import scrapear
import logging_config

app = Flask(__name__)
app.config.from_object(Config)
CORS(app, origins=app.config["ALLOWED_ORIGINS"])  # Permitir peticiones desde dominios permitidos

@app.route("/api/scrape", methods=["POST"])
def scrape():
    data = request.get_json() or {}
    producto = data.get("producto")
    plataforma = data.get("plataforma")

    if not producto or not plataforma:
        logging.warning("Parametros faltantes en solicitud de scraping")
        return (
            jsonify(
                {
                    "success": False,
                    "message": "Los parámetros 'producto' y 'plataforma' son obligatorios.",
                }
            ),
            400,
        )
    logging.info("Iniciando scraping de %s en %s", producto, plataforma)
    try:
        task = scrapear.delay(producto, plataforma)
    except OperationalError:
        logging.exception("Error al enviar la tarea de scraping")
        return (
            jsonify(
                {
                    "success": False,
                    "message": "El servicio de mensajería no está disponible.",
                }
            ),
            503,
        )
    return jsonify({"task_id": task.id}), 202


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

@app.route("/api/descargar/<nombre>")
def descargar(nombre):
    path = f"data/{nombre}"
    if not os.path.exists(path):
        return (
            jsonify({"success": False, "message": "Archivo no encontrado"}),
            404,
        )
    return send_file(path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"])
