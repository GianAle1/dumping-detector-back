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
                    EC.presence_of_element_located((By.CSS_SELECTOR, "div.lh_jy"))
                )
                self.scroll(6)
            except TimeoutException:
                logging.warning("No se cargó la página %s", page)
                continue

            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            bloques = soup.find_all("div", class_="lh_jy")
            logging.info("Página %s: %s productos encontrados", page, len(bloques))

            for bloque in bloques:
                try:
                    titulo_tag = bloque.select_one("div.lh_ae h3.lh_ki")
                    titulo = titulo_tag.text.strip() if titulo_tag else "Sin título"

                    precio_tag = bloque.select_one("div.lh_cv div.lh_k0")
                    if precio_tag:
                        spans = precio_tag.find_all("span")
                        precio_texto = "".join(span.text for span in spans)
                        precio_texto = (
                            re.sub(r"[^0-9.,]", "", precio_texto).replace(",", ".")
                        )
                        precio = float(precio_texto) if precio_texto else None
                    else:
                        precio = None

                    precio_ori_tag = bloque.select_one("div.lh_cv div.lh_k1 span")
                    if precio_ori_tag:
                        texto = (
                            re.sub(r"[^0-9.,]", "", precio_ori_tag.text).replace(",", ".")
                        )
                        precio_original = float(texto) if texto else None
                    else:
                        precio_original = None

                    descuento_tag = bloque.select_one("div.lh_cv span.lh_lz")
                    descuento = (
                        descuento_tag.text.strip() if descuento_tag else None
                    )

                    ventas_tag = bloque.select_one("div.lh_j5 span.lh_j7")
                    if ventas_tag:
                        ventas_texto = (
                            ventas_tag.text.strip().replace(" vendidos", "").replace("+", "")
                        )
                        ventas = (
                            int(re.sub(r"[^\d]", "", ventas_texto)) if ventas_texto else 0
                        )
                    else:
                        ventas = 0

                    link_tag = bloque.find("a", class_="lh_e")
                    link = (
                        "https:" + link_tag["href"]
                        if link_tag and link_tag["href"].startswith("//")
                        else link_tag["href"]
                        if link_tag
                        else ""
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
