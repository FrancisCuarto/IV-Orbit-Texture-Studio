# IV Orbit Texture Studio

Suite de escritorio para extraer, transformar, organizar y preparar texturas y sprites para videojuegos.

## Estado del proyecto

* **Fase actual:** Fase 2 completada (Texture Ripper: selección interactiva de 4 esquinas, homografías, rectificación y exportación).
* **Próxima fase:** Fase 3 (Proyectos e historial: formato `.ivtex`, guardar/abrir proyectos, deshacer y rehacer).
* **Plataforma:** Windows (arquitectura multiplataforma preparada).

---

## Características implementadas

### Fase 1: Aplicación base y lienzo
1. **Ventana principal funcional en PySide6**:
   - Barra de menús (`Archivo`, `Ver`, `Ventana`), barra de herramientas y barra de estado informativa.
   - Apertura de imágenes mediante diálogo nativo o argumento de línea de comandos.
   - Mensajes de error claros e informativos ante formatos dañados, archivos inexistentes o tamaños excesivos.

2. **Lienzo interactivo (`ImageCanvas`)**:
   - Fondo de tablero de ajedrez para visualizar áreas con transparencia (canal alfa).
   - Zoom suave y centrado en la posición del cursor mediante la rueda del ratón.
   - Controles de zoom dedicados: *Acercar* (`Ctrl++`), *Alejar* (`Ctrl+-`), *Ajustar a ventana* (`Ctrl+0`) y *Tamaño real (100 %)* (`Ctrl+1`).
   - Paneo/desplazamiento continuo mediante arrastre con botón central o manteniendo la barra espaciadora.
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
   - Arrastre interactivo de vértices con detección de colisión (*hit test*) en espacio de pantalla.
   - Modo de colocación punto a punto (1..4 clics) con línea guía punteada al cursor.
   - Inicialización automática de cuadrilátero centrado al cargar una imagen.
   - Botones para restablecer a rectángulo por defecto o limpiar para marcado manual.
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
│       ├── ui/
│       │   ├── main_window.py             # Ventana principal, menús, barras de estado y acciones
│       │   ├── qt_image.py                # Conversión desacoplada entre ndarray y QImage
│       │   └── canvas/
│       │       ├── coordinate_mapper.py   # Lógica matemática pura de zoom/pan y mapeo de coordenadas
│       │       └── image_canvas.py        # Widget de dibujo y eventos de interacción del usuario
│       └── imaging/
│           └── image_io.py                # Carga, validación de dimensiones y normalización RGBA
└── tests/
    ├── unit/
    │   ├── test_coordinate_mapper.py      # Pruebas matemáticas de escala, traslación y límites
    │   ├── test_image_io.py               # Pruebas de carga, fallos de formato y límites de tamaño
    │   └── test_qt_image.py               # Pruebas de conversión ndarray -> QImage
    └── ui/
        ├── test_image_canvas.py           # Pruebas de interacción con ratón y señales del lienzo
        └── test_main_window.py            # Pruebas de interfaz completa con pytest-qt
```

---

## Atajos de teclado y navegación del lienzo

| Acción | Atajo / Control |
|---|---|
| Abrir imagen | `Ctrl + O` |
| Acercar | `Ctrl + +` o Rueda del ratón hacia arriba |
| Alejar | `Ctrl + -` o Rueda del ratón hacia abajo |
| Ajustar a la ventana | `Ctrl + 0` |
| Tamaño real (100 %) | `Ctrl + 1` |
| Centrar imagen | `Ctrl + Shift + C` |
| Paneo / Desplazamiento | Arrastrar con botón central / botón izquierdo / `Espacio` + botón izquierdo |
| Salir | `Ctrl + Q` |
