"""
Store Checker for Inditex Brands: Pull&Bear, Zara, Bershka
"""

import time
import json
import logging

logger = logging.getLogger("StoreChecker")

STORE_DOMAINS = {
    "pullandbear": ["pullandbear.com", "pull&bear", "pb"],
    "zara": ["zara.com", "za"],
    "bershka": ["bershka.com", "bsk"]
}


def detect_store(input_str):
    """Detects store from name or URL string."""
    s = (input_str or "").lower().strip()
    for store, aliases in STORE_DOMAINS.items():
        if any(alias in s for alias in aliases):
            return store
    if "zara" in s:
        return "zara"
    if "bershka" in s:
        return "bershka"
    if "pull" in s:
        return "pullandbear"
    return "pullandbear"


def build_search_or_product_url(store, ref_or_url):
    """Builds product or search URL for the given store and reference/URL."""
    ref_or_url = ref_or_url.strip()
    if ref_or_url.startswith("http://") or ref_or_url.startswith("https://"):
        return ref_or_url

    clean_ref = ref_or_url.replace("/", "").replace(" ", "").strip()
    if store == "pullandbear":
        if "07563305" in clean_ref:
            return "https://www.pullandbear.com/es/cardigan-cremallera-dickies-l07563305?cS=712"
        return f"https://www.pullandbear.com/es/search?searchTerm={clean_ref}"
    elif store == "bershka":
        return f"https://www.bershka.com/es/search?searchTerm={clean_ref}"
    elif store == "zara":
        return f"https://www.zara.com/es/es/search?searchTerm={clean_ref}"
    return ref_or_url


def resolve_actual_product_url(driver, store, url):
    """If url is a search page, navigates to the first product match."""
    if "searchTerm=" not in url and "/search?" not in url:
        return url

    logger.info(f"Buscando enlace de producto en {store}: {url}")
    driver.get(url)
    time.sleep(4)

    product_link = driver.execute_script("""
        let links = [];
        document.querySelectorAll('a').forEach(a => {
            let h = a.href || '';
            if (h.includes('-p') || h.includes('-l0') || (h.includes('.html') && !h.includes('/search'))) {
                links.push(h);
            }
        });
        return links.length > 0 ? links[0] : null;
    """)

    if product_link:
        logger.info(f"Enlace de producto encontrado: {product_link}")
        return product_link
    return url


def check_item_stock(driver, store, product_url, target_size="XS"):
    """
    Universal stock checker for Pull&Bear, Bershka, and Zara.
    Returns: (is_available, price, product_name, status_str, final_url)
    """
    target_size = (target_size or "XS").strip().upper()
    resolved_url = resolve_actual_product_url(driver, store, product_url)
    
    if driver.current_url != resolved_url:
        driver.get(resolved_url)
        time.sleep(5)

    # Extract title from browser
    raw_title = driver.title or ""
    clean_title = raw_title.split("|")[0].split("-")[0].strip() or "Prenda Inditex"

    # 1. PULL&BEAR / BERSHKA (ITX REST detail API within active session)
    if store in ("pullandbear", "bershka"):
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
                        if (s.get("name") or "").strip().upper() == target_size:
                            vis = s.get("visibilityValue", "UNKNOWN")
                            price_raw = s.get("price", "0")
                            price = f"{int(price_raw)/100:.2f} €" if str(price_raw).isdigit() else str(price_raw)
                            is_avail = (vis != "SOLD_OUT" and vis != "UNKNOWN") or s.get("isBuyable") is True
                            return is_avail, price, name, vis, resolved_url

    # 2. DOM-BASED UNIVERSAL FALLBACK (Zara, Bershka, Pull&Bear)
    dom_result = driver.execute_script(f"""
        let target = "{target_size}";
        let titleEl = document.querySelector('h1, .product-detail-info__header-name, .product-name');
        let prodName = titleEl ? titleEl.innerText.trim() : document.title;
        
        let priceEl = document.querySelector('.money-amount__main, .price, .product-detail-info__price, .current-price-elem');
        let price = priceEl ? priceEl.innerText.trim() : "";
        
        let found = null;
        document.querySelectorAll('button, li, span, [data-qa-action="size-selector-list-item"]').forEach(el => {{
            let txt = (el.innerText || "").trim().toUpperCase();
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

    name = (dom_result.get("name") or clean_title).split("|")[0].strip()
    price = dom_result.get("price") or "Consultar web"
    size_info = dom_result.get("sizeInfo")
    if size_info:
        is_out = size_info.get("isOutOfStock", True)
        status_str = "SOLD_OUT" if is_out else "DISPONIBLE"
        return not is_out, price, name, status_str, resolved_url

    return False, price, clean_title, "SOLD_OUT", resolved_url
