"""Herramienta interactiva Texture Ripper para el lienzo."""

from __future__ import annotations

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
)

from iv_orbit_texture_studio.imaging.perspective import Quad
from iv_orbit_texture_studio.tools.texture_ripper.selection import (
    VERTEX_LABELS,
    SelectionModel,
    SelectionState,
)
from iv_orbit_texture_studio.ui.canvas.coordinate_mapper import CoordinateMapper, Point, Size

# Colores de la selección válida
COLOR_QUAD_FILL = QColor(0, 190, 255, 35)
COLOR_QUAD_STROKE = QColor(0, 220, 255, 240)
COLOR_HANDLE_FILL = QColor(30, 30, 30, 220)
COLOR_HANDLE_STROKE = QColor(0, 220, 255, 255)
COLOR_HANDLE_ACTIVE = QColor(255, 220, 40, 255)
COLOR_HANDLE_TEXT = QColor(255, 255, 255)

# Colores de la selección inválida
COLOR_INVALID_FILL = QColor(255, 60, 60, 45)
COLOR_INVALID_STROKE = QColor(255, 70, 70, 240)

# Geometría de asas
HANDLE_RADIUS = 9.0
HANDLE_RADIUS_HOVER = 12.0
HIT_RADIUS = 16.0


class TextureRipperTool(QObject):
    """Controla la interacción y el dibujo del cuadrilátero sobre el lienzo."""

    selection_changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.selection = SelectionModel()
        self._mouse_screen_pos: QPointF | None = None
        self._image_size: Size | None = None

    def set_image_size(self, size: Size | None) -> None:
        self._image_size = size
        if size is not None and self.selection.state == SelectionState.EMPTY:
            # Inicializar por defecto cuadrilátero con margen del 10%
            self.selection.init_default_rect(size, margin_ratio=0.10)
            self.selection_changed.emit()

    def set_quad(self, quad: Quad) -> None:
        self.selection.set_quad(quad)
        self.selection_changed.emit()

    def reset_to_default(self) -> None:
        if self._image_size is not None:
            self.selection.init_default_rect(self._image_size, margin_ratio=0.10)
            self.selection_changed.emit()

    def clear(self) -> None:
        self.selection.clear()
        self.selection_changed.emit()

    # -------------------------------------------------------- eventos de ratón
    def handle_mouse_press(
        self,
        event: QMouseEvent,
        mapper: CoordinateMapper,
    ) -> bool:
        """Procesa clic del ratón. Retorna True si consumió el evento."""
        if self._image_size is None or event.button() != Qt.MouseButton.LeftButton:
            return False

        pos = event.position()
        scr_pt = Point(pos.x(), pos.y())
        img_pt = mapper.screen_to_image(scr_pt)

        # 1. Comprobar si se hizo clic sobre un vértice existente para arrastrarlo
        hit = self.selection.hit_test_vertex(scr_pt, mapper, radius_screen_px=HIT_RADIUS)
        if hit is not None:
            self.selection.dragged_index = hit
            self.selection_changed.emit()
            return True

        # 2. Si la selección está incompleta, agregar un nuevo punto
        if self.selection.state != SelectionState.COMPLETE:
            # Clampear a los límites de la imagen
            cx = min(max(img_pt.x, 0.0), self._image_size.width)
            cy = min(max(img_pt.y, 0.0), self._image_size.height)
            self.selection.add_point(Point(cx, cy))
            self.selection_changed.emit()
            return True

        return False

    def handle_mouse_move(
        self,
        event: QMouseEvent,
        mapper: CoordinateMapper,
    ) -> bool:
        """Procesa movimiento del ratón. Retorna True si consumió el evento."""
        pos = event.position()
        self._mouse_screen_pos = pos
        scr_pt = Point(pos.x(), pos.y())

        # Si estamos arrastrando un vértice
        dragged = self.selection.dragged_index
        if dragged is not None and self._image_size is not None:
            img_pt = mapper.screen_to_image(scr_pt)
            # Clampear a los límites de la imagen
            cx = min(max(img_pt.x, 0.0), self._image_size.width)
            cy = min(max(img_pt.y, 0.0), self._image_size.height)
            self.selection.move_vertex(dragged, Point(cx, cy))
            self.selection_changed.emit()
            return True

        # Actualizar índice en hover
        old_hover = self.selection.hovered_index
        new_hover = self.selection.hit_test_vertex(scr_pt, mapper, radius_screen_px=HIT_RADIUS)
        if old_hover != new_hover:
            self.selection.hovered_index = new_hover
            self.selection_changed.emit()

        return dragged is not None

    def handle_mouse_release(
        self,
        event: QMouseEvent,
        mapper: CoordinateMapper,
    ) -> bool:
        """Finaliza el arrastre."""
        if self.selection.dragged_index is not None:
            self.selection.dragged_index = None
            self.selection_changed.emit()
            return True
        return False

    def handle_key_press(self, event: QKeyEvent) -> bool:
        if event.key() == Qt.Key.Key_Escape and self.selection.state == SelectionState.COLLECTING:
            self.clear()
            return True
        return False

    # --------------------------------------------------------- cursor sugerido
    def get_cursor(self) -> Qt.CursorShape | None:
        if self.selection.dragged_index is not None:
            return Qt.CursorShape.ClosedHandCursor
        if self.selection.hovered_index is not None:
            return Qt.CursorShape.SizeAllCursor
        if self.selection.state != SelectionState.COMPLETE and self._image_size is not None:
            return Qt.CursorShape.CrossCursor
        return None

    # ----------------------------------------------------------------- dibujo
    def paint_overlay(self, painter: QPainter, mapper: CoordinateMapper) -> None:
        pts = self.selection.points
        if not pts:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        screen_pts = [mapper.image_to_screen(p) for p in pts]
        qpoints = [QPointF(sp.x, sp.y) for sp in screen_pts]

        is_complete = self.selection.state == SelectionState.COMPLETE
        is_valid = self.selection.is_valid() if is_complete else True

        stroke_color = COLOR_QUAD_STROKE if is_valid else COLOR_INVALID_STROKE
        fill_color = COLOR_QUAD_FILL if is_valid else COLOR_INVALID_FILL

        # 1. Dibujar polígono o líneas conectoras
        if len(qpoints) >= 2:
            path = QPainterPath()
            path.moveTo(qpoints[0])
            for qp in qpoints[1:]:
                path.lineTo(qp)
            if is_complete:
                path.closeSubpath()
                painter.fillPath(path, QBrush(fill_color))

            # Contorno con sombra suave para visibilidad sobre fondos claros u oscuros
            shadow_pen = QPen(QColor(0, 0, 0, 160), 3.5)
            painter.setPen(shadow_pen)
            painter.drawPath(path)

            pen = QPen(stroke_color, 2.0)
            painter.setPen(pen)
            painter.drawPath(path)

        # 2. Si está en colección (1..3 puntos), dibujar línea guía punteada al cursor
        if not is_complete and self._mouse_screen_pos is not None and len(qpoints) > 0:
            guide_pen = QPen(COLOR_QUAD_STROKE, 1.5, Qt.PenStyle.DashLine)
            painter.setPen(guide_pen)
            painter.drawLine(qpoints[-1], self._mouse_screen_pos)

        # 3. Dibujar asas de los vértices
        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)

        for i, qp in enumerate(qpoints):
            is_hovered = self.selection.hovered_index == i
            is_dragged = self.selection.dragged_index == i
            active = is_hovered or is_dragged

            r = HANDLE_RADIUS_HOVER if active else HANDLE_RADIUS

            # Sombra del asa
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 120))
            painter.drawEllipse(qp, r + 1.5, r + 1.5)

            # Fondo del asa
            painter.setBrush(COLOR_HANDLE_ACTIVE if active else COLOR_HANDLE_FILL)
            stroke = COLOR_HANDLE_FILL if active else (stroke_color)
            painter.setPen(QPen(stroke, 2.0))
            painter.drawEllipse(qp, r, r)

            # Número del vértice
            text_color = QColor(0, 0, 0) if active else COLOR_HANDLE_TEXT
            painter.setPen(text_color)
            label = str(i + 1)
            rect = QRectF(qp.x() - r, qp.y() - r, r * 2, r * 2)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

            # Etiqueta de coordenadas (si está activo o es hover)
            if active:
                img_p = pts[i]
                coord_text = f"{VERTEX_LABELS[i]} ({int(round(img_p.x))}, {int(round(img_p.y))})"
                metrics = painter.fontMetrics()
                tw = metrics.horizontalAdvance(coord_text) + 12
                th = metrics.height() + 4
                tag_rect = QRectF(qp.x() + r + 6, qp.y() - th / 2, tw, th)

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(0, 0, 0, 200))
                painter.drawRoundedRect(tag_rect, 4.0, 4.0)

                painter.setPen(QColor(255, 255, 255))
                painter.drawText(tag_rect, Qt.AlignmentFlag.AlignCenter, coord_text)

        painter.restore()
