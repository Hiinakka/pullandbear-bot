"""
Inditex Multi-Store Restock Bot (Zara, Bershka, Pull&Bear)
Dashboard Web & 24/7 Runner
"""

import os
import sys
import time
import json
import logging
import threading
from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

import bot

app = FastAPI(title="Inditex Restock Bot 24/7")

@app.on_event("startup")
def startup_event():
    # Run the main bot loop in background
    t = threading.Thread(target=bot.main, daemon=True)
    t.start()


@app.get("/health")
def health():
    """Uptime health check endpoint for UptimeRobot / cron-job.org."""
    alerts = bot.load_alerts()
    return JSONResponse({
        "status": "healthy",
        "active_alerts_count": len(alerts),
        "items": alerts
    })


@app.get("/", response_class=HTMLResponse)
def dashboard():
    """Multi-Store live dashboard for mobile and PC."""
    alerts = bot.load_alerts()
    
    items_html = ""
    for idx, item in enumerate(alerts, start=1):
        store = item.get("store", "tienda").upper()
        name = item.get("name", "Prenda")
        size = item.get("size", "XS")
        status = item.get("status", "Comprobando...")
        price = item.get("price", "")
        url = item.get("url", "#")
        last_checked = item.get("last_checked") or "Pendiente"
        
        is_avail = status not in ("SOLD_OUT", "Comprobando...", "UNKNOWN")
        badge_color = "#22c55e" if is_avail else "#ef4444"
        badge_text = "DISPONIBLE ✅" if is_avail else "AGOTADO ❌"
        
        # Store tag color
        store_color = "#e11d48" if "ZARA" in store else "#0284c7" if "PULL" in store else "#d97706"
        
        items_html += f"""
        <div class="card">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <span class="store-tag" style="background:{store_color};">{store}</span>
                <span class="badge" style="background:{badge_color};">{badge_text}</span>
            </div>
            <div class="item-title">{name}</div>
            <div class="meta-grid">
                <div class="meta-box">
                    <div class="meta-label">Talla</div>
                    <div class="meta-val">{size}</div>
                </div>
                <div class="meta-box">
                    <div class="meta-label">Precio</div>
                    <div class="meta-val">{price or 'Consultar'}</div>
                </div>
            </div>
            <div style="font-size:0.75rem; color:#94a3b8; margin-top:8px;">
                Última comprobación: {last_checked}
            </div>
            <a href="{url}" target="_blank" class="btn-small">Ver en Tienda</a>
        </div>
        """

    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Inditex Restock Bot (Zara, Bershka, Pull&Bear)</title>
        <meta http-equiv="refresh" content="10">
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; }}
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 20px; }}
            .container {{ max-width: 650px; margin: 0 auto; background: #1e293b; border-radius: 16px; padding: 24px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
            h1 {{ font-size: 1.5rem; color: #38bdf8; margin-bottom: 6px; }}
            .subtitle {{ font-size: 0.85rem; color: #94a3b8; margin-bottom: 20px; }}
            .card {{ background: #0f172a; border-radius: 12px; padding: 16px; margin-bottom: 14px; border: 1px solid #334155; }}
            .store-tag {{ padding: 3px 8px; border-radius: 6px; font-size: 0.75rem; font-weight: bold; text-transform: uppercase; }}
            .badge {{ padding: 4px 10px; border-radius: 9999px; font-weight: bold; font-size: 0.75rem; color: #fff; }}
            .item-title {{ font-size: 1.05rem; font-weight: bold; margin-top: 6px; color: #f1f5f9; }}
            .meta-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px; }}
            .meta-box {{ background: #1e293b; padding: 8px 12px; border-radius: 8px; }}
            .meta-label {{ font-size: 0.7rem; color: #94a3b8; text-transform: uppercase; }}
            .meta-val {{ font-size: 0.95rem; font-weight: bold; color: #f8fafc; margin-top: 2px; }}
            .btn-small {{ display: inline-block; background: #3b82f6; color: #fff; text-decoration: none; padding: 8px 12px; border-radius: 6px; font-size: 0.8rem; font-weight: bold; margin-top: 10px; text-align: center; }}
            .telegram-box {{ background: #0c4a6e; border-left: 4px solid #38bdf8; padding: 12px; border-radius: 8px; font-size: 0.85rem; margin-bottom: 20px; }}
            .footer {{ text-align: center; font-size: 0.75rem; color: #64748b; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Inditex Restock Monitor</h1>
            <div class="subtitle">Zara • Bershka • Pull&Bear (Monitor 24/7)</div>
            
            <div class="telegram-box">
                💬 <b>Control desde tu Telegram:</b><br>
                Escribe <code>/add &lt;tienda&gt; &lt;referencia&gt; &lt;talla&gt;</code> a tu bot <b>@PruebaPullBot</b> para añadir prendas al instante.
            </div>
            
            <h2 style="font-size:1rem; margin-bottom:12px; color:#94a3b8;">PRENDAS VIGILADAS ({len(alerts)}):</h2>
            {items_html if items_html else "<div style='color:#94a3b8; text-align:center; padding:20px;'>No hay prendas en seguimiento. Usa /add en Telegram.</div>"}
            
            <div class="footer">
                Actualizado automáticamente en vivo • Monitorizando 24/7
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("app:app", host="0.0.0.0", port=port, log_level="info")
