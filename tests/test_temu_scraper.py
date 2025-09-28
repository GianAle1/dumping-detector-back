import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import quote_plus

from scraper.temu_scraper import TemuScraper


class TestTemuScraper(unittest.TestCase):
    @patch("scraper.temu_scraper.BaseScraper.__init__", return_value=None)
    @patch("scraper.temu_scraper.WebDriverWait")
    def test_parse_product_without_discount(self, mock_wait, mock_base_init):
        mock_wait.return_value.until.return_value = True

        scraper = TemuScraper()
        mock_driver = MagicMock()
        scraper.driver = mock_driver
        scraper.scroll = MagicMock()
        scraper.close = MagicMock()

        mock_driver.page_source = """
        <html><body>
        <div class="_6q6qVUF5 _1UrrHYym">
            <h2 class="_2BvQbnbN">Producto</h2>
            <span class="_2de9ERAH">10</span>
            <span class="_3SrxhhHh">99</span>
            <span class="_3vfo0XTx">1 vendido</span>
            <a href="/pe/item"></a>
        </div>
        </body></html>
        """

        search_term = "cafetera & taza fría"
        productos = scraper.parse(search_term)

        self.assertIsNone(productos[0]["descuento_extra"])
        expected_url = (
            "https://www.temu.com/pe/search.html?search_key="
            f"{quote_plus(search_term)}"
        )
        mock_driver.get.assert_called_once_with(expected_url)

    @patch("scraper.temu_scraper.BaseScraper.__init__", return_value=None)
    @patch("scraper.temu_scraper.WebDriverWait")
    def test_parse_price_with_currency_and_thousands(self, mock_wait, mock_base_init):
        mock_wait.return_value.until.return_value = True

        scraper = TemuScraper()
        mock_driver = MagicMock()
        scraper.driver = mock_driver
        scraper.scroll = MagicMock()
        scraper.close = MagicMock()

        mock_driver.page_source = """
        <html><body>
        <div class="_6q6qVUF5 _1UrrHYym">
            <h2 class="_2BvQbnbN">Producto Premium</h2>
            <span class="_2de9ERAH">S/ 1,299</span>
            <span class="_3SrxhhHh">50</span>
            <span class="_3TAPHDOX">US$ 1,499</span>
            <a href="/pe/item-premium"></a>
        </div>
        </body></html>
        """

        productos = scraper.parse("producto premium")

        self.assertEqual(len(productos), 1)
        producto = productos[0]
        self.assertEqual(producto["titulo"], "Producto Premium")
        self.assertEqual(producto["precio"], 1299.50)
        self.assertEqual(producto["precio_original"], 1499.0)
        self.assertEqual(producto["link"], "https://www.temu.com/pe/item-premium")


if __name__ == "__main__":
    unittest.main()
