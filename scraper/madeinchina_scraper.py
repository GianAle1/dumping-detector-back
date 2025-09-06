from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time
import os
from datetime import datetime
import re

def obtener_productos_made_in_china(producto, paginas=4):
    options = Options()
    # options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    resultados = []

    for pagina in range(1, paginas + 1):
        url = f"https://es.made-in-china.com/productSearch?keyword={producto.replace(' ', '+')}&currentPage={pagina}&type=Product"
        print(f"🌐 Visitando página {pagina} - {url}")
        driver.get(url)
        time.sleep(8)

        for _ in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        bloques = soup.find_all("div", class_="list-node-content")
        print(f"🔍 Página {pagina}: {len(bloques)} productos encontrados")

        for bloque in bloques:
            try:
                # Título y enlace
                titulo_tag = bloque.find("h2", class_="product-name")
                titulo = titulo_tag.get("title", "Sin título").strip() if titulo_tag else "Sin título"
                enlace_tag = titulo_tag.find("a", href=True) if titulo_tag else None
                link = enlace_tag['href'] if enlace_tag else ""

                # Precio
                precio_tag = bloque.find("strong", class_="price")
                precio_texto = precio_tag.text.strip().replace("US$", "") if precio_tag else ""
                precio_min, precio_max = None, None
                if "-" in precio_texto:
                    partes = precio_texto.split("-")
                    precio_min = float(partes[0].replace(",", "."))
                    precio_max = float(partes[1].replace(",", "."))
                elif precio_texto:
                    precio_min = precio_max = float(precio_texto.replace(",", "."))

                # MOQ
                moq_tag = bloque.find("div", class_="info")
                moq = moq_tag.text.strip() if moq_tag else "No info"

                # Empresa
                empresa_tag = bloque.find("a", class_="compnay-name")
                empresa = empresa_tag.text.strip() if empresa_tag else "Desconocida"

                # Ubicación
                ubicacion_tag = bloque.find("div", class_="company-address-detail")
                ubicacion = ubicacion_tag.text.strip() if ubicacion_tag else "Sin ubicación"

                # Miembro diamante
                es_diamante = "Miembro Diamante" in bloque.text

                resultados.append({
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
                    "fecha_scraping": datetime.now().strftime("%Y-%m-%d")
                })

            except Exception as e:
                print(f"❌ Error procesando producto en página {pagina}: {e}")
                continue

    driver.quit()

    os.makedirs("data", exist_ok=True)
    df = pd.DataFrame(resultados)
    df.to_csv("data/productos_madeinchina.csv", index=False, encoding="utf-8-sig")
    print(f"✅ {len(resultados)} productos guardados en productos_madeinchina.csv")
    return resultados
