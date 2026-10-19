# IV Orbit Texture Studio

Suite de escritorio para extraer, transformar, organizar y preparar texturas y sprites para videojuegos.

## Estado del proyecto

* **Fase actual:** Fase 1 completada (Aplicación base con lienzo interactivo y coordenadas verificadas).
* **Próxima fase:** Fase 2 (Texture Ripper: selección de 4 esquinas y rectificación de perspectiva con homografías).
* **Plataforma:** Windows (arquitectura multiplataforma preparada).

---

## Características implementadas (Fase 1)

1. **Ventana principal funcional en PySide6**:
   - Barra de menús (`Archivo`, `Ver`), barra de herramientas y barra de estado informativa.
   - Apertura de imágenes mediante diálogo nativo o argumento de línea de comandos.
   - Mensajes de error claros e informativos ante formatos dañados, archivos inexistentes o tamaños excesivos.

2. **Lienzo interactivo (`ImageCanvas`)**:
   - Fondo de tablero de ajedrez para visualizar áreas con transparencia (canal alfa).
   - Zoom suave y centrado en la posición del cursor mediante la rueda del ratón.
   - Controles de zoom dedicados: *Acercar* (`Ctrl++`), *Alejar* (`Ctrl+-`), *Ajustar a ventana* (`Ctrl+0`) y *Tamaño real (100 %)* (`Ctrl+1`).
   - Paneo/desplazamiento continuo mediante arrastre con botón central, botón izquierdo o manteniendo la barra espaciadora.
   - Centrado de imagen sin modificar la escala (`Ctrl+Shift+C`).
   - Muestreo suave al alejar y píxeles nítidos (*nearest-neighbor*) a partir de zoom 200 % para facilitar la inspección de píxeles individuales.

3. **Mapeo desacoplado de coordenadas (`CoordinateMapper`)**:
   - Conversión bidireccional exacta entre coordenadas de pantalla (widget) y coordenadas lógicas de imagen (píxel exacto).
   - Completamente independiente de Qt, permitiendo pruebas unitarias deterministas sin entorno gráfico.
   - Indicador de coordenadas del cursor en tiempo real en la barra de estado.

4. **Motor de carga y validación de imágenes (`imaging.image_io`)**:
   - Desacoplado de la interfaz gráfica.
   - Normalización a arreglos NumPy RGBA `uint8` protegidos contra escritura (`read-only`) para evitar mutaciones de los datos originales.
   - Lectura de metadatos de cabecera previa para validar límites de memoria y dimensiones antes de decodificar.
   - Corrección automática de orientación EXIF.

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
