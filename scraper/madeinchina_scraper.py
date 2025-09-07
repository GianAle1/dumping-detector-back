from bs4 import BeautifulSoup
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import logging
from .base import BaseScraper


class MadeInChinaScraper(BaseScraper):
    def parse(self, producto: str, paginas: int = 4):
        resultados = []

        for pagina in range(1, paginas + 1):
            url = (
                "https://es.made-in-china.com/productSearch?keyword="
                f"{producto.replace(' ', '+')}&currentPage={pagina}&type=Product"
            )
            logging.info("Visitando página %s - %s", pagina, url)
            self.driver.get(url)
            WebDriverWait(self.driver, 8).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.list-node-content"))
            )
            self.scroll(3)

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
                    precio_texto = (
                        precio_tag.text.strip().replace("US$", "")
                        if precio_tag
                        else ""
                    )
                    precio_min, precio_max = None, None
                    if "-" in precio_texto:
                        partes = precio_texto.split("-")
                        precio_min = float(partes[0].replace(",", "."))
                        precio_max = float(partes[1].replace(",", "."))
                    elif precio_texto:
                        precio_min = precio_max = float(precio_texto.replace(",", "."))

                    moq_tag = bloque.find("div", class_="info")
                    moq = moq_tag.text.strip() if moq_tag else "No info"

                    empresa_tag = bloque.find("a", class_="compnay-name")
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

        self.close()
        return resultados
