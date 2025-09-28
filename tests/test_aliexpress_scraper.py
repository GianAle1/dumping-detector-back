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
        mock_driver.get.assert_called_with(expected_url)

    @patch("scraper.aliexpress_scraper.BaseScraper.__init__", return_value=None)
    def test_preserves_cards_when_final_search_empty(self, mock_base_init):
        scraper = AliExpressScraper()
        mock_driver = MagicMock()
        mock_driver.current_url = "https://es.aliexpress.com/"
        scraper.driver = mock_driver

        scraper.wait_ready = MagicMock()
        scraper._accept_banners = MagicMock()
        scraper._human_scroll_until_growth = MagicMock()
        scraper._is_blocked = MagicMock(return_value=False)
        scraper.close = MagicMock()

        card_element = MagicMock(name="card")
        card_data = {
            "titulo": "Producto",
            "precio": 10.0,
            "precio_original": None,
            "descuento": None,
            "ventas": 5,
            "link": "https://example.com/item",
        }

        with patch.object(scraper, "_find_all_any", side_effect=[[card_element], []]) as mock_find_all, \
             patch.object(scraper, "_extract_card", return_value=card_data) as mock_extract:
            resultados = scraper.parse("producto", paginas=1)

        self.assertEqual(mock_find_all.call_count, 2)
        mock_extract.assert_called_once_with(card_element)
        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]["titulo"], "Producto")


if __name__ == "__main__":
    unittest.main()

