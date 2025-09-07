from bs4 import BeautifulSoup
from datetime import datetime
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .base import BaseScraper


class AliExpressScraper(BaseScraper):
    def parse(self, producto: str, paginas: int = 4):
        resultados = []

        for page in range(1, paginas + 1):
            url = (
                f"https://es.aliexpress.com/wholesale?SearchText={producto.replace(' ', '+')}&page={page}"
            )
            print(f"🌀 Cargando AliExpress: Página {page}")
            self.driver.get(url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.jr_js"))
            )
            self.scroll(6)

            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            bloques = soup.find_all("div", class_="jr_js")
            print(f"🔍 Página {page}: {len(bloques)} productos encontrados")

            for bloque in bloques:
                try:
                    titulo_tag = bloque.find("div", class_="jr_ae")
                    titulo = (
                        titulo_tag.get("title", "").strip() if titulo_tag else "Sin título"
                    )

                    precio_tag = bloque.find("div", class_="jr_kr")
                    spans = precio_tag.find_all("span") if precio_tag else []
                    if len(spans) >= 3:
                        precio = float(spans[1].text + spans[2].text)
                    else:
                        precio = None

                    precio_ori_tag = bloque.find("div", class_="jr_ks")
                    if precio_ori_tag:
                        texto = precio_ori_tag.text.replace("PEN", "").strip()
                        precio_original = float(texto) if texto else None
                    else:
                        precio_original = None

                    descuento_tag = bloque.find("span", class_="jr_kt")
                    if descuento_tag:
                        porcentaje = re.findall(r"-?\d+%", descuento_tag.text)
                        descuento = porcentaje[0] if porcentaje else None
                    else:
                        descuento = None

                    ventas_tag = bloque.find("span", class_="jr_kw")
                    if ventas_tag:
                        ventas_texto = (
                            ventas_tag.text.strip()
                            .replace(" vendidos", "")
                            .replace("+", "")
                        )
                        ventas = (
                            int(re.sub(r"[^\d]", "", ventas_texto)) if ventas_texto else 0
                        )
                    else:
                        ventas = 0

                    link_tag = bloque.find("a", class_="jr_g")
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
                    print(f"❌ Error en producto: {e}")
                    continue

        self.close()
        return resultados
