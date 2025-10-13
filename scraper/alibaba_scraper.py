# alibaba_scraper.py
import logging
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Set
from urllib.parse import quote_plus

from bs4 import BeautifulSoup
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .base import BaseScraper

# ------------------- utilidades compartidas -------------------

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

_RANGE_SPLIT_PATTERN = re.compile(r"(?<=\d)\s*[-–—]\s*(?=\d)")

def limpiar_precio(texto: Optional[str]) -> Optional[float]:
    def _normalizar(texto_unitario: str) -> Optional[float]:
        cleaned = re.sub(r"[^0-9.,]", "", texto_unitario)
        if not cleaned:
            return None
        decimal_sep: Optional[str] = None
        has_dot = "." in cleaned
        has_comma = "," in cleaned
        if has_dot and has_comma:
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

    if not texto:
        return None
    texto = texto.strip()
    if not texto:
        return None
    if _RANGE_SPLIT_PATTERN.search(texto):
        partes = [p.strip() for p in _RANGE_SPLIT_PATTERN.split(texto) if p.strip()]
        cand = [(v, p) for p in partes if (v := _normalizar(p)) is not None]
        if cand:
            texto = min(cand, key=lambda x: x[0])[1]
        elif partes:
            texto = partes[0]
    return _normalizar(texto)

def limpiar_cantidad(texto: Optional[str]) -> int:
    if texto is None:
        return 0
    t = texto.strip().lower().replace("+", "")
    if not t:
        return 0
    mult = 1
    if re.search(r"k\b", t):
        mult = 1000
        t = re.sub(r"k\b", "", t)
    if "mil" in t:
        mult = max(mult, 1000)
        t = t.replace("mil", "")
    n = limpiar_precio(t) or 0.0
    return int(round(n * mult))

# Parsers específicos Alibaba
_currency_re = re.compile(r"(US\$|S/|[$€£¥])")
_rating_re = re.compile(r"([\d.]+)\s*/\s*5(?:\.0)?\s*\((\d+)\)")
_years_re  = re.compile(r"(\d+)\s*(?:años|years?)", re.I)
_percent_re = re.compile(r"(\d+)\s*%")

def detectar_moneda(texto: str) -> Optional[str]:
    if not texto: return None
    m = _currency_re.search(texto)
    return m.group(1) if m else None

def parse_rating(texto: str) -> (Optional[float], Optional[int]):
    if not texto: return (None, None)
    m = _rating_re.search(texto)
    if not m: return (None, None)
    try:
        return float(m.group(1)), int(m.group(2))
    except:
        return (None, None)

def parse_years_country(node) -> (Optional[int], Optional[str]):
    """
    De nodos tipo:
      <a class="searchx-product-e-supplier__year"><span>4 años</span><img ... alt="CN"><span>CN</span></a>
    """
    text = ""
    country = None
    try:
        text = (node.text or "").strip()
    except Exception:
        pass
    # country por <img alt> o último span
    try:
        img = node.find_element(By.CSS_SELECTOR, "img[alt]")
        country = (img.get_attribute("alt") or "").strip() or None
    except Exception:
        try:
            spans = node.find_elements(By.CSS_SELECTOR, "span")
            if spans:
                maybe = (spans[-1].text or "").strip()
                if maybe and len(maybe) <= 3:
                    country = maybe
        except Exception:
            pass
    years = None
    m = _years_re.search(text)
    if m:
        try:
            years = int(m.group(1))
        except:
            years = None
    return years, country

def parse_moq(texto: str) -> (Optional[int], Optional[str]):
    """
    'Pedido mín: 2 unidades' -> (2, 'Pedido mín: 2 unidades')
    """
    if not texto: return (None, None)
    m = re.search(r"(\d[\d.,]*)", texto)
    if not m: return (None, texto.strip())
    try:
        val = limpiar_cantidad(m.group(1))
    except:
        val = None
    return val, texto.strip()

def parse_repeat_rate(texto: str) -> Optional[int]:
    if not texto: return None
    m = _percent_re.search(texto)
    if not m: return None
    try:
        return int(m.group(1))
    except:
        return None

# ------------------- Scraper Alibaba -------------------

class AlibabaScraper(BaseScraper):
    """Scraper Alibaba (layout searchx/fy26) con scroll humano y datos extra para comparativas."""

    # Contenedores de cards
    CARD_CONTAINERS: List[str] = [
        "div.fy26-product-card-content",
        "div.searchx-product-card",
        "div.card-info.gallery-card-layout-info",  # legacy
    ]

    # Selectores internos
    A_CARD: List[str] = [
        "h2.searchx-product-e-title a",
        "a.searchx-product-link-wrapper",
        "a",
    ]
    TITLE: List[str] = [
        "h2.searchx-product-e-title span",
        "h2.searchx-product-e-title a",
        "h2.search-card-e-title a",
        "h2.search-card-e-title",
        "h1, h2, h3",
    ]
    PRICE: List[str] = [
        "div.searchx-product-price-price-main",
        "div.searchx-product-price",
        "div.search-card-e-price-main",
    ]
    PRICE_ORIGINAL: List[str] = ["del", "s", ".price-origin"]
    DISCOUNT: List[str] = [".discount", ".sale-tag", "[data-discount]"]
    SOLD: List[str] = ["div.searchx-moq", "div.price-area-center"]

    # Datos propios Alibaba
    SUPPLIER_NAME: List[str] = ["a.searchx-product-e-company", "a.search-card-e-company"]
    SUPPLIER_YEAR_COUNTRY: List[str] = ["a.searchx-product-e-supplier__year"]
    VERIFIED_BADGE: List[str] = [".verified-supplier-icon__wrapper", "img.searchx-verified-icon"]
    RATING: List[str] = ["span.searchx-product-e-review"]
    SELLING_POINTS: List[str] = [".searchx-selling-point-text"]

    PRICE_CONTAINER_CLASSES: Set[str] = set()

    # ----------------- utilidades privadas -----------------

    def _accept_banners(self, timeout: int = 5):
        candidates = [
            (By.XPATH, "//button[contains(., 'Aceptar') or contains(., 'Accept')]"),
            (By.XPATH, "//button[contains(., 'Allow all')]"),
            (By.CSS_SELECTOR, "[role='button'][aria-label*='accept' i]"),
        ]
        for by, sel in candidates:
            try:
                btn = WebDriverWait(self.driver, timeout).until(EC.element_to_be_clickable((by, sel)))
                btn.click()
                time.sleep(0.3)
            except Exception:
                pass

    def _human_scroll_until_growth(self, max_scrolls: int = 16, pause: float = 1.0):
        last_height = 0
        for _ in range(max_scrolls):
            try:
                height = self.driver.execute_script("return document.body.scrollHeight")
                if height == last_height:
                    self.driver.execute_script("window.scrollBy(0, 700);")
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

    @classmethod
    def _resolve_text(cls, node) -> Optional[str]:
        if node is None:
            return None
        get_attribute = getattr(node, "get_attribute", None)
        if callable(get_attribute):
            inner = get_attribute("innerText")
            if inner:
                return inner.strip()
            return (getattr(node, "text", "") or "").strip() or None
        # BS4
        return node.get_text(" ", strip=True) or None

    @classmethod
    def _resolve_price_text(cls, node, data_attribute: Optional[str] = None) -> Optional[str]:
        if node is None:
            return None
        get_attribute = getattr(node, "get_attribute", None)
        if callable(get_attribute):
            if data_attribute:
                v = get_attribute(data_attribute)
                if v:
                    return v.strip()
            inner = get_attribute("innerText")
            if inner:
                return inner.strip()
            return (get_attribute("textContent") or "").strip() or None
        return node.get_text(" ", strip=True) or None

    @staticmethod
    def _abs_link(href: str) -> str:
        if not href:
            return ""
        if href.startswith("//"):
            return "https:" + href
        if href.startswith("/"):
            return "https://www.alibaba.com" + href
        if not href.startswith("http"):
            return "https://www.alibaba.com/" + href
        return href

    # ----------------- extracción Selenium -----------------

    def _extract_card(self, card) -> Optional[Dict]:
        try:
            a = self._first_match(card, self.A_CARD) or card
            link = self._abs_link((a.get_attribute("href") or "").strip())

            # Título
            titulo_el = self._first_match(card, self.TITLE)
            titulo = self._resolve_text(titulo_el) or (a.get_attribute("title") or a.text or "").strip() or "Sin título"

            # Precio + moneda (si se ve)
            price_el = self._first_match(card, self.PRICE)
            price_text = self._resolve_price_text(price_el, "data-price")
            precio = limpiar_precio(price_text)
            moneda = detectar_moneda(price_text or "") if price_text else None

            # Original/descuento (poco frecuente en listado)
            pori_el = self._first_match(card, self.PRICE_ORIGINAL)
            precio_original = limpiar_precio(self._resolve_price_text(pori_el, "data-original-price") if pori_el else None)

            desc_el = self._first_match(card, self.DISCOUNT)
            descuento = self._resolve_text(desc_el) if desc_el else None

            # MOQ / ventas proxy
            moq_el = self._first_match(card, ["div.searchx-moq"])
            moq_val, moq_text = (None, None)
            if moq_el:
                moq_text = self._resolve_text(moq_el)
                moq_val, _ = parse_moq(moq_text or "")
            ventas = int(moq_val or 0)  # mantenemos compat de campo

            # Proveedor
            proveedor_el = self._first_match(card, self.SUPPLIER_NAME)
            proveedor = self._resolve_text(proveedor_el) if proveedor_el else None

            year_ctry_el = self._first_match(card, self.SUPPLIER_YEAR_COUNTRY)
            proveedor_anios, proveedor_pais = (None, None)
            if year_ctry_el:
                proveedor_anios, proveedor_pais = parse_years_country(year_ctry_el)

            verified = False
            vb = self._first_match(card, self.VERIFIED_BADGE)
            if vb:
                verified = True

            # Rating
            rating_el = self._first_match(card, self.RATING)
            rating_score, rating_count = (None, None)
            if rating_el:
                rating_score, rating_count = parse_rating(self._resolve_text(rating_el) or "")

            # Selling points (envío/tasa repetición)
            envio_promesa = None
            tasa_repeticion = None
            sp = self._first_match(card, self.SELLING_POINTS)
            if sp:
                txt = (sp.text or "").strip()
                if "envío" in txt.lower():
                    envio_promesa = txt
                pr = parse_repeat_rate(txt)
                if pr is not None:
                    tasa_repeticion = pr

            return {
                # comunes
                "titulo": titulo,
                "precio": precio,
                "precio_original": precio_original,
                "descuento": descuento,
                "ventas": ventas,
                "link": link,
                "moneda": moneda,
                # propios Alibaba
                "proveedor": proveedor,
                "proveedor_anios": proveedor_anios,
                "proveedor_pais": proveedor_pais,
                "proveedor_verificado": verified,
                "rating_score": rating_score,
                "rating_count": rating_count,
                "moq": moq_val,
                "moq_texto": moq_text,
                "envio_promesa": envio_promesa,
                "tasa_repeticion": tasa_repeticion,  # %
            }
        except (NoSuchElementException, StaleElementReferenceException):
            return None
        except Exception as e:
            logging.error("Error extrayendo card Alibaba: %s", e)
            return None

    @staticmethod
    def _is_blocked(driver) -> bool:
        url = (getattr(driver, "current_url", "") or "").lower()
        if any(p in url for p in BLOCK_PATTERNS):
            return True
        html = getattr(driver, "page_source", "") or ""
        if isinstance(html, bytes):
            try:
                html = html.decode("utf-8", "ignore")
            except Exception:
                html = ""
        soup_text = ""
        try:
            soup = BeautifulSoup(html, "html.parser")
            soup_text = soup.get_text(separator=" ", strip=True).lower()
        except Exception:
            soup_text = html.lower()
        return any(p in soup_text for p in BLOCK_PATTERNS)

    # ----------------- flujo principal -----------------

    def parse(self, producto: str, paginas: int = 4):
        try:
            resultados: List[Dict] = []

            for page in range(1, paginas + 1):
                q = quote_plus(producto)
                url = f"https://www.alibaba.com/trade/search?SearchText={q}&page={page}"
                logging.info("Cargando Alibaba: Página %s -> %s", page, url)

                cargada = False
                for intento in range(3):
                    try:
                        self.driver.get(url)
                        self._accept_banners(5)
                        WebDriverWait(self.driver, 15).until(
                            EC.presence_of_all_elements_located((By.CSS_SELECTOR, ", ".join(self.CARD_CONTAINERS)))
                        )
                        self._human_scroll_until_growth(max_scrolls=16, pause=1.0)
                        cargada = True
                        break
                    except (TimeoutException, WebDriverException) as e:
                        logging.warning("Reintento Alibaba p%s (%s): %s", page, intento + 1, e)
                        time.sleep(1.0)

                if not cargada:
                    logging.error("Omitiendo página %s por fallos de carga.", page)
                    continue

                if self._is_blocked(self.driver):
                    logging.warning("Posible bloqueo/antibot detectado en Alibaba (página %s).", page)

                # Selenium path
                bloques = self._find_all_any(self.CARD_CONTAINERS, timeout=8)
                logging.info("Página %s: %s productos (candidatos via Selenium)", page, len(bloques))

                count_page = 0
                for card in bloques:
                    data = self._extract_card(card)
                    if not data:
                        continue
                    data.update({
                        "pagina": page,
                        "plataforma": "Alibaba",
                        "fecha_scraping": datetime.now().strftime("%Y-%m-%d"),
                    })
                    resultados.append(data)
                    count_page += 1

                logging.info("Página %s: %s productos válidos (Selenium)", page, count_page)

                # Fallback BeautifulSoup si quedó vacío
                if count_page == 0:
                    page_source = getattr(self.driver, "page_source", "") or ""
                    soup = BeautifulSoup(page_source, "html.parser")
                    bs_cards: List = []
                    for sel in self.CARD_CONTAINERS:
                        bs_cards.extend(soup.select(sel) or [])

                    for bloque in bs_cards:
                        try:
                            # Link
                            a = None
                            for sel in self.A_CARD:
                                a = bloque.select_one(sel)
                                if a: break
                            href = a.get("href", "") if a else ""
                            link = self._abs_link(href)

                            # Título
                            titulo = None
                            for tsel in self.TITLE:
                                tag = bloque.select_one(tsel)
                                if tag:
                                    titulo = tag.get_text(" ", strip=True)
                                    break
                            if not titulo and a:
                                titulo = (a.get("title") or a.get_text(" ", strip=True) or "").strip()
                            titulo = titulo or "Sin título"

                            # Precio/moneda
                            price_tag = None
                            for psel in self.PRICE:
                                price_tag = bloque.select_one(psel)
                                if price_tag: break
                            ptxt = price_tag.get_text(" ", strip=True) if price_tag else None
                            precio = limpiar_precio(ptxt)
                            moneda = detectar_moneda(ptxt or "") if ptxt else None

                            # Original/Descuento
                            pori_tag = None
                            for osel in self.PRICE_ORIGINAL:
                                pori_tag = bloque.select_one(osel)
                                if pori_tag: break
                            precio_original = limpiar_precio(pori_tag.get_text(" ", strip=True) if pori_tag else None)

                            desc_tag = None
                            for dsel in self.DISCOUNT:
                                desc_tag = bloque.select_one(dsel)
                                if desc_tag: break
                            descuento = desc_tag.get_text(" ", strip=True) if desc_tag else None

                            # MOQ / ventas proxy
                            moq_tag = bloque.select_one("div.searchx-moq")
                            moq_val, moq_text = (None, None)
                            if moq_tag:
                                moq_text = moq_tag.get_text(" ", strip=True)
                                moq_val, _ = parse_moq(moq_text)
                            ventas = int(moq_val or 0)

                            # Proveedor
                            proveedor = None
                            for s in self.SUPPLIER_NAME:
                                t = bloque.select_one(s)
                                if t:
                                    proveedor = t.get_text(" ", strip=True)
                                    break

                            proveedor_anios = None
                            proveedor_pais = None
                            y = bloque.select_one(self.SUPPLIER_YEAR_COUNTRY[0])
                            if y:
                                # vía BS4
                                txt = y.get_text(" ", strip=True)
                                m = _years_re.search(txt)
                                if m:
                                    try: proveedor_anios = int(m.group(1))
                                    except: pass
                                img = y.select_one("img[alt]")
                                if img:
                                    proveedor_pais = img.get("alt", "").strip() or proveedor_pais
                                else:
                                    spans = y.select("span")
                                    if spans:
                                        last = (spans[-1].get_text(strip=True) or "")
                                        if last and len(last) <= 3:
                                            proveedor_pais = last

                            verified = bool(bloque.select_one(self.VERIFIED_BADGE[0]) or bloque.select_one(self.VERIFIED_BADGE[1]))

                            # Rating
                            rating_score = None
                            rating_count = None
                            r = bloque.select_one(self.RATING[0])
                            if r:
                                rating_score, rating_count = parse_rating(r.get_text(" ", strip=True))

                            # Selling points
                            envio_promesa = None
                            tasa_repeticion = None
                            sp = bloque.select_one(self.SELLING_POINTS[0])
                            if sp:
                                stxt = sp.get_text(" ", strip=True)
                                if "envío" in stxt.lower():
                                    envio_promesa = stxt
                                rr = parse_repeat_rate(stxt)
                                if rr is not None:
                                    tasa_repeticion = rr

                            resultados.append({
                                "pagina": page,
                                "titulo": titulo,
                                "precio": precio,
                                "precio_original": precio_original,
                                "descuento": descuento,
                                "ventas": ventas,
                                "link": link,
                                "plataforma": "Alibaba",
                                "fecha_scraping": datetime.now().strftime("%Y-%m-%d"),
                                "moneda": moneda,
                                "proveedor": proveedor,
                                "proveedor_anios": proveedor_anios,
                                "proveedor_pais": proveedor_pais,
                                "proveedor_verificado": verified,
                                "rating_score": rating_score,
                                "rating_count": rating_count,
                                "moq": moq_val,
                                "moq_texto": moq_text,
                                "envio_promesa": envio_promesa,
                                "tasa_repeticion": tasa_repeticion,
                            })
                        except Exception:
                            continue

            return resultados
        finally:
            self.close()
