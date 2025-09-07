import unittest
from unittest.mock import patch, MagicMock

from scraper.base import BaseScraper


class TestBaseScraper(unittest.TestCase):
    @patch("scraper.base.webdriver.Chrome")
    @patch("scraper.base.Service")
    def test_initialization_and_close(self, mock_service, mock_chrome):
        mock_driver = MagicMock()
        mock_chrome.return_value = mock_driver

        scraper = BaseScraper()

        mock_service.assert_called_once_with("/usr/bin/chromedriver")
        mock_chrome.assert_called_once()
        self.assertIs(scraper.driver, mock_driver)

        scraper.close()
        mock_driver.quit.assert_called_once()
        self.assertIsNone(scraper.driver)


if __name__ == "__main__":
    unittest.main()
