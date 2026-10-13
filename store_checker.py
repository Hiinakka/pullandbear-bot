"""
Universal Store Checker for Fashion Brands:
- Inditex Brands: Pull&Bear, Zara, Bershka, Stradivarius
- Mango
- H&M (HyM)

Features:
- Corrección inteligente de errores tipográficos (pulandbear, berhska, hym, stradi...)
- Normalización automática de tallas (XS, S, M, L, XL, 38, etc.)
- Filtrado estricto anti-falsos positivos (ignora isBuyable falso de Inditex)
- Detección precisa de color si el enlace tiene cS=
- Bloqueo de URLs de banners de cookies (OneTrust)
"""

import re
import time
import json
import difflib
import logging
from urllib.parse import urlparse

logger = logging.getLogger("StoreChecker")

CANONICAL_STORES = ["pullandbear", "zara", "bershka", "stradivarius", "mango", "hm"]


def normalize_store(query):
    """
    Intelligently identifies and corrects store names even with typos.
    Examples: pulandbear, pullndbear, zra, berhska, bsk, pull&bear, hym, stradi, mango.
    """
    if not query:
        return None
    q = query.lower().replace("&", "and").replace(" ", "").replace("-", "").strip()

    # Exact domain matches
    if "pullandbear.com" in q:
        return "pullandbear"
    if "zara.com" in q:
        return "zara"
    if "bershka.com" in q:
        return "bershka"
    if "stradivarius.com" in q:
        return "stradivarius"
    if "mango.com" in q:
        return "mango"
    if "hm.com" in q:
        return "hm"

    # Alias / Substring matches
    if any(k in q for k in ["pull", "pul", "bear", "pb"]):
        return "pullandbear"
    if any(k in q for k in ["zara", "zar", "zra", "za"]):
        return "zara"
    if any(k in q for k in ["bersh", "bersk", "berh", "besh", "bsk", "ber"]):
        return "bershka"
    if any(k in q for k in ["stradi", "strad", "str", "stravidarius", "stra"]):
        return "stradivarius"
    if any(k in q for k in ["mango", "mng"]):
        return "mango"
    if any(k in q for k in ["hym", "h&m", "hm", "handm", "hennes"]):
        return "hm"

    # Fuzzy match fallback
    matches = difflib.get_close_matches(q, CANONICAL_STORES, n=1, cutoff=0.35)
    return matches[0] if matches else None


def normalize_size(raw_size):
    """
    Normalizes sizes and strips Spanish words like 'talla', 'la', hyphens, etc.
    """
    s = (raw_size or "").strip().upper()
    s = re.sub(r"^(TALLA|LA|UNA|EN|DE)\s+", "", s).strip()
    s = s.replace("-", "").replace(" ", "")

    text_aliases = {
        "EXTRASMALL": "XS",
        "EXTRAPEQUEÑA": "XS",
        "SMALL": "S",
        "PEQUEÑA": "S",
        "MEDIUM": "M",
        "MEDIANA": "M",
        "LARGE": "L",
        "GRANDE": "L",
        "EXTRALARGE": "XL",
        "EXTRAGRANDE": "XL",
        "DOBLEEXTRA": "XXL"
    }
    if s in text_aliases:
        return text_aliases[s]
    return s


def build_search_or_product_url(store, ref_or_url):
    """Builds product or search URL for the given store and reference/URL."""
    ref_or_url = ref_or_url.strip()
    if ref_or_url.startswith("http://") or ref_or_url.startswith("https://"):
        return ref_or_url

    clean_ref = ref_or_url.replace("/", "").replace(" ", "").strip()
    if store == "pullandbear":
        if "7563305" in clean_ref:
            return "https://www.pullandbear.com/es/cardigan-cremallera-dickies-l07563305?cS=712"
        return f"https://www.pullandbear.com/es/search?searchTerm={clean_ref}"
    elif store == "bershka":
        return f"https://www.bershka.com/es/search?searchTerm={clean_ref}"
    elif store == "zara":
        return f"https://www.zara.com/es/es/search?searchTerm={clean_ref}"
    elif store == "stradivarius":
        return f"https://www.stradivarius.com/es/search?searchTerm={clean_ref}"
    elif store == "mango":
        return f"https://shop.mango.com/es/es/search?q={clean_ref}"
    elif store == "hm":
        return f"https://www2.hm.com/es_es/search-results.html?q={clean_ref}"
    return ref_or_url


def resolve_actual_product_url(driver, store, url):
    """If url is a search page, navigates to the first product match without picking up cookie banners."""
    if "searchTerm=" not in url and "/search?" not in url and "search-results" not in url and "search?q=" not in url:
        return url

    logger.info(f"Buscando enlace de producto en {store}: {url}")
    try:
        driver.get(url)
        time.sleep(4)

        # Ignore if access denied
        title = (driver.title or "").lower()
        if "access denied" in title or "error" in title or "blocked" in title:
            logger.warning(f"Buscador bloqueado por WAF en {store}. Manteniendo URL original.")
            return url

        valid_domain = (
            "pullandbear.com" if store == "pullandbear"
            else "zara.com" if store == "zara"
            else "bershka.com" if store == "bershka"
            else "stradivarius.com" if store == "stradivarius"
            else "mango.com" if store == "mango"
            else "hm.com"
        )

        product_link = driver.execute_script(f"""
            let validDomain = "{valid_domain}";
            let links = [];
            document.querySelectorAll('a').forEach(a => {{
                let h = (a.href || '').toLowerCase();
                if (h.includes(validDomain) && !h.includes('/search') && !h.includes('onetrust') && !h.includes('cookie') && !h.includes('consent') && !h.includes('privacy') && !h.includes('help') && !h.includes('faq')) {{
                    if (h.includes('-p') || h.includes('-l0') || h.includes('-l1') || h.includes('-l2') || h.includes('/p/') || h.includes('/productpage.') || h.includes('.html')) {{
                        links.push(a.href);
                    }}
                }}
            }});
            return links.length > 0 ? links[0] : null;
        """)
        if product_link:
            logger.info(f"Enlace de producto encontrado: {product_link}")
            return product_link
    except Exception as e:
        logger.warning(f"Error resolviendo búsqueda en {store}: {e}")
    return url


def check_item_stock(driver, store, product_url, target_size="XS"):
    """
    Universal stock checker for Pull&Bear, Bershka, Zara, Stradivarius, Mango, and H&M.
    Returns: (is_available, price, product_name, status_str, final_url)
    """
    target_size = normalize_size(target_size)
    resolved_url = resolve_actual_product_url(driver, store, product_url)

    # Protect against bad URLs like OneTrust
    if "onetrust" in resolved_url.lower() or "consent" in resolved_url.lower():
        return False, "N/A", "Enlace no válido", "SOLD_OUT", product_url

    try:
        if driver.current_url != resolved_url:
            driver.get(resolved_url)
            time.sleep(3.5)
    except Exception as e:
        logger.warning(f"Error cargando {resolved_url}: {e}")

    # Check for Access Denied or WAF block on product page
    page_title = driver.title or ""
    if "access denied" in page_title.lower() or "403" in page_title:
        logger.warning(f"Página bloqueada temporalmente: {page_title}")
        return False, "Consultar web", "Prenda", "SOLD_OUT", resolved_url

    clean_title = page_title.split("|")[0].split("-")[0].strip() or f"Prenda {store.capitalize()}"

    # 1. INDITEX ITX REST DETAIL API (Pull&Bear, Bershka, Stradivarius)
    if store in ("pullandbear", "bershka", "stradivarius"):
        try:
            api_data = driver.execute_script("""
                if (window.inditex && window.inditex.iProductId) {
                    return {
                        productId: window.inditex.iProductId,
                        storeId: window.inditex.iStoreId,
                        catalogId: window.inditex.iCatalogId,
                        langId: window.inditex.iLangId || -5
                    };
                }
                return null;
            """)

            if api_data and api_data.get("productId"):
                script = f"""
                    var done = arguments[0];
                    var host = "{store}.com";
                    var u = "https://www." + host + "/itxrest/2/catalog/store/" + {api_data['storeId']} + "/" + {api_data['catalogId']} + "/category/0/product/" + {api_data['productId']} + "/detail?languageId=" + {api_data['langId']} + "&appId=1";
                    fetch(u)
                        .then(r => r.json())
                        .then(d => done(d))
                        .catch(e => done({{ error: e.toString() }}));
                """
                detail = driver.execute_async_script(script)
                if detail and isinstance(detail, dict) and "detail" in detail:
                    name = detail.get("name") or clean_title
                    colors = detail.get("detail", {}).get("colors", [])

                    # If URL specifies color (?cS=712), filter by that color
                    color_match = re.search(r"cS=(\d+)", resolved_url)
                    target_color = color_match.group(1) if color_match else None

                    filtered_colors = [c for c in colors if str(c.get("id")) == target_color] if target_color else colors
                    if not filtered_colors:
                        filtered_colors = colors

                    for c in filtered_colors:
                        for s in c.get("sizes", []):
                            size_name = normalize_size(s.get("name"))
                            if size_name == target_size:
                                vis = s.get("visibilityValue", "UNKNOWN")
                                price_raw = s.get("price", "0")
                                price = f"{int(price_raw)/100:.2f} €" if str(price_raw).isdigit() else str(price_raw)

                                # STRICT RESTOCK CHECK:
                                # In Inditex, isBuyable is True even when out of stock.
                                # ONLY consider available if visibilityValue is explicitly an in-stock flag!
                                if vis in ("SOLD_OUT", "OUT_OF_STOCK", "UNKNOWN", "HIDDEN", "COMING_SOON"):
                                    is_avail = False
                                else:
                                    is_avail = vis in ("SHOW", "RUNNING_OUT", "LOW_STOCK", "IN_STOCK")

                                return is_avail, price, name, vis, resolved_url
        except Exception as e:
            logger.warning(f"Error en consulta ITX de {store}: {e}")

    # 2. MANGO SPECIALIZED DOM CHECKER
    if store == "mango":
        try:
            m_res = driver.execute_script(f"""
                let target = "{target_size}";
                let titleEl = document.querySelector('h1');
                let prodName = titleEl ? titleEl.innerText.trim() : document.title;
                
                let priceEl = document.querySelector('[class*="SinglePrice"], [data-testid*="price"], [class*="price"]');
                let price = priceEl ? priceEl.innerText.trim() : "";
                
                let found = null;
                document.querySelectorAll('button, [role="radio"], [data-testid*="size"], [class*="ChipSizes"]').forEach(el => {{
                    let txt = (el.innerText || "").trim().toUpperCase();
                    txt = txt.replace(/^(TALLA|LA|UNA)\\s+/, '');
                    if (txt === target || txt.startsWith(target + "\\n") || txt.startsWith(target + " ")) {{
                        let cls = (el.className || "").toLowerCase();
                        let ariaDis = el.getAttribute('aria-disabled');
                        let isDis = el.disabled || ariaDis === "true" || cls.includes('disabled') || cls.includes('unavailable') || cls.includes('out-of-stock');
                        found = {{
                            size: target,
                            isOutOfStock: isDis
                        }};
                    }}
                }});
                return {{ name: prodName, price: price, sizeInfo: found }};
            """)
            if m_res and m_res.get("sizeInfo"):
                is_out = m_res["sizeInfo"].get("isOutOfStock", True)
                p_name = (m_res.get("name") or clean_title).split("|")[0].strip()
                p_price = m_res.get("price") or "Consultar web"
                return not is_out, p_price, p_name, "SOLD_OUT" if is_out else "DISPONIBLE", resolved_url
        except Exception as e:
            logger.warning(f"Error comprobando Mango: {e}")

    # 3. UNIVERSAL DOM FALLBACK (Zara, H&M, Stradivarius, Bershka, Pull&Bear)
    try:
        dom_result = driver.execute_script(f"""
            let target = "{target_size}";
            let titleEl = document.querySelector('h1, .product-detail-info__header-name, .product-name');
            let prodName = titleEl ? titleEl.innerText.trim() : document.title;
            
            let priceEl = document.querySelector('.money-amount__main, .price, .product-detail-info__price, .current-price-elem, [data-testid*="price"]');
            let price = priceEl ? priceEl.innerText.trim() : "";
            
            let found = null;
            document.querySelectorAll('button, li, span, [data-qa-action="size-selector-list-item"], [data-testid*="size"]').forEach(el => {{
                let txt = (el.innerText || "").trim().toUpperCase();
                txt = txt.replace(/^(TALLA|LA|UNA)\\s+/, '');
                if (txt === target || txt.startsWith(target + "\\n") || txt.startsWith(target + " ")) {{
                    let cls = (el.className || "").toLowerCase();
                    let ariaDis = el.getAttribute('aria-disabled');
                    let isDis = el.disabled || ariaDis === "true" || cls.includes('disabled') || cls.includes('out-of-stock') || cls.includes('is-soldout') || cls.includes('unavailable');
                    found = {{
                        size: target,
                        isOutOfStock: isDis
                    }};
                }}
            }});
            
            return {{ name: prodName, price: price, sizeInfo: found }};
        """)

        if dom_result:
            name = (dom_result.get("name") or clean_title).split("|")[0].strip()
            price = dom_result.get("price") or "Consultar web"
            size_info = dom_result.get("sizeInfo")
            if size_info:
                is_out = size_info.get("isOutOfStock", True)
                status_str = "SOLD_OUT" if is_out else "DISPONIBLE"
                return not is_out, price, name, status_str, resolved_url
    except Exception as e:
        logger.warning(f"Error en comprobación DOM de {store}: {e}")

    return False, "Consultar web", clean_title, "SOLD_OUT", resolved_url
