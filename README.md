# Pull&Bear Restock & Auto-Buy Bot

Bot especializado para monitorizar y comprar automáticamente el **Cárdigan cremallera Dickies** (Ref `07563305` / Color `712`) en talla **XS** en la tienda oficial de Pull&Bear España.

---

## ⚡ ¿Cómo funciona?

1. **Bypass de Akamai / WAF:** Emplea una instancia de Chrome automatizada que resuelve de forma transparente el interstitial challenge de Akamai.
2. **Latencia ultra-baja (90 ms por comprobación):** Realiza consultas periódicas a la API privada de Inditex (`/itxrest/`) sin recargar toda la página pesada, evitando bloqueos por peticiones excesivas.
3. **Reserva automática en la cesta (Auto-Add-to-Cart):** En cuanto la talla XS pasa de `SOLD_OUT` a disponible, ejecuta la llamada de adición a la cesta (`/order/0/orderitem`) y hace clic en la interfaz.
4. **Alerta sonora + Ventana emergente en Windows:** Hace sonar un pitido insistente por los altavoces de tu PC y muestra una ventana emergente en pantalla para avisarte de inmediato si estás lejos del teclado.
5. **Navegación al Checkout:** Te coloca directamente en la pantalla de pago de la cesta para que solo tengas que confirmar el pedido o autorizar en la app de tu banco (cumpliendo con la normativa europea de autenticación reforzada 3D Secure / PSD2).
6. **Soporte Telegram y Discord:** Envía un mensaje instantáneo prioritario a tu teléfono móvil en cuanto detecta stock.

---

## 🚀 Cómo ponerlo en marcha en tu PC (Modo Local)

### 1. Iniciar el bot
Simplemente haz doble clic en el archivo:
```text
run_bot.bat
```
O desde la consola (PowerShell / CMD):
```powershell
cd C:\Users\ariba\.gemini\antigravity\scratch\pullandbear_bot
py bot.py
```

### 2. Guardar tu sesión (Recomendado para compra rápida)
La primera vez que se abra la ventana de Chrome:
1. Inicia sesión con tu cuenta de Pull&Bear (o introduce tus datos de envío).
2. Las cookies y tu sesión se guardan automáticamente en la carpeta `chrome_profile/`.
3. De esta forma, cuando ocurra el restock, la prenda se añadirá directamente a **tu cuenta** y el checkout será instantáneo.

---

## ☁️ Cómo tenerlo 24/7 SIN tener tu ordenador encendido

Para que el bot funcione sin depender de que tu ordenador personal esté encendido, necesitas alojarlo en un entorno que esté siempre activo.

Al no tener los altavoces ni la pantalla de tu PC delante, el bot te avisará **directamente a tu teléfono móvil por Telegram o Discord**.

### Opción A: Un Servidor VPS en la nube (Recomendada)
Un VPS (Servidor Privado Virtual) con Linux cuesta entre 0€ y 3€/mes y está encendido 24/7 los 365 días del año.
* **Gratis:** [Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/) ofrece servidores virtuales gratuitos de por vida (Always Free).
* **Económicos (~3€ - 4€/mes):** Hetzner Cloud (CX22), OVHcloud, Contabo o DigitalOcean.

#### Despliegue en 2 minutos con Docker en el servidor:
1. Sube los archivos del bot al servidor.
2. En `config.json`, pon `"headless": true` y activa Telegram.
3. Ejecuta:
   ```bash
   docker compose up -d --build
   ```
   *(El bot correrá en segundo plano y se reiniciará automáticamente si el servidor se reinicia).*

---

### Opción B: Dispositivo de bajo consumo en casa (Raspberry Pi / Portátil viejo)
Si tienes en casa una **Raspberry Pi**, un Mini PC o un portátil antiguo que no uses:
* Conéctalo a tu router con cable o WiFi y ciérrale la tapa.
* Consume apenas 2-5W de electricidad (unos céntimos al mes).
* **Gran ventaja:** Utiliza la **dirección IP residencial de tu casa**, lo que hace que los sistemas anti-bot de Inditex nunca sospechen que se trata de un centro de datos.

---

## 📱 Cómo configurar las alertas en tu móvil (Telegram) en 1 minuto

1. Abre **Telegram** en tu móvil o PC y busca el contacto `@BotFather`.
2. Escribe `/newbot`, ponle un nombre (por ejemplo `DickiesPullBot`) y un usuario que termine en `bot`.
3. BotFather te dará un **Token** (ejemplo: `7123456789:AAH...`).
4. Busca ahora en Telegram el usuario `@userinfobot`, envíale un mensaje y te responderá con tu **Id** numérico (ejemplo: `123456789`).
5. Abre conversación con tu nuevo bot en Telegram y dale a **Iniciar** (Start).
6. En tu `config.json`, activa Telegram:
   ```json
   "telegram": {
     "enabled": true,
     "bot_token": "TU_TOKEN_DE_BOTFATHER",
     "chat_id": "TU_ID_NUMERICO"
   }
   ```
¡Listo! En el momento en que haya restock, tu teléfono sonará con la notificación de compra inmediata.

---

## ⚙️ Archivo de Configuración (`config.json`)

```json
{
  "product_url": "https://www.pullandbear.com/es/cardigan-cremallera-dickies-l07563305?cS=712",
  "target_size": "XS",
  "check_interval_seconds": 5,
  "refresh_page_interval_minutes": 15,
  "headless": false,
  "user_data_dir": "./chrome_profile",
  "auto_add_to_cart": true,
  "auto_open_checkout": true,
  "sound_alarm": true,
  "windows_notification": true,
  "telegram": {
    "enabled": false,
    "bot_token": "TU_BOT_TOKEN_AQUI",
    "chat_id": "TU_CHAT_ID_AQUI"
  },
  "discord": {
    "enabled": false,
    "webhook_url": "TU_DISCORD_WEBHOOK_AQUI"
  }
}
```
