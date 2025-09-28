# base.py
import os
import shutil
import tempfile
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException, SessionNotCreatedException


class BaseScraper:
    """Common setup for Selenium-based scrapers (visible o headless)."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

        self._tmp_profile = None
        self._temp_dir = None

        remote_url = os.getenv("SELENIUM_REMOTE_URL")  # ej: http://selenium:4444
        proxy = os.getenv("PROXY_URL")
        use_custom_profile = os.getenv("USE_CUSTOM_PROFILE", "").lower() in {"1", "true", "yes"}

        def build_options(use_profile: bool, profile_dir: str | None) -> webdriver.ChromeOptions:
            opts = webdriver.ChromeOptions()
            # Idioma + UA realista
            opts.add_argument("--lang=es-ES,es;q=0.9")
            opts.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            )
            # Flags estables para contenedor
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--disable-gpu")
            opts.add_argument("--window-size=1366,900")
            # Evita el bug de DevToolsActivePort
            opts.add_argument("--remote-debugging-port=0")
            # Stealth básico
            opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts.add_experimental_option("useAutomationExtension", False)
            opts.add_argument("--disable-blink-features=AutomationControlled")
            # Proxy (opcional)
            if proxy:
                opts.add_argument(f"--proxy-server={proxy}")
            # Perfil (solo si lo pedimos)
            if use_profile and profile_dir:
                # OJO: no verificamos desde aquí si existe; Chrome lo validará dentro del contenedor Selenium.
                opts.add_argument(f"--user-data-dir={profile_dir}")
            return opts

        if remote_url:
            # --- MODO REMOTO: Selenium Standalone (contenedor selenium)
            profile_dir = os.getenv("SELENIUM_PROFILE_DIR") if use_custom_profile else None

            # 1º intento: con perfil (si está habilitado)
            options = build_options(use_custom_profile, profile_dir)
            try:
                self.driver = webdriver.Remote(command_executor=remote_url, options=options)
            except SessionNotCreatedException as e:
                # Si Chrome crashea (p.ej. perfil corrupto/permiso), reintenta sin perfil
                options = build_options(False, None)
                self.driver = webdriver.Remote(command_executor=remote_url, options=options)

        else:
            # --- MODO LOCAL: sin grid
            chromium_path = shutil.which("chromium") or shutil.which("google-chrome") or shutil.which("chrome")
            if not chromium_path:
                raise FileNotFoundError("Chromium/Chrome no encontrado en PATH.")
            chromedriver_path = shutil.which("chromedriver")
            if not chromedriver_path:
                raise FileNotFoundError("chromedriver no encontrado en PATH.")

            # Prepara perfil local (temporal por defecto)
            local_profile_dir = None
            if use_custom_profile:
                self._temp_dir = tempfile.TemporaryDirectory(prefix="ali_profile_")
                local_profile_dir = self._temp_dir.name
            else:
                self._tmp_profile = tempfile.mkdtemp(prefix="ali_profile_")
                local_profile_dir = self._tmp_profile

            options = build_options(True, local_profile_dir)
            options.binary_location = chromium_path
            service = Service(chromedriver_path)
            try:
                self.driver = webdriver.Chrome(service=service, options=options)
            except SessionNotCreatedException:
                # Reintento sin perfil local
                options = build_options(False, None)
                options.binary_location = chromium_path
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
                current = self.driver.execute_script("return document.body.scrollHeight")
                if current <= prev:
                    break

    def close(self):
        # Si estás mirando, puedes dejar la ventana abierta exportando VISUAL_MODE=1
        if os.getenv("VISUAL_MODE") == "1":
            return
        if getattr(self, "driver", None):
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
        if getattr(self, "_tmp_profile", None):
            shutil.rmtree(self._tmp_profile, ignore_errors=True)
            self._tmp_profile = None
        if getattr(self, "_temp_dir", None):
            self._temp_dir.cleanup()
            self._temp_dir = None
