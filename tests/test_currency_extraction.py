import re
from scraper.alibaba_scraper import extraer_rango_precio


def extract_currency(precio_texto):
    moneda_match = re.search(r"[A-Z]{2,4}|\w+/", precio_texto)
    moneda = moneda_match.group(0).replace("/", "") if moneda_match else "N/A"
    precio_texto = re.sub(r"US\$|/", "", precio_texto)
    _ = extraer_rango_precio(precio_texto)
    return moneda


def test_currency_examples():
    assert extract_currency("S/ 18.24 - 31.00") == "S"
    assert extract_currency("USD 5 - 7") == "USD"
