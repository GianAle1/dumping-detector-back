import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import quote_plus

from scraper.alibaba_scraper import AlibabaScraper


class TestAlibabaScraper(unittest.TestCase):
    @patch("scraper.alibaba_scraper.BaseScraper.__init__", return_value=None)
    @patch("scraper.alibaba_scraper.WebDriverWait")
    def test_url_encoding_special_characters(self, mock_wait, mock_base_init):
        mock_wait.return_value.until.return_value = True

        scraper = AlibabaScraper()
        mock_driver = MagicMock()
        mock_driver.page_source = "<html></html>"
        scraper.driver = mock_driver
        scraper.scroll = MagicMock()

        producto = "zapatos niño & niña"
        scraper.parse(producto, max_paginas=1)

        encoded = quote_plus(producto)
        expected_url = (
            f"https://www.alibaba.com/trade/search?SearchText={encoded}&page=1"
        )
        mock_driver.get.assert_called_with(expected_url)


if __name__ == "__main__":
    unittest.main()

