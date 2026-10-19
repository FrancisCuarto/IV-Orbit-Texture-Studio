"""Lienzo de visualización con zoom y desplazamiento.

El lienzo solo gestiona la interacción visual. La lógica de conversión de
coordenadas vive en :class:`CoordinateMapper`, que no depende de Qt.

Interacción actual (Fase 1):

* Rueda del ratón: zoom centrado en el cursor.
* Botón central, o barra espaciadora + botón izquierdo, o botón izquierdo:
  desplazamiento. En la Fase 2 el botón izquierdo se reservará para la
  herramienta activa; el botón central y la barra espaciadora seguirán
  desplazando.
"""

from __future__ import annotations

import contextlib

from PySide6.QtCore import QPoint, QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPixmap,
    QResizeEvent,
    QTransform,
    QWheelEvent,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from iv_orbit_texture_studio.ui.canvas.coordinate_mapper import CoordinateMapper, Point, Size

if False:  # TYPE_CHECKING
    from iv_orbit_texture_studio.tools.texture_ripper.tool import TextureRipperTool

#: Factor de zoom por "paso" de rueda (120 unidades de ``angleDelta``).
WHEEL_ZOOM_STEP = 1.25
#: Factor de zoom de los comandos Acercar / Alejar.
BUTTON_ZOOM_STEP = 1.25
#: Margen en píxeles de pantalla al ajustar la imagen a la ventana.
FIT_MARGIN = 16.0
#: A partir de este zoom se dibujan píxeles nítidos (vecino más cercano).
PIXELATED_ZOOM_THRESHOLD = 2.0

_BACKGROUND = QColor(45, 45, 48)
_CHECKER_LIGHT = QColor(204, 204, 204)
_CHECKER_DARK = QColor(153, 153, 153)
_CHECKER_CELL = 8


def _make_checker_brush() -> QBrush:
    tile = QPixmap(_CHECKER_CELL * 2, _CHECKER_CELL * 2)
    tile.fill(_CHECKER_LIGHT)
    painter = QPainter(tile)
    painter.fillRect(0, 0, _CHECKER_CELL, _CHECKER_CELL, _CHECKER_DARK)
    painter.fillRect(_CHECKER_CELL, _CHECKER_CELL, _CHECKER_CELL, _CHECKER_CELL, _CHECKER_DARK)
    painter.end()
    return QBrush(tile)


class ImageCanvas(QWidget):
    """Widget que muestra una imagen con navegación por zoom y desplazamiento."""

    #: Emitida cuando cambia el zoom o el desplazamiento. Argumento: zoom actual.
    view_changed = Signal(float)
    #: Posición del cursor en coordenadas de imagen (x, y, dentro_de_la_imagen).
    cursor_moved = Signal(float, float, bool)
    #: El cursor salió del lienzo o no hay imagen.
    cursor_left = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._mapper = CoordinateMapper()
        self._image: QImage | None = None
        self._image_size: Size | None = None
        self._fit_mode = True
        self._pan_anchor: QPointF | None = None
        self._space_held = False
        self._checker_brush: QBrush | None = None
        self._tool: TextureRipperTool | None = None

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAutoFillBackground(False)
        self.setAccessibleName(self.tr("Lienzo de imagen"))

    @property
    def tool(self) -> TextureRipperTool | None:
        return self._tool

    def set_tool(self, tool: TextureRipperTool | None) -> None:
        if self._tool is not None:
            with contextlib.suppress(RuntimeError, TypeError):
                self._tool.selection_changed.disconnect(self.update)
        self._tool = tool
        if self._tool is not None:
            self._tool.selection_changed.connect(self.update)
            if self._image_size is not None:
                self._tool.set_image_size(self._image_size)
        self.update()

    # ------------------------------------------------------------- propiedades
    @property
    def mapper(self) -> CoordinateMapper:
        return self._mapper

    @property
    def image_size(self) -> Size | None:
        return self._image_size

    @property
    def has_image(self) -> bool:
        return self._image is not None

    @property
    def fit_mode(self) -> bool:
        """``True`` mientras la vista se reajusta automáticamente al redimensionar."""
        return self._fit_mode

    def sizeHint(self) -> QSize:  # noqa: N802 (API de Qt)
        return QSize(800, 600)

    # ---------------------------------------------------------------- imagen
    def set_image(self, image: QImage) -> None:
        if image.isNull():
            raise ValueError("No se puede mostrar una imagen vacía")
        self._image = image
        self._image_size = Size(float(image.width()), float(image.height()))
        if self._tool is not None:
            self._tool.set_image_size(self._image_size)
        self.fit_to_view()

    def clear_image(self) -> None:
        self._image = None
        self._image_size = None
        if self._tool is not None:
            self._tool.set_image_size(None)
        self._mapper.reset()
        self._fit_mode = True
        self.update()
        self.cursor_left.emit()
        self.view_changed.emit(self._mapper.zoom)

    # ------------------------------------------------------------ navegación
    def _viewport(self) -> Size:
        return Size(float(max(self.width(), 1)), float(max(self.height(), 1)))

    def _view_center(self) -> Point:
        viewport = self._viewport()
        return Point(viewport.width / 2.0, viewport.height / 2.0)

    def _notify_view_changed(self) -> None:
        self.update()
        self.view_changed.emit(self._mapper.zoom)

    def fit_to_view(self) -> None:
        """Ajusta la imagen completa a la ventana y activa el reajuste automático."""
        if self._image_size is None:
            return
        self._mapper.fit(self._image_size, self._viewport(), margin=FIT_MARGIN)
        self._fit_mode = True
        self._notify_view_changed()

    def center_image(self) -> None:
        """Centra la imagen sin cambiar el zoom."""
        if self._image_size is None:
            return
        self._mapper.center(self._image_size, self._viewport())
        self._notify_view_changed()

    def set_zoom(self, zoom: float, anchor: Point | None = None) -> None:
        """Fija el zoom; por defecto alrededor del centro de la vista."""
        if self._image_size is None:
            return
        self._mapper.set_zoom(zoom, anchor if anchor is not None else self._view_center())
        self._fit_mode = False
        self._notify_view_changed()

    def actual_size(self) -> None:
        """Zoom 100 % centrado."""
        if self._image_size is None:
            return
        self._mapper.set_zoom(1.0, self._view_center())
        self._mapper.center(self._image_size, self._viewport())
        self._fit_mode = False
        self._notify_view_changed()

    def zoom_in(self) -> None:
        self.set_zoom(self._mapper.zoom * BUTTON_ZOOM_STEP)

    def zoom_out(self) -> None:
        self.set_zoom(self._mapper.zoom / BUTTON_ZOOM_STEP)

    def pan_by(self, dx: float, dy: float) -> None:
        if self._image_size is None:
            return
        self._mapper.pan(dx, dy)
        self._fit_mode = False
        self._notify_view_changed()

    # ---------------------------------------------------------------- pintura
    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 (API de Qt)
        painter = QPainter(self)
        painter.fillRect(self.rect(), _BACKGROUND)
        if self._image is None or self._image_size is None:
            painter.setPen(QColor(170, 170, 170))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                self.tr("Abrí una imagen con Archivo › Abrir imagen… (Ctrl+O)"),
            )
            painter.end()
            return

        top_left, bottom_right = self._mapper.image_rect_on_screen(self._image_size)
        image_rect = QRectF(
            QPointF(top_left.x, top_left.y), QPointF(bottom_right.x, bottom_right.y)
        )

        # Fondo de cuadros para visualizar la transparencia (en espacio de pantalla).
        if self._checker_brush is None:
            self._checker_brush = _make_checker_brush()
        painter.fillRect(image_rect, self._checker_brush)

        zoom = self._mapper.zoom
        offset = self._mapper.offset
        painter.setRenderHint(
            QPainter.RenderHint.SmoothPixmapTransform, zoom < PIXELATED_ZOOM_THRESHOLD
        )
        painter.setTransform(QTransform(zoom, 0.0, 0.0, zoom, offset.x, offset.y))
        painter.drawImage(QPointF(0.0, 0.0), self._image)

        # Dibujar superposición de la herramienta activa (vértices, cuadrilátero)
        if self._tool is not None:
            self._tool.paint_overlay(painter, self._mapper)

        painter.end()

    # ---------------------------------------------------------------- eventos
    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 (API de Qt)
        super().resizeEvent(event)
        if self._image_size is not None and self._fit_mode:
            self._mapper.fit(self._image_size, self._viewport(), margin=FIT_MARGIN)
            self._notify_view_changed()

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 (API de Qt)
        if self._image_size is None:
            event.ignore()
            return
        steps = event.angleDelta().y() / 120.0
        if steps == 0:
            event.ignore()
            return
        position = event.position()
        self._mapper.zoom_by(WHEEL_ZOOM_STEP**steps, Point(position.x(), position.y()))
        self._fit_mode = False
        self._notify_view_changed()
        self._emit_cursor(position)
        event.accept()

    def _is_pan_press(self, event: QMouseEvent) -> bool:
        button = event.button()
        return button == Qt.MouseButton.MiddleButton or self._space_held

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (API de Qt)
        if self._image_size is not None and self._is_pan_press(event):
            self._pan_anchor = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        if (
            self._image_size is not None
            and self._tool is not None
            and self._tool.handle_mouse_press(event, self._mapper)
        ):
            self.update()
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (API de Qt)
        position = event.position()
        if self._pan_anchor is not None:
            delta = position - self._pan_anchor
            self._pan_anchor = position
            self.pan_by(delta.x(), delta.y())
        elif self._tool is not None:
            handled = self._tool.handle_mouse_move(event, self._mapper)
            tool_cursor = self._tool.get_cursor()
            if tool_cursor is not None:
                self.setCursor(tool_cursor)
            else:
                self._update_idle_cursor()
            if handled:
                self.update()

        self._emit_cursor(position)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 (API de Qt)
        if self._pan_anchor is not None:
            self._pan_anchor = None
            self._update_idle_cursor()
            event.accept()
            return

        if self._tool is not None and self._tool.handle_mouse_release(event, self._mapper):
            self.update()
            self._update_idle_cursor()
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (API de Qt)
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_held = True
            self._update_idle_cursor()
            event.accept()
            return
        if self._tool is not None and self._tool.handle_key_press(event):
            self.update()
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:  # noqa: N802 (API de Qt)
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_held = False
            self._update_idle_cursor()
            event.accept()
            return
        super().keyReleaseEvent(event)

    def leaveEvent(self, event: object) -> None:  # noqa: N802 (API de Qt)
        self.cursor_left.emit()

    # --------------------------------------------------------------- helpers
    def _update_idle_cursor(self) -> None:
        if self._space_held:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.unsetCursor()

    def _emit_cursor(self, position: QPointF) -> None:
        if self._image_size is None:
            self.cursor_left.emit()
            return
        image_point = self._mapper.screen_to_image(Point(position.x(), position.y()))
        inside = (
            0.0 <= image_point.x < self._image_size.width
            and 0.0 <= image_point.y < self._image_size.height
        )
        self.cursor_moved.emit(image_point.x, image_point.y, inside)

    def screen_to_image(self, position: QPoint | QPointF) -> Point:
        """Atajo para convertir una posición del widget a coordenadas de imagen."""
        return self._mapper.screen_to_image(Point(float(position.x()), float(position.y())))
