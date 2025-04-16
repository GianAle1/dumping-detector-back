from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import pandas as pd

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
