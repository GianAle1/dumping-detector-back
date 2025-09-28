from scraper.alibaba_scraper import extraer_rango_precio


def test_currency_and_range_examples():
    minimo, maximo, _, moneda = extraer_rango_precio("S/ 18.24 - 31.00")
    assert minimo == 18.24
    assert maximo == 31.00
    assert moneda == "S/"

    minimo, maximo, _, moneda = extraer_rango_precio("S/ 18,24 - 31,00")
    assert minimo == 18.24
    assert maximo == 31.00
    assert moneda == "S/"

    minimo, maximo, _, moneda = extraer_rango_precio("USD 5 - 7")
    assert minimo == 5.0
    assert maximo == 7.0
    assert moneda == "USD"


def test_range_detection_specific():
    minimo, maximo, _, moneda = extraer_rango_precio("USD 72.41-80.00")
    assert minimo == 72.41
    assert maximo == 80.00
    assert moneda == "USD"


def test_single_value_with_decimal_comma():
    minimo, maximo, _, moneda = extraer_rango_precio("S/ 18,24")
    assert minimo == 18.24
    assert maximo == 18.24
    assert moneda == "S/"
