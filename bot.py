"""
=============================================================================
Pull&Bear Restock & Auto-Buy Monitor Bot
Producto: Cardigan cremallera Dickies (Ref 07563305 / Color 712)
=============================================================================
"""

import sys
import os
import time
import json
import logging
import threading
import urllib.request
import urllib.parse
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("PullBearBot")

# Alarm flag
ALARM_ACTIVE = False


def play_sound_alarm():
    """Plays continuous beep alarm on Windows."""
    global ALARM_ACTIVE
    if sys.platform != "win32":
        return
    try:
        import winsound
        while ALARM_ACTIVE:
            winsound.Beep(1200, 350)
            time.sleep(0.15)
            winsound.Beep(1600, 350)
            time.sleep(0.3)
    except Exception as e:
        logger.warning(f"No se pudo reproducir sonido de alarma: {e}")


def show_windows_popup(title, message):
    """Displays a top-most Windows alert box without blocking."""
    if sys.platform != "win32":
        return
    def _popup():
        try:
            import ctypes
            # MB_OK | MB_ICONEXCLAMATION | MB_SYSTEMMODAL (0x0 | 0x30 | 0x1000)
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x30 | 0x1000)
        except Exception as e:
            logger.warning(f"Error mostrando ventana emergente: {e}")
    threading.Thread(target=_popup, daemon=True).start()


def send_telegram(token, chat_id, message):
    """Sends notification to Telegram bot."""
    if not token or not chat_id or token == "TU_BOT_TOKEN_AQUI":
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = json.dumps({"chat_id": chat_id, "text": message, "parse_mode": "HTML"}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                logger.info("Notificacion Telegram enviada con exito.")
    except Exception as e:
        logger.error(f"Error enviando Telegram: {e}")


def send_discord(webhook_url, content, embed_data=None):
    """Sends notification to Discord webhook."""
    if not webhook_url or webhook_url == "TU_DISCORD_WEBHOOK_AQUI":
        return
    try:
        body = {"content": content}
        if embed_data:
            body["embeds"] = [embed_data]
        payload = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(webhook_url, data=payload, headers={"Content-Type": "application/json", "User-Agent": "PullBearBot"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status in (200, 204):
                logger.info("Notificacion Discord enviada con exito.")
    except Exception as e:
        logger.error(f"Error enviando Discord: {e}")


def load_config():
    """Loads configuration from config.json or returns default values."""
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    defaults = {
        "product_url": "https://www.pullandbear.com/es/cardigan-cremallera-dickies-l07563305?cS=712",
        "target_size": "XS",
        "check_interval_seconds": 5,
        "refresh_page_interval_minutes": 15,
        "headless": False,
        "user_data_dir": "./chrome_profile",
        "auto_add_to_cart": True,
        "auto_open_checkout": True,
        "sound_alarm": True,
        "windows_notification": True,
        "telegram": {"enabled": False, "bot_token": "", "chat_id": ""},
        "discord": {"enabled": False, "webhook_url": ""}
    }
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_conf = json.load(f)
                defaults.update(user_conf)
                logger.info(f"Configuracion cargada desde {config_path}")
        except Exception as e:
            logger.warning(f"Error leyendo config.json ({e}). Usando configuracion por defecto.")
    return defaults


def create_driver(config):
    """Initializes and returns a Selenium Chrome driver with anti-detection options."""
    options = Options()
    if config.get("headless", False):
        options.add_argument("--headless=new")
        logger.info("Modo Headless activado (Chrome en segundo plano).")
    else:
        logger.info("Modo Visual activado (Ventana de Chrome visible).")

    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36")
    options.add_argument("--window-size=1280,850")
    options.add_argument("--log-level=3")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    profile_dir = config.get("user_data_dir")
    if profile_dir:
        abs_profile = os.path.abspath(profile_dir)
        options.add_argument(f"--user-data-dir={abs_profile}")
        logger.info(f"Perfil de usuario de Chrome: {abs_profile}")

    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"}
    )
    return driver


def wait_for_page_and_extract_metadata(driver, url, max_retries=6):
    """Loads the product page and retrieves Inditex IDs."""
    logger.info(f"Navegando a la prenda: {url}")
    driver.get(url)

    for attempt in range(max_retries):
        time.sleep(3)
        title = driver.title
        logger.info(f"Esperando verificacion Akamai/Inditex... (Intento {attempt+1}/{max_retries}) | Titulo: {title}")

        meta = driver.execute_script("""
            if (window.inditex && window.inditex.iProductId) {
                return {
                    productId: window.inditex.iProductId,
                    storeId: window.inditex.iStoreId || 24009400,
                    catalogId: window.inditex.iCatalogId || 20309459,
                    langId: window.inditex.iLangId || -5,
                    productRef: window.inditex.iProductReference || '07563305'
                };
            }
            return null;
        """)

        if meta and meta.get("productId"):
            logger.info(f"Metadatos obtenidos: ProductId={meta['productId']}, StoreId={meta['storeId']}, CatalogId={meta['catalogId']}")
            return meta

    # Fallback to known constants for this product if metadata wasn't populated in global window
    logger.warning("No se pudo extraer window.inditex automaticamente. Usando identificadores conocidos del producto Dickies.")
    return {
        "productId": 751020357,
        "storeId": 24009400,
        "catalogId": 20309459,
        "langId": -5,
        "productRef": "07563305"
    }


def query_product_stock_info(driver, meta, target_size="XS"):
    """Queries in-session ITX detail endpoint and returns target size info."""
    script = f"""
        var done = arguments[0];
        var url = "https://www.pullandbear.com/itxrest/2/catalog/store/{meta['storeId']}/{meta['catalogId']}/category/0/product/{meta['productId']}/detail?languageId={meta['langId']}&appId=1";
        fetch(url)
            .then(r => r.json())
            .then(data => {{
                var found = null;
                var productName = data.name || "Cárdigan Dickies";
                var colors = (data.detail && data.detail.colors) ? data.detail.colors : [];
                for (var i = 0; i < colors.length; i++) {{
                    var sizes = colors[i].sizes || [];
                    for (var j = 0; j < sizes.length; j++) {{
                        var s = sizes[j];
                        if (s.name && s.name.toUpperCase() === "{target_size.upper()}") {{
                            found = {{
                                name: s.name,
                                sku: s.sku,
                                price: s.price,
                                visibilityValue: s.visibilityValue,
                                backSoon: s.backSoon,
                                isBuyable: s.isBuyable,
                                colorId: colors[i].id,
                                colorName: colors[i].name,
                                productName: productName
                            }};
                            break;
                        }}
                    }}
                    if (found) break;
                }}
                done({{ success: true, target: found, allSizes: (colors[0] ? colors[0].sizes.map(x => ({{ name: x.name, vis: x.visibilityValue }})) : []) }});
            }})
            .catch(err => done({{ success: false, error: err.toString() }}));
    """
    res = driver.execute_async_script(script)
    return res


def execute_auto_cart(driver, meta, size_info):
    """Executes automated addition to shopping cart both via API and DOM."""
    sku = size_info.get("sku", 751020361)
    logger.info(f"Ejecutando adicion al carrito para SKU {sku} (Talla {size_info.get('name')})...")

    # 1. Direct in-session API call
    cart_script = f"""
        var done = arguments[0];
        var url = "https://www.pullandbear.com/itxrest/2/order/store/{meta['storeId']}/order/0/orderitem?languageId={meta['langId']}&appId=1";
        fetch(url, {{
            method: "POST",
            headers: {{
                "Content-Type": "application/json",
                "Accept": "application/json"
            }},
            body: JSON.stringify({{
                "orderItems": [{{ "catentryId": {sku}, "quantity": 1 }}]
            }})
        }})
        .then(r => r.json())
        .then(data => done({{ success: true, data: data }}))
        .catch(err => done({{ success: false, error: err.toString() }}));
    """
    api_cart_res = driver.execute_async_script(cart_script)
    logger.info(f"Resultado llamada API Cesta: {api_cart_res}")

    # 2. DOM click backup
    dom_res = driver.execute_script(f"""
        var clickedSize = false;
        var clickedBuy = false;
        var sizeName = "{size_info.get('name', 'XS')}";
        document.querySelectorAll('button.size-item').forEach(btn => {{
            if (btn.innerText.includes(sizeName)) {{
                btn.click();
                clickedSize = true;
            }}
        }});
        var buyBtn = document.querySelector('button.itx-buy-button');
        if (buyBtn && !buyBtn.disabled) {{
            buyBtn.click();
            clickedBuy = true;
        }}
        return {{ clickedSize: clickedSize, clickedBuy: clickedBuy }};
    """)
    logger.info(f"Resultado interaccion DOM: {dom_res}")


def trigger_notifications(config, meta, size_info):
    """Dispatches alerts across all configured channels."""
    global ALARM_ACTIVE
    product_name = size_info.get("productName", "Cárdigan Dickies")
    size_name = size_info.get("name", "XS")
    price_cents = int(size_info.get("price", 4599))
    price_euros = f"{price_cents / 100:.2f} €"
    url = config.get("product_url")

    alert_text = (
        f"🚨 ¡RESTOCK DETECTADO EN PULL&BEAR! 🚨\n"
        f"Prenda: {product_name}\n"
        f"Talla: {size_name} DISPONIBLE\n"
        f"Precio: {price_euros}\n"
        f"Enlace: {url}"
    )

    # Console banner
    print("\n" + "=" * 60)
    print("      🎉 ¡¡¡RESTOCK DETECTADO - TALLA DISPONIBLE!!! 🎉")
    print(f"  Prenda: {product_name}")
    print(f"  Talla:  {size_name}")
    print(f"  Precio: {price_euros}")
    print("=" * 60 + "\n")

    # Sound alarm
    if config.get("sound_alarm", True):
        ALARM_ACTIVE = True
        threading.Thread(target=play_sound_alarm, daemon=True).start()

    # Windows Modal Popup
    if config.get("windows_notification", True):
        show_windows_popup(
            "¡RESTOCK EN PULL&BEAR!",
            f"¡La talla {size_name} de '{product_name}' vuelve a estar disponible!\n\nRevisa la ventana del navegador ahora."
        )

    # Telegram
    tg = config.get("telegram", {})
    if tg.get("enabled", False):
        cart_url = "https://www.pullandbear.com/es/cart.html"
        auto_cart_status = "✅ Añadida automáticamente a la cesta" if config.get("auto_add_to_cart", True) else "⚠️ Pendiente de añadir"
        tg_msg = (
            f"🔥 <b>¡RESTOCK PULL&BEAR!</b> 🔥\n\n"
            f"<b>Prenda:</b> {product_name}\n"
            f"<b>Talla:</b> {size_name} DISPONIBLE ✅\n"
            f"<b>Precio:</b> {price_euros}\n"
            f"<b>Estado Cesta:</b> {auto_cart_status}\n\n"
            f"🛒 <a href='{cart_url}'><b>IR DIRECTO AL PAGO / CESTA</b></a>\n"
            f"🔗 <a href='{url}'>Ver Ficha del Producto</a>"
        )
        send_telegram(tg.get("bot_token"), tg.get("chat_id"), tg_msg)

    # Discord
    dc = config.get("discord", {})
    if dc.get("enabled", False):
        embed = {
            "title": f"¡Restock! {product_name} ({size_name})",
            "url": url,
            "color": 0x2ECC71,  # Green
            "fields": [
                {"name": "Talla", "value": size_name, "inline": True},
                {"name": "Precio", "value": price_euros, "inline": True},
                {"name": "Estado", "value": "DISPONIBLE", "inline": True}
            ],
            "footer": {"text": "Pull&Bear Restock Bot"}
        }
        send_discord(dc.get("webhook_url"), "@everyone ¡Restock detectado!", embed)


def main():
    config = load_config()
    target_size = config.get("target_size", "XS").upper()
    check_interval = max(2, config.get("check_interval_seconds", 5))
    refresh_interval = config.get("refresh_page_interval_minutes", 15) * 60

    print("=" * 60)
    print("   PULL&BEAR RESTOCK & AUTO-BUY BOT")
    print(f"   Objetivo: {config.get('product_url')}")
    print(f"   Talla objetivo: {target_size}")
    print(f"   Intervalo de escaneo: {check_interval} segundos")
    print(f"   Auto-añadir al carrito: {config.get('auto_add_to_cart', True)}")
    print(f"   Auto-abrir checkout: {config.get('auto_open_checkout', True)}")
    print("=" * 60)

    driver = create_driver(config)
    last_page_refresh = time.time()
    consecutive_errors = 0
    checks_count = 0

    try:
        meta = wait_for_page_and_extract_metadata(driver, config.get("product_url"))

        # Initial check
        init_res = query_product_stock_info(driver, meta, target_size)
        if init_res.get("success") and init_res.get("target"):
            t_info = init_res["target"]
            logger.info(f"Prenda identificada: '{t_info.get('productName')}' | Color: {t_info.get('colorName')}")
            logger.info(f"SKU Talla {target_size}: {t_info.get('sku')} | Precio: {int(t_info.get('price', 4599))/100:.2f} €")
            logger.info(f"Estado inicial de la talla {target_size}: [{t_info.get('visibilityValue')}]")
        else:
            logger.warning(f"No se pudo consultar el estado inicial: {init_res}")

        logger.info(f"--- Iniciando monitorizacion continua cada {check_interval}s (Pulsa Ctrl+C para detener) ---")

        while True:
            checks_count += 1
            now_str = datetime.now().strftime("%H:%M:%S")

            # Check if it's time for a session refresh
            if time.time() - last_page_refresh > refresh_interval:
                logger.info("Refrescando la pagina para mantener la sesion de Akamai activa...")
                driver.get(config.get("product_url"))
                time.sleep(4)
                last_page_refresh = time.time()

            # Query stock
            t0 = time.time()
            res = query_product_stock_info(driver, meta, target_size)
            latency = time.time() - t0

            if not res or not res.get("success"):
                consecutive_errors += 1
                logger.warning(f"[{now_str}] Error comprobando stock (Intento {consecutive_errors}): {res.get('error') if res else 'None'}")
                if consecutive_errors >= 3:
                    logger.info("Demasiados fallos seguidos. Recargando la pagina web...")
                    driver.get(config.get("product_url"))
                    time.sleep(5)
                    consecutive_errors = 0
                    last_page_refresh = time.time()
                time.sleep(check_interval)
                continue

            consecutive_errors = 0
            size_data = res.get("target")

            if not size_data:
                logger.warning(f"[{now_str}] Talla {target_size} no encontrada en los datos recibidos.")
                time.sleep(check_interval)
                continue

            visibility = size_data.get("visibilityValue", "UNKNOWN")
            is_buyable = size_data.get("isBuyable", False)

            # RESTOCK CHECK:
            # When sold out, visibilityValue is 'SOLD_OUT'.
            # When available, it is 'SHOW', 'RUNNING_OUT', 'IN_STOCK', or backSoon changes.
            is_available = (visibility != "SOLD_OUT") or (is_buyable and visibility in ("SHOW", "RUNNING_OUT", "LOW_STOCK"))

            if is_available:
                logger.info(f"[{now_str}] ¡¡¡RESTOCK CONFIRMADO!!! Estado actual: {visibility}")

                # 1. Disparar notificaciones y alarmas
                trigger_notifications(config, meta, size_data)

                # 2. Auto Add to Cart
                if config.get("auto_add_to_cart", True):
                    execute_auto_cart(driver, meta, size_data)

                # 3. Auto Open Checkout
                if config.get("auto_open_checkout", True):
                    logger.info("Navegando a la pasarela de compra (Checkout/Cesta)...")
                    driver.get("https://www.pullandbear.com/es/cart.html")
                    time.sleep(2)

                # Mantener la ventana abierta y activa
                logger.info("El bot ha reservado la prenda en la cesta. Finaliza el pago manualmente en la ventana.")
                print("\nPulsa Enter en esta consola cuando hayas terminado para cerrar el bot...")
                try:
                    input()
                except Exception:
                    time.sleep(3600)
                break
            else:
                # Log status periodically
                all_status = ", ".join([f"{x['name']}:{x['vis']}" for x in res.get("allSizes", [])])
                if checks_count % 5 == 1 or check_interval >= 10:
                    logger.info(f"[{now_str}] Comprobacion #{checks_count} ({latency:.2f}s) -> Talla {target_size}: {visibility} | (Todas: {all_status})")

            time.sleep(check_interval)

    except KeyboardInterrupt:
        logger.info("\nMonitorizacion detenida manualmente por el usuario.")
    except Exception as e:
        logger.error(f"Error inesperado en la ejecucion del bot: {e}", exc_info=True)
    finally:
        global ALARM_ACTIVE
        ALARM_ACTIVE = False
        try:
            driver.quit()
        except Exception:
            pass
        logger.info("Navegador cerrado. Bot finalizado.")


if __name__ == "__main__":
    main()
