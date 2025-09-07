from bs4 import BeautifulSoup
from datetime import datetime
import re
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from .base import BaseScraper

logger = logging.getLogger(__name__)


def extraer_rango_precio(texto):
    match = re.findall(r"([\d.,]+)", texto)
    if len(match) == 1:
        precio_min = precio_max = float(match[0].replace(",", ""))
    elif len(match) >= 2:
        precio_min = float(match[0].replace(",", ""))
        precio_max = float(match[1].replace(",", ""))
    else:
        return None, None, None
    promedio = round((precio_min + precio_max) / 2, 2)
    return precio_min, precio_max, promedio


class AlibabaScraper(BaseScraper):
    def parse(self, producto: str, max_paginas: int = 4):
        resultados = []

        for pagina in range(1, max_paginas + 1):
            logger.info("Scrapeando página %s", pagina)
            url = (
                f"https://www.alibaba.com/trade/search?SearchText={producto.replace(' ', '+')}&page={pagina}"
            )
            self.driver.get(url)
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.card-info.gallery-card-layout-info"))
                )
                self.scroll(3)
            except TimeoutException:
                logger.warning("No se cargó la página %s", pagina)
                continue

            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            bloques = soup.find_all("div", class_="card-info gallery-card-layout-info")
            if not bloques:
                logger.info("Alibaba no devolvió más resultados; deteniendo en la página %s", pagina)
                break

            for bloque in bloques:
                try:
                    titulo_tag = bloque.find("h2", class_="search-card-e-title")
                    titulo = (
                        titulo_tag.get_text(strip=True) if titulo_tag else "Sin título"
                    )

                    enlace_tag = bloque.select_one("h2.search-card-e-title a")
                    enlace = enlace_tag.get("href", "") if enlace_tag else ""
                    if enlace and not enlace.startswith("http"):
                        enlace = "https:" + enlace

                    precio_tag = bloque.find("div", class_="search-card-e-price-main")
                    precio_texto = (
                        precio_tag.get_text(strip=True).replace("\xa0", " ")
                        if precio_tag
                        else "Sin precio"
                    )
                    moneda_match = re.search(r"[A-Z]{1,4}/?|\w+/?", precio_texto)
                    moneda = (
                        moneda_match.group(0).rstrip() if moneda_match else "N/A"
                    )
                    precio_texto = re.sub(r"US\$|/", "", precio_texto)
                    precio_min, precio_max, precio_prom = extraer_rango_precio(precio_texto)

                    proveedor_tag = bloque.find("a", class_="search-card-e-company")
                    proveedor = (
                        proveedor_tag.get_text(strip=True) if proveedor_tag else "Sin proveedor"
                    )

                    ventas_tag = None
                    for item in bloque.find_all(
                        "div", class_="search-card-m-sale-features__item"
                    ):
                        if "Pedido mín" in item.get_text():
                            ventas_tag = item
                            break
                    ventas = ventas_tag.get_text(strip=True) if ventas_tag else "No info"

                    rating_tag = bloque.find("span", class_="search-card-e-review")
                    rating = rating_tag.get_text(strip=True) if rating_tag else "No rating"

                    resultados.append(
                        {
                            "pagina": pagina,
                            "titulo": titulo,
                            "precio_min": precio_min,
                            "precio_max": precio_max,
                            "precio_promedio": precio_prom,
                            "moneda": moneda,
                            "proveedor": proveedor,
                            "ventas": ventas,
                            "rating": rating,
                            "link": enlace,
                            "plataforma": "Alibaba",
                            "fecha_scraping": datetime.now().strftime("%Y-%m-%d"),
                        }
                    )
                except Exception as e:
                    logger.error("Error en producto: %s", e)
                    continue

        self.close()
        return resultados
