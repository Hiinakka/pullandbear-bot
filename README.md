# Universal Fashion Restock Bot (Zara, Bershka, Pull&Bear, Stradivarius, Mango & H&M)

Bot inteligente para monitorizar reposiciones de stock en tiempo real en **Pull&Bear**, **Zara**, **Bershka**, **Stradivarius**, **Mango** y **H&M (HyM)**, con notificaciones directas a tu móvil por Telegram, tolerancia a fallos tipográficos y consultas ultra-rápidas.

---

## ⚡ Funcionalidades

1. **6 Tiendas de Moda Soportadas:**
   * **Pull&Bear**, **Zara**, **Bershka**, **Stradivarius**, **Mango** y **H&M**.
2. **Corrección de errores tipográficos (Fuzzy Matching):**
   * El bot entiende variaciones y erratas comunes como `pulandbear`, `pullndbear`, `berhska`, `bsk`, `stradi`, `stra`, `mango`, `mng`, `hym`, `h&m`, etc.
3. **Flujo interactivo guiado:**
   * Si escribes solo la referencia o pegas un enlace sin indicar la talla, el bot te preguntará amablemente:  
     *“¿Qué talla estás buscando? (Ej: XS, S, M, L, XL, 38...)”*  
     y solo tienes que responder con la talla para guardar la alerta.
4. **Consultas ultra-rápidas configurables:**
   * Configurable (por ejemplo, cada 5 segundos para cazar restocks instantáneos antes de que se agoten).
5. **Filtrado estricto anti-falsas alarmas:**
   * Inditex (Pull&Bear, Zara, etc.) marca internamente `isBuyable: True` en prendas sin stock real. El bot filtra estrictamente este comportamiento para avisar **solo** cuando la talla esté realmente disponible para comprar.
6. **Soporte multi-usuario completo:**
   * Cada usuario gestiona sus alertas de forma privada con su propio Telegram.

---

## 📱 Cómo usar el Bot en Telegram (`@TrackerRopaBot`)

### 1. Añadir una prenda (Todo en un mensaje):
* `pulandbear 07563305 XS`
* `zara 2731/240 S`
* `berhska 0123/456 M`
* `stradivarius 0453/642 36`
* `mango 37045842 M`
* `hym 1324742001 S`
* O pegando el enlace directo: `https://www.zara.com/es/es/... S`

### 2. O déjate guiar (En dos pasos):
* Escribes: `pulandbear 07563305` o pegas un enlace.
* El bot te responde: *“¿Qué talla estás buscando?”*
* Respondes: `XS` (o `la S`, `talla 38`, `mediana`, etc.).
* El bot confirma y empieza a vigilarla al instante.

### 3. Comandos útiles:
* `/list` : Ver tus prendas en seguimiento y si están agotadas o disponibles.
* `/del <número>` : Dejar de seguir una prenda.
* `/prueba` : Probar que recibes avisos y comprobar que todo funciona.
* `/cancelar` : Cancelar cualquier operación en curso.
* `/help` : Ver la guía de ayuda.
