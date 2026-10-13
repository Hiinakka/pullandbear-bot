# Inditex Restock Bot 24/7 (Zara, Bershka & Pull&Bear)

Bot especializado para monitorizar reposiciones de stock en tiempo real en las tiendas de **Zara**, **Bershka** y **Pull&Bear**, con notificaciones sonoras directas a tu teléfono móvil por Telegram y panel web en vivo.

---

## ⚡ Novedades de la versión Multi-Tienda

1. **Soporte para 3 marcas de Inditex:** Monitoriza prendas simultáneamente en Zara, Bershka y Pull&Bear.
2. **Control interactivo por Telegram:** Puedes añadir prendas directamente escribiéndole a tu bot de Telegram sin tener que tocar código ni reiniciar nada.
3. **Múltiples prendas a la vez:** Vigila el cárdigan Dickies de Pull&Bear y a la vez ropa de Zara o Bershka.
4. **Enlace directo a compra:** Cada alerta te envía el enlace directo a la prenda para comprarla en 1 segundo.

---

## 📱 Comandos del Bot en Telegram (`@PruebaPullBot`)

Puedes hablarle a tu bot en Telegram con estos comandos:

* **Añadir una prenda:**
  ```text
  /add <tienda> <referencia o enlace> <talla>
  ```
  *Ejemplos:*
  * `/add pullandbear 07563305 XS`
  * `/add zara 2731/240 S`
  * `/add bershka 0123/456 M`
  * `/add https://www.zara.com/es/es/vestido-satinado-p01234567.html L`

* **Ver prendas activas:**
  ```text
  /list
  ```
  Te responde con la lista de todas las prendas que está vigilando y su stock actual.

* **Eliminar una alerta:**
  ```text
  /del 1
  ```
  Elimina la prenda número 1 de tu lista.

* **Probar notificación:**
  ```text
  /test
  ```
  Envía un aviso de prueba para verificar el sonido en tu smartphone.

---

## 🚀 Cómo ejecutarlo

### Opción 1: En tu propio PC
Haz doble clic en `run_bot.bat` o ejecuta:
```powershell
cd C:\Users\ariba\.gemini\antigravity\scratch\pullandbear_bot
py bot.py
```

### Opción 2: 24/7 en GitHub Actions (Nube gratuita)
1. Haz un commit y `git push origin main`.
2. En GitHub entra en **Actions** > **Pull&Bear Restock Bot 24/7** > **Run workflow**.
3. El bot se quedará escuchando en la nube y responderá a tus comandos de Telegram.
