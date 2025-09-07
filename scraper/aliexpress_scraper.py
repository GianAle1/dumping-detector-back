from bs4 import BeautifulSoup
from datetime import datetime
import re
import logging
from urllib.parse import quote_plus
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException
from .base import BaseScraper


def limpiar_precio(texto: str):
    """Convierte una cadena de precio a ``float``.

    Primero elimina los separadores de miles (``.``) y luego
    reemplaza la coma decimal por un punto. Si el resultado queda
    vacío, retorna ``None`` en lugar de intentar la conversión.
    """

    numero = re.sub(r"[^0-9.,]", "", texto or "")
    numero = numero.replace(".", "").replace(",", ".").strip()
    return float(numero) if numero else None


def limpiar_cantidad(texto: str) -> int:
    """Convierte una cadena de cantidad a ``int``.

    Detecta sufijos ``k`` o ``mil`` antes de limpiar el número para
    multiplicar la cantidad por mil. Si no hay sufijo, procesa el número
    como un entero simple.
    """

    texto = (texto or "").lower().replace("+", "").strip()
    if not texto:
        return 0

    multiplicador = 1
    if "k" in texto or "mil" in texto:
        multiplicador = 1000

    match = re.search(r"(\d+(?:[\.,]\d+)?)", texto)
    if not match:
        return 0

    numero = match.group(1).replace(",", ".")
    try:
        return int(float(numero) * multiplicador)
    except ValueError:
        return 0


class AliExpressScraper(BaseScraper):
    def parse(self, producto: str, paginas: int = 4):
        try:
            resultados = []

            for page in range(1, paginas + 1):
                url = (
                    f"https://es.aliexpress.com/wholesale?SearchText={quote_plus(producto)}&page={page}"
                )
                logging.info("Cargando AliExpress: Página %s", page)

                cargada = False
                for intento in range(3):
                    try:
                        if intento == 0:
                            self.driver.get(url)
                        WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located(
                                (By.CSS_SELECTOR, "div.search-item-card-wrapper-gallery")
                            )
                        )
                        self.scroll(6)
                        cargada = True
                        break
                    except WebDriverException as e:
                        logging.error(
                            "Error cargando AliExpress página %s (intento %s): %s",
                            page,
                            intento + 1,
                            e,
                        )
                if not cargada:
                    logging.error(
                        "Omitiendo página %s de AliExpress tras varios fallos", page
                    )
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
                            precio = limpiar_precio(precio_texto)
                        else:
                            precio = None

                        precio_ori_tag = card.select_one("[data-original-price]")
                        if precio_ori_tag:
                            texto = precio_ori_tag.get("data-original-price") or precio_ori_tag.text
                            precio_original = limpiar_precio(texto)
                        else:
                            precio_original = None

                        descuento_tag = card.select_one("[data-discount]")
                        if descuento_tag:
                            if descuento_tag.get("data-discount"):
                                descuento = descuento_tag.get("data-discount")
                            elif descuento_tag.text:
                                descuento = descuento_tag.text.strip()
                            else:
                                descuento = None
                        else:
                            descuento = None

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
                        ventas = limpiar_cantidad(ventas_texto)

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

            return resultados
        finally:
            self.close()
