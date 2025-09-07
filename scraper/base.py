import os
import tempfile
import shutil
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class BaseScraper:
    """Common setup for Selenium based scrapers."""

    def __init__(self, data_dir: str = "data"):
        options = webdriver.ChromeOptions()
        options.binary_location = "/usr/bin/chromium"
        ##options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        profile_dir = tempfile.mkdtemp()
        options.add_argument(f"--user-data-dir={profile_dir}")
        options.add_argument("--start-maximized")

        service = Service("/usr/bin/chromedriver")
        self.driver = webdriver.Chrome(service=service, options=options)

        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.profile_dir = profile_dir

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

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
        if getattr(self, "profile_dir", None):
            shutil.rmtree(self.profile_dir, ignore_errors=True)
            self.profile_dir = None
