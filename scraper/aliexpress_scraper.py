from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
import time

CHROMEDRIVER_PATH = "C:\\Program Files (x86)\\chromedriver.exe"

def obtener_productos(producto):
    options = Options()
    # options.add_argument('--headless')  # puedes activarlo si no deseas ver la ventana
    options.add_argument('--disable-gpu')
    service = Service(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)

    url = f"https://es.aliexpress.com/wholesale?SearchText={producto.replace(' ', '+')}&page=1"
    print(f"🌀 Cargando página 1...")
    driver.get(url)
    time.sleep(5)

    # ⬇️ Hacer scroll hacia abajo para cargar todos los productos
    SCROLL_PAUSE_TIME = 2
    last_height = driver.execute_script("return document.body.scrollHeight")

    for _ in range(5):  # puedes ajustar la cantidad de scrolls según la longitud de la página
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(SCROLL_PAUSE_TIME)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height

    print("📥 Scroll completo. Extrayendo HTML...")

    soup = BeautifulSoup(driver.page_source, 'html.parser')
    bloques = soup.find_all('div', class_='l5_t')

    print(f"🔍 Productos encontrados: {len(bloques)}")

    resultados = []

    for bloque in bloques:
        try:
            titulo_tag = bloque.find('div', class_='l5_ae')
            titulo = titulo_tag.get('title', '').strip() if titulo_tag else 'Sin título'

            precio_tag = bloque.find('div', class_='l5_kt')
            spans = precio_tag.find_all('span') if precio_tag else []
            if len(spans) >= 3:
                precio = float(''.join(span.text for span in spans[1:]))
            else:
                precio = None

            resultados.append({"titulo": titulo, "precio": precio})
        except Exception as e:
            print(f"❌ Error procesando producto: {e}")
            continue

    driver.quit()
    return resultados
