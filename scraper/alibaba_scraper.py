from bs4 import BeautifulSoup
from datetime import datetime
import re
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException
from .base import BaseScraper


def extraer_rango_precio(texto):
    """Extrae precios mínimo, máximo y moneda desde una cadena.

    La moneda se extrae antes de limpiar los caracteres no numéricos.
    Soporta rangos de precios indicados con un guion, por ejemplo
    ``"72.41-80.00"``.
    """

    # Detectar la moneda antes de eliminar caracteres
    moneda_match = re.search(r"(US\$|S/|[$€£¥]|[A-Z]{1,4})", texto)
    moneda = moneda_match.group(0) if moneda_match else "N/A"

    # Eliminar la moneda y otros caracteres no numéricos para procesar el rango
    texto_limpio = re.sub(r"(US\$|S/|[$€£¥]|[A-Z]{1,4})", "", texto)
    texto_limpio = re.sub(r"[^0-9.,-]", "", texto_limpio)

    match = re.findall(r"([\d.,]+)", texto_limpio)
    if len(match) == 1:
        precio_min = precio_max = float(match[0].replace(",", ""))
    elif len(match) >= 2:
        precio_min = float(match[0].replace(",", ""))
        precio_max = float(match[1].replace(",", ""))
    else:
        return None, None, None, moneda

    promedio = round((precio_min + precio_max) / 2, 2)
    return precio_min, precio_max, promedio, moneda


class AlibabaScraper(BaseScraper):
    def parse(self, producto: str, max_paginas: int = 4):
        try:
            resultados = []

            for pagina in range(1, max_paginas + 1):
                logging.info("Scrapeando página %s", pagina)
                url = (
                    f"https://www.alibaba.com/trade/search?SearchText={producto.replace(' ', '+')}&page={pagina}"
                )

                cargada = False
                for intento in range(3):
                    try:
                        self.driver.get(url)
                        WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located(
                                (By.CSS_SELECTOR, "div.card-info.gallery-card-layout-info")
                            )
                        )
                        self.scroll(3)
                        cargada = True
                        break
                    except WebDriverException as e:
                        logging.error(
                            "Error cargando Alibaba página %s (intento %s): %s",
                            pagina,
                            intento + 1,
                            e,
                        )
                if not cargada:
                    logging.error(
                        "Omitiendo página %s de Alibaba tras varios fallos", pagina
                    )
                    continue

                soup = BeautifulSoup(self.driver.page_source, "html.parser")
                bloques = soup.find_all("div", class_="card-info gallery-card-layout-info")
                if not bloques:
                    logging.info("Alibaba no devolvió más resultados; deteniendo en la página %s", pagina)
                    break

                for bloque in bloques:
                    try:
                        titulo_tag = bloque.find("h2", class_="search-card-e-title")
                        titulo = (
                            titulo_tag.get_text(strip=True) if titulo_tag else "Sin título"
                        )

                        enlace_tag = (
                            bloque.select_one("a.search-card-item")
                            or bloque.select_one("h2.search-card-e-title a")
                        )
                        enlace = enlace_tag.get("href", "") if enlace_tag else ""
                        if enlace:
                            if enlace.startswith("//"):
                                enlace = "https:" + enlace
                            elif enlace.startswith("/"):
                                enlace = "https://www.alibaba.com" + enlace
                            elif not enlace.startswith("http"):
                                enlace = "https://www.alibaba.com/" + enlace

                        precio_tag = bloque.find("div", class_="search-card-e-price-main")
                        precio_texto = (
                            precio_tag.get_text(strip=True).replace("\xa0", " ")
                            if precio_tag
                            else "Sin precio"
                        )
                        precio_min, precio_max, precio_prom, moneda = extraer_rango_precio(
                            precio_texto
                        )

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
                        logging.error("Error en producto: %s", e)
                        continue

            return resultados
        finally:
            self.close()
