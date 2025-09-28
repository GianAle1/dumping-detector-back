# base.py
import os
import shutil
import tempfile
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException


class BaseScraper:
    """Common setup for Selenium-based scrapers (visible o headless)."""

    def __init__(self, data_dir: str = "data"):
        remote_url = os.getenv("SELENIUM_REMOTE_URL")
        options = webdriver.ChromeOptions()

        # Idioma + UA realista
        options.add_argument("--lang=es-ES,es;q=0.9")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        )

        # Flags estables
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1366,900")
        options.add_argument("--start-maximized")

        # Stealth básico
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_argument("--disable-blink-features=AutomationControlled")

        # Proxy (opcional). Exporta PROXY_URL si lo usas (ideal residencial).
        proxy = os.getenv("PROXY_URL")
        if proxy:
            options.add_argument(f"--proxy-server={proxy}")

        # PERFIL
        use_custom_profile = os.getenv("USE_CUSTOM_PROFILE", "").lower() in {
            "1",
            "true",
            "yes",
        }

        self._tmp_profile = None
        self._temp_dir = None

        if remote_url:
            # Perfil PERSISTENTE dentro del contenedor selenium (montado por docker-compose)
            profile_dir = os.getenv("SELENIUM_PROFILE_DIR", "/home/seluser/profiles/aliexpress")
            options.add_argument(f"--user-data-dir={profile_dir}")
            self.driver = webdriver.Remote(command_executor=remote_url, options=options)
        else:
            # Local (por si alguna vez corres sin selenium remoto)
            chromium_path = shutil.which("chromium")
            if not chromium_path:
                raise FileNotFoundError("Chromium no encontrado en PATH.")
            options.binary_location = chromium_path

            if use_custom_profile:
                self._temp_dir = tempfile.TemporaryDirectory(prefix="ali_profile_")
                options.add_argument(f"--user-data-dir={self._temp_dir.name}")
            else:
                tmp_profile = tempfile.mkdtemp(prefix="ali_profile_")
                options.add_argument(f"--user-data-dir={tmp_profile}")
                self._tmp_profile = tmp_profile

            chromedriver_path = shutil.which("chromedriver")
            if not chromedriver_path:
                raise FileNotFoundError("chromedriver no encontrado en PATH.")
            service = Service(chromedriver_path)
            self.driver = webdriver.Chrome(service=service, options=options)

        # Stealth extra vía CDP (tras crear driver)
        try:
            self.driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {"source": """
                    Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
                    window.chrome = window.chrome || {};
                    window.chrome.app = {isInstalled: false};
                    Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4]});
                    Object.defineProperty(navigator, 'languages', {get: () => ['es-ES','es']});
                """}
            )
        except Exception:
            pass

        # Estructura de datos
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def wait_ready(self, timeout: int = 15):
        """Espera a que el documento termine de cargar."""
        WebDriverWait(self.driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )

    def scroll(self, times: int = 5, delay: float = 2):
        """Scroll básico (para páginas simples)."""
        for _ in range(times):
            prev = self.driver.execute_script("return document.body.scrollHeight")
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            try:
                WebDriverWait(self.driver, delay).until(
                    lambda d: d.execute_script("return document.body.scrollHeight") > prev
                )
            except TimeoutException:
                current = self.driver.execute_script(
                    "return document.body.scrollHeight"
                )
                if current <= prev:
                    break

    def close(self):
        # Si estás mirando, puedes dejar la ventana abierta exportando VISUAL_MODE=1
        if os.getenv("VISUAL_MODE") == "1":
            return
        if getattr(self, "driver", None):
            self.driver.quit()
            self.driver = None
        if getattr(self, "_tmp_profile", None):
            shutil.rmtree(self._tmp_profile, ignore_errors=True)
            self._tmp_profile = None
        if getattr(self, "_temp_dir", None):
            self._temp_dir.cleanup()
            self._temp_dir = None
