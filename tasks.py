from celery import Celery
import os
import pandas as pd

from scraper.aliexpress_scraper import AliExpressScraper
from scraper.temu_scraper import TemuScraper
from scraper.alibaba_scraper import AlibabaScraper
from scraper.madeinchina_scraper import MadeInChinaScraper


celery_app = Celery(
    "tasks",
    broker=os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
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
        return {"success": False, "message": "Plataforma no soportada."}

    scraper_cls, csv_name = scraper_info
    scraper = scraper_cls()
    productos = scraper.parse(producto)
    archivo_csv = os.path.join("data", csv_name)

    if productos:
        os.makedirs("data", exist_ok=True)
        df = pd.DataFrame(productos)
        df.to_csv(archivo_csv, index=False, encoding="utf-8-sig")
        return {"success": True, "productos": productos, "archivo": csv_name}

    return {"success": False, "message": "No se encontraron productos."}
