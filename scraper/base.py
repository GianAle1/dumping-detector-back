import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class BaseScraper:
    """Common setup for Selenium based scrapers."""

    def __init__(self, data_dir: str = "data"):
        options = webdriver.ChromeOptions()
        options.binary_location = "/usr/bin/chromium"
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)

        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

    def scroll(self, times: int = 5, delay: float = 2):
        """Scroll the current page several times waiting for new content."""
        for _ in range(times):
            prev_height = self.driver.execute_script(
                "return document.body.scrollHeight"
            )
            self.driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);"
            )
            WebDriverWait(self.driver, delay).until(
                lambda d: d.execute_script("return document.body.scrollHeight") > prev_height
            )

    def parse(self, *args, **kwargs):
        """Method to be implemented by subclasses."""
        raise NotImplementedError

    def close(self):
        if getattr(self, "driver", None):
            self.driver.quit()
            self.driver = None
