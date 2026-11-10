# 🦅 BirdRuta Los Lagos

**Optimizador de Rutas de Observación de Aves (Pajareo) & Explorador eBird API** para la **Región de Los Lagos, Chile (CL-LL)**.

Diseñado para resolver el desafío:
> *¿Cuál sería la mejor ruta para registrar la mayor cantidad de especies de aves en la Región de Los Lagos, considerando los últimos registros de eBird, el clima, las horas de luz y los picos de actividad biológica?*

---

## 🌟 Funcionalidades Principales

### 1. 🗺️ Optimizador Inteligente de Rutas de Pajareo
- **Algoritmo Bioclimático:**
  - **Amanecer y Coro Matutino (Dawn Chorus, 06:30 - 09:30):** Prioriza bosques templados valdivianos (PN Vicente Pérez Rosales, Lahuen Ñadi, Puyehue) para maximizar la detección por canto de especialistas y tapaculos escurridizos (**Chucao**, **Huet-huet común**, **Carpintero negro**, **Churrín de la mocha**, **Rayadito**, **Comesebo**).
  - **Mediodía y Tarde (11:00 - 16:30):** Dirige la ruta a estuarios, humedales y costas (Santuario Humedales de Maullín, Caulín, Pullao en Chiloé, Lago Llanquihue) para avistar aves acuáticas, rapaces y playeras migratorias (**Zarapito de pico recto**, **Cisne de cuello negro**, **Flamenco chileno**, **Pilpilén negro**).
  - **Integración Meteorológica en Tiempo Real (Open-Meteo):** Evalúa para cada coordenada y hora exacta la probabilidad de precipitación, viento (km/h) y temperatura, aplicando penalizaciones si las condiciones reducen la detectabilidad.
  - **Cálculo de Luz Solar:** Determina automáticamente la hora exacta de salida y puesta del sol para aprovechar el 100% de la ventana de luz.
- **Mapa Interactivo Leaflet:** Pines numerados por parada, trazado de ruta en carretera y popups con enlaces directos a las checklists de eBird.
- **Integración con Google Maps:** Botón con un clic para abrir la ruta completa con todos los waypoints secuenciales en Google Maps en tu móvil o navegador.
- **Hoja de Campo Imprimible:** Exporta el itinerario con la lista de especies objetivo por parada para llevar al terreno.

### 2. 📋 Lista Maestra de Especies Probables (Checklist de Campo)
- **Checklist consolidado:** Genera la lista de todas las especies con probabilidad real de avistamiento para el conjunto de paradas seleccionadas (típicamente **80 a 140+ especies**).
- **Marcador en terreno interactivo:** Casillas de verificación `[ ]` para ir marcando especies vistas en vivo en tu móvil o laptop con contador en tiempo real (`✓ X / Total registradas`).
- **Filtros por grupo/nicho:**
  - 🌲 Bosque Templado y Sotobosque (*Chucao, Huet-huet, Carpintero negro, Rayadito, Comesebo grande, Churrín, Colilarga, Fío-fío*)
  - 🦢 Humedales, Anátidas y Acuáticas (*Cisne de cuello negro, Cisne coscoroba, Flamenco chileno, Patos, Taguas, Hualas, Siete-colores, Martín pescador*)
  - 🌊 Aves Playeras y Marinas (*Zarapito de pico recto, Zarapito común, Pilpilén común y negro, Quetrus, Chorlos, Playeros, Gaviotas, Cormoranes*)
  - 🦅 Rapaces y Búhos (*Concón, Chuncho, Águila mora, Aguilucho, Peuquito, Bailarín, Halcón peregrino*)
  - 🌾 Pradera, Matorral y Paseriformes (*Bandurria, Queltehue, Zorzal patagónico, Diucón, Colegial, Loica, Cometocino*)
- **Asignación del mejor hotspot:** Cada especie indica cuál es la parada óptima de la ruta para registrarla.
- **Exportación:** Botón directo para copiar la lista formateada al portapapeles y compartir con el grupo.

### 3. ⚡ Explorador eBird API UI (Estilo ebird-api-ui.com)
- Permite consultar cualquier endpoint de la API oficial de eBird v2:
  - Observaciones recientes (`/data/obs/{regionCode}/recent`)
  - Observaciones notables / rarezas (`/data/obs/{regionCode}/recent/notable`)
  - Hotspots por región (`/ref/hotspot/{regionCode}`)
  - Hotspots por cercanía GPS (`/ref/hotspot/geo`)
  - Observaciones en un Hotspot específico (`/data/obs/{locId}/recent`)
  - Taxonomía eBird oficial (`/ref/taxonomy/ebird`)
- **Proxy transparente integrado:** Soluciona el bloqueo CORS y 403 Forbidden que eBird impone a navegadores web al consultar directamente desde JavaScript.
- Visor JSON con formato, tiempo de respuesta en milisegundos, status HTTP y vista tabular interactiva.
- Soporte para nombres comunes en español chileno (`sppLocale=es_CL`).

### 4. 📡 Radar de Especies en Vivo
- Visualiza en tiempo real las especies registradas en los últimos 14 días en la Región de Los Lagos.
- Filtros rápidos: Bosque Templado, Humedales & Playeras, Rapaces y Rarezas.
- Enlaces directos a fotos y cantos grabados en la Macaulay Library.

### 5. 🌦️ Guía de Biorritmo & Clima Regional
- Explicación de los patrones de actividad aviar en el bosque lluvioso y estuarios de la Patagonia norte.

---

## 🚀 Cómo Iniciar la Aplicación

1. **Requisitos:** Tener instalado Python 3.10 o superior (ya instalado en tu sistema).
2. **Ejecución rápida:**
   - Haz doble clic en el archivo `run.bat` o ejecuta en la consola:
   ```powershell
   python app.py
   ```
3. **Abre tu navegador en:**
   ```
   http://localhost:5000
   ```

---

## 🔑 Configuración de API Key
La aplicación ya viene preconfigurada con tu API key de eBird (`dnbm87a73dmo`), la cual puedes cambiar o actualizar en cualquier momento desde la interfaz.
