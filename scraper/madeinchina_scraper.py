from bs4 import BeautifulSoup
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException
import logging
import re
from urllib.parse import quote_plus
from .base import BaseScraper


class MadeInChinaScraper(BaseScraper):
    def _normalizar_precio(self, precio_texto: str):
        if not precio_texto:
            return None, None

        texto = re.sub(r"[^\d,\.\-]", "", precio_texto)
        if not texto:
            return None, None

        partes = [parte for parte in texto.split("-") if parte]
        if not partes:
            return None, None

        def convertir(parte: str):
            valor = parte.strip()
            if not valor:
                return None

            valor = valor.replace(" ", "")

            decimal_sep = None
            thousand_sep = None

            if "," in valor and "." in valor:
                if valor.rfind(",") > valor.rfind("."):
                    decimal_sep = ","
                    thousand_sep = "."
                else:
                    decimal_sep = "."
                    thousand_sep = ","
            elif "," in valor:
                partes_coma = valor.split(",")
                if len(partes_coma[-1]) in (1, 2):
                    decimal_sep = ","
                else:
                    thousand_sep = ","
            elif "." in valor:
                partes_punto = valor.split(".")
                if len(partes_punto[-1]) in (1, 2):
                    decimal_sep = "."
                else:
                    thousand_sep = "."

            if thousand_sep:
                valor = valor.replace(thousand_sep, "")

            if decimal_sep and decimal_sep != ".":
                valor = valor.replace(decimal_sep, ".")

            try:
                return float(valor)
            except ValueError:
                return None

        valores = [convertir(parte) for parte in partes]
        valores_validos = [valor for valor in valores if valor is not None]

        if not valores_validos:
            return None, None

        if len(valores_validos) == 1:
            return valores_validos[0], valores_validos[0]

        return min(valores_validos), max(valores_validos)

    def parse(self, producto: str, paginas: int = 4):
        try:
            resultados = []

            for pagina in range(1, paginas + 1):
                url = (
                    "https://es.made-in-china.com/productSearch?keyword="
                    f"{quote_plus(producto)}&currentPage={pagina}&type=Product"
                )
                logging.info("Visitando página %s - %s", pagina, url)

                cargada = False
                for intento in range(3):
                    try:
                        self.driver.get(url)
                        WebDriverWait(self.driver, 8).until(
                            EC.presence_of_element_located(
                                (By.CSS_SELECTOR, "div.list-node-content")
                            )
                        )
                        self.scroll(3)
                        cargada = True
                        break
                    except WebDriverException as e:
                        logging.error(
                            "Error cargando Made-in-China página %s (intento %s): %s",
                            pagina,
                            intento + 1,
                            e,
                        )
                if not cargada:
                    logging.error(
                        "Omitiendo página %s de Made-in-China tras varios fallos", pagina
                    )
                    continue

                soup = BeautifulSoup(self.driver.page_source, "html.parser")
                bloques = soup.find_all("div", class_="list-node-content")
                logging.info("Página %s: %s productos encontrados", pagina, len(bloques))

                for bloque in bloques:
                    try:
                        titulo_tag = bloque.find("h2", class_="product-name")
                        titulo = (
                            titulo_tag.get("title", "Sin título").strip()
                            if titulo_tag
                            else "Sin título"
                        )
                        enlace_tag = titulo_tag.find("a", href=True) if titulo_tag else None
                        link = enlace_tag["href"] if enlace_tag else ""

                        precio_tag = bloque.find("strong", class_="price")
                        precio_texto = precio_tag.text.strip() if precio_tag else ""
                        precio_min, precio_max = self._normalizar_precio(precio_texto)

                        moq_tag = bloque.find("div", class_="info")
                        moq = moq_tag.text.strip() if moq_tag else "No info"

                        empresa_tag = bloque.find("a", class_="company-name")
                        empresa = (
                            empresa_tag.text.strip() if empresa_tag else "Desconocida"
                        )

                        ubicacion_tag = bloque.find("div", class_="company-address-detail")
                        ubicacion = (
                            ubicacion_tag.text.strip() if ubicacion_tag else "Sin ubicación"
                        )

                        es_diamante = "Miembro Diamante" in bloque.text

                        resultados.append(
                            {
                                "titulo": titulo,
                                "precio_min": precio_min,
                                "precio_max": precio_max,
                                "moq": moq,
                                "empresa": empresa,
                                "ubicacion": ubicacion,
                                "miembro_diamante": es_diamante,
                                "link": link,
                                "plataforma": "Made-in-China",
                                "pagina": pagina,
                                "fecha_scraping": datetime.now().strftime("%Y-%m-%d"),
                            }
                        )
                    except Exception as e:
                        logging.error("Error procesando producto en página %s: %s", pagina, e)
                        continue

            return resultados
        finally:
            self.close()
