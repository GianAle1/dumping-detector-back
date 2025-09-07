from bs4 import BeautifulSoup
from datetime import datetime
import re
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from .base import BaseScraper


class AliExpressScraper(BaseScraper):
    def parse(self, producto: str, paginas: int = 4):
        resultados = []

        for page in range(1, paginas + 1):
            url = (
                f"https://es.aliexpress.com/wholesale?SearchText={producto.replace(' ', '+')}&page={page}"
            )
            logging.info("Cargando AliExpress: Página %s", page)
            self.driver.get(url)
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, "div.search-item-card-wrapper-gallery")
                    )
                )
                self.scroll(6)
            except TimeoutException:
                logging.warning("No se cargó la página %s", page)
                continue

            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            bloques = soup.select("div.search-item-card-wrapper-gallery")
            logging.info("Página %s: %s productos encontrados", page, len(bloques))

            for bloque in bloques:
                try:
                    card = bloque.select_one("a.search-card-item")
                    if not card:
                        continue

                    titulo = card.get("title", "Sin título").strip()

                    precio_tag = card.select_one("[data-price]")
                    if precio_tag:
                        precio_texto = precio_tag.get("data-price") or precio_tag.text
                        precio_texto = (
                            re.sub(r"[^0-9.,]", "", precio_texto).replace(",", ".")
                        )
                        precio = float(precio_texto) if precio_texto else None
                    else:
                        precio = None

                    precio_ori_tag = card.select_one("[data-original-price]")
                    if precio_ori_tag:
                        texto = precio_ori_tag.get("data-original-price") or precio_ori_tag.text
                        texto = re.sub(r"[^0-9.,]", "", texto).replace(",", ".")
                        precio_original = float(texto) if texto else None
                    else:
                        precio_original = None

                    descuento_tag = card.select_one("[data-discount]")
                    descuento = (
                        descuento_tag.get("data-discount")
                        if descuento_tag and descuento_tag.get("data-discount")
                        else descuento_tag.text.strip()
                        if descuento_tag
                        else None
                    )

                    ventas_tag = card.select_one("[data-sold]")
                    if ventas_tag:
                        ventas_texto = ventas_tag.get("data-sold") or ventas_tag.text
                    else:
                        ventas_texto = card.get_text(" ")
                        ventas_match = re.search(
                            r"([\d\.\,]+)\s*vendidos?",
                            ventas_texto,
                            re.IGNORECASE,
                        )
                        ventas_texto = ventas_match.group(1) if ventas_match else ""
                    ventas_texto = ventas_texto.replace("+", "")
                    ventas = (
                        int(re.sub(r"[^\d]", "", ventas_texto)) if ventas_texto else 0
                    )

                    link = (
                        "https:" + card["href"]
                        if card["href"].startswith("//")
                        else card["href"]
                    )

                    resultados.append(
                        {
                            "pagina": page,
                            "titulo": titulo,
                            "precio": precio,
                            "precio_original": precio_original,
                            "descuento": descuento,
                            "ventas": ventas,
                            "link": link,
                            "plataforma": "AliExpress",
                            "fecha_scraping": datetime.now().strftime("%Y-%m-%d"),
                        }
                    )
                except Exception as e:
                    logging.error("Error en producto: %s", e)
                    continue

        self.close()
        return resultados
