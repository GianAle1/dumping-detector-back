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
        headless = os.getenv("HEADLESS", "true").lower() in {"1", "true", "yes"}

        chromium_path = shutil.which("chromium")
        if not chromium_path:
            raise FileNotFoundError(
                "Chromium executable not found. Please install chromium or adjust your PATH."
            )
        options.binary_location = chromium_path
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        temp_dir = tempfile.TemporaryDirectory()
        options.add_argument(f"--user-data-dir={temp_dir.name}")
        if headless:
            options.add_argument("--headless=new")
        else:
            options.add_argument("--start-maximized")

        chromedriver_path = shutil.which("chromedriver")
        if not chromedriver_path:
            raise FileNotFoundError(
                "Chromedriver executable not found. Please install chromedriver or adjust your PATH."
            )
        service = Service(chromedriver_path)
        try:
            self.driver = webdriver.Chrome(service=service, options=options)
        except Exception:
            temp_dir.cleanup()
            raise

        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.temp_dir = temp_dir

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
        if getattr(self, "temp_dir", None):
            self.temp_dir.cleanup()
            self.temp_dir = None
