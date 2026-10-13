"""
Pull&Bear Restock Bot - Web Service & 24/7 Background Runner
Compatible con Render, Koyeb, Hugging Face Spaces, Docker y VPS.
"""

import os
import sys
import time
import json
import logging
import threading
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

# Import bot routines
import bot

# Global state for dashboard
bot_state = {
    "status": "Iniciando...",
    "running": True,
    "last_check_time": None,
    "checks_count": 0,
    "target_size": "XS",
    "visibility": "Comprobando...",
    "is_available": False,
    "latency": 0.0,
    "product_name": "Cárdigan Dickies",
    "product_url": "https://www.pullandbear.com/es/cardigan-cremallera-dickies-l07563305?cS=712",
    "error_message": None,
    "history": []
}

app = FastAPI(title="Pull&Bear Restock Bot 24/7")

def background_monitor_worker():
    """Runs the continuous Chrome headless stock monitor in background."""
    config = bot.load_config()
    # Ensure headless is True when running as a web service
    config["headless"] = True
    config["sound_alarm"] = False
    config["windows_notification"] = False

    target_size = config.get("target_size", "XS").upper()
    check_interval = max(3, config.get("check_interval_seconds", 5))
    refresh_interval = config.get("refresh_page_interval_minutes", 15) * 60

    bot_state["target_size"] = target_size
    bot_state["product_url"] = config.get("product_url")
    bot_state["status"] = "Iniciando navegador Chrome..."

    driver = None
    try:
        driver = bot.create_driver(config)
        bot_state["status"] = "Conectando con Pull&Bear..."
        meta = bot.wait_for_page_and_extract_metadata(driver, config.get("product_url"))
        
        last_page_refresh = time.time()
        consecutive_errors = 0
        bot_state["status"] = "🟢 ACTIVO Y MONITORIZANDO 24/7"

        while bot_state["running"]:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            bot_state["checks_count"] += 1
            bot_state["last_check_time"] = now_str

            # Auto refresh page to keep Akamai cookies fresh
            if time.time() - last_page_refresh > refresh_interval:
                driver.get(config.get("product_url"))
                time.sleep(4)
                last_page_refresh = time.time()

            t0 = time.time()
            res = bot.query_product_stock_info(driver, meta, target_size)
            latency = time.time() - t0
            bot_state["latency"] = round(latency, 3)

            if not res or not res.get("success"):
                consecutive_errors += 1
                bot_state["error_message"] = res.get("error") if res else "No response"
                if consecutive_errors >= 3:
                    driver.get(config.get("product_url"))
                    time.sleep(5)
                    consecutive_errors = 0
                    last_page_refresh = time.time()
                time.sleep(check_interval)
                continue

            consecutive_errors = 0
            bot_state["error_message"] = None
            size_data = res.get("target")

            if size_data:
                vis = size_data.get("visibilityValue", "UNKNOWN")
                bot_state["visibility"] = vis
                bot_state["product_name"] = size_data.get("productName", "Cárdigan Dickies")
                is_buyable = size_data.get("isBuyable", False)

                # Keep a short log history
                entry = f"[{now_str}] Check #{bot_state['checks_count']}: {vis} ({latency:.2f}s)"
                bot_state["history"].insert(0, entry)
                if len(bot_state["history"]) > 25:
                    bot_state["history"].pop()

                # RESTOCK DETECTED
                if vis != "SOLD_OUT" or (is_buyable and vis in ("SHOW", "RUNNING_OUT")):
                    bot_state["is_available"] = True
                    bot_state["status"] = "🎉 ¡¡¡RESTOCK DETECTADO!!!"
                    
                    # 1. Trigger Telegram / Discord
                    bot.trigger_notifications(config, meta, size_data)

                    # 2. Auto add to cart
                    if config.get("auto_add_to_cart", True):
                        bot.execute_auto_cart(driver, meta, size_data)

                    # Keep checking but sleep longer
                    time.sleep(30)
            
            time.sleep(check_interval)

    except Exception as e:
        bot_state["status"] = f"❌ Error: {str(e)}"
        bot_state["error_message"] = str(e)
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


@app.on_event("startup")
def startup_event():
    # Start background worker thread
    t = threading.Thread(target=background_monitor_worker, daemon=True)
    t.start()


@app.get("/health")
def health():
    """Uptime health check endpoint."""
    return JSONResponse({
        "status": "healthy",
        "bot_status": bot_state["status"],
        "checks": bot_state["checks_count"],
        "last_check": bot_state["last_check_time"],
        "target_size": bot_state["target_size"],
        "visibility": bot_state["visibility"],
        "is_available": bot_state["is_available"],
        "latency_sec": bot_state["latency"]
    })


@app.get("/", response_class=HTMLResponse)
def dashboard():
    """Visual real-time status dashboard for mobile and PC."""
    history_html = "".join([f"<li>{h}</li>" for h in bot_state["history"][:10]])
    status_badge_color = "#27ae60" if "ACTIVO" in bot_state["status"] else "#e67e22" if "Iniciando" in bot_state["status"] else "#e74c3c"
    
    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Pull&Bear Restock Bot 24/7</title>
        <meta http-equiv="refresh" content="8">
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: #0f172a; color: #f8fafc; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #1e293b; border-radius: 16px; padding: 24px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
            h1 {{ font-size: 1.5rem; margin-bottom: 8px; color: #38bdf8; }}
            .subtitle {{ font-size: 0.9rem; color: #94a3b8; margin-bottom: 20px; }}
            .badge {{ display: inline-block; padding: 6px 14px; border-radius: 9999px; font-weight: bold; font-size: 0.85rem; background: {status_badge_color}; color: #fff; margin-bottom: 20px; }}
            .card {{ background: #0f172a; border-radius: 12px; padding: 16px; margin-bottom: 16px; border: 1px solid #334155; }}
            .item-title {{ font-size: 1.1rem; font-weight: bold; margin-bottom: 6px; }}
            .meta-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }}
            .meta-box {{ background: #1e293b; padding: 10px; border-radius: 8px; }}
            .meta-label {{ font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; }}
            .meta-val {{ font-size: 1rem; font-weight: bold; color: #f1f5f9; margin-top: 2px; }}
            .val-soldout {{ color: #ef4444; }}
            .val-available {{ color: #22c55e; }}
            .history-list {{ list-style: none; font-family: monospace; font-size: 0.8rem; color: #cbd5e1; max-height: 180px; overflow-y: auto; }}
            .history-list li {{ padding: 4px 0; border-bottom: 1px solid #1e293b; }}
            .btn {{ display: block; width: 100%; text-align: center; background: #2563eb; color: #fff; text-decoration: none; padding: 12px; border-radius: 8px; font-weight: bold; margin-top: 16px; transition: background 0.2s; }}
            .btn:hover {{ background: #1d4ed8; }}
            .footer {{ text-align: center; font-size: 0.75rem; color: #64748b; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Pull&Bear Restock Bot</h1>
            <div class="subtitle">Monitor 24/7 en la nube para Cárdigan Dickies</div>
            
            <div class="badge">{bot_state['status']}</div>
            
            <div class="card">
                <div class="item-title">{bot_state['product_name']}</div>
                <div style="font-size:0.85rem; color:#94a3b8;">Ref: 07563305 | Color: 712 Crudo</div>
                
                <div class="meta-grid">
                    <div class="meta-box">
                        <div class="meta-label">Talla</div>
                        <div class="meta-val">{bot_state['target_size']}</div>
                    </div>
                    <div class="meta-box">
                        <div class="meta-label">Estado Stock</div>
                        <div class="meta-val {'val-available' if bot_state['visibility'] != 'SOLD_OUT' else 'val-soldout'}">{bot_state['visibility']}</div>
                    </div>
                    <div class="meta-box">
                        <div class="meta-label">Comprobaciones</div>
                        <div class="meta-val">{bot_state['checks_count']}</div>
                    </div>
                    <div class="meta-box">
                        <div class="meta-label">Latencia API</div>
                        <div class="meta-val">{bot_state['latency']}s</div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <div style="font-size: 0.85rem; font-weight: bold; color: #94a3b8; margin-bottom: 8px;">HISTORIAL RECIENTE</div>
                <ul class="history-list">
                    {history_html if history_html else "<li>Esperando primeras lecturas...</li>"}
                </ul>
            </div>
            
            <a href="{bot_state['product_url']}" target="_blank" class="btn">Ver Prenda en Pull&Bear</a>
            
            <div class="footer">
                Actualizado automáticamente cada 8s • Último escaneo: {bot_state['last_check_time'] or 'Iniciando...'}
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("app:app", host="0.0.0.0", port=port, log_level="info")
