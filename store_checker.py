"""
Store Checker for Inditex Brands: Pull&Bear, Zara, Bershka
Con correccion inteligente de errores tipograficos y normalizacion de tallas.
"""

import re
import time
import json
import difflib
import logging
from urllib.parse import urlparse

logger = logging.getLogger("StoreChecker")

CANONICAL_STORES = ["pullandbear", "zara", "bershka"]


def normalize_store(query):
    """
    Intelligently identifies and corrects store names even with typos.
    Examples: pulandbear, pullndbear, zra, berhska, bsk, pull&bear.
    """
    if not query:
        return None
    q = query.lower().replace("&", "and").replace(" ", "").replace("-", "").strip()

    if "pullandbear.com" in q:
        return "pullandbear"
    if "zara.com" in q:
        return "zara"
    if "bershka.com" in q:
        return "bershka"

    if any(k in q for k in ["pull", "pul", "bear", "pb"]):
        return "pullandbear"
    if any(k in q for k in ["zara", "zar", "zra", "za"]):
        return "zara"
    if any(k in q for k in ["bersh", "bersk", "berh", "besh", "bsk", "ber"]):
        return "bershka"

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
        # Known mapping for the Dickies cardigan (both 07563305, 7563305 and color suffix 712)
        if "7563305" in clean_ref:
            return "https://www.pullandbear.com/es/cardigan-cremallera-dickies-l07563305?cS=712"
        return f"https://www.pullandbear.com/es/search?searchTerm={clean_ref}"
    elif store == "bershka":
        return f"https://www.bershka.com/es/search?searchTerm={clean_ref}"
    elif store == "zara":
        return f"https://www.zara.com/es/es/search?searchTerm={clean_ref}"
    return ref_or_url


def resolve_actual_product_url(driver, store, url):
    """If url is a search page, navigates to the first product match without picking up cookie banners."""
    if "searchTerm=" not in url and "/search?" not in url:
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

        valid_domain = "pullandbear.com" if store == "pullandbear" else "zara.com" if store == "zara" else "bershka.com"
        product_link = driver.execute_script(f"""
            let validDomain = "{valid_domain}";
            let links = [];
            document.querySelectorAll('a').forEach(a => {{
                let h = (a.href || '').toLowerCase();
                if (h.includes(validDomain) && !h.includes('/search') && !h.includes('onetrust') && !h.includes('cookie') && !h.includes('consent') && !h.includes('privacy') && !h.includes('help') && !h.includes('faq')) {{
                    if (h.includes('-p') || h.includes('-l0') || h.includes('-l1') || h.includes('-l2') || h.includes('.html')) {{
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
    Universal stock checker for Pull&Bear, Bershka, and Zara.
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
            time.sleep(4)
    except Exception as e:
        logger.warning(f"Error cargando {resolved_url}: {e}")

    # Check for Access Denied or WAF block on product page
    page_title = driver.title or ""
    if "access denied" in page_title.lower() or "403" in page_title:
        logger.warning(f"Página bloqueada temporalmente: {page_title}")
        return False, "Consultar web", "Prenda", "SOLD_OUT", resolved_url

    clean_title = page_title.split("|")[0].split("-")[0].strip() or "Prenda Inditex"

    # 1. PULL&BEAR / BERSHKA (ITX REST detail API within active session)
    if store in ("pullandbear", "bershka"):
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
                    for c in colors:
                        for s in c.get("sizes", []):
                            size_name = normalize_size(s.get("name"))
                            if size_name == target_size:
                                vis = s.get("visibilityValue", "UNKNOWN")
                                price_raw = s.get("price", "0")
                                price = f"{int(price_raw)/100:.2f} €" if str(price_raw).isdigit() else str(price_raw)
                                
                                # STRICT RESTOCK CHECK: NEVER consider SOLD_OUT as available!
                                if vis in ("SOLD_OUT", "OUT_OF_STOCK", "UNKNOWN", "HIDDEN"):
                                    is_avail = False
                                else:
                                    is_avail = vis in ("SHOW", "RUNNING_OUT", "LOW_STOCK", "IN_STOCK")
                                    
                                return is_avail, price, name, vis, resolved_url
        except Exception as e:
            logger.warning(f"Error en consulta ITX de {store}: {e}")

    # 2. DOM-BASED UNIVERSAL FALLBACK (Zara, Bershka, Pull&Bear)
    try:
        dom_result = driver.execute_script(f"""
            let target = "{target_size}";
            let titleEl = document.querySelector('h1, .product-detail-info__header-name, .product-name');
            let prodName = titleEl ? titleEl.innerText.trim() : document.title;
            
            let priceEl = document.querySelector('.money-amount__main, .price, .product-detail-info__price, .current-price-elem');
            let price = priceEl ? priceEl.innerText.trim() : "";
            
            let found = null;
            document.querySelectorAll('button, li, span, [data-qa-action="size-selector-list-item"]').forEach(el => {{
                let txt = (el.innerText || "").trim().toUpperCase();
                txt = txt.replace(/^(TALLA|LA|UNA)\\s+/, '');
                if (txt === target || txt.startsWith(target + "\\n") || txt.startsWith(target + " ")) {{
                    let cls = (el.className || "").toLowerCase();
                    let ariaDis = el.getAttribute('aria-disabled');
                    let isDis = el.disabled || ariaDis === "true" || cls.includes('disabled') || cls.includes('out-of-stock') || cls.includes('is-soldout');
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
