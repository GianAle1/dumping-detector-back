from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import pandas as pd
import time
import os
from datetime import datetime
import re

CHROMEDRIVER_PATH = "C:\\Program Files (x86)\\chromedriver.exe"

def obtener_productos_aliexpress(producto, paginas=4):
    options = Options()
    # options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)

    resultados = []

    for page in range(1, paginas + 1):
        url = f"https://es.aliexpress.com/wholesale?SearchText={producto.replace(' ', '+')}&page={page}"
        print(f"🌀 Cargando AliExpress: Página {page}")
        driver.get(url)
        time.sleep(10)

        # Scroll hacia abajo varias veces
        for _ in range(6):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        bloques = soup.find_all('div', class_='jr_js')
        print(f"🔍 Página {page}: {len(bloques)} productos encontrados")

        for bloque in bloques:
            try:
                # Título
                titulo_tag = bloque.find('div', class_='jr_ae')
                titulo = titulo_tag.get('title', '').strip() if titulo_tag else 'Sin título'

                # Precio
                precio_tag = bloque.find('div', class_='jr_kr')
                spans = precio_tag.find_all('span') if precio_tag else []
                if len(spans) >= 3:
                    precio = float(spans[1].text + spans[2].text)
                else:
                    precio = None

                # Precio original (tachado)
                precio_ori_tag = bloque.find('div', class_='jr_ks')
                if precio_ori_tag:
                    texto = precio_ori_tag.text.replace("PEN", "").strip()
                    precio_original = float(texto) if texto else None
                else:
                    precio_original = None

                # Descuento
                descuento_tag = bloque.find('span', class_='jr_kt')
                if descuento_tag:
                    porcentaje = re.findall(r'-?\d+%', descuento_tag.text)
                    descuento = porcentaje[0] if porcentaje else None
                else:
                    descuento = None

                # Ventas
                ventas_tag = bloque.find('span', class_='jr_kw')
                if ventas_tag:
                    ventas_texto = ventas_tag.text.strip().replace(" vendidos", "").replace("+", "")
                    ventas = int(re.sub(r"[^\d]", "", ventas_texto)) if ventas_texto else 0
                else:
                    ventas = 0

                # Link
                link_tag = bloque.find('a', class_='jr_g')
                link = "https:" + link_tag['href'] if link_tag and link_tag['href'].startswith("//") else link_tag['href'] if link_tag else ""

                resultados.append({
                    "pagina": page,
                    "titulo": titulo,
                    "precio": precio,
                    "precio_original": precio_original,
                    "descuento": descuento,
                    "ventas": ventas,
                    "link": link,
                    "plataforma": "AliExpress",
                    "fecha_scraping": datetime.now().strftime("%Y-%m-%d")
                })
            except Exception as e:
                print(f"❌ Error en producto: {e}")
                continue

    driver.quit()

    os.makedirs("data", exist_ok=True)
    df = pd.DataFrame(resultados)
    df.to_csv("data/productos_aliexpress.csv", index=False, encoding="utf-8-sig")
    print(f"✅ Total: {len(resultados)} productos guardados en productos_aliexpress.csv")

    return resultados
