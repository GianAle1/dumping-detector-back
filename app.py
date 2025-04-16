from flask import Flask, render_template, request
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

app = Flask(__name__)

# Cargar datos locales ficticios
data_local = pd.read_csv('data/productos_nacionales.csv')

def scrape_aliexpress(producto):
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    driver = webdriver.Chrome(options=options)

    url = f"https://www.aliexpress.com/wholesale?SearchText={producto}"
    driver.get(url)
    time.sleep(5)

    resultados = []
    items = driver.find_elements(By.CSS_SELECTOR, 'div._3t7zg._2f4Ho')[:5]
    for item in items:
        try:
            nombre = item.find_element(By.CSS_SELECTOR, 'a._3t7zg._2f4Ho span').text
            precio = item.find_element(By.CSS_SELECTOR, 'div.mGXnE._37W_B span').text
            precio = float(precio.replace('$', '').strip())
            resultados.append({'producto': nombre, 'precio': precio})
        except:
            continue

    driver.quit()
    return pd.DataFrame(resultados)

@app.route('/', methods=['GET', 'POST'])
def index():
    comparacion = pd.DataFrame()
    if request.method == 'POST':
        producto = request.form['producto']
        precios_china = scrape_aliexpress(producto)
        precios_local = data_local[data_local['producto'].str.contains(producto, case=False)]

        if not precios_local.empty and not precios_china.empty:
            precio_local_prom = precios_local['precio'].mean()
            precios_china['dumping'] = precios_china['precio'] < precio_local_prom * 0.8
            comparacion = precios_china
            comparacion['precio_local_prom'] = precio_local_prom

    return render_template('index.html', tabla=comparacion.to_html(classes='table table-bordered', index=False))

if __name__ == '__main__':
    app.run(debug=True)
