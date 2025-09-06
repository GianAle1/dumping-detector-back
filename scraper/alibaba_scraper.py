from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
import pandas as pd
import os
import re

def extraer_rango_precio(texto):
    match = re.findall(r"([\d.,]+)", texto)
    if len(match) == 1:
        precio_min = precio_max = float(match[0].replace(",", ""))
    elif len(match) >= 2:
        precio_min = float(match[0].replace(",", ""))
        precio_max = float(match[1].replace(",", ""))
    else:
        return None, None, None
    promedio = round((precio_min + precio_max) / 2, 2)
    return precio_min, precio_max, promedio

def obtener_productos_alibaba(producto, max_paginas=4):
    options = Options()
    # options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    resultados = []

    for pagina in range(1, max_paginas + 1):
        print(f"🌐 Scrapeando página {pagina}...")
        url = f"https://www.alibaba.com/trade/search?SearchText={producto.replace(' ', '+')}&page={pagina}"
        driver.get(url)
        time.sleep(10)

        for _ in range(3):
            driver.execute_script("window.scrollBy(0, document.body.scrollHeight);")
            time.sleep(2)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        bloques = soup.find_all("div", class_="card-info gallery-card-layout-info")

        for bloque in bloques:
            try:
                titulo_tag = bloque.find("h2", class_="search-card-e-title")
                titulo = titulo_tag.get_text(strip=True) if titulo_tag else "Sin título"

                enlace_tag = bloque.find("a", href=True)
                enlace = enlace_tag['href'] if enlace_tag else ""
                if enlace and not enlace.startswith("http"):
                    enlace = "https:" + enlace

                precio_tag = bloque.find("div", class_="search-card-e-price-main")
                precio_texto = precio_tag.get_text(strip=True).replace("\xa0", " ") if precio_tag else "Sin precio"
                moneda = re.search(r"[A-Z]{2,4}", precio_texto)
                moneda = moneda.group(0) if moneda else "N/A"
                precio_min, precio_max, precio_prom = extraer_rango_precio(precio_texto)

                proveedor_tag = bloque.find("a", class_="search-card-e-company")
                proveedor = proveedor_tag.get_text(strip=True) if proveedor_tag else "Sin proveedor"

                ventas_tag = bloque.find("div", class_="search-card-e-market-power-common")
                ventas = ventas_tag.get_text(strip=True) if ventas_tag else "No info"

                rating_tag = bloque.find("span", class_="search-card-e-review")
                rating = rating_tag.get_text(strip=True) if rating_tag else "No rating"

                resultados.append({
                    "pagina": pagina,
                    "titulo": titulo,
                    "precio_min": precio_min,
                    "precio_max": precio_max,
                    "precio_promedio": precio_prom,
                    "moneda": moneda,
                    "proveedor": proveedor,
                    "ventas": ventas,
                    "rating": rating,
                    "link": enlace
                })
            except Exception as e:
                print(f"❌ Error en producto: {e}")
                continue

    driver.quit()

    os.makedirs("data", exist_ok=True)
    df = pd.DataFrame(resultados)
    df.to_csv("data/productos_alibaba.csv", index=False, encoding="utf-8-sig")
    print(f"✅ {len(resultados)} productos guardados en productos_alibaba.csv")

    return resultados
