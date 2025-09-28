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
