import unittest
from unittest.mock import patch, MagicMock

from scraper.base import BaseScraper


class TestBaseScraper(unittest.TestCase):
    @patch("scraper.base.webdriver.Chrome")
    @patch("scraper.base.ChromeDriverManager")
    def test_initialization_and_close(self, mock_manager, mock_chrome):
        mock_driver = MagicMock()
        mock_chrome.return_value = mock_driver
        mock_manager.return_value.install.return_value = "/path/to/chromedriver"

        scraper = BaseScraper()
        self.assertIs(scraper.driver, mock_driver)

        scraper.close()
        mock_driver.quit.assert_called_once()
        self.assertIsNone(scraper.driver)


if __name__ == "__main__":
    unittest.main()
