from bs4 import BeautifulSoup
from datetime import datetime
import time
from .base import BaseScraper


class TemuScraper(BaseScraper):
    def parse(self, producto: str):
        url = f"https://www.temu.com/pe/search.html?search_key={producto.replace(' ', '%20')}"
        self.driver.get(url)
        time.sleep(10)
        self.scroll(5)

        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        productos = []

        bloques = soup.find_all("div", class_="_6q6qVUF5 _1UrrHYym")
        print(f"🔍 Se encontraron {len(bloques)} productos en Temu")

        for bloque in bloques:
            try:
                titulo_tag = bloque.find("h2", class_="_2BvQbnbN")
                titulo = titulo_tag.text.strip() if titulo_tag else "Sin título"

                precio_entero = bloque.find("span", class_="_2de9ERAH")
                precio_decimal = bloque.find("span", class_="_3SrxhhHh")
                if precio_entero and precio_decimal:
                    precio = float(f"{precio_entero.text}.{precio_decimal.text}")
                else:
                    precio = None

                precio_ori_tag = bloque.find("span", class_="_3TAPHDOX")
                if precio_ori_tag:
                    precio_original = float(precio_ori_tag.text.strip())
                else:
                    precio_original = None

                descuento_tag = bloque.find("div", class_="_1LLbpUTn")
                descuento_extra = descuento_tag.text.strip() if descuento_tag else None

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
                print(f"❌ Error procesando producto: {e}")
                continue

        self.close()
        return productos
