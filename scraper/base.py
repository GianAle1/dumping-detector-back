import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


class BaseScraper:
    """Common setup for Selenium based scrapers."""

    def __init__(self, headless: bool = False, data_dir: str = "data"):
        options = Options()
        if headless:
            options.add_argument("--headless")
        options.add_argument("--disable-gpu")

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)

        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

    def scroll(self, times: int = 5, delay: float = 2):
        """Scroll the current page several times."""
        for _ in range(times):
            self.driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);"
            )
            time.sleep(delay)

    def parse(self, *args, **kwargs):
        """Method to be implemented by subclasses."""
        raise NotImplementedError

    def close(self):
        if getattr(self, "driver", None):
            self.driver.quit()
            self.driver = None
