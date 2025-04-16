from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
import pandas as pd
import os

CHROMEDRIVER_PATH = "C:\\Program Files (x86)\\chromedriver.exe"

def obtener_productos_alibaba(producto):
    options = Options()
    # options.add_argument('--headless')  # Descomenta para ocultar el navegador
    options.add_argument('--disable-gpu')
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)

    url = f"https://www.alibaba.com/trade/search?SearchText={producto.replace(' ', '+')}"
    driver.get(url)
    time.sleep(10)

    # Scroll para cargar productos
    for _ in range(3):
        driver.execute_script("window.scrollBy(0, document.body.scrollHeight);")
        time.sleep(2)

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    driver.quit()

    resultados = []

    bloques = soup.find_all("div", class_="card-info gallery-card-layout-info")

    for bloque in bloques:
        try:
            # Título
            titulo_tag = bloque.find("h2", class_="search-card-e-title")
            titulo = titulo_tag.get_text(strip=True) if titulo_tag else "Sin título"

            # Enlace
            enlace_tag = bloque.find("a", href=True)
            enlace = enlace_tag['href'] if enlace_tag else ""

            if enlace and not enlace.startswith("http"):
                enlace = "https:" + enlace

            # Precio
            precio_tag = bloque.find("div", class_="search-card-e-price-main")
            precio = precio_tag.get_text(strip=True).replace("\xa0", " ") if precio_tag else "Sin precio"

            resultados.append({
                "titulo": titulo,
                "precio": precio,
                "link": enlace
            })
        except Exception as e:
            print(f"❌ Error en producto: {e}")
            continue

    # Guardar CSV
    os.makedirs("data", exist_ok=True)
    df = pd.DataFrame(resultados)
    df.to_csv("data/productos_alibaba.csv", index=False, encoding="utf-8-sig")
    print(f"✅ {len(resultados)} productos guardados en productos_alibaba.csv")
    return resultados
