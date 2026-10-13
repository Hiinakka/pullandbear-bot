"""
Broadcast update notifications to ALL users who have ever interacted with the bot.
"""

import sys
import json
import urllib.request
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
USERS_PATH = os.path.join(BASE_DIR, "users.json")
ALERTS_PATH = os.path.join(BASE_DIR, "alerts.json")


def get_all_target_chat_ids():
    """Collects unique chat IDs across users.json, alerts.json, and config.json."""
    chat_ids = set()

    # 1. From config.json (admin)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                conf = json.load(f)
                admin_id = conf.get("telegram", {}).get("chat_id")
                if admin_id:
                    chat_ids.add(str(admin_id))
        except Exception:
            pass

    # 2. From users.json (all users who ever started or talked to the bot)
    if os.path.exists(USERS_PATH):
        try:
            with open(USERS_PATH, "r", encoding="utf-8") as f:
                users = json.load(f)
                for cid in users.keys():
                    chat_ids.add(str(cid))
        except Exception:
            pass

    # 3. From alerts.json (all subscribers)
    if os.path.exists(ALERTS_PATH):
        try:
            with open(ALERTS_PATH, "r", encoding="utf-8") as f:
                alerts = json.load(f)
                for item in alerts:
                    for cid in item.get("chat_ids", []):
                        chat_ids.add(str(cid))
        except Exception:
            pass

    return list(chat_ids)


def broadcast_update(message_html):
    """Sends the update notification to all registered users."""
    if not os.path.exists(CONFIG_PATH):
        print("Error: config.json not found")
        return

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        conf = json.load(f)

    token = conf.get("telegram", {}).get("bot_token")
    if not token:
        print("Error: bot_token no configurado en config.json")
        return

    recipients = get_all_target_chat_ids()
    print(f"Enviando mensaje a {len(recipients)} usuario(s): {recipients}")

    success_count = 0
    for chat_id in recipients:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = json.dumps({
            "chat_id": chat_id,
            "text": message_html,
            "parse_mode": "HTML"
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    print(f"[OK] Enviado con exito a chat_id: {chat_id}")
                    success_count += 1
        except Exception as e:
            print(f"[ERROR] Error enviando a {chat_id}: {e}")

    print(f"Transmision completada: {success_count}/{len(recipients)} mensajes enviados.")


if __name__ == "__main__":
    default_msg = (
        "🚀 <b>¡ACTUALIZACIÓN DEL BOT APLICADA!</b> 🚀\n\n"
        "✨ <b>Novedades de esta versión:</b>\n"
        "• 🏪 <b>Nuevas tiendas añadidas:</b> Stradivarius, Mango y H&M (HyM).\n"
        "• ⏱️ <b>Escaneo cada 5 segundos:</b> Comprobaciones ultra-rápidas para cazar stock al instante.\n"
        "• 🛡️ <b>Falso restock corregido:</b> Solucionado el bug de <code>isBuyable</code> de Inditex; nunca más te avisará si está en <code>SOLD_OUT</code>.\n"
        "• 🎨 <b>Filtro por color exacto:</b> Ahora detecta la variante de color exacta del enlace.\n\n"
        "👗 <b>Prueba a añadir prendas de las nuevas tiendas:</b>\n"
        "• <code>stradivarius 0453/642 36</code>\n"
        "• <code>mango 37045842 M</code>\n"
        "• <code>hym 1324742001 S</code>\n\n"
        "Escribe <code>/list</code> para ver tus alertas activas o <code>/help</code> para ver todos los comandos."
    )
    msg = sys.argv[1] if len(sys.argv) > 1 else default_msg
    broadcast_update(msg)
