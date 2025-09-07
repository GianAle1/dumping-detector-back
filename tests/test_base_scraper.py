import unittest
from unittest.mock import patch, MagicMock

from scraper.base import BaseScraper


class TestBaseScraper(unittest.TestCase):
    @patch("scraper.base.webdriver.Chrome")
    @patch("scraper.base.Service")
    @patch("scraper.base.shutil.which")
    def test_initialization_and_close(self, mock_which, mock_service, mock_chrome):
        mock_which.side_effect = lambda name: f"/usr/bin/{name}"
        mock_driver = MagicMock()
        mock_chrome.return_value = mock_driver

        scraper = BaseScraper()

        mock_which.assert_any_call("chromium")
        mock_which.assert_any_call("chromedriver")
        mock_service.assert_called_once_with("/usr/bin/chromedriver")
        mock_chrome.assert_called_once()
        self.assertIs(scraper.driver, mock_driver)

        scraper.close()
        mock_driver.quit.assert_called_once()
        self.assertIsNone(scraper.driver)

    @patch("scraper.base.shutil.which")
    def test_missing_chromium_raises_error(self, mock_which):
        mock_which.side_effect = (
            lambda name: "/usr/bin/chromedriver" if name == "chromedriver" else None
        )
        with self.assertRaises(FileNotFoundError):
            BaseScraper()

    @patch("scraper.base.shutil.which")
    def test_missing_chromedriver_raises_error(self, mock_which):
        mock_which.side_effect = (
            lambda name: "/usr/bin/chromium" if name == "chromium" else None
        )
        with self.assertRaises(FileNotFoundError):
            BaseScraper()


if __name__ == "__main__":
    unittest.main()

