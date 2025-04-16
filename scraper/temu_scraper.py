from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
import time
import pandas as pd
import os

CHROMEDRIVER_PATH = "C:\\Program Files (x86)\\chromedriver.exe"

def obtener_productos_temu(producto):
    options = Options()
    options.add_argument('--headless')  # descomenta si no quieres ver el navegador
    options.add_argument('--disable-gpu')
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)

    url = f"https://www.temu.com/pe/search.html?search_key={producto.replace(' ', '%20')}"
    driver.get(url)
    time.sleep(10)

    # Scroll lento para cargar productos
    for _ in range(3):
        driver.execute_script("window.scrollBy(0, document.body.scrollHeight);")
        time.sleep(2)

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    driver.quit()

    productos = []

    # Buscar los contenedores de productos
    bloques = soup.find_all("div", class_="_6q6qVUF5 _1UrrHYym")

    for bloque in bloques:
        try:
            # Título
            titulo_tag = bloque.find("h2", class_="_2BvQbnbN")
            titulo = titulo_tag.text.strip() if titulo_tag else "Sin título"

            # Precio
            precio_entero = bloque.find("span", class_="_2de9ERAH")
            precio_decimal = bloque.find("span", class_="_3SrxhhHh")
            if precio_entero and precio_decimal:
                precio = float(f"{precio_entero.text}.{precio_decimal.text}")
            else:
                precio = None

            productos.append({
                "titulo": titulo,
                "precio": precio
            })
        except Exception as e:
            print(f"❌ Error procesando producto: {e}")
            continue

    # Guardar CSV
    os.makedirs("data", exist_ok=True)
    df = pd.DataFrame(productos)
    df.to_csv("data/productos_temu.csv", index=False, encoding="utf-8-sig")
    print(f"✅ {len(productos)} productos guardados en productos_temu.csv")
    return productos
