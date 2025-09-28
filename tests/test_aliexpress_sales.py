from scraper.aliexpress_scraper import limpiar_cantidad


def test_limpiar_cantidad_k():
    assert limpiar_cantidad("1.2k") == 1200


def test_limpiar_cantidad_mil():
    assert limpiar_cantidad("3 mil") == 3000


def test_limpiar_cantidad_simple():
    assert limpiar_cantidad("450") == 450


def test_limpiar_cantidad_english_sold():
    assert limpiar_cantidad("14 sold") == 14


def test_limpiar_cantidad_english_sold_plus():
    assert limpiar_cantidad("1,000+ sold") == 1000
