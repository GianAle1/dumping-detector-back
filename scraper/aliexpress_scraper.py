# aliexpress_scraper.py
import logging
import re
import time
from datetime import datetime
from typing import Dict, List, Optional
from urllib.parse import urlencode, quote_plus

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


BLOCK_PATTERNS = ("punish", "unusual traffic", "error:gvs", "robot", "captcha")


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
        "div.price", "span.price", "span._18_85"
    ]
    PRICE_ORIGINAL: List[str] = [
        "[data-original-price]", "del", ".original-price", "span._18_84"
    ]
    DISCOUNT: List[str] = [
        "[data-discount]", ".discount", ".sale-tag", "span._18_86"
    ]
    SOLD: List[str] = [
        "[data-sold]", ".sold", ".trade-num", ".sale-desc"
    ]

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

    def _extract_card(self, card) -> Optional[Dict]:
        try:
            a = self._first_match(card, self.A_CARD) or card
            link = a.get_attribute("href") or ""
            if link.startswith("//"):
                link = "https:" + link
            titulo = (a.get_attribute("title") or a.text or "Sin título").strip()

            price_el = self._first_match(card, self.PRICE)
            price_text = price_el.get_attribute("data-price") if price_el else None
            if not price_text and price_el:
                price_text = price_el.text
            precio = self._to_float(price_text)

            pori_el = self._first_match(card, self.PRICE_ORIGINAL)
            pori_text = pori_el.get_attribute("data-original-price") if pori_el else None
            if not pori_text and pori_el:
                pori_text = pori_el.text
            precio_original = self._to_float(pori_text)

            desc_el = self._first_match(card, self.DISCOUNT)
            descuento = None
            if desc_el:
                descuento = (desc_el.get_attribute("data-discount") or desc_el.text or "").strip() or None

            sold_el = self._first_match(card, self.SOLD)
            if sold_el:
                ventas_txt = sold_el.get_attribute("data-sold") or sold_el.text
            else:
                txt = card.text
                m = re.search(r"([\d\.\,]+)\s*vendidos?", txt, re.IGNORECASE)
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
        url = (driver.current_url or "").lower()
        if any(p in url for p in BLOCK_PATTERNS):
            return True
        html = (driver.page_source or "").lower()
        return any(p in html for p in BLOCK_PATTERNS)

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
                q = producto.replace(" ", "+")
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
                host = (self.driver.current_url or "").split("/")[2].lower()
                containers = self.MOBILE_CARD_CONTAINERS if host.startswith(("m.", "h5.")) else self.CARD_CONTAINERS

                # Espera/scroll para lazy-load
                bloques = self._find_all_any(containers, timeout=12)
                if not bloques:
                    self._human_scroll_until_growth(max_scrolls=4, pause=0.8)
                    bloques = self._find_all_any(containers, timeout=6)

                self._human_scroll_until_growth(max_scrolls=10, pause=1.0)
                bloques = self._find_all_any(containers, timeout=4)
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
                    soup = BeautifulSoup(self.driver.page_source, "html.parser")
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
                                ptxt = (price_tag.get("data-price") if price_tag else None) or (price_tag.get_text(" ") if price_tag else None)
                                precio = self._to_float(ptxt)

                                pori_tag = bloque.select_one(", ".join(self.PRICE_ORIGINAL))
                                potxt = (pori_tag.get("data-original-price") if pori_tag else None) or (pori_tag.get_text(" ") if pori_tag else None)
                                precio_original = self._to_float(potxt)

                                desc_tag = bloque.select_one(", ".join(self.DISCOUNT))
                                descuento = (desc_tag.get("data-discount") if desc_tag else None) or (desc_tag.get_text(" ").strip() if desc_tag else None)

                                sold_tag = bloque.select_one(", ".join(self.SOLD))
                                ventas_txt = (sold_tag.get("data-sold") if sold_tag else None) or (sold_tag.get_text(" ") if sold_tag else "")
                                if not ventas_txt:
                                    m = re.search(r"([\d\.\,]+)\s*vendidos?", bloque.get_text(" "), re.IGNORECASE)
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
