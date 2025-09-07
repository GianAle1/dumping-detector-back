from scraper.aliexpress_scraper import limpiar_precio


def test_limpiar_precio_con_separador_miles():
    assert limpiar_precio("1.299,00") == 1299.00
