from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

from config import Config
from tasks import scrapear

app = Flask(__name__)
app.config.from_object(Config)
CORS(app, origins=app.config["ALLOWED_ORIGINS"])  # Permitir peticiones desde dominios permitidos

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
    task = scrapear.delay(producto, plataforma)
    return jsonify({"task_id": task.id}), 202


@app.route("/api/resultado/<task_id>")
def resultado(task_id):
    task = scrapear.AsyncResult(task_id)
    if task.state == "PENDING":
        return jsonify({"state": task.state})
    if task.state == "SUCCESS":
        return jsonify({"state": task.state, **task.result})
    return jsonify({"state": task.state, "message": str(task.info)}), 400

@app.route("/api/descargar/<nombre>")
def descargar(nombre):
    path = f"data/{nombre}"
    return send_file(path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=app.config["DEBUG"])
