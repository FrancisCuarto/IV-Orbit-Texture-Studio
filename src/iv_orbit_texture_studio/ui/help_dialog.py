"""Diálogo de Ayuda, Documentación y Tutoriales Guiados para IV Orbit Texture Studio.

Presenta una interfaz organizada en secciones temáticas con guías paso a paso,
diagramas explicativos, tabla de atajos de teclado y la opción de cargar texturas
de muestra para practicar la transformación libre y composición de atlas.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from iv_orbit_texture_studio.core.atlas_item import AtlasItem


def create_demo_texture_items() -> list[AtlasItem]:
    """Genera 4 texturas de demostración coloridas para practicar en el Atlas."""
    items = []

    # 1. Textura de ladrillos estilizada (128x128)
    brick = np.full((128, 128, 4), [180, 70, 45, 255], dtype=np.uint8)
    for y in range(0, 128, 32):
        brick[y : y + 3, :] = [40, 40, 45, 255]
    for y_idx, y in enumerate(range(0, 128, 32)):
        offset = 0 if (y_idx % 2 == 0) else 32
        for x in range(offset, 128, 64):
            brick[y : y + 32, max(0, x - 1) : min(128, x + 2)] = [40, 40, 45, 255]
    brick.setflags(write=False)
    items.append(AtlasItem.create("muestra_ladrillo", brick, x=0, y=0))

    # 2. Textura de madera estilizada (128x128)
    wood = np.full((128, 128, 4), [145, 95, 55, 255], dtype=np.uint8)
    for y in range(128):
        variation = int(18 * np.sin(y * 0.18))
        wood[y, :, 0] = np.clip(145 + variation, 0, 255)
        wood[y, :, 1] = np.clip(95 + variation // 2, 0, 255)
        wood[y, :, 2] = np.clip(55 + variation // 3, 0, 255)
    for x in range(0, 128, 42):
        wood[:, max(0, x - 1) : min(128, x + 2)] = [60, 38, 20, 255]
    wood.setflags(write=False)
    items.append(AtlasItem.create("muestra_madera", wood, x=136, y=0))

    # 3. Textura de piedra / roca (128x128)
    stone = np.full((128, 128, 4), [110, 120, 130, 255], dtype=np.uint8)
    for i in range(128):
        for j in range(128):
            noise = ((i * 37 + j * 73) % 29) - 14
            stone[i, j, 0] = np.clip(110 + noise, 0, 255)
            stone[i, j, 1] = np.clip(120 + noise, 0, 255)
            stone[i, j, 2] = np.clip(130 + noise, 0, 255)
    stone.setflags(write=False)
    items.append(AtlasItem.create("muestra_piedra", stone, x=0, y=136))

    # 4. Baldosas doradas / metal (96x96)
    metal = np.full((96, 96, 4), [215, 175, 45, 255], dtype=np.uint8)
    for i in range(0, 96, 24):
        metal[i : i + 2, :] = [80, 60, 15, 255]
        metal[:, i : i + 2] = [80, 60, 15, 255]
    metal.setflags(write=False)
    items.append(AtlasItem.create("muestra_baldosas", metal, x=136, y=136))

    return items


HTML_STYLE = """
<style>
    body {
        background-color: #161b22;
        color: #e6edf3;
        font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto,
            Helvetica, Arial, sans-serif;
        font-size: 13px;
        line-height: 1.6;
        padding: 10px 18px;
    }
    h1 {
        color: #58a6ff;
        font-size: 20px;
        border-bottom: 1px solid #30363d;
        padding-bottom: 8px;
        margin-top: 5px;
    }
    h2 {
        color: #79c0ff;
        font-size: 16px;
        margin-top: 18px;
        margin-bottom: 6px;
    }
    h3 {
        color: #d2a8ff;
        font-size: 14px;
        margin-top: 14px;
        margin-bottom: 4px;
    }
    p, li {
        color: #c9d1d9;
    }
    strong {
        color: #ffffff;
    }
    code {
        background-color: #21262d;
        color: #7ee787;
        padding: 2px 5px;
        border-radius: 4px;
        font-family: Consolas, 'Cascadia Code', monospace;
        font-size: 12px;
    }
    .badge {
        background-color: #1f6feb;
        color: #ffffff;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 11px;
        font-weight: bold;
    }
    .tip-box {
        background-color: #1c2128;
        border-left: 4px solid #58a6ff;
        padding: 10px 14px;
        margin: 12px 0;
        border-radius: 0 6px 6px 0;
    }
    .warn-box {
        background-color: #2d2218;
        border-left: 4px solid #d29922;
        padding: 10px 14px;
        margin: 12px 0;
        border-radius: 0 6px 6px 0;
    }
    .step-num {
        display: inline-block;
        background-color: #238636;
        color: white;
        border-radius: 50%;
        width: 22px;
        height: 22px;
        text-align: center;
        line-height: 22px;
        font-weight: bold;
        margin-right: 6px;
    }
    table {
        border-collapse: collapse;
        width: 100%;
        margin: 14px 0;
    }
    th, td {
        border: 1px solid #30363d;
        padding: 8px 12px;
        text-align: left;
    }
    th {
        background-color: #21262d;
        color: #58a6ff;
        font-weight: bold;
    }
    tr:nth-child(even) {
        background-color: #161b22;
    }
    tr:nth-child(odd) {
        background-color: #0d1117;
    }
</style>
"""


DOCS_CONTENT = {
    "welcome": f"""{HTML_STYLE}
        <h1>🌟 Bienvenido a IV Orbit Texture Studio</h1>
        <p><strong>IV Orbit Texture Studio</strong> es una suite especializada de grado
            profesional diseñada para creadores de videojuegos, artistas técnicos y modeladores
            3D que necesitan <strong>rippear, rectificar de perspectiva, componer en atlas,
            transformar libremente y generar materiales PBR completos</strong> a partir de
            capturas de pantalla, fotos o assets existentes.</p>

        <div class="tip-box">
            <strong>🎯 Objetivo principal:</strong> Tomar cualquier textura observada dentro de
                un juego o captura en ángulo trapezoidal, rectificarla matemáticamente como
                ortogonal plana, acumularla en un Texture Atlas interactivo, ajustar su tamaño
                y bordes a gusto, y exportarla lista para Unity, Godot, Unreal Engine o
                Blender.
        </div>

        <h2>Módulos integrados</h2>
        <ul>
            <li><strong>📷 Texture Ripper:</strong> Pegado instantáneo con <code>Ctrl+V</code>,
                selección trapezoidal de 4 vértices con lupa de alta precisión en tiempo real,
                corrección proyectiva (homografía) e interpolación Lanczos4.</li>
            <li><strong>🧩 Sprites y Compositor de Atlas:</strong> Composición interactiva sobre
                lienzo de potencia de dos (POT), transformación libre de texturas
                (redimensionamiento por vértices y bordes), imán magnético (snapping),
                rotaciones, duplicación y empaquetado MaxRects óptimo.</li>
            <li><strong>🔁 Preparación y Mosaico (Seamless):</strong> Conversión a patrones
                repetibles sin costuras con síntesis inteligente de bordes, aplanamiento de
                sombras e iluminación irregular y visor 3×3.</li>
            <li><strong>✨ Mapas PBR y Normales:</strong> Generación de Normales (DirectX /
                OpenGL), Rugosidad (Roughness), Altura (Height) y Oclusión Ambiental (AO) con
                visor 3D en tiempo real.</li>
        </ul>
    """,
    "workflow": f"""{HTML_STYLE}
        <h1>🚀 Flujo de Trabajo Completo (Pipeline)</h1>
        <p>A continuación se describe el ciclo de trabajo típico recomendado para aprovechar al
            máximo todas las herramientas:</p>

        <p><span class="step-num">1</span> <strong>Captura de pantalla:</strong> Tomá una
            captura de cualquier juego o imagen de referencia usando <code>Win+Shift+S</code> o
            <code>Impr Pant</code>.</p>
        <p><span class="step-num">2</span> <strong>Pegado directo:</strong> Presioná
            <code>Ctrl+V</code> en IV Orbit Texture Studio. La captura se cargará de inmediato
            en el Texture Ripper.</p>
        <p><span class="step-num">3</span> <strong>Ajuste de perspectiva:</strong> Ubicá los 4
            vértices cian en las 4 esquinas de la textura usando la lupa para precisión a nivel
            de píxel.</p>
        <p><span class="step-num">4</span> <strong>Añadir al Atlas:</strong> Presioná el botón
            <code>➕ Añadir al Atlas</code> (o <code>Ctrl+Shift+A</code>). La textura se
            rectificará e integrará automáticamente al Atlas sin pisar a las demás.</p>
        <p><span class="step-num">5</span> <strong>Acomodar y redimensionar:</strong> En el
            Compositor de Atlas, ajustá el tamaño arrastrando los vértices o bordes con el
            ratón. Ubicalas como prefieras o usá <code>Auto-empaquetar (MaxRects)</code>.</p>
        <p><span class="step-num">6</span> <strong>PBR y Mosaico (opcional):</strong> Enviá la
            textura a Preparación para volverla seamless o generá mapas PBR con
            previsualización 3D.</p>
        <p><span class="step-num">7</span> <strong>Exportación:</strong> Guardá tu atlas en PNG
            con sus metadatos (JSON, Unity, Godot o CSS) con un solo clic.</p>
    """,
    "tutorial_ripper": f"""{HTML_STYLE}
        <h1>🎓 Tutorial 1: Extraer y Rectificar Texturas con Texture Ripper</h1>
        <p>Aprendé a extraer una textura limpia y plana a partir de una superficie vista en
            perspectiva oblicua:</p>

        <h2>Pasos detallados</h2>
        <p><span class="step-num">1</span> <strong>Pegar la imagen:</strong> Usá
            <code>Ctrl+V</code> para pegar desde el portapapeles o Menú <code>Archivo → Abrir
            imagen…</code>.</p>
        <p><span class="step-num">2</span> <strong>Posicionar los 4 puntos:</strong>
            Hacé clic y arrastrá cada manija circular hacia las cuatro esquinas de la textura
                que querés extraer:
            <ul>
                <li><strong>Superior-Izquierda (TL)</strong></li>
                <li><strong>Superior-Derecha (TR)</strong></li>
                <li><strong>Inferior-Derecha (BR)</strong></li>
                <li><strong>Inferior-Izquierda (BL)</strong></li>
            </ul>
        </p>
        <p><span class="step-num">3</span> <strong>Uso de la Lupa de Precisión:</strong>
            Al arrastrar cualquier vértice, en la esquina inferior izquierda del lienzo
                aparecerá automáticamente una <strong>lupa de aumento 4×</strong> con retícula
                central. Mirala para situar el punto exactamente en la junta del azulejo o
                ladrillo.
        </p>
        <p><span class="step-num">4</span> <strong>Definir dimensiones de salida:</strong>
            En el panel lateral derecho (Texture Ripper), podés seleccionar resoluciones
                predefinidas (512×512, 1024×1024, 2048×2048) o escribir un tamaño
                personalizado.
        </p>
        <p><span class="step-num">5</span> <strong>Añadir al Atlas o Exportar:</strong>
            <ul>
                <li>Hacé clic en <code>➕ Añadir al Atlas</code> (<code>Ctrl+Shift+A</code>)
                    para ir armando tu atlas de texturas.</li>
                <li>Hacé clic en <code>Exportar textura rectificada…</code>
                    (<code>Ctrl+E</code>) si solo necesitás el archivo individual.</li>
            </ul>
        </p>

        <div class="tip-box">
            <strong>💡 Consejo:</strong> Si la textura es plana de frente, podés presionar
                <code>Ajustar selección a las esquinas</code> en el menú Editar para abarcar
                toda la imagen al instante.
        </div>
    """,
    "tutorial_atlas": f"""{HTML_STYLE}
        <h1>🎓 Tutorial 2: Compositor de Atlas y Transformación Libre</h1>
        <p>El Compositor de Atlas te permite reunir y organizar texturas en una sola hoja
            unificada con control total sobre su escala y posición:</p>

        <h2>Transformación Libre con el Ratón</h2>
        <p>Al seleccionar cualquier textura en el lienzo del Atlas, verás su marco cian con
            <strong>8 manijas interactivas</strong>:</p>
        <ul>
            <li><strong>4 Vértices / Esquinas (NW, NE, SE, SW):</strong> Arrastrá cualquier
                esquina para modificar el ancho y el alto simultáneamente.</li>
            <li><strong>4 Bordes (N, S, W, E):</strong> Arrastrá cualquier borde para ensanchar
                o estirar la textura en ese eje exclusivo.</li>
            <li><strong>Mantener relación de aspecto:</strong> Mantené presionada la tecla
                <code>Shift</code> mientras arrastrás para que la textura crezca o se encoja
                proporcionalmente.</li>
            <li><strong>Botón 🔒 / 🔓 en el panel:</strong> Bloquea la proporción permanentemente
                si lo preferís.</li>
            <li><strong>Botón ↺ Original:</strong> Restaura la textura a sus dimensiones
                originales sin perder resolución (el programa preserva los píxeles originales
                sin degradación acumulativa).</li>
        </ul>

        <h2>Posicionamiento y Snapping Magnético</h2>
        <ul>
            <li><strong>Arrastrar cuerpo:</strong> Hacé clic en el centro de la textura para
                moverla.</li>
            <li><strong>Ajuste magnético:</strong> La textura se imanta automáticamente a los
                bordes de otras texturas y a los límites del lienzo. Aparecerán <strong>guías
                fucsias</strong> indicando la alineación perfecta.</li>
            <li><strong>Desactivar imán temporalmente:</strong> Mantené presionada la tecla
                <code>Alt</code> mientras arrastrás para mover con libertad milimétrica.</li>
            <li><strong>Mover con teclado:</strong> Usá las flechas de dirección para mover 1
                px (o <code>Shift + Flechas</code> para mover 10 px).</li>
        </ul>

        <h2>Transformaciones Rápidas</h2>
        <ul>
            <li><code>R</code>: Rotar 90° horario (con <code>Shift</code>: antihorario).</li>
            <li><code>H</code> / <code>V</code>: Voltear horizontalmente o verticalmente.</li>
            <li><code>Ctrl+D</code>: Duplicar textura seleccionada en un hueco libre del
                lienzo.</li>
            <li><code>Supr</code> o <code>Retroceso</code>: Eliminar textura.</li>
            <li><code>Ctrl+Z</code> / <code>Ctrl+Y</code>: Deshacer y Rehacer ilimitado para
                cualquier movimiento o cambio de tamaño.</li>
        </ul>

        <h2>Auto-empaquetado (MaxRects)</h2>
        <p>Hacé clic en el botón <code>⚡ Auto-empaquetar (MaxRects)</code> para que el
            algoritmo ordene todas las piezas automáticamente optimizando el espacio y
            asegurando cero solapamientos.</p>
    """,
    "tutorial_pbr": f"""{HTML_STYLE}
        <h1>🎓 Tutorial 3: Mosaicos Seamless y Mapas PBR</h1>
        <p>Convertí cualquier textura extraída en un material para motores 3D modernos:</p>

        <h2>1. Preparación y Mosaico (Seamless)</h2>
        <ul>
            <li>Cambiá a la pestaña <strong>Preparación y Mosaico</strong>.</li>
            <li>Ajustá el ancho de borde de transición (Fade Margin) y activá el modo
                Seamless.</li>
            <li>El visor mostrará una repetición 3×3 para que verifiques que las costuras
                desaparezcan por completo.</li>
            <li>Usá la herramienta de <strong>Eliminación de Iluminación</strong> si la foto
                original tenía sombras o gradientes de luz solar.</li>
        </ul>

        <h2>2. Mapas PBR (Normal, Roughness, Height, AO)</h2>
        <ul>
            <li>Cambiá a la pestaña <strong>Mapas PBR</strong>.</li>
            <li><strong>Normal Map:</strong> Generado con filtros derivados de Sobel/Scharr.
                Podés ajustar la intensidad y el formato del canal Y (OpenGL para
                Unity/Blender/Godot, DirectX invertido para Unreal Engine).</li>
            <li><strong>Roughness (Rugosidad):</strong> Define qué tan mate o reflectante es la
                superficie.</li>
            <li><strong>Height (Desplazamiento):</strong> Mapa de altura en escala de grises
                para parallax mapping o teselación.</li>
            <li><strong>AO (Ambient Occlusion):</strong> Simula las sombras de contacto en
                hendiduras y grietas.</li>
            <li><strong>Visor 3D:</strong> Rotá la esfera o cubo 3D con el ratón para ver cómo
                reacciona a la luz en tiempo real.</li>
            <li><strong>Exportar lote:</strong> Guardá los 4 mapas listos con sus nombres
                estándar (<code>_normal</code>, <code>_roughness</code>, etc.).</li>
        </ul>
    """,
    "shortcuts": f"""{HTML_STYLE}
        <h1>⌨️ Tabla Completa de Atajos de Teclado</h1>
        <p>Todos los atajos disponibles en la aplicación organizados por contexto:</p>

        <h2>Globales</h2>
        <table>
            <tr><th>Atajo</th><th>Acción</th></tr>
            <tr><td><code>Ctrl+V</code></td><td>Pegar captura de pantalla desde el
                portapapeles</td></tr>
            <tr><td><code>Ctrl+O</code></td><td>Abrir archivo de imagen desde disco</td></tr>
            <tr><td><code>Ctrl+Shift+O</code></td><td>Abrir proyecto existente
                (.ivtex)</td></tr>
            <tr><td><code>Ctrl+S</code></td><td>Guardar proyecto (.ivtex)</td></tr>
            <tr><td><code>Ctrl+Shift+S</code></td><td>Guardar proyecto como…</td></tr>
            <tr><td><code>Ctrl+Z</code></td><td>Deshacer la última acción</td></tr>
            <tr><td><code>Ctrl+Y</code> / <code>Ctrl+Shift+Z</code></td><td>Rehacer</td></tr>
            <tr><td><code>F1</code></td><td>Abrir este panel de Ayuda y Documentación</td></tr>
            <tr><td><code>Ctrl++</code> / <code>Ctrl+-</code></td><td>Acercar / Alejar zoom del
                lienzo</td></tr>
            <tr><td><code>Ctrl+0</code></td><td>Ajustar vista al tamaño de ventana</td></tr>
            <tr><td><code>Ctrl+1</code></td><td>Ver a tamaño real (100 %)</td></tr>
        </table>

        <h2>Texture Ripper</h2>
        <table>
            <tr><th>Atajo</th><th>Acción</th></tr>
            <tr><td><code>Ctrl+Shift+A</code></td><td>➕ Rectificar y añadir al Atlas</td></tr>
            <tr><td><code>Ctrl+E</code></td><td>Exportar textura rectificada
                individual</td></tr>
            <tr><td><code>Arrastrar vértice</code></td><td>Mover esquina con lupa de precisión
                4× activa</td></tr>
            <tr><td><code>Doble clic en vértice</code></td><td>Alinear esquina al cuadrante más
                cercano</td></tr>
        </table>

        <h2>Compositor de Atlas</h2>
        <table>
            <tr><th>Atajo</th><th>Acción</th></tr>
            <tr><td><code>Arrastrar manijas</code></td><td><strong>Transformación
                libre:</strong> redimensionar ancho/alto</td></tr>
            <tr><td><code>Shift + Arrastrar manija</code></td><td>Redimensionar
                <strong>conservando la relación de aspecto</strong></td></tr>
            <tr><td><code>Arrastrar centro</code></td><td>Mover textura por el lienzo con imán
                magnético</td></tr>
            <tr><td><code>Alt + Arrastrar</code></td><td>Mover libremente <strong>sin ajuste
                magnético (snapping)</strong></td></tr>
            <tr><td><code>Flechas de dirección</code></td><td>Mover textura seleccionada 1
                píxel</td></tr>
            <tr><td><code>Shift + Flechas</code></td><td>Mover textura seleccionada 10
                píxeles</td></tr>
            <tr><td><code>Ctrl+D</code></td><td>Duplicar la textura seleccionada en un hueco
                libre</td></tr>
            <tr><td><code>R</code></td><td>Rotar 90° en sentido horario</td></tr>
            <tr><td><code>Shift + R</code></td><td>Rotar 90° en sentido antihorario</td></tr>
            <tr><td><code>H</code></td><td>Voltear horizontalmente (espejo)</td></tr>
            <tr><td><code>V</code></td><td>Voltear verticalmente (espejo)</td></tr>
            <tr><td><code>Supr</code> / <code>Retroceso</code></td><td>Eliminar textura
                seleccionada del atlas</td></tr>
            <tr><td><code>Esc</code></td><td>Deseleccionar textura activa</td></tr>
        </table>
    """,
    "about": f"""{HTML_STYLE}
        <h1>ℹ️ Acerca de IV Orbit Texture Studio</h1>
        <p><strong>IV Orbit Texture Studio</strong> — Versión 0.1.0</p>
        <p>Desarrollado para agilizar radicalmente el pipeline de extracción y creación de
            texturas en el desarrollo de videojuegos.</p>
        <hr style="border: 0; border-top: 1px solid #30363d; margin: 15px 0;" />
        <p><strong>Tecnologías utilizadas:</strong></p>
        <ul>
            <li><strong>PySide6 (Qt 6):</strong> Interfaz gráfica moderna, soporte de
                aceleración por hardware y eventos táctiles/ratón.</li>
            <li><strong>OpenCV & NumPy:</strong> Algoritmos de homografía proyectiva,
                transformaciones afines, convoluciones Sobel/Scharr e interpolación
                Lanczos4.</li>
            <li><strong>Pillow:</strong> Carga y guardado de formatos de imagen universales
                (PNG, JPEG, WebP, BMP, TGA).</li>
            <li><strong>Formato .ivtex:</strong> Contenedor ZIP seguro con protección ZipSlip y
                guardado atómico.</li>
        </ul>
        <p style="color: #8b949e; font-size: 11px; margin-top: 20px;">© IV Orbit. Todos los
            derechos reservados.</p>
    """,
}


class HelpDialog(QDialog):
    """Diálogo completo de Ayuda, Documentación y Tutoriales interactivos."""

    demo_requested = Signal()

    def __init__(self, parent: QWidget | None = None, initial_page: str = "welcome") -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Documentación y Tutoriales — IV Orbit Texture Studio"))
        self.resize(920, 620)
        self.setMinimumSize(780, 480)
        self.setStyleSheet("""
            QDialog {
                background-color: #0d1117;
                color: #e6edf3;
            }
            QListWidget {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 6px;
                color: #c9d1d9;
                font-size: 13px;
                padding: 6px;
            }
            QListWidget::item {
                padding: 10px 12px;
                border-radius: 6px;
                margin-bottom: 3px;
            }
            QListWidget::item:hover {
                background-color: #21262d;
                color: #58a6ff;
            }
            QListWidget::item:selected {
                background-color: #1f6feb;
                color: #ffffff;
                font-weight: bold;
            }
            QTextBrowser {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 6px;
            }
            QPushButton {
                background-color: #21262d;
                border: 1px solid #30363d;
                border-radius: 6px;
                color: #c9d1d9;
                padding: 6px 14px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #30363d;
                color: #ffffff;
            }
            QPushButton#btn_demo {
                background-color: #238636;
                border: 1px solid #2ea043;
                color: #ffffff;
            }
            QPushButton#btn_demo:hover {
                background-color: #2ea043;
            }
        """)

        self._setup_ui()
        self.show_page(initial_page)

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(12)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 1. Lista lateral de navegación
        self._nav_list = QListWidget()
        self._nav_list.setFixedWidth(240)

        nav_items = [
            ("welcome", "🌟 Bienvenido"),
            ("workflow", "🚀 Flujo de Trabajo"),
            ("tutorial_ripper", "🎓 Tutorial: Texture Ripper"),
            ("tutorial_atlas", "🎓 Tutorial: Atlas y Escala"),
            ("tutorial_pbr", "🎓 Tutorial: Seamless y PBR"),
            ("shortcuts", "⌨️ Atajos de Teclado"),
            ("about", "ℹ️ Acerca de"),
        ]

        for key, title in nav_items:
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self._nav_list.addItem(item)

        self._nav_list.currentRowChanged.connect(self._on_nav_changed)
        splitter.addWidget(self._nav_list)

        # 2. Visor HTML de documentación
        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        splitter.addWidget(self._browser)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

        # 3. Barra inferior de acciones
        h_bottom = QHBoxLayout()
        self._btn_demo = QPushButton(self.tr("▶ Cargar Texturas de Muestra en el Atlas"))
        self._btn_demo.setObjectName("btn_demo")
        self._btn_demo.setToolTip(
            self.tr(
                "Carga 4 texturas de muestra en el Atlas para probar "
                "la transformación libre inmediatamente"
            )
        )
        self._btn_demo.clicked.connect(self._on_demo_clicked)

        self._btn_close = QPushButton(self.tr("Cerrar"))
        self._btn_close.clicked.connect(self.accept)

        h_bottom.addWidget(self._btn_demo)
        h_bottom.addStretch()
        h_bottom.addWidget(self._btn_close)
        main_layout.addLayout(h_bottom)

    def _on_nav_changed(self, row: int) -> None:
        item = self._nav_list.item(row)
        if item is not None:
            key = str(item.data(Qt.ItemDataRole.UserRole))
            html = DOCS_CONTENT.get(key, "<p>Contenido no disponible.</p>")
            self._browser.setHtml(html)

    def show_page(self, page_key: str) -> None:
        for idx in range(self._nav_list.count()):
            it = self._nav_list.item(idx)
            if it.data(Qt.ItemDataRole.UserRole) == page_key:
                self._nav_list.setCurrentRow(idx)
                break

    def _on_demo_clicked(self) -> None:
        self.demo_requested.emit()
        self.accept()
