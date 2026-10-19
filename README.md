# IV Orbit Texture Studio

Suite de escritorio para extraer, transformar, organizar y preparar texturas y sprites para videojuegos.

## Estado del proyecto

* **Fase actual:** Fase 4 completada (Sprites y atlas: detección automática por transparencia, pivotes/anclas configurables, empaquetador 2D MaxRects BSSF sin solapamientos, exportación atómica PNG + JSON estándar, persistencia en `.ivtex`).
* **Próxima fase:** Fase 5 (PBR y mapas de normales).
* **Plataforma:** Windows (arquitectura multiplataforma preparada).

---

## Características implementadas

### Correcciones de interacción y experiencia de usuario (Fase 2+)
* **Acceso completo a esquinas y bordes**: Margen de ajuste ampliado (`FIT_MARGIN = 48.0 px`) para que los vértices no queden apretados contra los bordes de la ventana.
* **Atracción magnética (Snapping)**: Imán inteligente (`SNAP_THRESHOLD_PX = 14.0 px`) que ajusta los vértices automáticamente a los límites exactos de la imagen `(0, 0)`, `(ancho, alto)`.
* **Botón "Ajustar a esquinas"**: 1 clic para posicionar inmediatamente los 4 vértices en las 4 esquinas exactas de la imagen.
* **Solución de bloqueo de vértices**: Salvaguarda contra liberación de ratón fuera de la ventana; si el botón izquierdo no está presionado, el vértice arrastrado se libera inmediatamente, permitiendo seleccionar los demás sin trabarse.
* **Desplazamiento intuitivo (Pan)**: Clic izquierdo y arrastre sobre el fondo del lienzo desplaza la imagen automáticamente sin necesidad de botón central o barra espaciadora.

### Fase 1: Aplicación base y lienzo
1. **Ventana principal funcional en PySide6**:
   - Barra de menús (`Archivo`, `Editar`, `Ver`, `Ventana`), barra de herramientas y barra de estado informativa.
   - Apertura de imágenes mediante diálogo nativo o argumento de línea de comandos.
   - Mensajes de error claros e informativos ante formatos dañados, archivos inexistentes o tamaños excesivos.

2. **Lienzo interactivo (`ImageCanvas`)**:
   - Fondo de tablero de ajedrez para visualizar áreas con transparencia (canal alfa).
   - Zoom suave y centrado en la posición del cursor mediante la rueda del ratón.
   - Controles de zoom dedicados: *Acercar* (`Ctrl++`), *Alejar* (`Ctrl+-`), *Ajustar a ventana* (`Ctrl+0`) y *Tamaño real (100 %)* (`Ctrl+1`).
   - Paneo/desplazamiento continuo mediante arrastre con botón izquierdo en espacio vacío, botón central o manteniendo la barra espaciadora.
   - Centrado de imagen sin modificar la escala (`Ctrl+Shift+C`).
   - Muestreo suave al alejar y píxeles nítidos (*nearest-neighbor*) a partir de zoom 200 %.

3. **Mapeo desacoplado de coordenadas (`CoordinateMapper`)**:
   - Conversión bidireccional exacta entre coordenadas de pantalla y coordenadas lógicas de imagen.
   - Totalmente independiente de Qt para pruebas unitarias deterministas.

4. **Motor de carga y validación de imágenes (`imaging.image_io`)**:
   - Normalización a arreglos NumPy RGBA `uint8` protegidos contra escritura (`read-only`).
   - Validación de cabecera previa para límites de memoria y orientación EXIF automática.

### Fase 2: Texture Ripper (Extracción y rectificación)
1. **Selección interactiva de 4 esquinas (`SelectionModel` y `TextureRipperTool`)**:
   - 4 asas circulares numeradas con etiquetas de coordenadas en tiempo real.
   - Arrastre interactivo de vértices con detección de colisión (*hit test*) en espacio de pantalla con radio ampliado a 28 px.
   - Modo de colocación punto a punto (1..4 clics) con línea guía punteada al cursor.
   - Inicialización automática de cuadrilátero centrado al cargar una imagen.
   - Botones para restablecer a rectángulo por defecto, ajustar a esquinas o limpiar para marcado manual.
   - Validación geométrica rigurosa: detección y rechazo de auto-intersecciones (efecto corbatín/reloj de arena), formas cóncavas, colinealidad o áreas degeneradas (< 1 px²).

2. **Motor de rectificación y homografías (`imaging.perspective`)**:
   - Mapeo de perspectiva puro mediante homografías 3x3 de OpenCV (`cv2.getPerspectiveTransform` y `cv2.warpPerspective`).
   - Estimación automática de dimensiones de salida basada en las longitudes de los bordes opuestos para preservar la máxima resolución disponible.
   - Múltiples métodos de interpolación configurables: **Lanczos4** (alta calidad por defecto), **Bicúbica**, **Bilineal** y **Vecino más cercano** (para pixel art).

3. **Panel de control y previsualización en vivo (`TextureRipperPanel`)**:
   - Panel acoplable y redimensionable en el lateral derecho de la ventana.
   - Control numérico de dimensiones de salida (ancho y alto).
   - Casilla de bloqueo de proporción (*Aspect Ratio Lock*).
   - Botón de cálculo de dimensiones estimadas.
   - Previsualización en vivo en miniatura generada de forma reactiva con escalado adaptativo para mantener la fluidez.

4. **Exportación atómica (`exporters.image_exporter`)**:
   - Exportación a **PNG**, **JPEG**, **WebP**, **BMP** y **Targa (.tga)**.
   - Composición limpia del canal alfa sobre fondo configurable para formatos sin transparencia (JPEG/BMP).
   - Escritura atómica mediante reemplazo de archivo temporal para evitar archivos dañados ante interrupciones.

### Fase 3: Proyectos e historial
1. **Formato de proyecto `.ivtex`**:
   - Contenedor ZIP estándar y portable con documento `project.json` y carpeta de recursos `assets/`.
   - Empaquetado automático de la imagen de origen para proyectos 100 % autónomos y portables entre equipos.
   - Hash SHA-256 de integridad para verificar el archivo de imagen de origen.
   - Protección de seguridad estricta: prevención de ataques ZipSlip (bloqueo de paths con `..` o absolutos) y límites contra descompresión excesiva (zip bombs).
   - Persistencia atómica mediante archivo temporal intermedio y reemplazo atómico en disco.

2. **Historial de Deshacer y Rehacer (`QUndoStack`)**:
   - Deshacer (`Ctrl+Z`) y Rehacer (`Ctrl+Y` o `Ctrl+Shift+Z`) para movimiento de vértices, cambio de esquinas, restablecimiento y limpieza.
   - Indicador de cambios sin guardar en la barra de título (`*`).
   - Diálogo de confirmación para guardar cambios al abrir otra imagen, abrir otro proyecto o salir de la aplicación.

### Fase 4: Sprites y Atlas
1. **Detección automática por transparencia (`imaging.sprites`)**:
   - Análisis de componentes conectados (8-conectividad) sobre el canal alfa mediante OpenCV y NumPy.
   - Umbral de opacidad alfa configurable (1 a 255), filtro de ruido por área mínima en píxeles y margen/padding perimetral opcional.
   - Fusión inteligente de rectángulos solapados o contiguos para evitar fragmentación.

2. **Herramienta interactiva de Sprites (`SpriteTool` y `SpritePanel`)**:
   - Conmutador de modos en barra de menús y herramientas: *Texture Ripper* vs *Sprites y Atlas*.
   - Superposición visual en el lienzo con contornos de selección, badges con nombre y dimensiones, y crucetas de pivote.
   - Creación manual mediante arrastre sobre espacio vacío o botón "Agregar".
   - Desplazamiento y ajuste interactivo de sprites seleccionados con el ratón.
   - Eliminación con tecla `Supr`/`Backspace` o botón de interfaz.
   - Tabla interactiva con búsqueda y sincronización bidireccional de selección, nombre y tamaño.

3. **Configuración de Pivotes y Puntos de Ancla**:
   - Presets estándar listos para motores de juegos: **Centro** `(0.5, 0.5)`, **Pies / Base inferior** `(0.5, 1.0)`, **Superior Izquierda** `(0.0, 0.0)`, **Centro Superior**, **Centro Inferior**, etc.
   - Coordenadas normalizadas personalizables `(X, Y)` entre `0.0` y `1.0`.

4. **Empaquetador 2D de Atlas (`imaging.atlas`)**:
   - Algoritmo de empaquetado **MaxRects** con heurística *Best Short Side Fit* (BSSF) para aprovechamiento óptimo del espacio.
   - Garantía matemática estricta de cero solapamientos entre sprites.
   - Prevención de sangrado de texturas (*anti-bleeding*): espaciado entre sprites y margen perimetral configurables.
   - Opciones para forzar dimensiones en Potencia de Dos (**POT**: 256, 512, 1024, 2048, 4096...) y atlas cuadrado (`Ancho == Alto`).
   - Previsualización en miniatura reactiva con estadísticas en vivo de dimensiones y cantidad de sprites.

5. **Exportación atómica y metadatos estándar (`exporters.atlas_exporter`)**:
   - Exportación simultánea y atómica de la imagen del atlas (`.png`) y el archivo de metadatos (`.json`).
   - Formato de metadatos JSON compatible con motores de videojuegos (Godot, Unity, PixiJS, Phaser), incluyendo dimensiones, cuadros (`frame`, `spriteSourceSize`, `sourceSize`) y pivotes normalizados.
   - Persistencia completa de regiones de sprites y configuraciones de atlas dentro del contenedor de proyecto `.ivtex`.

---

## Requisitos previos

* **Python:** 3.12 o 3.13 (usando `uv` o el instalador estándar de Python).
* **Gestor de paquetes recomendado:** [`uv`](https://docs.astral.sh/uv/) (rápido, determinista y autónomo).

---

## Instalación y preparación del entorno

### Con `uv` (Recomendado)

1. Clonar o ubicarse en el directorio del repositorio:
   ```bash
   cd d:\Textureripper
   ```

2. Instalar dependencias en el entorno virtual local:
   ```bash
   uv sync
   ```

### Con `pip` estándar

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
pip install pytest pytest-qt ruff mypy
```

---

## Ejecución de la aplicación

Para iniciar la aplicación:

```bash
uv run iv-orbit-texture-studio
```

O abriendo una imagen directamente:

```bash
uv run iv-orbit-texture-studio ruta/a/tu/imagen.png
```

También puede iniciarse ejecutando el módulo:

```bash
uv run python -m iv_orbit_texture_studio
```

---

## Ejecución de pruebas y calidad de código

### Pruebas automatizadas (pytest)

Ejecuta las pruebas unitarias y de interfaz (utilizando `pytest-qt`):

```bash
uv run pytest
```

Para ver la salida detallada con cada prueba individual:

```bash
uv run pytest -v
```

### Comprobación de estilo y linter (Ruff)

```bash
uv run ruff check .
```

### Comprobación de tipos estáticos (mypy)

```bash
uv run mypy
```

---

## Estructura del código

```text
iv-orbit-texture-studio/
├── pyproject.toml                         # Configuración de dependencias, scripts, ruff, mypy y pytest
├── .python-version                        # Versión de Python fijada (3.12)
├── README.md                              # Documentación e instrucciones
├── src/
│   └── iv_orbit_texture_studio/
│       ├── __init__.py
│       ├── __main__.py                    # Ejecución como módulo (python -m ...)
│       ├── main.py                        # Entrypoint de consola
│       ├── app/
│       │   └── application.py             # Arranque y configuración de QApplication
│       ├── core/
│       │   ├── commands.py                # Comandos reversibles QUndoCommand (MoveVertex, SetQuad, etc.)
│       │   └── document.py                # Modelo de datos del documento y proyecto activo
│       ├── project_io/
│       │   ├── serializer.py              # Contenedor ZIP .ivtex, atomic write, safe extraction (ZipSlip)
│       │   └── migrations.py              # Manejo de versiones de esquema
│       ├── tools/
│       │   └── texture_ripper/
│       │       ├── tool.py                # Control de interacción, dibujo y snapping magnético
│       │       ├── selection.py           # Modelo de 4 vértices, estados y validación geométrica
│       │       └── preview.py             # Panel lateral con previsualización en vivo y controles
│       ├── exporters/
│       │   └── image_exporter.py          # Exportador atómico multiformato (PNG, JPG, WebP, BMP, TGA)
│       ├── ui/
│       │   ├── main_window.py             # Ventana principal, menús, barras de estado y acciones
│       │   ├── qt_image.py                # Conversión desacoplada entre ndarray y QImage
│       │   └── canvas/
│       │       ├── coordinate_mapper.py   # Lógica matemática pura de zoom/pan y mapeo de coordenadas
│       │       └── image_canvas.py        # Widget de dibujo y eventos de interacción del usuario
│       └── imaging/
│           ├── image_io.py                # Carga, validación de dimensiones y normalización RGBA
│           └── perspective.py             # Homografías OpenCV, rectificación y validación de quads
└── tests/
    ├── unit/
    │   ├── test_commands.py               # Pruebas de comandos deshacer/rehacer y QUndoStack
    │   ├── test_coordinate_mapper.py      # Pruebas matemáticas de escala, traslación y límites
    │   ├── test_image_exporter.py         # Pruebas de exportación atómica y composición alfa
    │   ├── test_image_io.py               # Pruebas de carga, fallos de formato y límites de tamaño
    │   ├── test_perspective.py            # Pruebas de homografía, estimación de tamaño e interpolación
    │   ├── test_project_io.py             # Pruebas de guardado/apertura .ivtex, ZipSlip y corrupción
    │   ├── test_qt_image.py               # Pruebas de conversión ndarray -> QImage
    │   └── test_selection.py              # Pruebas de ciclo de vida del cuadrilátero y hit-testing
    └── ui/
        ├── test_image_canvas.py           # Pruebas de interacción con ratón y señales del lienzo
        ├── test_main_window.py            # Pruebas de interfaz completa con pytest-qt
        ├── test_project_workflow.py       # Pruebas de flujo de proyecto y deshacer/rehacer en UI
        └── test_texture_ripper_ui.py      # Pruebas de controles, arrastre y snapping del Texture Ripper
```

---

## Atajos de teclado y navegación del lienzo

| Acción | Atajo / Control |
|---|---|
| Nuevo proyecto | `Ctrl + N` |
| Abrir imagen… | `Ctrl + O` |
| Abrir proyecto… | `Ctrl + Shift + O` |
| Guardar proyecto | `Ctrl + S` |
| Guardar proyecto como… | `Ctrl + Shift + S` |
| Deshacer | `Ctrl + Z` |
| Rehacer | `Ctrl + Y` o `Ctrl + Shift + Z` |
| Exportar textura rectificada… | `Ctrl + E` |
| Acercar | `Ctrl + +` o Rueda del ratón hacia arriba |
| Alejar | `Ctrl + -` o Rueda del ratón hacia abajo |
| Ajustar a la ventana | `Ctrl + 0` |
| Tamaño real (100 %) | `Ctrl + 1` |
| Centrar imagen | `Ctrl + Shift + C` |
| Paneo / Desplazamiento | Arrastrar con botón izquierdo en fondo / botón central / `Espacio` + arrastre |
| Salir | `Ctrl + Q` |
