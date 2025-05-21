from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
import pandas as pd
import os
from datetime import datetime
import re

CHROMEDRIVER_PATH = "C:\\Program Files (x86)\\chromedriver.exe"

def obtener_productos_temu(producto):
    options = Options()
    # options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)

    url = f"https://www.temu.com/pe/search.html?search_key={producto.replace(' ', '%20')}"
    driver.get(url)
    time.sleep(10)

    for _ in range(5):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    driver.quit()

    productos = []

    bloques = soup.find_all("div", class_="_6q6qVUF5 _1UrrHYym")
    print(f"🔍 Se encontraron {len(bloques)} productos en Temu")

    for bloque in bloques:
        try:
            # Título
            titulo_tag = bloque.find("h2", class_="_2BvQbnbN")
            titulo = titulo_tag.text.strip() if titulo_tag else "Sin título"

            # Precio actual
            precio_entero = bloque.find("span", class_="_2de9ERAH")
            precio_decimal = bloque.find("span", class_="_3SrxhhHh")
            if precio_entero and precio_decimal:
                precio = float(f"{precio_entero.text}.{precio_decimal.text}")
            else:
                precio = None

            # Precio original (tachado)
            precio_ori_tag = bloque.find("span", class_="_3TAPHDOX")
            if precio_ori_tag:
                precio_original = float(precio_ori_tag.text.strip())
            else:
                precio_original = None

            # Descuento extra
            descuento_tag = bloque.find("div", class_="_1LLbpUTn")
            descuento_extra = descuento_tag.text.strip() if descuento_tag else None

            # Ventas
            ventas_tag = bloque.find("span", class_="_3vfo0XTx")
            ventas = ventas_tag.text.strip() if ventas_tag else "0"

            # Link
            link_tag = bloque.find("a", href=True)
            link = "https://www.temu.com" + link_tag['href'] if link_tag and link_tag['href'].startswith("/pe") else ""

            productos.append({
                "titulo": titulo,
                "precio": precio,
                "precio_original": precio_original,
                "descuento_extra": descuento_extra,
                "ventas": ventas,
                "link": link,
                "plataforma": "Temu",
                "fecha_scraping": datetime.now().strftime("%Y-%m-%d")
            })
        except Exception as e:
            print(f"❌ Error procesando producto: {e}")
            continue

    os.makedirs("data", exist_ok=True)
    df = pd.DataFrame(productos)
    df.to_csv("data/productos_temu.csv", index=False, encoding="utf-8-sig")
    print(f"✅ {len(productos)} productos guardados en productos_temu.csv")
    return productos
