# aliexpress_scraper.py
import logging
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Set
from urllib.parse import urlencode, quote_plus, urlparse

from bs4 import BeautifulSoup
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .base import BaseScraper


BLOCK_PATTERNS = (
    "punish",
    "unusual traffic",
    "error:gvs",
    "robot check",
    "are you a robot",
    "are you human",
    "please verify you are a human",
    "verify you are human",
    "security verification",
    "complete the captcha",
    "captcha verification",
    "please complete the captcha",
)


def limpiar_precio(texto: Optional[str]) -> Optional[float]:
    """Normaliza cadenas de precio manejando separadores de miles y decimales."""

    if texto is None:
        return None

    texto = texto.strip()
    if not texto:
        return None

    # Filtramos solo dígitos y separadores comunes.
    cleaned = re.sub(r"[^0-9.,]", "", texto)
    if not cleaned:
        return None

    decimal_sep: Optional[str] = None
    has_dot = "." in cleaned
    has_comma = "," in cleaned

    if has_dot and has_comma:
        # Cuando hay ambos separadores, asumimos que el último que aparece es el decimal.
        decimal_sep = "," if cleaned.rfind(",") > cleaned.rfind(".") else "."
    elif has_dot:
        head, _, tail = cleaned.rpartition(".")
        if len(tail) in (1, 2):
            decimal_sep = "."
    elif has_comma:
        head, _, tail = cleaned.rpartition(",")
        if len(tail) in (1, 2):
            decimal_sep = ","

    if decimal_sep:
        int_part, dec_part = cleaned.rsplit(decimal_sep, 1)
        int_digits = re.sub(r"[^0-9]", "", int_part)
        dec_digits = re.sub(r"[^0-9]", "", dec_part)
        if not int_digits and not dec_digits:
            return None
        number_str = f"{int_digits}.{dec_digits or '0'}"
    else:
        number_str = re.sub(r"[^0-9]", "", cleaned)
        if not number_str:
            return None

    try:
        return float(number_str)
    except ValueError:
        return None


def limpiar_cantidad(texto: Optional[str]) -> int:
    """Convierte expresiones de cantidad como "1.2k" o "3 mil" a enteros."""

    if texto is None:
        return 0

    texto_normalizado = texto.strip().lower()
    if not texto_normalizado:
        return 0

    texto_normalizado = texto_normalizado.replace("+", "")

    multiplicador = 1
    if re.search(r"k\b", texto_normalizado):
        multiplicador = 1000
        texto_normalizado = re.sub(r"k\b", "", texto_normalizado)
    if "mil" in texto_normalizado:
        multiplicador = max(multiplicador, 1000)
        texto_normalizado = texto_normalizado.replace("mil", "")

    numero = limpiar_precio(texto_normalizado)
    if numero is None:
        numero = 0.0

    return int(round(numero * multiplicador))


class AliExpressScraper(BaseScraper):
    """Scraper AliExpress (visible) con banners, selectores robustos y fallback móvil."""

    # Contenedores de cards (desktop)
    CARD_CONTAINERS: List[str] = [
        "div.search-item-card-wrapper-gallery",
        "div[data-widget-name='search-product']",
        "div.list-item",
        "a.search-card-item",
        "div.product-card",
    ]

    # Contenedores en móvil
    MOBILE_CARD_CONTAINERS: List[str] = [
        "div.list-item", "div.product-card", "a.product", "a.list-item"
    ]

    # Selectores internos
    A_CARD: List[str] = [
        "a.search-card-item", "a.product", "a"
    ]
    PRICE: List[str] = [
        "[data-price]",
        "[data-widget='price']",
        "div.price",
        "span.price",
        "span._18_85",
        "div.ks_kn",
        "div.ks_le",
        ".ks_kn span",
        ".ks_le span",
        ".ks_cv",
    ]
    PRICE_ORIGINAL: List[str] = [
        "[data-original-price]",
        "del",
        ".original-price",
        "span._18_84",
        "div.ks_kw",
        "div.ks_kv",
        ".ks_kw span",
        ".ks_kv span",
    ]
    DISCOUNT: List[str] = [
        "[data-discount]", ".discount", ".sale-tag", "span._18_86"
    ]
    SOLD: List[str] = [
        "[data-sold]",
        ".sold",
        ".trade-num",
        ".sale-desc",
        ".order-num",
        ".ks_j7",
        ".ks_i2",
        ".product-reviewer-sold",
        ".product-info-sale",
        ".product-info-sold",
    ]
    PRICE_CONTAINER_CLASSES: Set[str] = {
        "ks_kn",
        "ks_le",
        "ks_cv",
        "ks_kw",
        "ks_kv",
    }

    # ----------------- utilidades privadas -----------------

    def _accept_banners(self, timeout: int = 5):
        """Cierra banners (GDPR/idioma/confirm). Silencioso si no hay."""
        candidates = [
            (By.XPATH, "//button[contains(., 'Aceptar') or contains(., 'Acepto') or contains(., 'Aceptar todo')]"),
            (By.XPATH, "//button[contains(., 'Allow all') or contains(., 'Accept all')]"),
            (By.CSS_SELECTOR, "[role='button'][aria-label*='Accept']"),
            (By.XPATH, "//button[contains(., 'Confirmar') or contains(., 'Guardar') or contains(., 'Continuar')]"),
        ]
        for by, sel in candidates:
            try:
                btn = WebDriverWait(self.driver, timeout).until(EC.element_to_be_clickable((by, sel)))
                btn.click()
                time.sleep(0.4)
            except Exception:
                pass

    def _human_scroll_until_growth(self, max_scrolls: int = 12, pause: float = 1.0):
        """Scroll visible con verificación de crecimiento del DOM."""
        last_height = 0
        for _ in range(max_scrolls):
            try:
                height = self.driver.execute_script("return document.body.scrollHeight")
                if height == last_height:
                    self.driver.execute_script("window.scrollBy(0, 600);")
                    time.sleep(pause)
                    new_h = self.driver.execute_script("return document.body.scrollHeight")
                    if new_h <= height:
                        break
                    last_height = new_h
                else:
                    last_height = height
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(pause)
            except Exception:
                break

    def _first_match(self, root, selectors: List[str]):
        for css in selectors:
            try:
                el = root.find_element(By.CSS_SELECTOR, css)
                if el:
                    return el
            except Exception:
                continue
        return None

    def _find_all_any(self, selectors: List[str], timeout: int = 10) -> List:
        for css in selectors:
            try:
                WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, css))
                )
                els = self.driver.find_elements(By.CSS_SELECTOR, css)
                if els:
                    return els
            except TimeoutException:
                continue
        return []

    @staticmethod
    def _to_float(text: Optional[str]) -> Optional[float]:
        return limpiar_precio(text)

    @staticmethod
    def _to_int(text: Optional[str]) -> int:
        return limpiar_cantidad(text)

    @classmethod
    def _resolve_price_text(cls, node, data_attribute: Optional[str] = None) -> Optional[str]:
        if node is None:
            return None

        get_attribute = getattr(node, "get_attribute", None)
        if callable(get_attribute):
            if data_attribute:
                value = get_attribute(data_attribute)
                if value:
                    return value.strip()

            class_attr = get_attribute("class") or ""
            classes = class_attr.split()
            if any(class_name in cls.PRICE_CONTAINER_CLASSES for class_name in classes):
                try:
                    spans = node.find_elements(By.CSS_SELECTOR, "span")
                    fragments = [
                        (span.text or "").strip()
                        for span in spans
                        if (span.text or "").strip()
                    ]
                    if fragments:
                        return "".join(fragments)
                except Exception:
                    pass

            inner = get_attribute("innerText")
            if inner:
                return inner.strip()

            text_content = getattr(node, "text", "")
            return text_content.strip() or None

        if data_attribute:
            value = node.get(data_attribute)
            if value:
                return value.strip()

        classes = node.get("class", [])
        if isinstance(classes, str):
            classes = classes.split()
        if any(cls_name in cls.PRICE_CONTAINER_CLASSES for cls_name in classes):
            spans = node.select("span")
            fragments = [
                span.get_text(strip=True)
                for span in spans
                if span.get_text(strip=True)
            ]
            if fragments:
                return "".join(fragments)

        text_content = node.get_text(" ", strip=True)
        return text_content or None

    def _extract_card(self, card) -> Optional[Dict]:
        try:
            a = self._first_match(card, self.A_CARD) or card
            link = a.get_attribute("href") or ""
            if link.startswith("//"):
                link = "https:" + link
            titulo = (a.get_attribute("title") or a.text or "Sin título").strip()

            price_el = self._first_match(card, self.PRICE)
            price_text = self._resolve_price_text(price_el, "data-price")
            precio = self._to_float(price_text)

            pori_el = self._first_match(card, self.PRICE_ORIGINAL)
            pori_text = self._resolve_price_text(pori_el, "data-original-price")
            precio_original = self._to_float(pori_text)

            desc_el = self._first_match(card, self.DISCOUNT)
            descuento = None
            if desc_el:
                descuento = (desc_el.get_attribute("data-discount") or desc_el.text or "").strip() or None

            sold_el = self._first_match(card, self.SOLD)
            if sold_el:
                ventas_txt = (sold_el.get_attribute("data-sold") or sold_el.text or "").strip()
            else:
                txt = card.text
                m = re.search(r"([\d\.\,]+)\s*(?:vendidos?|sold)", txt, re.IGNORECASE)
                ventas_txt = m.group(1) if m else ""
            ventas = self._to_int((ventas_txt or "").replace("+", ""))

            return {
                "titulo": titulo,
                "precio": precio,
                "precio_original": precio_original,
                "descuento": descuento,
                "ventas": ventas,
                "link": link,
            }
        except (NoSuchElementException, StaleElementReferenceException):
            return None
        except Exception as e:
            logging.error("Error extrayendo card: %s", e)
            return None

    @staticmethod
    def _is_blocked(driver) -> bool:
        url = getattr(driver, "current_url", "") or ""
        if isinstance(url, bytes):
            url = url.decode("utf-8", "ignore")
        url = url.lower()
        if any(p in url for p in BLOCK_PATTERNS):
            return True

        html = getattr(driver, "page_source", "") or ""
        if isinstance(html, bytes):
            html = html.decode("utf-8", "ignore")

        text_content = ""
        try:
            soup = BeautifulSoup(html, "html.parser")
            for meta in soup.find_all(
                "meta", attrs={"name": re.compile(r"^robots$", re.IGNORECASE)}
            ):
                meta.decompose()
            text_content = soup.get_text(separator=" ", strip=True).lower()
        except Exception:
            cleaned_html = re.sub(
                r"<meta[^>]+name=['\"]robots['\"][^>]*>",
                " ",
                html,
                flags=re.IGNORECASE,
            )
            text_content = cleaned_html.lower()

        if any(p in text_content for p in BLOCK_PATTERNS):
            return True

        verification_markers = ("g-recaptcha", "h-captcha", "cf-chl-captcha")
        lowered_html = html.lower()
        return any(marker in lowered_html for marker in verification_markers)

    @staticmethod
    def _apply_mobile_ua(driver):
        """Cambia UA a móvil en caliente (CDP)."""
        mobile_ua = (
            "Mozilla/5.0 (Linux; Android 10; SM-G975F) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36"
        )
        try:
            driver.execute_cdp_cmd("Network.enable", {})
            driver.execute_cdp_cmd(
                "Network.setUserAgentOverride",
                {"userAgent": mobile_ua, "platform": "Android"}
            )
        except Exception:
            pass

    # ----------------- flujo principal -----------------

    def parse(self, producto: str, paginas: int = 4):
        try:
            resultados: List[Dict] = []

            for page in range(1, paginas + 1):
                q = quote_plus(producto)
                url = f"https://es.aliexpress.com/wholesale?SearchText={q}&page={page}"
                logging.info("Cargando AliExpress: Página %s -> %s", page, url)
                self.driver.get(url)

                # Espera carga base + banners
                try:
                    self.wait_ready(15)
                    self._accept_banners(4)
                except Exception:
                    pass

                # ¿bloqueo desktop? -> fallback móvil
                if self._is_blocked(self.driver):
                    logging.warning("Bloqueo detectado en desktop. Cambiando a versión móvil...")
                    self._apply_mobile_ua(self.driver)
                    m_url = "https://m.aliexpress.com/search.htm?" + urlencode(
                        {"keywords": producto, "page": page}, quote_via=quote_plus
                    )
                    self.driver.get(m_url)
                    time.sleep(2)

                # Decide selectores según host
                current_url = getattr(self.driver, "current_url", "") or ""
                if not isinstance(current_url, (str, bytes)):
                    current_url = str(current_url)
                parsed_url = urlparse(current_url)
                host = parsed_url.netloc or ""
                if isinstance(host, bytes):
                    host = host.decode("utf-8", "ignore")
                host = host.lower()
                if host.startswith(("m.", "h5.")):
                    containers = self.MOBILE_CARD_CONTAINERS
                else:
                    containers = self.CARD_CONTAINERS

                # Espera/scroll para lazy-load
                bloques = self._find_all_any(containers, timeout=12)
                if not bloques:
                    self._human_scroll_until_growth(max_scrolls=4, pause=0.8)
                    bloques = self._find_all_any(containers, timeout=6)

                self._human_scroll_until_growth(max_scrolls=10, pause=1.0)
                nuevos_bloques = self._find_all_any(containers, timeout=4)
                if nuevos_bloques:
                    if bloques:
                        for bloque in nuevos_bloques:
                            if bloque not in bloques:
                                bloques.append(bloque)
                    else:
                        bloques = nuevos_bloques
                logging.info("Página %s: %s productos (candidatos)", page, len(bloques))

                # Extrae con Selenium
                count_page = 0
                for card in bloques:
                    data = self._extract_card(card)
                    if not data:
                        continue
                    data.update({
                        "pagina": page,
                        "plataforma": "AliExpress",
                        "fecha_scraping": datetime.now().strftime("%Y-%m-%d")
                    })
                    resultados.append(data)
                    count_page += 1

                logging.info("Página %s: %s productos válidos", page, count_page)

                # Fallback BeautifulSoup si quedó vacío
                if count_page == 0:
                    page_source = getattr(self.driver, "page_source", "") or ""
                    if not isinstance(page_source, (str, bytes)):
                        page_source = str(page_source)
                    soup = BeautifulSoup(page_source, "html.parser")
                    for sel in containers:
                        bs_cards = soup.select(sel)
                        if not bs_cards:
                            continue
                        for bloque in bs_cards:
                            try:
                                a = bloque.select_one("a[href]")
                                if not a:
                                    continue
                                link = a.get("href", "")
                                if link.startswith("//"):
                                    link = "https:" + link
                                titulo = (a.get("title") or a.get_text(" ") or "Sin título").strip()

                                price_tag = bloque.select_one(", ".join(self.PRICE))
                                ptxt = self._resolve_price_text(price_tag, "data-price")
                                precio = self._to_float(ptxt)

                                pori_tag = bloque.select_one(", ".join(self.PRICE_ORIGINAL))
                                potxt = self._resolve_price_text(pori_tag, "data-original-price")
                                precio_original = self._to_float(potxt)

                                desc_tag = bloque.select_one(", ".join(self.DISCOUNT))
                                descuento = (desc_tag.get("data-discount") if desc_tag else None) or (desc_tag.get_text(" ").strip() if desc_tag else None)

                                ventas_txt = ""
                                for sold_selector in self.SOLD:
                                    sold_tag = bloque.select_one(sold_selector)
                                    if sold_tag:
                                        ventas_txt = (
                                            sold_tag.get("data-sold")
                                            or sold_tag.get_text(" ")
                                            or ""
                                        ).strip()
                                        if ventas_txt:
                                            break
                                if not ventas_txt:
                                    m = re.search(
                                        r"([\d\.\,]+)\s*(?:vendidos?|sold)",
                                        bloque.get_text(" "),
                                        re.IGNORECASE,
                                    )
                                    ventas_txt = m.group(1) if m else ""
                                ventas = self._to_int((ventas_txt or "").replace("+", ""))

                                resultados.append({
                                    "pagina": page,
                                    "titulo": titulo,
                                    "precio": precio,
                                    "precio_original": precio_original,
                                    "descuento": descuento,
                                    "ventas": ventas,
                                    "link": link,
                                    "plataforma": "AliExpress",
                                    "fecha_scraping": datetime.now().strftime("%Y-%m-%d"),
                                })
                            except Exception:
                                continue
                        break  # usa el primer selector que devolvió algo

            return resultados
        finally:
            # Si VISUAL_MODE=1, BaseScraper.close() no cierra el navegador.
            self.close()
