"""Herramienta interactiva de lienzo para composición y ordenamiento manual de texturas en el Atlas.

Permite visualizar el lienzo del atlas final, seleccionar texturas individuales y arrastrarlas
libremente con el ratón para ubicarlas en cualquier posición (X, Y), con soporte de ajuste
magnético (snapping), detección visual de solapamientos y auto-empaquetado inteligente.
"""

from __future__ import annotations

import logging

import numpy as np
from numpy.typing import NDArray
from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QKeyEvent, QMouseEvent, QPainter, QPen

from iv_orbit_texture_studio.core.atlas_item import AtlasItem
from iv_orbit_texture_studio.core.region import Rect
from iv_orbit_texture_studio.imaging.atlas import auto_pack_atlas_items, composite_atlas_items
from iv_orbit_texture_studio.ui.canvas.coordinate_mapper import CoordinateMapper, Point

RgbaArray = NDArray[np.uint8]
logger = logging.getLogger(__name__)

COLOR_SELECTION = QColor(0, 210, 255, 240)
COLOR_SELECTION_FILL = QColor(0, 210, 255, 25)
COLOR_HOVER = QColor(255, 215, 0, 180)
COLOR_OVERLAP = QColor(255, 60, 60, 220)
COLOR_ATLAS_BORDER = QColor(100, 150, 240, 200)
COLOR_BADGE_BG = QColor(20, 24, 32, 220)
COLOR_BADGE_TXT = QColor(255, 255, 255, 240)
SNAP_THRESHOLD_PX = 8.0


class AtlasTool(QObject):
    """Herramienta de lienzo para acomodar texturas interactivamente dentro del Atlas."""

    atlas_changed = Signal()
    item_selected = Signal(str)  # item_id o ""
    item_moved = Signal(str, int, int)  # item_id, nuevo x, nuevo y

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._items: list[AtlasItem] = []
        self._atlas_width: int = 1024
        self._atlas_height: int = 1024
        self._selected_id: str | None = None
        self._hovered_id: str | None = None

        # Caché de composición
        self._composite_cache: RgbaArray | None = None

        # Estado de interacción de arrastre
        self._is_dragging: bool = False
        self._drag_start_item_pos: tuple[int, int] = (0, 0)
        self._drag_start_mouse_pos: tuple[float, float] = (0.0, 0.0)

    # ------------------------------------------------------------- propiedades
    @property
    def items(self) -> tuple[AtlasItem, ...]:
        return tuple(self._items)

    @property
    def atlas_width(self) -> int:
        return self._atlas_width

    @property
    def atlas_height(self) -> int:
        return self._atlas_height

    @property
    def selected_id(self) -> str | None:
        return self._selected_id

    @property
    def selected_item(self) -> AtlasItem | None:
        if self._selected_id is None:
            return None
        for item in self._items:
            if item.id == self._selected_id:
                return item
        return None

    @property
    def composite_pixels(self) -> RgbaArray:
        if self._composite_cache is None:
            self.rebuild_composite()
        assert self._composite_cache is not None
        return self._composite_cache

    # ----------------------------------------------------------------- gestión
    def set_atlas_dimensions(self, width: int, height: int) -> None:
        """Establece las dimensiones del lienzo del atlas."""
        w = max(32, min(width, 16384))
        h = max(32, min(height, 16384))
        if self._atlas_width != w or self._atlas_height != h:
            self._atlas_width = w
            self._atlas_height = h
            self.rebuild_composite()
            self.atlas_changed.emit()

    def set_items(self, items: list[AtlasItem]) -> None:
        """Reemplaza la lista completa de texturas del atlas."""
        self._items = list(items)
        if self._selected_id is not None and not any(
            it.id == self._selected_id for it in self._items
        ):
            self._selected_id = self._items[0].id if self._items else None
            self.item_selected.emit(self._selected_id or "")
        self.rebuild_composite()
        self.atlas_changed.emit()

    def add_item(self, item: AtlasItem, auto_place: bool = True) -> None:
        """Añade una textura al atlas."""
        if auto_place:
            # Buscar una ubicación donde no solape inmediatamente si es posible
            placed_rects = [it.rect for it in self._items]
            cur_x, cur_y = 4, 4
            candidate = Rect(cur_x, cur_y, item.width, item.height)
            while any(candidate.intersects(r) for r in placed_rects):
                cur_x += 16
                if cur_x + item.width > self._atlas_width:
                    cur_x = 4
                    cur_y += 16
                if cur_y + item.height > self._atlas_height:
                    break
                candidate = Rect(cur_x, cur_y, item.width, item.height)
            item.x = cur_x
            item.y = cur_y

        self._items.append(item)
        self._selected_id = item.id
        self.rebuild_composite()
        self.item_selected.emit(item.id)
        self.atlas_changed.emit()

    def remove_item(self, item_id: str) -> None:
        """Elimina una textura del atlas por su ID."""
        initial_len = len(self._items)
        self._items = [it for it in self._items if it.id != item_id]
        if len(self._items) != initial_len:
            if self._selected_id == item_id:
                self._selected_id = self._items[0].id if self._items else None
                self.item_selected.emit(self._selected_id or "")
            self.rebuild_composite()
            self.atlas_changed.emit()

    def select_item(self, item_id: str | None) -> None:
        """Selecciona una textura por su ID."""
        if self._selected_id != item_id:
            self._selected_id = item_id
            self.item_selected.emit(item_id or "")
            self.atlas_changed.emit()

    def clear(self) -> None:
        """Borra todas las texturas del atlas."""
        self._items.clear()
        self._selected_id = None
        self._hovered_id = None
        self.rebuild_composite()
        self.item_selected.emit("")
        self.atlas_changed.emit()

    def auto_pack(
        self,
        padding: int = 2,
        spacing: int = 2,
        power_of_two: bool = True,
        square: bool = False,
    ) -> None:
        """Acomoda automáticamente todas las texturas usando MaxRects con cero solapamientos."""
        if not self._items:
            return
        result = auto_pack_atlas_items(
            self._items,
            padding=padding,
            spacing=spacing,
            max_width=self._atlas_width,
            max_height=self._atlas_height,
            power_of_two=power_of_two,
            square=square,
        )
        self._atlas_width = result.width
        self._atlas_height = result.height
        self.rebuild_composite()
        self.atlas_changed.emit()

    def rebuild_composite(self) -> None:
        """Reconstruye el mapa composite RGBA con las posiciones actuales."""
        result = composite_atlas_items(self._items, self._atlas_width, self._atlas_height)
        self._composite_cache = result.image

    # ---------------------------------------------------------- eventos de ratón
    # ---------------------------------------------------------- eventos de ratón
    def _hit_test(self, px: float, py: float) -> AtlasItem | None:
        """Busca el item en (px, py) de arriba a abajo (orden inverso de lista)."""
        for item in reversed(self._items):
            if item.x <= px < item.x + item.width and item.y <= py < item.y + item.height:
                return item
        return None

    def handle_mouse_press(self, event: QMouseEvent, mapper: CoordinateMapper) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False

        pos = event.position()
        img_pt = mapper.screen_to_image(Point(pos.x(), pos.y()))
        hit = self._hit_test(img_pt.x, img_pt.y)

        if hit is not None:
            self._selected_id = hit.id
            self._is_dragging = True
            self._drag_start_item_pos = (hit.x, hit.y)
            self._drag_start_mouse_pos = (img_pt.x, img_pt.y)
            self.item_selected.emit(hit.id)
            self.atlas_changed.emit()
            return True

        # Clic fuera de cualquier textura deselecciona
        if self._selected_id is not None:
            self._selected_id = None
            self.item_selected.emit("")
            self.atlas_changed.emit()
        return False

    def mouse_press(self, pos: QPointF, mapper: CoordinateMapper, event: QMouseEvent) -> bool:
        """Alias retrocompatible."""
        return self.handle_mouse_press(event, mapper)

    def handle_mouse_move(self, event: QMouseEvent, mapper: CoordinateMapper) -> bool:
        pos = event.position()
        img_pt = mapper.screen_to_image(Point(pos.x(), pos.y()))

        if self._is_dragging and (event.buttons() & Qt.MouseButton.LeftButton):
            item = self.selected_item
            if item is None:
                self._is_dragging = False
                return False

            dx = img_pt.x - self._drag_start_mouse_pos[0]
            dy = img_pt.y - self._drag_start_mouse_pos[1]
            new_x = int(round(self._drag_start_item_pos[0] + dx))
            new_y = int(round(self._drag_start_item_pos[1] + dy))

            # Snapping magnético a los bordes del atlas (0 y atlas_dim - item_dim)
            if abs(new_x) <= SNAP_THRESHOLD_PX:
                new_x = 0
            elif abs(new_x + item.width - self._atlas_width) <= SNAP_THRESHOLD_PX:
                new_x = self._atlas_width - item.width

            if abs(new_y) <= SNAP_THRESHOLD_PX:
                new_y = 0
            elif abs(new_y + item.height - self._atlas_height) <= SNAP_THRESHOLD_PX:
                new_y = self._atlas_height - item.height

            # Snapping magnético respecto a otras texturas cercanas
            for other in self._items:
                if other.id == item.id:
                    continue
                # Alinear lado izquierdo con lado derecho de otro
                if abs(new_x - other.rect.right) <= SNAP_THRESHOLD_PX:
                    new_x = other.rect.right
                # Alinear lado derecho con lado izquierdo de otro
                elif abs(new_x + item.width - other.x) <= SNAP_THRESHOLD_PX:
                    new_x = other.x - item.width
                # Alinear lado superior con inferior de otro
                if abs(new_y - other.rect.bottom) <= SNAP_THRESHOLD_PX:
                    new_y = other.rect.bottom
                # Alinear lado inferior con superior de otro
                elif abs(new_y + item.height - other.y) <= SNAP_THRESHOLD_PX:
                    new_y = other.y - item.height

            if item.x != new_x or item.y != new_y:
                item.x = new_x
                item.y = new_y
                self.rebuild_composite()
                self.item_moved.emit(item.id, new_x, new_y)
                self.atlas_changed.emit()
            return True

        # Actualizar hover
        hit = self._hit_test(img_pt.x, img_pt.y)
        new_hover = hit.id if hit is not None else None
        if self._hovered_id != new_hover:
            self._hovered_id = new_hover
            self.atlas_changed.emit()

        return False

    def mouse_move(self, pos: QPointF, mapper: CoordinateMapper, event: QMouseEvent) -> bool:
        """Alias retrocompatible."""
        return self.handle_mouse_move(event, mapper)

    def handle_mouse_release(self, event: QMouseEvent, mapper: CoordinateMapper) -> bool:
        if self._is_dragging:
            self._is_dragging = False
            self.atlas_changed.emit()
            return True
        return False

    def mouse_release(self, pos: QPointF, mapper: CoordinateMapper, event: QMouseEvent) -> bool:
        """Alias retrocompatible."""
        return self.handle_mouse_release(event, mapper)

    def handle_key_press(self, event: QKeyEvent) -> bool:
        if (
            event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace)
            and self._selected_id is not None
        ):
            self.remove_item(self._selected_id)
            return True
        return False

    def key_press(self, event: QKeyEvent) -> bool:
        """Alias retrocompatible."""
        return self.handle_key_press(event)

    def get_cursor(self) -> Qt.CursorShape | None:
        if self._is_dragging:
            return Qt.CursorShape.ClosedHandCursor
        if self._hovered_id is not None:
            return Qt.CursorShape.OpenHandCursor
        return None

    # ------------------------------------------------------------- renderizado
    def paint_overlay(self, painter: QPainter, mapper: CoordinateMapper) -> None:
        """Dibuja bordes del atlas, contornos de selección y etiquetas."""
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # 1. Borde del límite del Atlas
        tl = mapper.image_to_screen(Point(0.0, 0.0))
        br = mapper.image_to_screen(Point(float(self._atlas_width), float(self._atlas_height)))
        atlas_rect = QRectF(tl.x, tl.y, br.x - tl.x, br.y - tl.y)

        pen_border = QPen(COLOR_ATLAS_BORDER, 1.5, Qt.PenStyle.DashLine)
        painter.setPen(pen_border)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(atlas_rect)

        # 2. Resaltar solapamientos entre elementos en rojo
        for i in range(len(self._items)):
            for j in range(i + 1, len(self._items)):
                it1 = self._items[i]
                it2 = self._items[j]
                if it1.rect.intersects(it2.rect):
                    # Dibujar advertencia en los dos rectángulos
                    for it in (it1, it2):
                        itl = mapper.image_to_screen(Point(float(it.x), float(it.y)))
                        ibr = mapper.image_to_screen(
                            Point(float(it.rect.right), float(it.rect.bottom))
                        )
                        pen_ov = QPen(COLOR_OVERLAP, 1.5, Qt.PenStyle.DotLine)
                        painter.setPen(pen_ov)
                        painter.drawRect(QRectF(itl.x, itl.y, ibr.x - itl.x, ibr.y - itl.y))

        # 3. Dibujar rectángulo de selección activa
        selected = self.selected_item
        if selected is not None:
            stl = mapper.image_to_screen(Point(float(selected.x), float(selected.y)))
            sbr = mapper.image_to_screen(
                Point(float(selected.rect.right), float(selected.rect.bottom))
            )
            sel_rect = QRectF(stl.x, stl.y, sbr.x - stl.x, sbr.y - stl.y)

            pen_sel = QPen(COLOR_SELECTION, 2.0)
            painter.setPen(pen_sel)
            painter.setBrush(QBrush(COLOR_SELECTION_FILL))
            painter.drawRect(sel_rect)

            # Manijas en las 4 esquinas
            handle_half = 4.0
            painter.setBrush(QBrush(COLOR_SELECTION))
            for hx, hy in [
                (sel_rect.left(), sel_rect.top()),
                (sel_rect.right(), sel_rect.top()),
                (sel_rect.left(), sel_rect.bottom()),
                (sel_rect.right(), sel_rect.bottom()),
            ]:
                painter.drawRect(
                    QRectF(hx - handle_half, hy - handle_half, handle_half * 2, handle_half * 2)
                )

            # Badge con información (Nombre | WxH | X, Y)
            font = QFont("Segoe UI", 9)
            font.setBold(True)
            painter.setFont(font)
            info_text = (
                f" {selected.name} | {selected.width}×{selected.height} px "
                f"| X:{selected.x} Y:{selected.y} "
            )
            metrics = painter.fontMetrics()
            txt_w = metrics.horizontalAdvance(info_text) + 8
            txt_h = metrics.height() + 4

            badge_rect = QRectF(sel_rect.left(), sel_rect.top() - txt_h - 4, txt_w, txt_h)
            if badge_rect.top() < 0:
                badge_rect.moveTop(sel_rect.top() + 4)

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(COLOR_BADGE_BG))
            painter.drawRoundedRect(badge_rect, 3, 3)

            painter.setPen(COLOR_BADGE_TXT)
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, info_text)

        painter.restore()
