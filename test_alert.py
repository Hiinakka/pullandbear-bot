"""
Script de prueba de alertas para Pull&Bear Restock Bot.
Permite verificar el sonido, ventana emergente, Telegram y Discord antes de poner el bot en marcha.
"""

import sys
import os
import json
import urllib.request

def load_config():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def test_telegram(token, chat_id):
    if not token or not chat_id or token == "TU_BOT_TOKEN_AQUI":
        print("❌ Telegram no configurado (Token o Chat ID vacios).")
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = json.dumps({
            "chat_id": chat_id,
            "text": "✅ <b>¡Prueba de Pull&Bear Bot Exitosa!</b>\nTu teléfono está listo para recibir alertas de restock.",
            "parse_mode": "HTML"
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                print("✅ ¡Mensaje de prueba de Telegram enviado con éxito a tu móvil!")
                return True
    except Exception as e:
        print(f"❌ Error al conectar con Telegram: {e}")
        return False

def test_discord(webhook_url):
    if not webhook_url or webhook_url == "TU_DISCORD_WEBHOOK_AQUI":
        print("❌ Discord no configurado.")
        return False
    try:
        payload = json.dumps({"content": "✅ **Prueba de Pull&Bear Bot Exitosa**: Canal listo para alertas."}).encode("utf-8")
        req = urllib.request.Request(webhook_url, data=payload, headers={"Content-Type": "application/json", "User-Agent": "PullBearBot"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status in (200, 204):
                print("✅ ¡Mensaje de prueba de Discord enviado con éxito!")
                return True
    except Exception as e:
        print(f"❌ Error al conectar con Discord: {e}")
        return False

def test_local_alerts():
    print("\n🔊 Probando sonido en altavoces...")
    try:
        import winsound
        winsound.Beep(1200, 300)
        winsound.Beep(1600, 300)
        print("✅ Sonido reproducido correctamente.")
    except Exception as e:
        print(f"ℹ️ Sonido local no disponible: {e}")

    print("\n🪟 Probando ventana emergente en pantalla...")
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, "¡La prueba de notificación en pantalla funciona correctamente!", "Pull&Bear Bot - Test", 0x40)
        print("✅ Ventana emergente mostrada.")
    except Exception as e:
        print(f"ℹ️ Ventana emergente no disponible: {e}")

def main():
    print("=" * 60)
    print("       TEST DE NOTIFICACIONES - PULL&BEAR BOT")
    print("=" * 60)
    config = load_config()

    tg = config.get("telegram", {})
    dc = config.get("discord", {})

    print(f"\n1. Comprobando configuración de Telegram (Activo: {tg.get('enabled')})...")
    test_telegram(tg.get("bot_token"), tg.get("chat_id"))

    print(f"\n2. Comprobando configuración de Discord (Activo: {dc.get('enabled')})...")
    test_discord(dc.get("webhook_url"))

    if sys.platform == "win32":
        test_local_alerts()

    print("\n" + "=" * 60)
    print("Prueba finalizada.")
    print("=" * 60)

if __name__ == "__main__":
    main()
