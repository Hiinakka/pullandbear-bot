"""
Asistente interactivo de configuracion para Pull&Bear Restock Bot.
"""

import sys
import os
import json
import urllib.request

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    print("\n✅ Configuracion guardada correctamente en config.json\n")

def test_telegram(token, chat_id):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = json.dumps({
            "chat_id": chat_id,
            "text": "🎉 <b>¡Enhorabuena!</b>\nTu bot de Pull&Bear esta vinculado correctamente con tu Telegram.\nRecibiras una notificacion aqui en cuanto se reponga la talla XS.",
            "parse_mode": "HTML"
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                print("   ✅ ¡Mensaje de prueba enviado con exito! Revisa tu Telegram.")
                return True
    except Exception as e:
        print(f"   ❌ Error al enviar mensaje a Telegram: {e}")
        return False

def main():
    print("=" * 65)
    print("      CONFIGURADOR GUIADO - PULL&BEAR RESTOCK BOT")
    print("=" * 65)
    
    cfg = load_config()
    
    print("\n[1/4] NOTIFICACIONES A TU MOVIL POR TELEGRAM")
    print("-----------------------------------------------------------------")
    print("Si tienes un bot de Telegram, recibiras avisos sonoros 24/7.")
    print("Si no lo tienes, puedes crearlo en 1 minuto con @BotFather en Telegram.")
    
    use_tg = input("\n¿Deseas activar avisos a Telegram? (s/n) [actual: {}]: ".format('s' if cfg.get('telegram', {}).get('enabled') else 'n')).strip().lower()
    if use_tg in ('s', 'si', 'y', 'yes'):
        curr_token = cfg.get("telegram", {}).get("bot_token", "")
        token = input(f"Introduce el Token de tu bot (actual: {curr_token}): ").strip()
        if not token:
            token = curr_token
            
        curr_chat = cfg.get("telegram", {}).get("chat_id", "")
        chat_id = input(f"Introduce tu Chat ID de Telegram (actual: {curr_chat}): ").strip()
        if not chat_id:
            chat_id = curr_chat
            
        cfg["telegram"] = {
            "enabled": True,
            "bot_token": token,
            "chat_id": chat_id
        }
        
        print("\nProbando conexion con Telegram...")
        test_telegram(token, chat_id)
    else:
        if "telegram" not in cfg:
            cfg["telegram"] = {}
        cfg["telegram"]["enabled"] = False
        print("Telegram desactivado.")

    print("\n[2/4] MODO DE VISUALIZACION")
    print("-----------------------------------------------------------------")
    print("s = Modo silencioso/segundo plano (Headless): no muestra ventana.")
    print("n = Modo visual: abre una ventana de Chrome para que veas la web.")
    curr_head = 's' if cfg.get("headless", False) else 'n'
    head_in = input(f"¿Quieres ejecutar Chrome en segundo plano sin ventana? (s/n) [actual: {curr_head}]: ").strip().lower()
    if head_in in ('s', 'si', 'y', 'yes'):
        cfg["headless"] = True
    elif head_in in ('n', 'no'):
        cfg["headless"] = False

    print("\n[3/4] INTERVALO DE ESCANEO")
    print("-----------------------------------------------------------------")
    print("Frecuencia de comprobacion en segundos (Recomendado: 5)")
    curr_sec = cfg.get("check_interval_seconds", 5)
    sec_in = input(f"Segundos entre cada comprobacion [actual: {curr_sec}]: ").strip()
    if sec_in.isdigit():
        cfg["check_interval_seconds"] = max(2, int(sec_in))

    print("\n[4/4] AUTO-COMPRA / AUTO-CESTA")
    print("-----------------------------------------------------------------")
    curr_cart = 's' if cfg.get("auto_add_to_cart", True) else 'n'
    cart_in = input(f"¿Anadir automaticamente la talla XS a la cesta al detectar stock? (s/n) [actual: {curr_cart}]: ").strip().lower()
    if cart_in in ('s', 'si', 'y', 'yes', ''):
        cfg["auto_add_to_cart"] = True
    elif cart_in in ('n', 'no'):
        cfg["auto_add_to_cart"] = False

    # Defaults ensure all keys exist
    cfg.setdefault("product_url", "https://www.pullandbear.com/es/cardigan-cremallera-dickies-l07563305?cS=712")
    cfg.setdefault("target_size", "XS")
    cfg.setdefault("refresh_page_interval_minutes", 15)
    cfg.setdefault("user_data_dir", "./chrome_profile")
    cfg.setdefault("auto_open_checkout", True)
    cfg.setdefault("sound_alarm", True)
    cfg.setdefault("windows_notification", True)

    save_config(cfg)
    print("¡Todo listo! Ya puedes iniciar el bot con run_bot.bat o en tu servidor.")

if __name__ == "__main__":
    main()
