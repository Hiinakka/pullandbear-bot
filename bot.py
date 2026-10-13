"""
=============================================================================
Inditex Multi-Store Restock Bot (Pull&Bear, Zara, Bershka)
- Escaneo cada 1 minuto (60s) para evitar sobrecargas.
- Soporte multi-usuario (hasta 5 o más personas por Telegram).
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

import store_checker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("InditexBot")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
ALERTS_PATH = os.path.join(BASE_DIR, "alerts.json")

ALARM_ACTIVE = False
LAST_NOTIFIED = {}  # item_id -> timestamp


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


def send_telegram(token, chat_id, message):
    """Sends notification to a specific Telegram chat_id."""
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = json.dumps({"chat_id": chat_id, "text": message, "parse_mode": "HTML"}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                logger.info(f"Mensaje Telegram enviado con éxito a {chat_id}.")
    except Exception as e:
        logger.error(f"Error enviando Telegram a {chat_id}: {e}")


def load_config():
    """Loads configuration from config.json."""
    defaults = {
        "check_interval_seconds": 60,
        "headless": True,
        "sound_alarm": True,
        "telegram": {
            "enabled": True,
            "bot_token": "8859607748:AAHMnjhS5quanBfrPul8f1PattZmh85ny3g",
            "chat_id": "1997921776"
        }
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user_conf = json.load(f)
                defaults.update(user_conf)
        except Exception as e:
            logger.warning(f"Error leyendo config.json: {e}")
    return defaults


def load_alerts():
    """Loads tracked items from alerts.json."""
    if os.path.exists(ALERTS_PATH):
        try:
            with open(ALERTS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Normalize chat_ids format
                for item in data:
                    if "chat_ids" not in item:
                        item["chat_ids"] = ["1997921776"]
                return data
        except Exception as e:
            logger.warning(f"Error leyendo alerts.json: {e}")
    return []


def save_alerts(alerts):
    """Saves tracked items to alerts.json."""
    try:
        with open(ALERTS_PATH, "w", encoding="utf-8") as f:
            json.dump(alerts, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error guardando alerts.json: {e}")


def create_driver(config):
    """Initializes and returns a Selenium Chrome driver with anti-detection options."""
    options = Options()
    if config.get("headless", True):
        options.add_argument("--headless=new")
        logger.info("Modo Headless activado.")
    else:
        logger.info("Modo Visual activado.")

    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36")
    options.add_argument("--window-size=1280,850")
    options.add_argument("--log-level=3")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    profile_dir = config.get("user_data_dir", "./chrome_profile")
    if profile_dir:
        abs_profile = os.path.abspath(profile_dir)
        options.add_argument(f"--user-data-dir={abs_profile}")

    driver = webdriver.Chrome(options=options)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"}
    )
    return driver


def telegram_listener_thread(config):
    """Listens for user commands via Telegram bot polling (multi-user support)."""
    tg = config.get("telegram", {})
    token = tg.get("bot_token")
    if not token or not tg.get("enabled"):
        logger.info("Telegram listener desactivado.")
        return

    logger.info("Iniciando escucha multi-usuario de comandos de Telegram...")
    offset = 0

    while True:
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates?offset={offset}&timeout=10"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    msg = update.get("message", {})
                    chat_id = str(msg.get("chat", {}).get("id", ""))
                    user_name = msg.get("from", {}).get("first_name", "Usuario")
                    text = (msg.get("text") or "").strip()

                    if chat_id and text:
                        handle_telegram_command(token, chat_id, user_name, text)
        except Exception as e:
            time.sleep(3)
        time.sleep(1)


def handle_telegram_command(token, chat_id, user_name, text):
    """Processes incoming Telegram bot commands for any user."""
    alerts = load_alerts()
    parts = text.split()
    cmd = parts[0].lower() if parts else ""

    if cmd in ("/start", "/help", "ayuda"):
        help_msg = (
            f"👋 <b>¡Hola {user_name}! Soy tu Bot de Restock para Inditex</b> (Zara, Bershka y Pull&Bear).\n\n"
            "👗 <b>Comandos disponibles:</b>\n\n"
            "• <b>Añadir alerta:</b>\n"
            "<code>/add &lt;tienda&gt; &lt;referencia o enlace&gt; &lt;talla&gt;</code>\n"
            "<i>Ejemplos:</i>\n"
            "<code>/add pullandbear 07563305 XS</code>\n"
            "<code>/add zara 2731/240 S</code>\n"
            "<code>/add bershka 0123/456 M</code>\n"
            "<code>/add https://www.zara.com/es/es/... M</code>\n\n"
            "• <code>/list</code> : Ver tus prendas en seguimiento y su estado.\n"
            "• <code>/del &lt;número&gt;</code> : Dejar de seguir una prenda (ej: <code>/del 1</code>).\n"
            "• <code>/prueba</code> o <code>/test</code> : Comprobar que recibes avisos y que todo funciona correctamente."
        )
        send_telegram(token, chat_id, help_msg)

    elif cmd in ("/list", "/status", "lista"):
        # Filter items where this chat_id is subscribed
        user_items = [item for item in alerts if chat_id in item.get("chat_ids", [])]

        if not user_items:
            send_telegram(token, chat_id, "ℹ️ No tienes ninguna prenda en seguimiento todavía.\nAñade una con:\n<code>/add &lt;tienda&gt; &lt;referencia&gt; &lt;talla&gt;</code>")
            return

        lines = [f"📋 <b>Tus prendas en seguimiento ({len(user_items)}):</b>\n"]
        for idx, item in enumerate(user_items, start=1):
            store_name = item.get("store", "tienda").upper()
            name = item.get("name", "Prenda")
            size = item.get("size", "XS")
            status = item.get("status", "Comprobando...")
            price = item.get("price", "")
            icon = "✅ DISPONIBLE" if status not in ("SOLD_OUT", "Comprobando...", "UNKNOWN") else "❌ AGOTADO"
            
            lines.append(
                f"<b>{idx}. [{store_name}] {name}</b>\n"
                f"   Talla: <b>{size}</b> | Estado: {icon}\n"
                f"   Precio: {price}\n"
                f"   🔗 <a href='{item.get('url')}'>Ver Prenda</a>\n"
            )
        lines.append("<i>Para borrar una alerta usa /del &lt;número&gt;</i>")
        send_telegram(token, chat_id, "\n".join(lines))

    elif cmd in ("/del", "/delete", "/borrar", "/eliminar"):
        user_items = [item for item in alerts if chat_id in item.get("chat_ids", [])]
        if len(parts) < 2 or not parts[1].isdigit():
            send_telegram(token, chat_id, "⚠️ Indica el número de la prenda a eliminar.\nEjemplo: <code>/del 1</code> (consulta tu lista con /list)")
            return
        idx = int(parts[1]) - 1
        if 0 <= idx < len(user_items):
            target_item = user_items[idx]
            # Remove chat_id from item's subscribers
            if chat_id in target_item.get("chat_ids", []):
                target_item["chat_ids"].remove(chat_id)

            # If no one is following it, remove the item completely
            if not target_item.get("chat_ids"):
                alerts = [x for x in alerts if x.get("id") != target_item.get("id")]

            save_alerts(alerts)
            send_telegram(token, chat_id, f"🗑️ Has dejado de seguir: <b>{target_item.get('name', 'Prenda')}</b> ({target_item.get('size')}).")
        else:
            send_telegram(token, chat_id, f"⚠️ Número no válido. Tienes {len(user_items)} prendas en /list.")

    elif cmd in ("/prueba", "/test", "prueba", "test"):
        test_msg = (
            "🔔 <b>¡PRUEBA DE FUNCIONAMIENTO EXITOSA!</b> 🔔\n\n"
            "🟢 <b>Estado del bot:</b> 100% Operativo y Conectado\n"
            "🏪 <b>Tiendas soportadas:</b> Zara, Bershka y Pull&Bear\n"
            "⏱️ <b>Frecuencia de escaneo:</b> Cada 1 minuto (60s)\n"
            f"📱 <b>Tu ID de usuario:</b> <code>{chat_id}</code>\n\n"
            "🚨 <i>Ejemplo de cómo te llegará una alerta real:</i>\n"
            "Prenda: <b>Cárdigan cremallera Dickies</b>\n"
            "Talla: <b>XS DISPONIBLE ✅</b>\n"
            "Precio: <b>45.99 €</b>\n\n"
            "🛒 <a href='https://www.pullandbear.com/es/cardigan-cremallera-dickies-l07563305?cS=712'><b>PULSA AQUÍ PARA COMPRAR</b></a>\n\n"
            "✨ <i>Todo está listo. Escribe /list para ver tus prendas o /add para añadir nuevas.</i>"
        )
        send_telegram(token, chat_id, test_msg)

    elif cmd in ("/add", "/alerta", "/crear"):
        if len(parts) < 3:
            send_telegram(
                token, chat_id,
                "⚠️ <b>Formato incorrecto.</b>\n"
                "Usa: <code>/add &lt;tienda&gt; &lt;referencia o enlace&gt; &lt;talla&gt;</code>\n\n"
                "<i>Ejemplo:</i> <code>/add pullandbear 07563305 XS</code>\n"
                "<i>Ejemplo:</i> <code>/add zara 2731/240 S</code>"
            )
            return

        first_arg = parts[1]
        if first_arg.startswith("http"):
            detected_store = store_checker.detect_store(first_arg)
            ref_or_url = first_arg
            size = parts[2].upper()
        else:
            detected_store = store_checker.detect_store(first_arg)
            ref_or_url = parts[2]
            size = parts[3].upper() if len(parts) >= 4 else "XS"

        url = store_checker.build_search_or_product_url(detected_store, ref_or_url)
        
        # Check if already tracked by someone
        existing = None
        for a in alerts:
            if a.get("store") == detected_store and a.get("size") == size and (a.get("ref") == ref_or_url or a.get("url") == url):
                existing = a
                break

        if existing:
            if chat_id not in existing.get("chat_ids", []):
                existing.setdefault("chat_ids", []).append(chat_id)
                save_alerts(alerts)
            send_telegram(
                token, chat_id,
                f"✅ <b>¡Prenda suscrita con éxito!</b>\n\n"
                f"🏪 <b>Tienda:</b> {detected_store.upper()}\n"
                f"👕 <b>Prenda:</b> {existing.get('name', 'Prenda')}\n"
                f"📏 <b>Talla:</b> {size}\n\n"
                f"<i>Ya estaba en seguimiento. Te avisaré por aquí en cuanto haya restock.</i>"
            )
        else:
            new_id = max([a.get("id", 0) for a in alerts], default=0) + 1
            new_item = {
                "id": new_id,
                "store": detected_store,
                "name": f"Prenda {detected_store.capitalize()}",
                "url": url,
                "ref": ref_or_url,
                "size": size,
                "status": "Comprobando...",
                "price": "Consultando...",
                "chat_ids": [chat_id],
                "last_checked": None
            }
            alerts.append(new_item)
            save_alerts(alerts)

            send_telegram(
                token, chat_id,
                f"✅ <b>¡Alerta añadida con éxito!</b>\n\n"
                f"🏪 <b>Tienda:</b> {detected_store.upper()}\n"
                f"📏 <b>Talla:</b> {size}\n"
                f"🔗 <a href='{url}'>Enlace guardado</a>\n\n"
                f"<i>El bot comprobará el stock periódicamente cada minuto y te avisará en cuanto repongan.</i>"
            )
    else:
        send_telegram(
            token, chat_id,
            "❓ Comando no reconocido.\nEscribe <code>/help</code> para ver cómo añadir prendas de Zara, Bershka y Pull&Bear."
        )


def main():
    config = load_config()
    check_interval = max(30, config.get("check_interval_seconds", 60))

    print("=" * 65)
    print("      INDITEX RESTOCK ALERT BOT (ZARA, BERSHKA, PULL&BEAR)")
    print("=" * 65)
    print("  Soporte multi-usuario activo (Telegram)")
    print(f"  Ciclo de escaneo: Cada {check_interval} segundos (~1 minuto)")
    print("=" * 65)

    # Launch Telegram Listener Thread
    threading.Thread(target=telegram_listener_thread, args=(config,), daemon=True).start()

    driver = create_driver(config)

    try:
        while True:
            alerts = load_alerts()
            if not alerts:
                logger.info("No hay prendas en seguimiento en alerts.json. Esperando comandos...")
                time.sleep(15)
                continue

            cycle_start_time = time.time()
            logger.info(f"--- Iniciando ciclo de comprobación de {len(alerts)} prenda(s) ---")

            for item in alerts:
                item_id = item.get("id")
                store = item.get("store", "pullandbear")
                url = item.get("url")
                size = item.get("size", "XS")
                chat_ids = item.get("chat_ids", ["1997921776"])

                now_str = datetime.now().strftime("%H:%M:%S")

                try:
                    is_avail, price, name, status, final_url = store_checker.check_item_stock(driver, store, url, size)
                    
                    # Update item info
                    item["name"] = name
                    item["price"] = price
                    item["status"] = status
                    item["url"] = final_url
                    item["last_checked"] = now_str
                    save_alerts(alerts)

                    logger.info(f"[{now_str}] [{store.upper()}] {name} ({size}) -> {status} ({price}) | Suscriptores: {len(chat_ids)}")

                    # RESTOCK DETECTED
                    if is_avail:
                        last_sent = LAST_NOTIFIED.get(item_id, 0)
                        # Throttle notifications: at most once every 10 min per item
                        if time.time() - last_sent > 600:
                            LAST_NOTIFIED[item_id] = time.time()
                            logger.info(f"🎉 ¡¡¡RESTOCK DETECTADO EN {store.upper()}!!! {name} ({size})")

                            # Windows sound
                            if config.get("sound_alarm", True):
                                global ALARM_ACTIVE
                                ALARM_ACTIVE = True
                                threading.Thread(target=play_sound_alarm, daemon=True).start()

                            # Notify ALL subscribed users
                            tg = config.get("telegram", {})
                            token = tg.get("bot_token")
                            msg = (
                                f"🚨 <b>¡RESTOCK EN {store.upper()}!</b> 🚨\n\n"
                                f"<b>Prenda:</b> {name}\n"
                                f"<b>Talla:</b> {size} DISPONIBLE ✅\n"
                                f"<b>Precio:</b> {price}\n\n"
                                f"🛒 <a href='{final_url}'><b>PULSA AQUÍ PARA COMPRAR</b></a>\n"
                            )
                            for cid in chat_ids:
                                send_telegram(token, cid, msg)

                except Exception as e:
                    logger.warning(f"Error comprobando [{store}] {url}: {e}")

                # Small delay between items within the same cycle
                time.sleep(3)

            # Sleep remaining time until 60s
            elapsed = time.time() - cycle_start_time
            sleep_needed = max(5, check_interval - elapsed)
            logger.info(f"Ciclo completado en {elapsed:.1f}s. Próxima comprobación en {sleep_needed:.1f}s...")
            time.sleep(sleep_needed)

    except KeyboardInterrupt:
        logger.info("Bot detenido por el usuario.")
    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    main()
