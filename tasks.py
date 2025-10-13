from celery import Celery
import os
import csv
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

    output_dir = os.environ.get("OUTPUT_DIR", "/app/data")
    os.makedirs(output_dir, exist_ok=True)
    archivo_csv = os.path.join(output_dir, csv_name)

    if not productos:
        logging.warning("No se encontraron productos para %s en %s", producto, plataforma)
        return {"success": False, "message": "No se encontraron productos."}

    df = pd.DataFrame(productos)

    # Orden fijo de columnas
    cols = [
        "titulo","precio","precio_original","descuento","ventas","link",
        "pagina","plataforma","fecha_scraping",
        # extras Alibaba:
        "moneda","proveedor","proveedor_anios","proveedor_pais","proveedor_verificado",
        "rating_score","rating_count","moq","moq_texto","envio_promesa","tasa_repeticion",
    ]

    df = df.reindex(columns=cols)

    # Limpieza básica (evitar saltos de línea) y neutralizar ';' por si apareciera en títulos
    for c in ["titulo", "link", "plataforma"]:
        if c in df.columns:
            df[c] = (
                df[c].astype(str)
                     .str.replace(r"[\r\n]+", " ", regex=True)
                     .str.replace(";", " -")
                     .str.strip()
            )

    # Escritura atómica (delimitador ';' para no chocar con comas en títulos)
    tmp_path = archivo_csv + ".tmp"
    try:
        df.to_csv(
            tmp_path,
            index=False,
            sep=";",                     # <— delimitador seguro en ES
            encoding="utf-8-sig",
            quotechar='"',
            quoting=csv.QUOTE_MINIMAL,   # comillas si alguna celda las necesita
            lineterminator="\n",
            na_rep=""
        )
        os.replace(tmp_path, archivo_csv)
        logging.info("Scraping completado: %d productos -> %s", len(df), archivo_csv)
        return {"success": True, "productos": productos, "archivo": archivo_csv}

    except PermissionError as e:
        logging.error("Sin permisos en %s: %s. Probando /tmp ...", archivo_csv, e)
        fallback_dir = "/tmp/dumping-detector"
        os.makedirs(fallback_dir, exist_ok=True)
        fallback_csv = os.path.join(fallback_dir, csv_name)
        tmp2 = fallback_csv + ".tmp"
        df.to_csv(
            tmp2,
            index=False,
            sep=";",                     # mantener el mismo delimitador
            encoding="utf-8-sig",
            quotechar='"',
            quoting=csv.QUOTE_MINIMAL,
            lineterminator="\n",
            na_rep=""
        )
        os.replace(tmp2, fallback_csv)
        logging.info("Guardado por fallback: %s", fallback_csv)
        return {"success": True, "productos": productos, "archivo": fallback_csv}
