import unittest
from unittest.mock import patch, MagicMock

from selenium.common.exceptions import TimeoutException

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

    @patch("scraper.base.WebDriverWait")
    def test_scroll_handles_timeout_without_exception(self, mock_wait):
        scraper = object.__new__(BaseScraper)
        driver = MagicMock()
        scraper.driver = driver

        driver.execute_script.side_effect = [
            100,  # initial height
            None,  # scroll action
            100,  # height after timeout check
        ]

        mock_wait.return_value.until.side_effect = TimeoutException()

        try:
            scraper.scroll(times=2, delay=1)
        except TimeoutException:  # pragma: no cover - should not be raised
            self.fail("scroll should handle TimeoutException without raising")

        mock_wait.assert_called_once()
        self.assertEqual(driver.execute_script.call_count, 3)


if __name__ == "__main__":
    unittest.main()

