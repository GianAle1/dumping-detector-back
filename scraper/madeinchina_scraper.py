# scraper/madeinchina_scraper.py
import logging
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
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

# ---------------- utilidades ----------------

_RANGE_SPLIT_PATTERN = re.compile(r"(?<=\d)\s*[-–—]\s*(?=\d)")

def limpiar_precio(texto: Optional[str]) -> Optional[float]:
    """Normaliza precios con separadores internacionales; si es rango, devuelve el menor."""
    def _norm(t: str) -> Optional[float]:
        cleaned = re.sub(r"[^0-9.,-]", "", t or "")
        if not cleaned:
            return None
        if _RANGE_SPLIT_PATTERN.search(cleaned):
            partes = [p.strip() for p in _RANGE_SPLIT_PATTERN.split(cleaned) if p.strip()]
            vals = []
            for p in partes:
                v = _norm(p)
                if v is not None:
                    vals.append(v)
            return min(vals) if vals else None

        has_dot, has_comma = "." in cleaned, "," in cleaned
        decimal_sep = None
        if has_dot and has_comma:
            decimal_sep = "," if cleaned.rfind(",") > cleaned.rfind(".") else "."
        elif has_dot:
            if len(cleaned.rpartition(".")[2]) in (1, 2):
                decimal_sep = "."
        elif has_comma:
            if len(cleaned.rpartition(",")[2]) in (1, 2):
                decimal_sep = ","

        if decimal_sep:
            int_part, dec_part = cleaned.rsplit(decimal_sep, 1)
            int_digits = re.sub(r"[^0-9]", "", int_part)
            dec_digits = re.sub(r"[^0-9]", "", dec_part)
            if not int_digits and not dec_digits:
                return None
            s = f"{int_digits}.{dec_digits or '0'}"
        else:
            s = re.sub(r"[^0-9]", "", cleaned)
            if not s:
                return None
        try:
            return float(s)
        except ValueError:
            return None

    if not texto:
        return None
    return _norm(texto.strip())

def limpiar_rango_precio(texto: Optional[str]) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """Devuelve (min, max, moneda) desde strings como 'US$3.60 - 5.60 / Piece'."""
    if not texto:
        return None, None, None
    m = re.search(r"(US\$|S/|[$€£¥]|[A-Z]{1,4})", texto)
    moneda = m.group(0) if m else None
    s = re.sub(r"(US\$|S/|[$€£¥]|[A-Z]{1,4})", "", texto)
    nums = re.findall(r"[\d][\d.,]*", s)
    vals: List[float] = []
    for n in nums[:2]:
        v = limpiar_precio(n)
        if v is not None:
            vals.append(v)
    if not vals:
        return None, None, moneda
    if len(vals) == 1:
        return vals[0], vals[0], moneda
    return min(vals), max(vals), moneda

def limpiar_cantidad(texto: Optional[str]) -> int:
    if not texto:
        return 0
    t = texto.strip().lower().replace("+", "")
    # “1,200 Pieces (MOQ)” -> 1200
    n = re.findall(r"[\d,\.]+", t)
    if not n:
        return 0
    base = n[0].replace(",", "").replace(".", "")
    try:
        return int(base)
    except ValueError:
        return 0

def _abs_link(href: str) -> str:
    if not href:
        return ""
    if href.startswith("//"):
        return "https:" + href
    if not href.startswith("http"):
        return "https://es.made-in-china.com/" + href.lstrip("/")
    return href

def _text(node) -> Optional[str]:
    if node is None:
        return None
    get_attribute = getattr(node, "get_attribute", None)
    if callable(get_attribute):
        return (get_attribute("innerText") or node.text or "").strip() or None
    return None

# ---------------- scraper ----------------

class MadeInChinaScraper(BaseScraper):
    """Scraper Made-in-China adaptado al HTML:
       - card: div.product-info
       - título: .product-name a h3/span
       - precio: .product-price .price  (rango con moneda)
       - moq: .product-unit
       - atributos: .prodcut-table .product-table-item
    """

    # Contenedor de cada producto (del snippet que pasaste)
    CARD_CONTAINERS: List[str] = [
        "div.product-info",                      # << principal
        "div.list-node-content",                 # fallback layouts previos
        "div.product-list div.product-item",
    ]

    # Selectores internos (ajustados al snippet)
    A_CARD: List[str] = [
        ".product-name a[href]", "a.product-title[href]", "a[href]"
    ]
    TITLE: List[str] = [
        ".product-name h3", ".product-name a h3", ".product-name", "h2.product-name"
    ]
    PRICE: List[str] = [
        ".product-price .price", "strong.price", ".search-price", ".product-price"
    ]
    MOQ: List[str] = [
        ".product-unit", "div.info", ".moq", "span.moq"
    ]
    ATTR_ROW: List[str] = [
        ".prodcut-table .product-table-item",  # (sic) 'prodcut-table' así viene en el HTML
        ".product-table .product-table-item"
    ]
    COMPANY: List[str] = [
        "a.company-name", ".supplier-name a", ".company a"
    ]
    LOCATION: List[str] = [
        "div.company-address-detail", ".supplier-location", ".location"
    ]
    BADGES: List[str] = [
        ".diamond-member", ".gold-member", ".member-tag"
    ]
    SOLD: List[str] = [
        ".sold", ".trade-num", ".sale-desc"
    ]

    # ----------- helpers de scroll / selección -----------

    def _accept_banners(self, timeout: int = 5):
        candidates = [
            (By.XPATH, "//button[contains(., 'Aceptar') or contains(., 'Accept')]"),
            (By.CSS_SELECTOR, "button[aria-label*='accept' i]"),
        ]
        for by, sel in candidates:
            try:
                btn = WebDriverWait(self.driver, timeout).until(EC.element_to_be_clickable((by, sel)))
                btn.click()
                time.sleep(0.3)
            except Exception:
                pass

    def _human_scroll_until_growth(self, max_scrolls: int = 16, pause: float = 0.9):
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

    # ----------- extracción por card (Selenium) -----------

    def _extract_card(self, card) -> Optional[Dict]:
        try:
            a = self._first_match(card, self.A_CARD) or card
            link = _abs_link((a.get_attribute("href") or "").strip())

            # Título
            titulo = None
            tnode = self._first_match(card, self.TITLE)
            if tnode:
                titulo = _text(tnode)
            if not titulo:
                titulo = (a.get_attribute("title") or a.text or "").strip() or "Sin título"

            # Precio (rango + moneda)
            pnode = self._first_match(card, self.PRICE)
            ptxt = _text(pnode) if pnode else None
            precio_min, precio_max, moneda = limpiar_rango_precio(ptxt)

            # Precio “base” para CSV comparativo
            precio = precio_min
            precio_original = precio_max if (precio_max and precio_min and precio_max > precio_min) else None
            descuento = None  # MIC no muestra % explícito en listados

            # MOQ
            moq_text = None
            mnode = self._first_match(card, self.MOQ)
            if mnode:
                moq_text = _text(mnode) or None
            moq_unidades = limpiar_cantidad(moq_text) if moq_text else 0

            # Atributos (tabla: Size, Collar Style, Color, etc.)
            atributos: Dict[str, str] = {}
            rows = None
            for sel in self.ATTR_ROW:
                try:
                    rows = card.find_elements(By.CSS_SELECTOR, sel)
                    if rows:
                        break
                except Exception:
                    continue
            if rows:
                for r in rows:
                    try:
                        desc = r.find_element(By.CSS_SELECTOR, ".product-table-description")
                        cont = r.find_element(By.CSS_SELECTOR, ".prodcut-table-content, .product-table-content")
                        k = (_text(desc) or "").strip().rstrip(":")
                        v = (_text(cont) or "").strip()
                        if k and v:
                            atributos[k] = v
                    except Exception:
                        continue

            # Empresa / ubicación / badges (si están en el card padre)
            empresa = None
            for sel in self.COMPANY:
                try:
                    cnode = card.find_element(By.CSS_SELECTOR, sel)
                    if cnode:
                        empresa = _text(cnode)
                        break
                except Exception:
                    continue
            empresa = empresa or "Desconocida"

            ubicacion = None
            for sel in self.LOCATION:
                try:
                    lnode = card.find_element(By.CSS_SELECTOR, sel)
                    if lnode:
                        ubicacion = _text(lnode)
                        break
                except Exception:
                    continue
            ubicacion = ubicacion or "Sin ubicación"

            miembro_diamante = False
            for sel in self.BADGES:
                try:
                    if card.find_element(By.CSS_SELECTOR, sel):
                        miembro_diamante = True
                        break
                except Exception:
                    continue

            # Ventas (raro en MIC)
            ventas = 0
            for s in self.SOLD:
                try:
                    sold_el = card.find_element(By.CSS_SELECTOR, s)
                    if sold_el:
                        ventas = limpiar_cantidad(_text(sold_el) or "")
                        break
                except Exception:
                    continue

            return {
                # columnas base (compatibles con tu CSV)
                "titulo": titulo,
                "precio": precio,
                "precio_original": precio_original,
                "descuento": descuento,
                "ventas": ventas,
                "link": link,

                # extras MIC útiles para comparativas
                "precio_min": precio_min,
                "precio_max": precio_max,
                "moneda": moneda,
                "moq": moq_text,
                "moq_unidades": moq_unidades,
                "empresa": empresa,
                "ubicacion": ubicacion,
                "miembro_diamante": miembro_diamante,
                "atributos": atributos,  # dict con pares k:v (Size, Collar Style, Color, etc.)
            }
        except (NoSuchElementException, StaleElementReferenceException):
            return None
        except Exception as e:
            logging.error("Error extrayendo card MIC: %s", e)
            return None

    # ----------- flujo principal -----------

    def parse(self, producto: str, paginas: int = 4):
        try:
            resultados: List[Dict] = []

            for page in range(1, paginas + 1):
                q = quote_plus(producto)
                url = f"https://es.made-in-china.com/productSearch?keyword={q}&currentPage={page}&type=Product"
                logging.info("Cargando Made-in-China: Página %s -> %s", page, url)

                cargada = False
                for intento in range(3):
                    try:
                        self.driver.get(url)
                        self._accept_banners(4)
                        WebDriverWait(self.driver, 12).until(
                            EC.presence_of_any_elements_located(
                                (By.CSS_SELECTOR, ", ".join(self.CARD_CONTAINERS))
                            )
                        )
                        # scroll humano para lazy-load
                        self._human_scroll_until_growth(max_scrolls=16, pause=0.9)
                        cargada = True
                        break
                    except (TimeoutException, WebDriverException) as e:
                        logging.warning("Reintento MIC p%s (%s): %s", page, intento + 1, e)
                        time.sleep(1.0)

                if not cargada:
                    logging.error("Omitiendo página %s (Made-in-China).", page)
                    continue

                # Selenium
                bloques = self._find_all_any(self.CARD_CONTAINERS, timeout=8)
                logging.info("Página %s: %s productos (Selenium)", page, len(bloques))

                validos = 0
                for card in bloques:
                    data = self._extract_card(card)
                    if not data:
                        continue
                    data.update({
                        "pagina": page,
                        "plataforma": "Made-in-China",
                        "fecha_scraping": datetime.now().strftime("%Y-%m-%d"),
                    })
                    resultados.append(data)
                    validos += 1

                # Fallback BS4 si hiciera falta
                if validos == 0:
                    page_source = getattr(self.driver, "page_source", "") or ""
                    soup = BeautifulSoup(page_source, "html.parser")
                    bs_cards: List = []
                    for sel in self.CARD_CONTAINERS:
                        bs_cards.extend(soup.select(sel) or [])

                    for bloque in bs_cards:
                        try:
                            a = None
                            for sel in self.A_CARD:
                                a = bloque.select_one(sel)
                                if a: break
                            link = _abs_link(a.get("href", "") if a else "")

                            titulo = None
                            for tsel in self.TITLE:
                                t = bloque.select_one(tsel)
                                if t:
                                    titulo = t.get_text(" ", strip=True)
                                    break
                            if not titulo and a:
                                titulo = (a.get("title") or a.get_text(" ", strip=True) or "").strip()
                            titulo = titulo or "Sin título"

                            pnode = None
                            for psel in self.PRICE:
                                pnode = bloque.select_one(psel)
                                if pnode: break
                            ptxt = pnode.get_text(" ", strip=True) if pnode else None
                            precio_min, precio_max, moneda = limpiar_rango_precio(ptxt)
                            precio = precio_min
                            precio_original = precio_max if (precio_max and precio_min and precio_max > precio_min) else None
                            descuento = None

                            mnode = None
                            for msel in self.MOQ:
                                mnode = bloque.select_one(msel)
                                if mnode: break
                            moq_text = mnode.get_text(" ", strip=True) if mnode else None
                            moq_unidades = limpiar_cantidad(moq_text) if moq_text else 0

                            atributos: Dict[str, str] = {}
                            rows = None
                            for rsel in self.ATTR_ROW:
                                rows = bloque.select(rsel)
                                if rows: break
                            if rows:
                                for r in rows:
                                    try:
                                        desc = r.select_one(".product-table-description")
                                        cont = r.select_one(".prodcut-table-content, .product-table-content")
                                        k = (desc.get_text(" ", strip=True) if desc else "").rstrip(":")
                                        v = cont.get_text(" ", strip=True) if cont else ""
                                        if k and v:
                                            atributos[k] = v
                                    except Exception:
                                        continue

                            empresa = "Desconocida"
                            for csel in self.COMPANY:
                                cnode = bloque.select_one(csel)
                                if cnode:
                                    empresa = cnode.get_text(" ", strip=True)
                                    break

                            ubicacion = "Sin ubicación"
                            for lsel in self.LOCATION:
                                lnode = bloque.select_one(lsel)
                                if lnode:
                                    ubicacion = lnode.get_text(" ", strip=True)
                                    break

                            miembro_diamante = False
                            for dsel in self.BADGES:
                                if bloque.select_one(dsel):
                                    miembro_diamante = True
                                    break

                            ventas = 0
                            sold_node = None
                            for ssel in self.SOLD:
                                sold_node = bloque.select_one(ssel)
                                if sold_node: break
                            if sold_node:
                                ventas = limpiar_cantidad(sold_node.get_text(" ", strip=True))

                            resultados.append({
                                "pagina": page,
                                "plataforma": "Made-in-China",
                                "fecha_scraping": datetime.now().strftime("%Y-%m-%d"),
                                "titulo": titulo,
                                "precio": precio,
                                "precio_original": precio_original,
                                "descuento": descuento,
                                "ventas": ventas,
                                "link": link,
                                "precio_min": precio_min,
                                "precio_max": precio_max,
                                "moneda": moneda,
                                "moq": moq_text,
                                "moq_unidades": moq_unidades,
                                "empresa": empresa,
                                "ubicacion": ubicacion,
                                "miembro_diamante": miembro_diamante,
                                "atributos": atributos,
                            })
                        except Exception:
                            continue

            return resultados
        finally:
            self.close()
