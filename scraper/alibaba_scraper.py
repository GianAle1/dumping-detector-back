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
    "punish", "unusual traffic", "error:gvs", "robot check",
    "are you a robot", "are you human", "please verify you are a human",
    "verify you are human", "security verification", "complete the captcha",
    "captcha verification", "please complete the captcha",
)

_RANGE_SPLIT_PATTERN = re.compile(r"(?<=\d)\s*[-–—]\s*(?=\d)")
_PRODUCT_ID_RE = re.compile(r"productId=(\d+)")
_ITEM_TYPE_RE = re.compile(r"item_type:([a-zA-Z0-9]+)")
_PRODUCT_TYPE_RE = re.compile(r"product_type:([a-zA-Z0-9]+)")
_P4P_ID_RE = re.compile(r"p4pid=([a-f0-9]+)") 
_RLT_RANK_RE = re.compile(r"rlt_rank:(\d+)") 
_PAGE_RANK_ID_RE = re.compile(r"rank_id:(\d+)")
_IS_P4P_RE = re.compile(r"is_p4p=(true|false)")
_IS_TOPRANK_RE = re.compile(r"is_toprank=(true|false)")

def limpiar_precio(texto: Optional[str]) -> Optional[float]:
    def _normalizar(texto_unitario: str) -> Optional[float]:
        cleaned = re.sub(r"[^0-9.,]", "", texto_unitario)
        if not cleaned: return None
        decimal_sep: Optional[str] = None
        has_dot = "." in cleaned; has_comma = "," in cleaned
        if has_dot and has_comma: decimal_sep = "," if cleaned.rfind(",") > cleaned.rfind(".") else "."
        elif has_dot:
            head, _, tail = cleaned.rpartition("."); 
            if len(tail) in (1, 2) and re.match(r"^\d+$", head.replace(",", "")): decimal_sep = "."
        elif has_comma:
            head, _, tail = cleaned.rpartition(","); 
            if len(tail) in (1, 2) and re.match(r"^\d+$", head.replace(".", "")): decimal_sep = ","
        
        if decimal_sep:
            int_part, dec_part = cleaned.rsplit(decimal_sep, 1)
            int_digits = re.sub(r"[^0-9]", "", int_part); dec_digits = re.sub(r"[^0-9]", "", dec_part)
            if not int_digits and not dec_digits: return None
            number_str = f"{int_digits}.{dec_digits or '0'}"
        else:
            number_str = re.sub(r"[^0-9]", "", cleaned)
            if not number_str: return None
        try: return float(number_str)
        except ValueError: return None

    if not texto: return None
    texto = texto.strip(); 
    if not texto: return None
    
    if _RANGE_SPLIT_PATTERN.search(texto):
        partes = [p.strip() for p in _RANGE_SPLIT_PATTERN.split(texto) if p.strip()]
        for p in partes:
            if (v := _normalizar(p)) is not None: return v
        if partes: texto = partes[0]
    
    return _normalizar(texto)

def limpiar_cantidad(texto: Optional[str]) -> int:
    if texto is None: return 0
    t = texto.strip().lower().replace("+", "")
    if not t: return 0
    mult = 1
    if re.search(r"k\b", t): mult = 1000; t = re.sub(r"k\b", "", t)
    if "mil" in t: mult = max(mult, 1000); t = t.replace("mil", "")
    n = limpiar_precio(t) or 0.0
    return int(round(n * mult))

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
    try: return float(m.group(1)), int(m.group(2))
    except: return (None, None)

def parse_years_country(node) -> (Optional[int], Optional[str]):
    text = ""; country = None
    try: text = (node.text or "").strip()
    except Exception: pass
    
    try:
        img = node.find_element(By.CSS_SELECTOR, "img[alt]")
        country = (img.get_attribute("alt") or "").strip() or None
    except Exception:
        try:
            spans = node.find_elements(By.CSS_SELECTOR, "span")
            if spans:
                maybe = (spans[-1].text or "").strip()
                if maybe and len(maybe) <= 3: country = maybe
        except Exception: pass
            
    years = None
    m = _years_re.search(text)
    if m:
        try: years = int(m.group(1))
        except: years = None
    return years, country

def parse_moq(texto: str) -> (Optional[int], Optional[str]):
    if not texto: return (None, None)
    m = re.search(r"(\d[\d.,]*)", texto)
    if not m: return (None, texto.strip())
    try: val = limpiar_cantidad(m.group(1))
    except: val = None
    return val, texto.strip()

def parse_repeat_rate(texto: str) -> Optional[int]:
    if not texto: return None
    m = _percent_re.search(texto)
    if not m: return None
    try: return int(m.group(1))
    except: return None
# -------------------------------------------------------------


class AlibabaScraper(BaseScraper):
    """Scraper Alibaba (layout searchx/fy26) con robustez extra en la extracción de datos críticos."""

    CARD_CONTAINERS: List[str] = [
        "div.fy26-product-card-wrapper", "div.fy26-product-card-content",
        "div.searchx-product-card", "div.card-info.gallery-card-layout-info",
    ]

    # Selectores para campos estándar
    A_CARD: List[str] = ["h2.searchx-product-e-title a", "a.searchx-product-link-wrapper", "a"]
    TITLE: List[str] = ["h2.searchx-product-e-title span", "h2.searchx-product-e-title a", "h2.search-card-e-title"]
    
    # Selectores de Precio: ¡Máxima prioridad a encontrar el precio!
    PRICE: List[str] = [
        "div.searchx-product-price-price-main", # Típico
        "div.searchx-product-price", 
        ".price--two-line", 
        "div[data-aplus-auto-card-mod*='area=price'] div", # Buscar por atributo de área
        "div.price" # Genérico
    ]
    
    PRICE_ORIGINAL: List[str] = ["del", "s", ".price-origin"]
    DISCOUNT: List[str] = [".discount", ".sale-tag", "[data-discount]"]
    MOQ_CONTAINER: List[str] = ["div.searchx-moq"]
    SOLD_COUNT: List[str] = ["div.searchx-sold-order"]
    IMAGE_URL: List[str] = ["img.searchx-product-e-slider__img", "img[src*='alicdn']"]

    # Selectores de Proveedor y Calidad
    SUPPLIER_NAME: List[str] = ["a.searchx-product-e-company", "a.search-card-e-company"]
    SUPPLIER_LINK: List[str] = ["a.searchx-product-e-company", "a.search-card-e-company"] 
    SUPPLIER_YEAR_COUNTRY: List[str] = ["a.searchx-product-e-supplier__year"]
    VERIFIED_BADGE: List[str] = [".verified-supplier-icon__wrapper", "img.searchx-verified-icon"]
    RATING: List[str] = ["span.searchx-product-e-review"]
    SELLING_POINTS: List[str] = [".searchx-selling-point-text"]
    
    # Selectores para metadatos y anuncios
    SPECIAL_TAGS: List[str] = [".title-area-features", ".searchx-product-m-product-features__productIcon"] 
    AD_BADGE: List[str] = [".searchx-card-e-ad", "div[data-role='ad-area']"]

    # ----------------- utilidades privadas -----------------

    @classmethod
    def _resolve_text(cls, node) -> Optional[str]:
        if node is None: return None
        get_attribute = getattr(node, "get_attribute", None)
        if callable(get_attribute):
            content = get_attribute("textContent")
            if content: return content.strip()
            return (getattr(node, "text", "") or "").strip() or None
        return node.get_text(" ", strip=True) or None

    @classmethod
    def _resolve_price_text(cls, node, data_attribute: Optional[str] = None) -> Optional[str]:
        if node is None: return None
        get_attribute = getattr(node, "get_attribute", None)
        if callable(get_attribute):
            if data_attribute:
                v = get_attribute(data_attribute)
                if v: return v.strip()
            content = get_attribute("textContent")
            if content: return content.strip()
            return (get_attribute("innerText") or "").strip() or None
        return node.get_text(" ", strip=True) or None
    
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
            except Exception: pass

    def _human_scroll_until_growth(self, max_scrolls: int = 16, pause: float = 1.0):
        last_height = 0
        for _ in range(max_scrolls):
            try:
                height = self.driver.execute_script("return document.body.scrollHeight")
                if height == last_height:
                    self.driver.execute_script("window.scrollBy(0, 700);")
                    time.sleep(pause)
                    new_h = self.driver.execute_script("return document.body.scrollHeight")
                    if new_h <= height: break
                    last_height = new_h
                else:
                    last_height = height
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(pause)
            except Exception: break

    def _first_match(self, root, selectors: List[str]):
        for css in selectors:
            try:
                elements = root.find_elements(By.CSS_SELECTOR, css)
                if elements: return elements[0]
            except Exception: continue
        return None

    def _find_all_any(self, selectors: List[str], timeout: int = 10) -> List:
        for css in selectors:
            try:
                WebDriverWait(self.driver, timeout).until(
                    EC.visibility_of_any_elements_located((By.CSS_SELECTOR, css)) 
                )
                els = self.driver.find_elements(By.CSS_SELECTOR, css)
                if els: return els
            except TimeoutException: continue
        return []
    
    @staticmethod
    def _abs_link(href: str) -> str:
        if not href: return ""
        if href.startswith("//"): return "https:" + href
        if href.startswith("/"): return "https://www.alibaba.com" + href
        if not href.startswith("http"): return "https://www.alibaba.com/" + href
        return href

    # ----------------- extracción Selenium (Robusta) -----------------

    def _extract_card(self, card) -> Optional[Dict]:
        data = {}
        try:
            # --- FASE 1: Datos Base (Críticos para la identificación) ---
            
            a = self._first_match(card, self.A_CARD) or card
            data["link"] = self._abs_link((a.get_attribute("href") or "").strip())
            
            titulo_el = self._first_match(card, self.TITLE)
            data["titulo"] = self._resolve_text(titulo_el) or (a.get_attribute("title") or a.text or "").strip() or "Sin título"
            
            data["product_id"] = card.get_attribute("data-ctrdot")
            
            if not data["link"] and data["titulo"] == "Sin título": return None

            # --- FASE 2: PRECIO (Extracción con máxima robustez) ---
            
            price_text = None
            # Iteramos sobre todos los selectores de precio definidos
            for price_sel in self.PRICE:
                price_el = self._first_match(card, [price_sel])
                if price_el:
                    price_text = self._resolve_price_text(price_el, "data-price")
                    if price_text: break
            
            data["precio"] = limpiar_precio(price_text)
            data["moneda"] = detectar_moneda(price_text or "") if price_text else None
            
            # Si el precio sigue siendo None, podríamos intentar buscar en todo el contenedor de la tarjeta,
            # pero eso puede ser demasiado agresivo y capturar ruido. Lo mantenemos así por ahora.
            # --------------------------------------------------------

            # Transacciones e Imagen
            moq_el = self._first_match(card, self.MOQ_CONTAINER)
            data["moq"], data["moq_texto"] = parse_moq(self._resolve_text(moq_el) or "")
            
            sold_el = self._first_match(card, self.SOLD_COUNT)
            data["ventas"] = limpiar_cantidad(self._resolve_text(sold_el)) 
            
            image_el = self._first_match(card, self.IMAGE_URL)
            data["imagen_url"] = self._abs_link(image_el.get_attribute("src") or "") if image_el else None

            # --- FASE 3: Proveedor y Calidad ---

            proveedor_el = self._first_match(card, self.SUPPLIER_NAME)
            data["proveedor"] = self._resolve_text(proveedor_el) if proveedor_el else None
            data["link_proveedor"] = self._abs_link(proveedor_el.get_attribute("href") or "") if proveedor_el else None

            year_ctry_el = self._first_match(card, self.SUPPLIER_YEAR_COUNTRY)
            data["proveedor_anios"], data["proveedor_pais"] = parse_years_country(year_ctry_el) if year_ctry_el else (None, None)
            
            vb = self._first_match(card, self.VERIFIED_BADGE)
            data["proveedor_verificado"] = bool(vb)

            rating_el = self._first_match(card, self.RATING)
            data["rating_score"], data["rating_count"] = parse_rating(self._resolve_text(rating_el) or "")
            
            # --- FASE 4: Metadatos Avanzados (Extracción completa) ---

            aplus_data = card.get_attribute("data-aplus-auto-offer") or ""
            track_info = card.get_attribute("data-p4p-eurl") or ""

            if not data.get("product_id"): m = _PRODUCT_ID_RE.search(aplus_data); data["product_id"] = m.group(1) if m else None
            
            m = _P4P_ID_RE.search(aplus_data) or _P4P_ID_RE.search(track_info)
            data["p4p_id"] = m.group(1) if m else None
            
            m = _RLT_RANK_RE.search(aplus_data); data["rlt_rank"] = int(m.group(1)) if m and m.group(1).isdigit() else None
            m = _PAGE_RANK_ID_RE.search(aplus_data); data["page_rank_id"] = int(m.group(1)) if m and m.group(1).isdigit() else None
            m = _ITEM_TYPE_RE.search(aplus_data); data["item_type"] = m.group(1) if m else None
            m = _PRODUCT_TYPE_RE.search(aplus_data); data["product_type"] = m.group(1) if m else None
            m = _IS_P4P_RE.search(aplus_data); data["is_p4p"] = (m and m.group(1) == 'true')
            m = _IS_TOPRANK_RE.search(aplus_data); data["is_toprank"] = (m and m.group(1) == 'true')

            data["es_anuncio"] = data.get("is_p4p", False) or data.get("is_toprank", False) or bool(self._first_match(card, self.AD_BADGE))
            if not data["es_anuncio"]:
                spm_type = card.get_attribute("data-spm") or ""
                if "p_offer" in spm_type or "is_ad=true" in aplus_data: data["es_anuncio"] = True

            pori_el = self._first_match(card, self.PRICE_ORIGINAL)
            data["precio_original"] = limpiar_precio(self._resolve_price_text(pori_el, "data-original-price") if pori_el else None)
            desc_el = self._first_match(card, self.DISCOUNT)
            data["descuento"] = self._resolve_text(desc_el) if desc_el else None

            sp = self._first_match(card, self.SELLING_POINTS)
            data["envio_promesa"] = None; data["tasa_repeticion"] = None
            if sp:
                txt = (sp.text or "").strip()
                if "envío" in txt.lower() or "entrega" in txt.lower(): data["envio_promesa"] = txt
                data["tasa_repeticion"] = parse_repeat_rate(txt)
            
            data["etiqueta_especial"] = None
            for sel in self.SPECIAL_TAGS:
                tag_el = self._first_match(card, [sel])
                if tag_el:
                    text = self._resolve_text(tag_el)
                    if text and ("mejor" in text.lower() or "#" in text or "precio" in text.lower()):
                         data["etiqueta_especial"] = text
                         break
            
            return data
        except (NoSuchElementException, StaleElementReferenceException): return None
        except Exception as e:
            logging.error("Error extrayendo card Alibaba: %s", e)
            return None

    @staticmethod
    def _is_blocked(driver) -> bool:
        url = (getattr(driver, "current_url", "") or "").lower()
        if any(p in url for p in BLOCK_PATTERNS): return True
        html = getattr(driver, "page_source", "") or ""
        if isinstance(html, bytes):
            try: html = html.decode("utf-8", "ignore")
            except Exception: html = ""
        soup_text = "";
        try:
            soup = BeautifulSoup(html, "html.parser")
            soup_text = soup.get_text(separator=" ", strip=True).lower()
        except Exception: soup_text = html.lower()
        return any(p in soup_text for p in BLOCK_PATTERNS)

    # ----------------- flujo principal -----------------

    def parse(self, producto: str, paginas: int = 4):
        try:
            resultados: List[Dict] = []
            
            # Columnas relevantes (15)
            COLUMN_ORDER = [
                "product_id", "titulo", "precio", "moneda", "precio_original", 
                "ventas", "moq", "proveedor_verificado", "proveedor_anios", 
                "rating_score", "es_anuncio", "is_p4p", "rlt_rank", "link", 
                "fecha_scraping"
            ]

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
                            EC.visibility_of_any_elements_located((By.CSS_SELECTOR, ", ".join(self.CARD_CONTAINERS)))
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

                bloques = self._find_all_any(self.CARD_CONTAINERS, timeout=8)
                logging.info("Página %s: %s productos (candidatos via Selenium)", page, len(bloques))

                count_page = 0
                for card in bloques:
                    data = self._extract_card(card)
                    if not data:
                        continue
                    
                    final_data = {col: data.get(col) for col in COLUMN_ORDER}
                    final_data.update({
                        "pagina": page,
                        "plataforma": "Alibaba",
                        "fecha_scraping": datetime.now().strftime("%Y-%m-%d"),
                    })
                    
                    resultados.append(final_data)
                    count_page += 1

                logging.info("Página %s: %s productos válidos (Selenium)", page, count_page)

            return resultados
        finally:
            self.close()