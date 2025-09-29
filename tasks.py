from celery import Celery
import os
import pandas as pd
from flask import Flask
import logging
import logging_config

from config import Config
from scraper.aliexpress_scraper import AliExpressScraper
from scraper.temu_scraper import TemuScraper
from scraper.alibaba_scraper import AlibabaScraper
from scraper.madeinchina_scraper import MadeInChinaScraper

flask_app = Flask(__name__)
flask_app.config.from_object(Config)

celery_app = Celery(
    "tasks",
    broker=flask_app.config["CELERY_BROKER_URL"],
    backend=flask_app.config["CELERY_RESULT_BACKEND"],
)

SCRAPERS = {
    "aliexpress": (AliExpressScraper, "productos_aliexpress.csv"),
    "temu": (TemuScraper, "productos_temu.csv"),
    "alibaba": (AlibabaScraper, "productos_alibaba.csv"),
    "madeinchina": (MadeInChinaScraper, "productos_madeinchina.csv"),
}

@celery_app.task(name="scrapear")
def scrapear(producto: str, plataforma: str):
    scraper_info = SCRAPERS.get(plataforma)
    if scraper_info is None:
        logging.error("Plataforma no soportada: %s", plataforma)
        return {"success": False, "message": "Plataforma no soportada."}

    scraper_cls, csv_name = scraper_info
    logging.info("Ejecutando scraper %s para %s", plataforma, producto)

    try:
        with scraper_cls() as scraper:
            productos = scraper.parse(producto)
    except Exception as e:
        logging.exception("Error al ejecutar scraper")
        return {"success": False, "message": str(e)}

    if not productos:
        logging.warning("No se encontraron productos para %s en %s", producto, plataforma)
        return {"success": False, "message": "No se encontraron productos."}

    df = pd.DataFrame(productos)

    # Rutas de guardado (primaria + respaldos)
    primary_dir = os.environ.get("OUTPUT_DIR", "/app/data")
    fallback_dirs = ["/tmp", os.path.join(os.getcwd(), "data")]
    candidate_paths = [os.path.join(primary_dir, csv_name)] + [os.path.join(d, csv_name) for d in fallback_dirs]

    saved_to = None
    last_error = None

    for path in candidate_paths:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            tmp_path = path + ".tmp"
            df.to_csv(tmp_path, index=False, encoding="utf-8-sig")
            os.replace(tmp_path, path)  # escritura atómica
            saved_to = path
            break
        except PermissionError as e:
            last_error = e
            logging.warning("Permiso denegado escribiendo %s. Probando ruta de respaldo...", path)
        except OSError as e:
            last_error = e
            logging.warning("No pude escribir en %s (%s). Probando ruta de respaldo...", path, e)

    if saved_to:
        logging.info("Scraping completado: %d productos -> %s", len(productos), saved_to)
        return {"success": True, "productos": productos, "archivo": saved_to}

    # Si todas fallan, reporta claramente el último error
    msg = f"No se pudo guardar el CSV en ninguna ruta. Último error: {last_error!s}"
    logging.error(msg)
    return {"success": False, "message": msg}
