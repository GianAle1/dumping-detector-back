from celery import Celery
import os
import pandas as pd
from flask import Flask
import logging
import logging_config

logger = logging.getLogger(__name__)

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
        logger.error("Plataforma no soportada: %s", plataforma)
        return {"success": False, "message": "Plataforma no soportada."}

    scraper_cls, csv_name = scraper_info
    logger.info("Ejecutando scraper %s para %s", plataforma, producto)
    scraper = scraper_cls()
    try:
        productos = scraper.parse(producto)
    except Exception as e:
        logger.exception("Error al ejecutar scraper")
        return {"success": False, "message": str(e)}
    archivo_csv = os.path.join("data", csv_name)

    if productos:
        os.makedirs("data", exist_ok=True)
        df = pd.DataFrame(productos)
        df.to_csv(archivo_csv, index=False, encoding="utf-8-sig")
        logger.info("Scraping completado: %d productos", len(productos))
        return {"success": True, "productos": productos, "archivo": csv_name}

    logger.warning("No se encontraron productos para %s en %s", producto, plataforma)
    return {"success": False, "message": "No se encontraron productos."}
