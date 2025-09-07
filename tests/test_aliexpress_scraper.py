import unittest
from unittest.mock import patch, MagicMock
from urllib.parse import quote_plus

from selenium.common.exceptions import TimeoutException

from scraper.aliexpress_scraper import AliExpressScraper


class TestAliExpressScraper(unittest.TestCase):
    @patch("scraper.aliexpress_scraper.BaseScraper.__init__", return_value=None)
    @patch("scraper.aliexpress_scraper.WebDriverWait")
    def test_url_encoding_special_characters(self, mock_wait, mock_base_init):
        mock_wait.return_value.until.side_effect = TimeoutException

        scraper = AliExpressScraper()
        mock_driver = MagicMock()
        scraper.driver = mock_driver

        producto = "zapatos niño & niña"
        scraper.parse(producto, paginas=1)

        encoded = quote_plus(producto)
        expected_url = (
            f"https://es.aliexpress.com/wholesale?SearchText={encoded}&page=1"
        )
        self.assertEqual(mock_driver.get.call_count, 3)
        mock_driver.get.assert_called_with(expected_url)

    @patch("scraper.aliexpress_scraper.BaseScraper.__init__", return_value=None)
    @patch.object(AliExpressScraper, "scroll")
    @patch("scraper.aliexpress_scraper.WebDriverWait")
    def test_skip_blocks_without_href(self, mock_wait, mock_scroll, mock_base_init):
        mock_wait.return_value.until.return_value = True

        scraper = AliExpressScraper()
        mock_driver = MagicMock()
        mock_driver.page_source = (
            '<div class="search-item-card-wrapper-gallery">'
            '<a class="search-card-item" title="Producto"></a>'
            "</div>"
        )
        scraper.driver = mock_driver

        resultados = scraper.parse("producto", paginas=1)
        self.assertEqual(resultados, [])


if __name__ == "__main__":
    unittest.main()

