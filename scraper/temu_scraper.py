from bs4 import BeautifulSoup
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException
from urllib.parse import quote_plus
import logging
import re
from .base import BaseScraper


class TemuScraper(BaseScraper):
    @staticmethod
    def _sanitize_numeric_text(text: str) -> str:
        if not text:
            return ""
        return re.sub(r"[^\d,]", "", text)

    @classmethod
    def _float_from_text(cls, text: str):
        sanitized = cls._sanitize_numeric_text(text)
        if not sanitized:
            return None
        if "," in sanitized:
            parts = sanitized.split(",")
            last_group = parts[-1]
            if len(last_group) in (1, 2):
                integer_part = "".join(parts[:-1]) or "0"
                normalized = f"{integer_part}.{last_group}"
            else:
                normalized = sanitized.replace(",", "")
        else:
            normalized = sanitized
        try:
            return float(normalized)
        except ValueError:
            return None

    def parse(self, producto: str):
        try:
            encoded_product = quote_plus(producto)
            url = f"https://www.temu.com/pe/search.html?search_key={encoded_product}"
            productos = []

            cargada = False
            for intento in range(3):
                try:
                    self.driver.get(url)
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, "div._6q6qVUF5._1UrrHYym")
                        )
                    )
                    self.scroll(5)
                    cargada = True
                    break
                except WebDriverException as e:
                    logging.error(
                        "Error cargando Temu (intento %s): %s", intento + 1, e
                    )
            if not cargada:
                logging.error("No se cargó la página de Temu tras varios intentos")
                return productos

            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            bloques = soup.find_all("div", class_="_6q6qVUF5 _1UrrHYym")
            logging.info("Se encontraron %s productos en Temu", len(bloques))

            for bloque in bloques:
                try:
                    titulo_tag = bloque.find("h2", class_="_2BvQbnbN")
                    titulo = titulo_tag.text.strip() if titulo_tag else "Sin título"

                    precio_entero_tag = bloque.find("span", class_="_2de9ERAH")
                    precio_decimal_tag = bloque.find("span", class_="_3SrxhhHh")

                    entero_limpio = self._sanitize_numeric_text(
                        precio_entero_tag.text if precio_entero_tag else ""
                    ).replace(",", "")
                    decimal_limpio = self._sanitize_numeric_text(
                        precio_decimal_tag.text if precio_decimal_tag else ""
                    ).replace(",", "")

                    precio_texto = entero_limpio
                    if decimal_limpio:
                        precio_texto = (
                            f"{precio_texto},{decimal_limpio}" if precio_texto else f"0,{decimal_limpio}"
                        )

                    precio = self._float_from_text(precio_texto)

                    precio_ori_tag = bloque.find("span", class_="_3TAPHDOX")
                    precio_original = self._float_from_text(
                        precio_ori_tag.text.strip() if precio_ori_tag else ""
                    )

                    descuento_tag = bloque.find("div", class_="_1LLbpUTn")
                    descuento_extra = (
                        descuento_tag.text.strip()
                        if descuento_tag and descuento_tag.text
                        else None
                    )

                    ventas_tag = bloque.find("span", class_="_3vfo0XTx")
                    ventas = ventas_tag.text.strip() if ventas_tag else "0"

                    link_tag = bloque.find("a", href=True)
                    link = (
                        "https://www.temu.com" + link_tag["href"]
                        if link_tag and link_tag["href"].startswith("/pe")
                        else ""
                    )

                    productos.append(
                        {
                            "titulo": titulo,
                            "precio": precio,
                            "precio_original": precio_original,
                            "descuento_extra": descuento_extra,
                            "ventas": ventas,
                            "link": link,
                            "plataforma": "Temu",
                            "fecha_scraping": datetime.now().strftime("%Y-%m-%d"),
                        }
                    )
                except Exception as e:
                    logging.error("Error procesando producto: %s", e)
                    continue
            return productos
        finally:
            self.close()
