# Inditex Restock Bot 24/7 (Zara, Bershka & Pull&Bear)

Bot inteligente para monitorizar reposiciones de stock en tiempo real en **Zara**, **Bershka** y **Pull&Bear**, con notificaciones directas a tu móvil por Telegram, tolerancia a fallos tipográficos y flujo conversacional guiado.

---

## ⚡ Nuevas Funcionalidades Inteligentes

1. **Corrección de errores tipográficos (Fuzzy Matching):**
   * El bot entiende variaciones y erratas comunes como `pulandbear`, `pullndbear`, `pull&bear`, `berhska`, `berska`, `bsk`, `zra`, etc.
2. **Flujo interactivo paso a paso:**
   * Si escribes solo la prenda o pegas un enlace sin indicar la talla, el bot te preguntará amablemente:  
     *“¿Qué talla estás buscando? (Ej: XS, S, M, L, XL, 38...)”*  
     y solo tienes que responder con la talla para guardar la alerta.
3. **Escaneo inteligente cada 1 minuto (60s):**
   * Tráfico suave y 100% natural para no sobrecargar los servidores de las tiendas y evitar bloqueos.
4. **Soporte multi-usuario completo:**
   * Puedes compartir el bot con amigos o familiares: cada uno gestiona sus propias prendas de forma privada. Si varios siguen la misma prenda, el bot solo hace 1 comprobación por minuto y avisa a todos a la vez.

---

## 📱 Cómo usar el Bot en Telegram (`@TrackerRopaBot`)

Puedes hablarle de forma completamente natural:

### 1. Añadir una prenda (Todo en un mensaje):
* `pulandbear 07563305 XS`
* `zara 2731/240 S`
* `berhska 0123/456 M`
* `https://www.zara.com/es/es/... M`

### 2. O déjate guiar (En dos pasos):
* Escribes: `pulandbear 07563305` o pegas un enlace.
* El bot te responde: *“¿Qué talla estás buscando?”*
* Respondes: `XS` (o `la S`, `talla 38`, `mediana`, etc.).
* El bot confirma y empieza a vigilarla.

### 3. Comandos útiles:
* `/list` : Ver tus prendas en seguimiento y si están agotadas o disponibles.
* `/del 1` : Dejar de seguir la prenda número 1 de tu lista.
* `/prueba` : Probar que recibes avisos y comprobar que todo funciona.
* `/cancelar` : Cancelar cualquier operación en curso.
* `/help` : Ver la guía de ayuda.
