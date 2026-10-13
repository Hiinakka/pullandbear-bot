"""
Helper script to send bot update notifications to Telegram.
"""

import sys
import json
import urllib.request
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

def send_update_message(text):
    if not os.path.exists(CONFIG_PATH):
        print("config.json not found")
        return
    
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        conf = json.load(f)
    
    token = conf.get("telegram", {}).get("bot_token")
    chat_id = conf.get("telegram", {}).get("chat_id")
    
    if not token or not chat_id:
        print("Token or Chat ID not configured")
        return
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                print("Mensaje de actualización enviado con éxito a Telegram.")
    except Exception as e:
        print(f"Error enviando mensaje: {e}")

if __name__ == "__main__":
    msg = sys.argv[1] if len(sys.argv) > 1 else "🚀 Actualización aplicada con éxito."
    send_update_message(msg)
