from scraper.aliexpress_scraper import limpiar_precio


def test_limpiar_precio_con_separador_miles():
    assert limpiar_precio("1.299,00") == 1299.00


def test_limpiar_precio_con_rango_decimal_punto():
    assert limpiar_precio("US $7.99 - 15.99") == 7.99


def test_limpiar_precio_con_rango_decimal_coma():
    assert limpiar_precio("€ 12,34 - 56,78") == 12.34


def test_limpiar_precio_toma_extremo_inferior():
    assert limpiar_precio("€56,78 - 12,34") == 12.34
