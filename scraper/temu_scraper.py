# scraper/temu_scraper.py
import logging
import re
import time
from datetime import datetime
from typing import Dict, List, Optional
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

# ---------------- utilidades compartidas ----------------

_RANGE_SPLIT_PATTERN = re.compile(r"(?<=\d)\s*[-–—]\s*(?=\d)")

def limpiar_precio(texto: Optional[str]) -> Optional[float]:
    def _normalizar(texto_unitario: str) -> Optional[float]:
        cleaned = re.sub(r"[^0-9.,]", "", texto_unitario or "")
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
    t = texto.strip()
    if not t:
        return None
    if _RANGE_SPLIT_PATTERN.search(t):
        partes = [p.strip() for p in _RANGE_SPLIT_PATTERN.split(t) if p.strip()]
        cand = [(v, p) for p in partes if (v := _normalizar(p)) is not None]
        if cand:
            t = min(cand, key=lambda x: x[0])[1]
        elif partes:
            t = partes[0]
    return _normalizar(t)

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

def _abs_link(href: str) -> str:
    if not href:
        return ""
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return "https://www.temu.com" + href
    if not href.startswith("http"):
        return "https://www.temu.com/" + href
    return href


class TemuScraper(BaseScraper):
    """Scraper Temu actualizado (mismo patrón que AliExpress/Alibaba)."""

    # Contenedores de card (según HTML actualizado)
    CARD_CONTAINERS: List[str] = [
        "div._6q6qVUF5._1UrrHYym",  # wrapper principal de la card
        "div._6q6qVUF5._1QhQr8pq._2gAD5fPC._3AbcHYoU",  # bloque de título
        "div._3tAUu0RX",  # bloque de precio/ventas
        # Genéricos de respaldo
        "div.product-card",
        "div.card",
    ]

    # Selectores internos
    A_CARD: List[str] = [
        "a._2Tl9qLr1",           # <a> del título
        "a[href^='/pe/']",
        "a[href^='/']",
        "a",
    ]
    TITLE: List[str] = [
        "h2._2BvQbnbN span._2D9RBAXL",  # texto del título dentro del h2
        "h2._2BvQbnbN",
        "h3._2BvQbnbN",
        "h2, h3",
        "span._2D9RBAXL",
    ]
    PRICE_INTEGER: str = "span._2de9ERAH"  # entero
    PRICE_DECIMAL: str = "span._3SrxhhHh"  # decimal (incluye el punto en el HTML)
    PRICE_ANY: List[str] = [
        "div._2myxWHLi [data-type='price']",
        "div[class*='price']", "span[class*='price']", "div.price", "span.price"
    ]
    PRICE_ORIGINAL: List[str] = [
        "span._3TAPHDOX", "del", "s", "span[class*='original']"
    ]
    DISCOUNT: List[str] = [
        # Temu no siempre muestra %; dejamos posibles contenedores de descuentos/cupones
        "div.gXSsgZXB", "div._1LLbpUTn", "div[class*='discount']", "span[class*='discount']"
    ]
    SOLD: List[str] = [
        "span._3vfo0XTx",  # aparece como '8.3K+' y 'ventas'
        "div[data-type='saleTips']", "span[class*='sold']", "div[class*='sold']",
    ]
    AD_BADGE: str = "div._2QlTgZaA"  # contiene el texto 'Anuncio' si es publicidad

    # ---------------- utilidades privadas ----------------

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

    def _human_scroll_until_growth(self, max_scrolls: int = 18, pause: float = 1.0):
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

    @staticmethod
    def _node_text(node) -> Optional[str]:
        if node is None:
            return None
        get_attribute = getattr(node, "get_attribute", None)
        if callable(get_attribute):
            return (get_attribute("innerText") or node.text or "").strip() or None
        return None

    def _resolve_price_text(self, card) -> Optional[str]:
        """
        Une los spans de precio entero y decimal si existen.
        """
        try:
            entero_el = None
            dec_el = None
            try:
                entero_el = card.find_element(By.CSS_SELECTOR, self.PRICE_INTEGER)
            except Exception:
                pass
            try:
                dec_el = card.find_element(By.CSS_SELECTOR, self.PRICE_DECIMAL)
            except Exception:
                pass

            entero = re.sub(r"[^\d]", "", (entero_el.text if entero_el else "")).strip()
            dec = re.sub(r"[^\d]", "", (dec_el.text if dec_el else "")).strip()

            if entero or dec:
                if entero and dec:
                    return f"{entero}.{dec}"
                if entero:
                    return entero
                return f"0.{dec}"

            # Fallback: cualquier nodo de precio
            any_price = None
            for css in self.PRICE_ANY:
                try:
                    any_price = card.find_element(By.CSS_SELECTOR, css)
                    if any_price:
                        break
                except Exception:
                    continue
            if any_price:
                return (any_price.text or "").strip()
        except Exception:
            pass
        return None

    def _is_ad(self, card) -> bool:
        # si aparece el badge "Anuncio", descartamos
        try:
            badge = card.find_element(By.CSS_SELECTOR, self.AD_BADGE)
            if badge and "anuncio" in (badge.text or "").strip().lower():
                return True
        except Exception:
            pass
        return False

    def _extract_card(self, card) -> Optional[Dict]:
        try:
            if self._is_ad(card):
                return None

            a = self._first_match(card, self.A_CARD) or card
            link = _abs_link((a.get_attribute("href") or "").strip())

            # Título
            titulo_el = self._first_match(card, self.TITLE)
            titulo = self._node_text(titulo_el) or (a.get_attribute("title") or a.text or "").strip() or "Sin título"

            # Precio actual (entero+decimal unidos)
            price_text = self._resolve_price_text(card)
            precio = limpiar_precio(price_text)

            # Precio original (tachado)
            pori_el = self._first_match(card, self.PRICE_ORIGINAL)
            precio_original = limpiar_precio(self._node_text(pori_el) if pori_el else None)

            # Descuento si aparece (texto)
            desc_el = self._first_match(card, self.DISCOUNT)
            descuento = self._node_text(desc_el) if desc_el else None

            # Ventas (8.3K+ventas -> 8300)
            sold_el = self._first_match(card, self.SOLD)
            ventas_txt = self._node_text(sold_el) if sold_el else None
            ventas = limpiar_cantidad(ventas_txt or "")

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
            logging.error("Error extrayendo card Temu: %s", e)
            return None

    # ---------------- flujo principal ----------------

    def parse(self, producto: str, paginas: int = 4):
        try:
            resultados: List[Dict] = []

            for page in range(1, paginas + 1):
                q = quote_plus(producto)
                url = f"https://www.temu.com/pe/search.html?search_key={q}&page={page}"
                logging.info("Cargando Temu: Página %s -> %s", page, url)

                cargada = False
                for intento in range(3):
                    try:
                        self.driver.get(url)
                        self._accept_banners(4)
                        WebDriverWait(self.driver, 15).until(
                            EC.presence_of_any_elements_located(
                                (By.CSS_SELECTOR, ", ".join(self.CARD_CONTAINERS))
                            )
                        )
                        self._human_scroll_until_growth(max_scrolls=18, pause=1.0)
                        cargada = True
                        break
                    except (TimeoutException, WebDriverException) as e:
                        logging.warning("Reintento Temu p%s (%s): %s", page, intento + 1, e)
                        time.sleep(1.0)

                if not cargada:
                    logging.error("Omitiendo página %s por fallos de carga.", page)
                    continue

                # Selenium
                bloques = self._find_all_any(self.CARD_CONTAINERS, timeout=8)
                logging.info("Página %s: %s productos (candidatos via Selenium)", page, len(bloques))

                count_page = 0
                for card in bloques:
                    data = self._extract_card(card)
                    if not data:
                        continue
                    data.update({
                        "pagina": page,
                        "plataforma": "Temu",
                        "fecha_scraping": datetime.now().strftime("%Y-%m-%d"),
                    })
                    resultados.append(data)
                    count_page += 1

                logging.info("Página %s: %s productos válidos (Selenium)", page, count_page)

                # Fallback BeautifulSoup
                if count_page == 0:
                    page_source = getattr(self.driver, "page_source", "") or ""
                    soup = BeautifulSoup(page_source, "html.parser")
                    bs_cards: List = []
                    for sel in self.CARD_CONTAINERS:
                        bs_cards.extend(soup.select(sel) or [])

                    for bloque in bs_cards:
                        try:
                            # skip Anuncio
                            ad = bloque.select_one(self.AD_BADGE)
                            if ad and "anuncio" in ad.get_text(" ", strip=True).lower():
                                continue

                            # link
                            a = None
                            for sel in self.A_CARD:
                                a = bloque.select_one(sel)
                                if a: break
                            link = _abs_link(a.get("href", "") if a else "")

                            # título
                            titulo = None
                            for tsel in self.TITLE:
                                t = bloque.select_one(tsel)
                                if t:
                                    titulo = t.get_text(" ", strip=True)
                                    break
                            if not titulo and a:
                                titulo = (a.get("title") or a.get_text(" ", strip=True) or "").strip()
                            titulo = titulo or "Sin título"

                            # precio (entero+decimal)
                            entero = bloque.select_one(self.PRICE_INTEGER)
                            dec = bloque.select_one(self.PRICE_DECIMAL)
                            if entero or dec:
                                e_txt = re.sub(r"[^\d]", "", entero.get_text() if entero else "")
                                d_txt = re.sub(r"[^\d]", "", dec.get_text() if dec else "")
                                ptxt = f"{e_txt}.{d_txt}" if (e_txt and d_txt) else (e_txt or (f"0.{d_txt}" if d_txt else ""))
                            else:
                                any_p = None
                                for css in self.PRICE_ANY:
                                    any_p = bloque.select_one(css)
                                    if any_p: break
                                ptxt = any_p.get_text(" ", strip=True) if any_p else None
                            precio = limpiar_precio(ptxt)

                            # precio original
                            pori_tag = None
                            for osel in self.PRICE_ORIGINAL:
                                pori_tag = bloque.select_one(osel)
                                if pori_tag: break
                            precio_original = limpiar_precio(pori_tag.get_text(" ", strip=True) if pori_tag else None)

                            # descuento
                            dtag = None
                            for dsel in self.DISCOUNT:
                                dtag = bloque.select_one(dsel)
                                if dtag: break
                            descuento = dtag.get_text(" ", strip=True) if dtag else None

                            # ventas
                            sold = None
                            for ssel in self.SOLD:
                                sold = bloque.select_one(ssel)
                                if sold: break
                            ventas = limpiar_cantidad(sold.get_text(" ", strip=True) if sold else "")

                            resultados.append({
                                "pagina": page,
                                "titulo": titulo,
                                "precio": precio,
                                "precio_original": precio_original,
                                "descuento": descuento,
                                "ventas": ventas,
                                "link": link,
                                "plataforma": "Temu",
                                "fecha_scraping": datetime.now().strftime("%Y-%m-%d"),
                            })
                        except Exception:
                            continue

            return resultados
        finally:
            self.close()
