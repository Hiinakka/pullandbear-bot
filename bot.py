"""
=============================================================================
Universal Multi-Store Restock Bot
- Tiendas: Zara, Bershka, Pull&Bear, Stradivarius, Mango, H&M (HyM)
- Tolerancia inteligente a errores tipográficos (pulandbear, berhska, hym...)
- Flujo conversacional guiado con detección de tallas
- Consultas ultra-rápidas configurables (ej: cada 5s o 60s)
- Soporte multi-usuario completo por Telegram
=============================================================================
"""

import sys
import os
import re
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

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

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
USERS_PATH = os.path.join(BASE_DIR, "users.json")

ALARM_ACTIVE = False
LAST_NOTIFIED = {}  # item_id -> timestamp
USER_STATES = {}    # chat_id -> dict(state, store, ref_or_url, timestamp)


USERS_LOCK = threading.Lock()
ALERTS_LOCK = threading.Lock()


def register_user(chat_id, first_name="", username=""):
    """Registers or updates a user in users.json to ensure they receive broadcast updates."""
    if not chat_id:
        return
    with USERS_LOCK:
        users = {}
        if os.path.exists(USERS_PATH):
            try:
                with open(USERS_PATH, "r", encoding="utf-8") as f:
                    users = json.load(f)
            except Exception:
                users = {}

        cid_str = str(chat_id)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if cid_str not in users:
            users[cid_str] = {
                "chat_id": cid_str,
                "name": first_name or "Usuario",
                "username": username or "",
                "joined_at": now_str,
                "last_active": now_str
            }
            logger.info(f"👤 ¡Nuevo usuario registrado en users.json!: {first_name} (@{username}) | ID: {cid_str}")
        else:
            users[cid_str]["last_active"] = now_str
            if first_name:
                users[cid_str]["name"] = first_name
            if username:
                users[cid_str]["username"] = username

        try:
            with open(USERS_PATH, "w", encoding="utf-8") as f:
                json.dump(users, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"Error guardando users.json: {e}")


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


def send_telegram(token, chat_id, message, reply_markup=None):
    """Sends notification to a specific Telegram chat_id with optional inline keyboard."""
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload_dict = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
        if reply_markup:
            payload_dict["reply_markup"] = reply_markup
        payload = json.dumps(payload_dict).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                logger.info(f"Mensaje Telegram enviado con éxito a {chat_id}.")
    except Exception as e:
        logger.error(f"Error enviando Telegram a {chat_id}: {e}")


def answer_callback_query(token, callback_query_id, text=None, show_alert=False):
    """Answers a Telegram callback query to dismiss loading state or show toast."""
    try:
        url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
            payload["show_alert"] = show_alert
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            pass
    except Exception as e:
        logger.warning(f"Error respondiendo callback_query: {e}")


def edit_message_reply_markup(token, chat_id, message_id, reply_markup=None):
    """Edits the inline keyboard of an existing message."""
    try:
        url = f"https://api.telegram.org/bot{token}/editMessageReplyMarkup"
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "reply_markup": reply_markup or {"inline_keyboard": []}
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            pass
    except Exception as e:
        logger.warning(f"Error editando reply_markup: {e}")


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


def _load_alerts_unlocked():
    """Loads tracked items from alerts.json (must already hold ALERTS_LOCK)."""
    if os.path.exists(ALERTS_PATH):
        try:
            with open(ALERTS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                clean_data = []
                for item in data:
                    if "onetrust" in item.get("url", "").lower() or "consent" in item.get("name", "").lower():
                        continue
                    raw_cids = item.get("chat_ids", ["1997921776"])
                    item["chat_ids"] = [str(c) for c in raw_cids]
                    clean_data.append(item)
                return clean_data
        except Exception as e:
            logger.warning(f"Error leyendo alerts.json: {e}")
    return []


def _save_alerts_unlocked(alerts):
    """Saves tracked items to alerts.json (must already hold ALERTS_LOCK)."""
    try:
        with open(ALERTS_PATH, "w", encoding="utf-8") as f:
            json.dump(alerts, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error guardando alerts.json: {e}")


def load_alerts():
    """Loads tracked items from alerts.json thread-safely."""
    with ALERTS_LOCK:
        return _load_alerts_unlocked()


def save_alerts(alerts):
    """Saves tracked items to alerts.json thread-safely."""
    with ALERTS_LOCK:
        _save_alerts_unlocked(alerts)


def update_item_status(item_id, name, price, status, final_url, last_checked):
    """
    Safely updates an item's status in alerts.json.
    Crucial: If the item was deleted by the user while being checked,
    it will NOT be resurrected. Returns updated item dict or None.
    """
    with ALERTS_LOCK:
        alerts = _load_alerts_unlocked()
        target = None
        for item in alerts:
            if item.get("id") == item_id:
                target = item
                break

        if not target:
            logger.info(f"Prenda ID {item_id} no existe en alerts.json (borrada por el usuario). No se guardará.")
            return None

        target["name"] = name
        target["price"] = price
        target["status"] = status
        target["url"] = final_url
        target["last_checked"] = last_checked
        _save_alerts_unlocked(alerts)
        return target


def delete_user_alert(chat_id, target_item_id=None, user_index=None):
    """
    Thread-safely removes chat_id from target item's chat_ids.
    If no subscribers remain, completely removes the item from alerts.json.
    Returns (success: bool, deleted_item: dict or None, remaining_user_items_count: int).
    """
    with ALERTS_LOCK:
        alerts = _load_alerts_unlocked()
        cid_str = str(chat_id)
        user_items = [it for it in alerts if cid_str in [str(c) for c in it.get("chat_ids", [])]]

        target = None
        if target_item_id is not None:
            for it in user_items:
                if it.get("id") == target_item_id:
                    target = it
                    break
        elif user_index is not None:
            if 0 <= user_index < len(user_items):
                target = user_items[user_index]

        if not target:
            return False, None, len(user_items)

        # Remove chat_id from target item
        target["chat_ids"] = [str(c) for c in target.get("chat_ids", []) if str(c) != cid_str]

        # If no users are following this item anymore, purge it completely
        if not target["chat_ids"]:
            alerts = [it for it in alerts if it.get("id") != target.get("id")]

        _save_alerts_unlocked(alerts)

        remaining_count = len([it for it in alerts if cid_str in [str(c) for c in it.get("chat_ids", [])]])
        logger.info(f"🗑️ Prenda ID {target.get('id')} ({target.get('name')}) eliminada para usuario {cid_str}. Restantes: {remaining_count}")
        return True, target, remaining_count


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


def save_new_alert(*args, **kwargs):
    """Helper to register a new alert in alerts.json thread-safely."""
    if len(args) == 5 and isinstance(args[0], list):
        _, store, ref_or_url, size, chat_id = args
    elif len(args) == 4:
        store, ref_or_url, size, chat_id = args
    else:
        store = kwargs.get("store")
        ref_or_url = kwargs.get("ref_or_url")
        size = kwargs.get("size")
        chat_id = kwargs.get("chat_id")

    size = store_checker.normalize_size(size)
    url = store_checker.build_search_or_product_url(store, ref_or_url)
    cid_str = str(chat_id)

    with ALERTS_LOCK:
        alerts = _load_alerts_unlocked()

        # Check if item + size is already tracked
        for a in alerts:
            if a.get("store") == store and a.get("size") == size and (a.get("ref") == ref_or_url or a.get("url") == url):
                current_cids = [str(c) for c in a.get("chat_ids", [])]
                if cid_str not in current_cids:
                    current_cids.append(cid_str)
                    a["chat_ids"] = current_cids
                    _save_alerts_unlocked(alerts)
                return a, False

        new_id = max([a.get("id", 0) for a in alerts], default=0) + 1
        new_item = {
            "id": new_id,
            "store": store,
            "name": f"Prenda {store.capitalize()}",
            "url": url,
            "ref": ref_or_url,
            "size": size,
            "status": "Comprobando...",
            "price": "Consultando...",
            "chat_ids": [cid_str],
            "last_checked": None
        }
        alerts.append(new_item)
        _save_alerts_unlocked(alerts)
        return new_item, True


def telegram_listener_thread(config):
    """Listens for user commands via Telegram bot polling."""
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

                    # 1. Callback query from inline button (like the delete dropdown button)
                    cb_query = update.get("callback_query")
                    if cb_query:
                        from_u = cb_query.get("from", {})
                        cid = str(from_u.get("id", ""))
                        uname = from_u.get("first_name", "Usuario")
                        uhandle = from_u.get("username", "")
                        if cid:
                            register_user(cid, uname, uhandle)
                        handle_telegram_callback(token, cb_query)
                        continue

                    # 2. Regular message
                    msg = update.get("message", {})
                    chat_id = str(msg.get("chat", {}).get("id", ""))
                    user_name = msg.get("from", {}).get("first_name", "Usuario")
                    user_handle = msg.get("from", {}).get("username", "")
                    text = (msg.get("text") or "").strip()

                    if chat_id:
                        register_user(chat_id, user_name, user_handle)

                    if chat_id and text:
                        handle_telegram_message(token, chat_id, user_name, text)
        except Exception as e:
            time.sleep(3)
        time.sleep(1)


def handle_telegram_callback(token, cb):
    """Handles inline button clicks (e.g. deleting an alert directly from a restock notification)."""
    cb_id = cb.get("id")
    data = cb.get("data", "")
    from_user = cb.get("from", {})
    chat_id = str(from_user.get("id", ""))
    msg = cb.get("message", {})
    message_id = msg.get("message_id")

    if not chat_id:
        return

    if data == "none":
        answer_callback_query(token, cb_id)
        return

    if data == "cancel_del":
        USER_STATES.pop(chat_id, None)
        answer_callback_query(token, cb_id, text="❌ Borrado cancelado.")
        if message_id:
            updated_kb = {
                "inline_keyboard": [
                    [{"text": "❌ Borrado cancelado", "callback_data": "none"}]
                ]
            }
            edit_message_reply_markup(token, chat_id, message_id, updated_kb)
        send_telegram(token, chat_id, "❌ Operación de borrado cancelada.")
        return

    if data == "test_del":
        answer_callback_query(token, cb_id, text="🗑️ ¡Ejemplo de borrado completado!")
        updated_kb = {
            "inline_keyboard": [
                [{"text": "🛒 Enlace de ejemplo", "url": "https://www.pullandbear.com/es/cardigan-cremallera-dickies-l07563305?cS=712"}],
                [{"text": "✅ Alerta borrada (Prueba)", "callback_data": "none"}]
            ]
        }
        if message_id:
            edit_message_reply_markup(token, chat_id, message_id, updated_kb)
        send_telegram(token, chat_id, "🗑️ <i>(Prueba)</i> Has pulsado el botón para borrar esta alerta.")
        return

    if data.startswith("del_"):
        try:
            item_id = int(data.replace("del_", ""))
        except ValueError:
            answer_callback_query(token, cb_id, text="⚠️ ID no reconocido.")
            return

        success, target_item, remaining = delete_user_alert(chat_id, target_item_id=item_id)
        USER_STATES.pop(chat_id, None)

        if success and target_item:
            item_name = target_item.get("name", "Prenda")
            item_size = target_item.get("size", "")
            answer_callback_query(token, cb_id, text=f"🗑️ Dejaste de seguir: {item_name} ({item_size})")

            # Update inline keyboard in original notification message
            updated_kb = {
                "inline_keyboard": [
                    [{"text": "🛒 Ver Prenda en Tienda", "url": target_item.get("url", "#")}],
                    [{"text": "✅ Borrada de tu lista", "callback_data": "none"}]
                ]
            }
            if message_id:
                edit_message_reply_markup(token, chat_id, message_id, updated_kb)
            send_telegram(
                token, chat_id,
                f"🗑️ Has eliminado de tu lista: <b>{item_name}</b> (Talla {item_size}).\n"
                f"Ya no recibirás más notificaciones de este artículo. (Prendas activas: {remaining})"
            )
        else:
            answer_callback_query(token, cb_id, text="ℹ️ Esta prenda ya no estaba en tu lista o ya fue borrada.")
            updated_kb = {
                "inline_keyboard": [
                    [{"text": "ℹ️ Ya no está en tu lista", "callback_data": "none"}]
                ]
            }
            if message_id:
                edit_message_reply_markup(token, chat_id, message_id, updated_kb)
        return


def handle_telegram_message(token, chat_id, user_name, text):
    """Conversational command handler with typo tolerance and interactive prompting."""
    global USER_STATES
    clean_text = text.strip()
    lower_text = clean_text.lower()
    alerts = load_alerts()

    # Cancel command
    if lower_text in ("/cancel", "/cancelar", "cancelar", "cancel", "salir"):
        if chat_id in USER_STATES:
            USER_STATES.pop(chat_id, None)
            send_telegram(token, chat_id, "❌ Operación cancelada. Escribe <code>/help</code> para ver opciones.")
        else:
            send_telegram(token, chat_id, "ℹ️ No había ninguna operación activa que cancelar.")
        return

    # Check if user is in an active conversational state
    user_state = USER_STATES.get(chat_id)
    if user_state:
        # Timeout states older than 15 minutes
        if time.time() - user_state.get("timestamp", 0) > 900:
            USER_STATES.pop(chat_id, None)
            user_state = None

    if user_state:
        state_type = user_state.get("state")
        
        # State: waiting for size
        if state_type == "WAITING_FOR_SIZE":
            chosen_size = store_checker.normalize_size(clean_text)
            store = user_state["store"]
            ref_or_url = user_state["ref_or_url"]
            USER_STATES.pop(chat_id, None)

            item, is_new = save_new_alert(store, ref_or_url, chosen_size, chat_id)
            send_telegram(
                token, chat_id,
                f"✅ <b>¡Alerta guardada con éxito!</b>\n\n"
                f"🏪 <b>Tienda:</b> {store.upper()}\n"
                f"👕 <b>Referencia:</b> <code>{ref_or_url}</code>\n"
                f"📏 <b>Talla:</b> <b>{chosen_size}</b>\n\n"
                f"🔔 <i>Te enviaré un aviso con el enlace directo en cuanto haya stock disponible.</i>"
            )
            return

        # State: waiting for delete index
        if state_type == "WAITING_FOR_DELETE":
            USER_STATES.pop(chat_id, None)
            num_match = re.search(r'\d+', clean_text)
            if num_match:
                idx = int(num_match.group()) - 1
                success, target_item, remaining = delete_user_alert(chat_id, user_index=idx)
                if success and target_item:
                    send_telegram(
                        token, chat_id,
                        f"🗑️ Has dejado de seguir: <b>{target_item.get('name', 'Prenda')}</b> (Talla {target_item.get('size')}).\n"
                        f"Te quedan {remaining} prendas en seguimiento."
                    )
                    return
                else:
                    send_telegram(token, chat_id, "⚠️ Número no válido o fuera de rango. Consulta tu lista con <code>/list</code>.")
                    return
            send_telegram(token, chat_id, "⚠️ No reconocí ningún número. Operación cancelada. Consulta tu lista con <code>/list</code>.")
            return

    # Standard Commands
    cmd_token = clean_text.split()[0].lower() if clean_text.split() else ""

    if cmd_token in ("/start", "/help", "/ayuda", "ayuda", "help"):
        help_msg = (
            f"👋 <b>¡Hola {user_name}! Soy tu Tracker de Ropa Multi-Tienda.</b>\n\n"
            "🏪 <b>Tiendas soportadas:</b>\n"
            "Zara, Bershka, Pull&Bear, Stradivarius, Mango y H&M (HyM).\n\n"
            "👗 <b>¿Cómo añadir una alerta?</b>\n"
            "Tienes 3 formas muy sencillas:\n\n"
            "1️⃣ <b>Escribiendo tienda, referencia y talla:</b>\n"
            "• <code>pulandbear 07563305 XS</code>\n"
            "• <code>zara 2731/240 S</code>\n"
            "• <code>bershka 0123/456 M</code>\n"
            "• <code>stradivarius 0453/642 36</code>\n"
            "• <code>mango 37045842 M</code>\n"
            "• <code>hym 1324742001 S</code>\n"
            "<i>(¡Corrijo automáticamente faltas como 'pulandbear', 'berhska', 'hym' o 'stradi'!)</i>\n\n"
            "2️⃣ <b>Pegando directamente el enlace de la prenda:</b>\n"
            "<code>https://www.zara.com/es/es/... S</code>\n\n"
            "3️⃣ <b>O déjate guiar:</b>\n"
            "Escribe solo la referencia o el enlace, y te preguntaré qué talla quieres.\n\n"
            "📋 <b>Otros comandos útiles:</b>\n"
            "• <code>/list</code> : Ver tus prendas en seguimiento y su estado.\n"
            "• <code>/del &lt;número&gt;</code> : Dejar de seguir una prenda.\n"
            "• <code>/prueba</code> : Enviar una alerta de prueba para verificar tu móvil."
        )
        send_telegram(token, chat_id, help_msg)
        return

    if cmd_token in ("/prueba", "/test", "prueba", "test"):
        test_msg = (
            "🔔 <b>¡PRUEBA DE FUNCIONAMIENTO EXITOSA!</b> 🔔\n\n"
            "🟢 <b>Estado del bot:</b> 100% Operativo y Conectado\n"
            "🏪 <b>Tiendas soportadas:</b> Pull&Bear, Zara, Bershka, Stradivarius, Mango y H&M\n"
            "⏱️ <b>Frecuencia de escaneo:</b> Consultas ultra-rápidas activas\n"
            f"📱 <b>Tu ID de usuario:</b> <code>{chat_id}</code>\n\n"
            "🚨 <i>Ejemplo de cómo te llegará una alerta real de compra:</i>\n"
            "Prenda: <b>Cárdigan cremallera Dickies</b>\n"
            "Talla: <b>XS DISPONIBLE ✅</b>\n"
            "Precio: <b>45.99 €</b>\n\n"
            "💡 <i>Pulsa los botones interactivos de abajo para comprar o borrar la prenda en 1 toque:</i>"
        )
        test_keyboard = {
            "inline_keyboard": [
                [
                    {"text": "🛒 Comprar Prenda", "url": "https://www.pullandbear.com/es/cardigan-cremallera-dickies-l07563305?cS=712"}
                ],
                [
                    {"text": "🗑️ Borrar este artículo de mi lista", "callback_data": "test_del"}
                ]
            ]
        }
        send_telegram(token, chat_id, test_msg, reply_markup=test_keyboard)
        return

    if cmd_token in ("/list", "/status", "lista", "status"):
        current_alerts = load_alerts()
        user_items = [item for item in current_alerts if str(chat_id) in [str(c) for c in item.get("chat_ids", [])]]
        if not user_items:
            send_telegram(token, chat_id, "ℹ️ No tienes ninguna prenda en seguimiento todavía.\n\nPuedes añadir una escribiendo:\n<code>pulandbear 07563305 XS</code>")
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
                f"   🔗 <a href='{item.get('url')}'>Ver en Tienda</a>\n"
            )
        lines.append("<i>Para borrar una prenda usa <code>/del</code> o escribe <code>/del &lt;número&gt;</code></i>")
        send_telegram(token, chat_id, "\n".join(lines))
        return

    if cmd_token in ("/del", "/delete", "/borrar", "/eliminar"):
        current_alerts = load_alerts()
        user_items = [item for item in current_alerts if str(chat_id) in [str(c) for c in item.get("chat_ids", [])]]
        if not user_items:
            send_telegram(token, chat_id, "ℹ️ No tienes ninguna prenda en seguimiento para borrar.")
            return

        parts = clean_text.split()
        if len(parts) >= 2 and parts[1].isdigit():
            idx = int(parts[1]) - 1
            success, target_item, remaining = delete_user_alert(chat_id, user_index=idx)
            if success and target_item:
                send_telegram(
                    token, chat_id,
                    f"🗑️ Has dejado de seguir: <b>{target_item.get('name', 'Prenda')}</b> (Talla {target_item.get('size')}).\n"
                    f"Te quedan {remaining} prendas en seguimiento."
                )
                return
            else:
                send_telegram(token, chat_id, f"⚠️ Número no válido. Tienes {len(user_items)} prendas en tu lista (elige entre 1 y {len(user_items)}).")
                return

        # If no number specified, show list with 1-tap delete buttons + prompt
        USER_STATES[chat_id] = {"state": "WAITING_FOR_DELETE", "timestamp": time.time()}
        list_lines = ["🗑️ <b>¿Qué prenda quieres eliminar?</b>\n"]
        buttons = []
        for idx, item in enumerate(user_items, start=1):
            s_name = item.get("store", "").upper()
            i_name = item.get("name", "Prenda")
            i_size = item.get("size", "")
            list_lines.append(f"<b>{idx}.</b> [{s_name}] {i_name} (Talla {i_size})")

            short_name = (i_name[:20] + "…") if len(i_name) > 20 else i_name
            btn_text = f"🗑️ {idx}. {short_name} ({i_size})"
            buttons.append([{"text": btn_text, "callback_data": f"del_{item.get('id')}"}])

        buttons.append([{"text": "❌ Cancelar", "callback_data": "cancel_del"}])
        list_lines.append("\n💡 <i>Toca un botón de abajo o responde con el número (Ej: 1) o escribe /cancelar.</i>")

        send_telegram(token, chat_id, "\n".join(list_lines), reply_markup={"inline_keyboard": buttons})
        return

    # Intelligent Input Parsing (handles /add or direct text like 'pulandbear 07563305 XS')
    processed_text = re.sub(r'pull\s*(&|and|y)\s*bear', 'pullandbear', clean_text, flags=re.IGNORECASE)
    words = processed_text.split()
    if words and words[0].lower() in ("/add", "/alerta", "/crear", "add"):
        words = words[1:]

    if not words:
        send_telegram(
            token, chat_id,
            "👗 <b>Añadir nueva prenda</b>\n\n"
            "Dime la tienda, referencia y talla:\n"
            "<i>Ejemplo:</i> <code>pulandbear 07563305 XS</code>\n"
            "<i>O pega el enlace:</i> <code>https://www.zara.com/es/es/... S</code>"
        )
        return

    # Case A: URL included
    url_found = None
    remaining_words = []
    for w in words:
        if w.startswith("http://") or w.startswith("https://"):
            url_found = w
        else:
            remaining_words.append(w)

    if url_found:
        detected_store = store_checker.normalize_store(url_found) or "zara"
        if remaining_words:
            size = store_checker.normalize_size(remaining_words[0])
            item, is_new = save_new_alert(detected_store, url_found, size, chat_id)
            send_telegram(
                token, chat_id,
                f"✅ <b>¡Alerta guardada con éxito!</b>\n\n"
                f"🏪 <b>Tienda:</b> {detected_store.upper()}\n"
                f"📏 <b>Talla:</b> <b>{size}</b>\n"
                f"🔗 <a href='{url_found}'>Enlace guardado</a>\n\n"
                f"🔔 <i>Te avisaré en cuanto haya stock disponible.</i>"
            )
        else:
            # Need size!
            USER_STATES[chat_id] = {
                "state": "WAITING_FOR_SIZE",
                "store": detected_store,
                "ref_or_url": url_found,
                "timestamp": time.time()
            }
            send_telegram(
                token, chat_id,
                f"👗 <b>He reconocido el enlace de {detected_store.upper()}</b>\n\n"
                "¿Qué talla quieres que vigile?\n"
                "<i>Responde escribiendo tu talla (Ej: XS, S, M, L, XL, 38...)</i>"
            )
        return

    # Case B: Store + Reference (+ Optional Size)
    potential_store = store_checker.normalize_store(words[0])
    if potential_store:
        rest = words[1:]
        if len(rest) >= 2:
            ref = rest[0]
            size = store_checker.normalize_size(rest[1])
            item, is_new = save_new_alert(potential_store, ref, size, chat_id)
            send_telegram(
                token, chat_id,
                f"✅ <b>¡Alerta guardada con éxito!</b>\n\n"
                f"🏪 <b>Tienda:</b> {potential_store.upper()}\n"
                f"👕 <b>Referencia:</b> <code>{ref}</code>\n"
                f"📏 <b>Talla:</b> <b>{size}</b>\n\n"
                f"🔔 <i>Comprobando stock cada minuto. Te avisaré al momento.</i>"
            )
            return
        elif len(rest) == 1:
            ref = rest[0]
            # Need size!
            USER_STATES[chat_id] = {
                "state": "WAITING_FOR_SIZE",
                "store": potential_store,
                "ref_or_url": ref,
                "timestamp": time.time()
            }
            send_telegram(
                token, chat_id,
                f"👗 <b>Prenda detectada en {potential_store.upper()}</b> (Ref: <code>{ref}</code>)\n\n"
                "¿Qué talla estás buscando?\n"
                "<i>Responde a este mensaje con tu talla (Ej: XS, S, M, L, XL, 38...)</i>"
            )
            return

    # Unrecognized message fallback
    send_telegram(
        token, chat_id,
        "❓ No he entendido ese mensaje.\n\n"
        "Puedes añadir una prenda escribiendo:\n"
        "<code>pulandbear 07563305 XS</code>\n"
        "o escribe <code>/help</code> para ver todos los comandos."
    )


def main():
    config = load_config()
    check_interval = max(3, config.get("check_interval_seconds", 5))

    print("=" * 65)
    print("  UNIVERSAL RESTOCK BOT (ZARA, BERSHKA, P&B, STRADI, MANGO, H&M)")
    print("=" * 65)
    print("  Tolerancia a errores tipográficos: Activa")
    print("  Flujo guiado interactivo: Activo")
    print(f"  Ciclo de escaneo: Cada {check_interval} segundos")
    print("=" * 65)

    threading.Thread(target=telegram_listener_thread, args=(config,), daemon=True).start()
    driver = create_driver(config)

    try:
        while True:
            alerts = load_alerts()
            if not alerts:
                logger.info("No hay prendas en seguimiento en alerts.json. Esperando comandos...")
                time.sleep(10)
                continue

            cycle_start_time = time.time()
            logger.info(f"--- Iniciando ciclo de comprobación ({len(alerts)} prendas) ---")

            for item in alerts:
                item_id = item.get("id")
                store = item.get("store", "pullandbear")
                url = item.get("url")
                size = item.get("size", "XS")
                chat_ids = item.get("chat_ids", ["1997921776"])

                now_str = datetime.now().strftime("%H:%M:%S")

                try:
                    is_avail, price, name, status, final_url = store_checker.check_item_stock(driver, store, url, size)

                    # Update status thread-safely in alerts.json
                    # Crucial: update_item_status returns None if item was deleted by user during check
                    updated_item = update_item_status(item_id, name, price, status, final_url, now_str)
                    if not updated_item:
                        logger.info(f"Prenda ID {item_id} fue eliminada durante la comprobación. No se notificará ni se restaurará.")
                        continue

                    chat_ids = updated_item.get("chat_ids", [])
                    if not chat_ids:
                        continue

                    logger.info(f"[{now_str}] [{store.upper()}] {name} ({size}) -> {status} ({price}) | Usuarios: {len(chat_ids)}")

                    # RESTOCK DETECTED (Strict check to prevent false positives)
                    if is_avail and status not in ("SOLD_OUT", "OUT_OF_STOCK", "UNKNOWN") and "onetrust" not in str(final_url).lower():
                        last_sent = LAST_NOTIFIED.get(item_id, 0)
                        # Throttle notifications: at most once every 10 min per available item
                        if time.time() - last_sent > 600:
                            LAST_NOTIFIED[item_id] = time.time()
                            logger.info(f"🎉 ¡¡¡RESTOCK DETECTADO EN {store.upper()}!!! {name} ({size})")

                            if config.get("sound_alarm", True):
                                global ALARM_ACTIVE
                                ALARM_ACTIVE = True
                                threading.Thread(target=play_sound_alarm, daemon=True).start()

                            tg = config.get("telegram", {})
                            token = tg.get("bot_token")
                            msg = (
                                f"🚨 <b>¡RESTOCK EN {store.upper()}!</b> 🚨\n\n"
                                f"<b>Prenda:</b> {name}\n"
                                f"<b>Talla:</b> {size} DISPONIBLE ✅\n"
                                f"<b>Precio:</b> {price}\n"
                            )
                            keyboard = {
                                "inline_keyboard": [
                                    [
                                        {"text": "🛒 Comprar Prenda", "url": final_url}
                                    ],
                                    [
                                        {"text": "🗑️ Borrar este artículo de mi lista", "callback_data": f"del_{item_id}"}
                                    ]
                                ]
                            }
                            for cid in chat_ids:
                                send_telegram(token, cid, msg, reply_markup=keyboard)

                except Exception as e:
                    logger.warning(f"Error comprobando [{store}] {url}: {e}")

                if len(alerts) > 1:
                    time.sleep(1)

            elapsed = time.time() - cycle_start_time
            sleep_needed = max(1, check_interval - elapsed)
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
