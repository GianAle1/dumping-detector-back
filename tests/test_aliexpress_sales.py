from scraper.aliexpress_scraper import limpiar_cantidad


def test_limpiar_cantidad_k():
    assert limpiar_cantidad("1.2k") == 1200


def test_limpiar_cantidad_mil():
    assert limpiar_cantidad("3 mil") == 3000


def test_limpiar_cantidad_simple():
    assert limpiar_cantidad("450") == 450
