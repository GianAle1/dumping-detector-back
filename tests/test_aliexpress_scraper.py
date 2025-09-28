import unittest
from unittest.mock import patch, MagicMock, call
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By

from scraper.aliexpress_scraper import AliExpressScraper


class TestAliExpressScraper(unittest.TestCase):
    @patch("scraper.aliexpress_scraper.BaseScraper.__init__", return_value=None)
    @patch("scraper.aliexpress_scraper.WebDriverWait")
    def test_url_encoding_special_characters(self, mock_wait, mock_base_init):
        mock_wait.return_value.until.side_effect = TimeoutException

        scraper = AliExpressScraper()
        mock_driver = MagicMock()
        scraper.driver = mock_driver
        mock_driver.page_source = ""

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

    @patch("scraper.aliexpress_scraper.BaseScraper.__init__", return_value=None)
    def test_parse_handles_blank_current_url(self, mock_base_init):
        scraper = AliExpressScraper()
        mock_driver = MagicMock()
        mock_driver.current_url = "about:blank"
        scraper.driver = mock_driver

        scraper.wait_ready = MagicMock()
        scraper._accept_banners = MagicMock()
        scraper._human_scroll_until_growth = MagicMock()
        scraper._is_blocked = MagicMock(return_value=False)
        scraper.close = MagicMock()

        def fake_find_all(selectors, timeout=10):
            return []

        with patch.object(scraper, "_find_all_any", side_effect=fake_find_all) as mock_find_all, \
             patch.object(scraper, "_extract_card", return_value=None) as mock_extract:
            resultados = scraper.parse("producto", paginas=1)

        self.assertIsInstance(resultados, list)
        self.assertEqual(resultados, [])
        self.assertTrue(all(call.args[0] == scraper.CARD_CONTAINERS for call in mock_find_all.call_args_list))
        mock_extract.assert_not_called()

    @patch("scraper.aliexpress_scraper.BaseScraper.__init__", return_value=None)
    @patch("scraper.aliexpress_scraper.WebDriverWait")
    def test_mobile_fallback_detects_gallery_cards(self, mock_wait, mock_base_init):
        scraper = AliExpressScraper()

        driver = MagicMock()
        driver.current_url = "https://es.aliexpress.com/"
        scraper.driver = driver

        scraper.wait_ready = MagicMock()
        scraper._accept_banners = MagicMock()
        scraper._human_scroll_until_growth = MagicMock()
        scraper._is_blocked = MagicMock(return_value=True)
        scraper._apply_mobile_ua = MagicMock()
        scraper.close = MagicMock()

        card_element = MagicMock(name="mobile_card")

        def fake_find_elements(by, selector):
            if by == By.CSS_SELECTOR and selector == "div.search-item-card-wrapper-gallery":
                return [card_element]
            return []

        driver.find_elements = MagicMock(side_effect=fake_find_elements)

        def fake_until(condition):
            result = condition(driver)
            if result:
                return result
            raise TimeoutException()

        mock_wait.return_value.until.side_effect = fake_until

        def get_side_effect(url):
            driver.current_url = url

        driver.get.side_effect = get_side_effect

        card_data = {
            "titulo": "Producto móvil",
            "precio": 9.99,
            "precio_original": None,
            "descuento": None,
            "ventas": 0,
            "link": "https://example.com/mobile",
        }

        scraper._extract_card = MagicMock(return_value=card_data)

        resultados = scraper.parse("producto", paginas=1)

        driver.find_elements.assert_any_call(By.CSS_SELECTOR, "div.search-item-card-wrapper-gallery")
        scraper._extract_card.assert_called_with(card_element)

        self.assertEqual(len(resultados), 1)
        self.assertEqual(resultados[0]["titulo"], "Producto móvil")

    @patch("scraper.aliexpress_scraper.BaseScraper.__init__", return_value=None)
    def test_extract_card_handles_price_container(self, mock_base_init):
        scraper = AliExpressScraper()

        anchor = MagicMock()
        anchor.text = "Producto"

        def anchor_get_attribute(attr):
            mapping = {"href": "https://example.com/item", "title": "Producto"}
            return mapping.get(attr)

        anchor.get_attribute.side_effect = anchor_get_attribute

        price_container = MagicMock()
        price_container.text = "US$ 12,34"
        price_container.tag_name = "div"

        price_spans = []
        for text in ("US$", "12,34"):
            span = MagicMock()
            span.text = text
            price_spans.append(span)

        def price_get_attribute(attr):
            mapping = {
                "data-price": None,
                "class": "ks_kn ks_le",
                "innerText": "US$ 12,34",
            }
            return mapping.get(attr)

        price_container.get_attribute.side_effect = price_get_attribute
        price_container.find_elements.return_value = price_spans

        pori_container = MagicMock()
        pori_container.text = "US$ 15,00"
        pori_container.tag_name = "div"

        pori_spans = []
        for text in ("US$", "15,00"):
            span = MagicMock()
            span.text = text
            pori_spans.append(span)

        def pori_get_attribute(attr):
            mapping = {
                "data-original-price": None,
                "class": "ks_kw ks_kv",
                "innerText": "US$ 15,00",
            }
            return mapping.get(attr)

        pori_container.get_attribute.side_effect = pori_get_attribute
        pori_container.find_elements.return_value = pori_spans

        sold_el = MagicMock()

        def sold_get_attribute(attr):
            mapping = {"data-sold": "1.2k"}
            return mapping.get(attr)

        sold_el.get_attribute.side_effect = sold_get_attribute
        sold_el.text = "1.2k vendidos"

        card = MagicMock()
        card.text = "1.2k vendidos"

        sequence = iter([anchor, price_container, pori_container, None, sold_el])

        def fake_first_match(root, selectors):
            return next(sequence, None)

        with patch.object(scraper, "_first_match", side_effect=fake_first_match):
            resultado = scraper._extract_card(card)

        self.assertIsNotNone(resultado)
        self.assertAlmostEqual(resultado["precio"], 12.34)
        self.assertAlmostEqual(resultado["precio_original"], 15.0)
        self.assertEqual(resultado["ventas"], 1200)

    @patch("scraper.aliexpress_scraper.BaseScraper.__init__", return_value=None)
    def test_resolve_price_text_with_bs_structure(self, mock_base_init):
        scraper = AliExpressScraper()

        html = """
        <div class="list-item">
            <div class="ks_kn">
                <span class="ks_cv">US$</span>
                <span class="ks_le">1.234,56</span>
            </div>
        </div>
        """
        soup = BeautifulSoup(html, "html.parser")
        bloque = soup.select_one("div.list-item")
        price_tag = bloque.select_one(", ".join(scraper.PRICE))

        precio = scraper._to_float(scraper._resolve_price_text(price_tag, "data-price"))

        self.assertAlmostEqual(precio, 1234.56)

    @patch("scraper.aliexpress_scraper.BaseScraper.__init__", return_value=None)
    def test_is_blocked_ignores_meta_robots(self, mock_base_init):
        scraper = AliExpressScraper()
        mock_driver = MagicMock()
        mock_driver.current_url = "https://es.aliexpress.com/item"
        mock_driver.page_source = """
        <html>
            <head>
                <meta name="robots" content="noindex, nofollow" />
                <title>Producto regular</title>
            </head>
            <body>
                <div>Contenido disponible sin captcha.</div>
            </body>
        </html>
        """

        self.assertFalse(scraper._is_blocked(mock_driver))


if __name__ == "__main__":
    unittest.main()

