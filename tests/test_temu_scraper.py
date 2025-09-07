import unittest
from unittest.mock import MagicMock, patch

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

        productos = scraper.parse("producto")

        self.assertIsNone(productos[0]["descuento_extra"])


if __name__ == "__main__":
    unittest.main()
