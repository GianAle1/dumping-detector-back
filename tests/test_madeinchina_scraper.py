from unittest.mock import MagicMock, patch

from scraper.madeinchina_scraper import MadeInChinaScraper


@patch("scraper.madeinchina_scraper.BaseScraper.__init__", return_value=None)
@patch("scraper.madeinchina_scraper.WebDriverWait")
def test_parse_returns_company_name(mock_wait, mock_base_init):
    mock_wait.return_value.until.return_value = True

    scraper = MadeInChinaScraper()
    scraper.driver = MagicMock()
    scraper.scroll = MagicMock()
    scraper.close = MagicMock()

    scraper.driver.get.return_value = None
    scraper.driver.page_source = """
    <html><body>
        <div class=\"list-node-content\">
            <h2 class=\"product-name\" title=\"Producto\">
                <a href=\"/product\">Producto</a>
            </h2>
            <strong class=\"price\">US$1-2</strong>
            <div class=\"info\">MOQ info</div>
            <a class=\"company-name\">Empresa S.A.</a>
            <div class=\"company-address-detail\">Perú</div>
        </div>
    </body></html>
    """

    resultados = scraper.parse("producto de prueba", paginas=1)

    assert resultados
    assert resultados[0]["empresa"] == "Empresa S.A."
    scraper.close.assert_called_once()


@patch("scraper.madeinchina_scraper.BaseScraper.__init__", return_value=None)
@patch("scraper.madeinchina_scraper.WebDriverWait")
def test_parse_normalizes_thousand_separators_and_currencies(
    mock_wait, mock_base_init
):
    mock_wait.return_value.until.return_value = True

    scraper = MadeInChinaScraper()
    scraper.driver = MagicMock()
    scraper.scroll = MagicMock()
    scraper.close = MagicMock()

    scraper.driver.get.return_value = None
    precios = [
        "US$1,299.50-1,599.75",
        "€1.299,50",
        "R$ 2.000,00 - R$ 2.500,00",
        "¥1,299",
    ]

    productos_html = "".join(
        f"""
        <div class=\"list-node-content\">
            <h2 class=\"product-name\" title=\"Producto {idx}\">
                <a href=\"/product{idx}\">Producto {idx}</a>
            </h2>
            <strong class=\"price\">{precio}</strong>
            <div class=\"info\">MOQ info</div>
            <a class=\"company-name\">Empresa {idx}</a>
            <div class=\"company-address-detail\">Ubicación</div>
        </div>
        """
        for idx, precio in enumerate(precios, start=1)
    )

    scraper.driver.page_source = f"""
    <html><body>
        {productos_html}
    </body></html>
    """

    resultados = scraper.parse("producto de prueba", paginas=1)

    assert len(resultados) == len(precios)
    assert resultados[0]["precio_min"] == 1299.5
    assert resultados[0]["precio_max"] == 1599.75
    assert resultados[1]["precio_min"] == resultados[1]["precio_max"] == 1299.5
    assert resultados[2]["precio_min"] == 2000.0
    assert resultados[2]["precio_max"] == 2500.0
    assert resultados[3]["precio_min"] == resultados[3]["precio_max"] == 1299.0
    scraper.close.assert_called_once()
