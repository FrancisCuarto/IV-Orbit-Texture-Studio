"""Herramienta interactiva para gestión, visualización y edición de sprites en el lienzo.

Gestiona las regiones rectangulares de sprites, la selección activa, los puntos
de ancla/pivote y la interacción con ratón y teclado sobre el lienzo.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QKeyEvent, QMouseEvent, QPainter, QPen

from iv_orbit_texture_studio.core.region import Pivot, Rect, SpriteRegion
from iv_orbit_texture_studio.imaging.sprites import (
    detect_sprites_by_transparency,
)
from iv_orbit_texture_studio.ui.canvas.coordinate_mapper import CoordinateMapper, Point, Size

if TYPE_CHECKING:
    import numpy as np

COLOR_SEL_BORDER = QColor(0, 210, 255, 240)
COLOR_SEL_FILL = QColor(0, 210, 255, 35)
COLOR_UNSEL_BORDER = QColor(255, 190, 40, 200)
COLOR_UNSEL_FILL = QColor(255, 190, 40, 15)
COLOR_PIVOT = QColor(255, 70, 70, 240)
COLOR_BADGE_BG = QColor(20, 25, 35, 210)
COLOR_BADGE_TXT = QColor(255, 255, 255, 240)

HANDLE_SIZE = 8.0
HIT_RADIUS = 16.0


class SpriteTool(QObject):
    """Herramienta de sprites: dibuja regiones y pivotes, y procesa eventos de ratón."""

    sprites_changed = Signal()
    selected_sprite_changed = Signal(str)  # sprite_id o "" si ninguno

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._sprites: list[SpriteRegion] = []
        self._selected_id: str | None = None
        self._image_size: Size | None = None

        # Estado de interacción de arrastre
        self._drag_mode: str | None = None  # "move", "resize_tl", "resize_br", "create", "pivot"
        self._drag_start_screen: QPointF | None = None
        self._drag_orig_rect: Rect | None = None
        self._create_start_img: Point | None = None

    # ------------------------------------------------------------- propiedades
    @property
    def sprites(self) -> tuple[SpriteRegion, ...]:
        return tuple(self._sprites)

    @property
    def selected_id(self) -> str | None:
        return self._selected_id

    @property
    def selected_sprite(self) -> SpriteRegion | None:
        if self._selected_id is None:
            return None
        for s in self._sprites:
            if s.id == self._selected_id:
                return s
        return None

    def set_image_size(self, size: Size | None) -> None:
        self._image_size = size

    # ------------------------------------------------------------- operaciones
    def set_sprites(self, sprites: list[SpriteRegion]) -> None:
        """Reemplaza la lista completa de sprites."""
        self._sprites = list(sprites)
        if self._selected_id is not None and not any(
            s.id == self._selected_id for s in self._sprites
        ):
            self._selected_id = self._sprites[0].id if self._sprites else None
            self.selected_sprite_changed.emit(self._selected_id or "")
        self.sprites_changed.emit()

    def select_sprite(self, sprite_id: str | None) -> None:
        """Selecciona un sprite por su ID."""
        if self._selected_id != sprite_id:
            self._selected_id = sprite_id
            self.selected_sprite_changed.emit(sprite_id or "")
            self.sprites_changed.emit()

    def add_sprite(self, rect: Rect, name: str | None = None) -> SpriteRegion:
        """Agrega manualmente un nuevo sprite."""
        idx = len(self._sprites) + 1
        sprite_name = name or f"sprite_{idx:02d}"
        sprite = SpriteRegion.create(sprite_name, rect)
        self._sprites.append(sprite)
        self._selected_id = sprite.id
        self.selected_sprite_changed.emit(sprite.id)
        self.sprites_changed.emit()
        return sprite

    def remove_sprite(self, sprite_id: str) -> bool:
        """Elimina el sprite con el ID especificado."""
        for idx, s in enumerate(self._sprites):
            if s.id == sprite_id:
                del self._sprites[idx]
                if self._selected_id == sprite_id:
                    self._selected_id = self._sprites[0].id if self._sprites else None
                    self.selected_sprite_changed.emit(self._selected_id or "")
                self.sprites_changed.emit()
                return True
        return False

    def remove_selected(self) -> bool:
        if self._selected_id is not None:
            return self.remove_sprite(self._selected_id)
        return False

    def clear(self) -> None:
        """Elimina todos los sprites."""
        if self._sprites:
            self._sprites.clear()
            self._selected_id = None
            self.selected_sprite_changed.emit("")
            self.sprites_changed.emit()

    def rename_sprite(self, sprite_id: str, new_name: str) -> bool:
        """Renombra un sprite."""
        clean_name = new_name.strip()
        if not clean_name:
            return False
        for s in self._sprites:
            if s.id == sprite_id:
                s.name = clean_name
                self.sprites_changed.emit()
                return True
        return False

    def set_sprite_pivot(self, sprite_id: str, pivot: Pivot) -> bool:
        """Actualiza el pivote de un sprite."""
        for s in self._sprites:
            if s.id == sprite_id:
                s.pivot = pivot
                self.sprites_changed.emit()
                return True
        return False

    def update_sprite_rect(self, sprite_id: str, rect: Rect) -> bool:
        """Actualiza el rectángulo de un sprite."""
        for s in self._sprites:
            if s.id == sprite_id:
                s.rect = rect
                self.sprites_changed.emit()
                return True
        return False

    def auto_detect(
        self,
        image_pixels: np.ndarray,
        alpha_threshold: int = 10,
        min_area: int = 4,
        padding: int = 0,
    ) -> int:
        """Detecta automáticamente los sprites en la imagen y actualiza la lista."""
        detected_rects = detect_sprites_by_transparency(
            image_pixels,
            alpha_threshold=alpha_threshold,
            min_area=min_area,
            padding=padding,
        )

        new_sprites: list[SpriteRegion] = []
        for idx, r in enumerate(detected_rects, start=1):
            name = f"sprite_{idx:02d}"
            new_sprites.append(SpriteRegion.create(name, r))

        self.set_sprites(new_sprites)
        return len(new_sprites)

    # ------------------------------------------------------------- hit testing
    def _hit_test_sprite(self, img_pt: Point) -> str | None:
        """Devuelve el ID del sprite bajo la coordenada de imagen (en orden inverso de apilado)."""
        for s in reversed(self._sprites):
            if s.rect.contains_point(img_pt.x, img_pt.y):
                return s.id
        return None

    # -------------------------------------------------------- eventos de ratón
    def handle_mouse_press(
        self,
        event: QMouseEvent,
        mapper: CoordinateMapper,
    ) -> bool:
        if self._image_size is None or event.button() != Qt.MouseButton.LeftButton:
            return False

        pos = event.position()
        scr_pt = Point(pos.x(), pos.y())
        img_pt = mapper.screen_to_image(scr_pt)

        # 1. Comprobar si se hizo clic sobre un sprite existente
        hit_id = self._hit_test_sprite(img_pt)
        if hit_id is not None:
            self.select_sprite(hit_id)
            self._drag_mode = "move"
            self._drag_start_screen = pos
            curr = self.selected_sprite
            if curr is not None:
                self._drag_orig_rect = curr.rect
            return True

        # 2. Clic en espacio vacío: iniciar creación de nuevo sprite con arrastre
        # Asegurar límites dentro de la imagen
        ix = max(0.0, min(img_pt.x, float(self._image_size.width)))
        iy = max(0.0, min(img_pt.y, float(self._image_size.height)))
        self._create_start_img = Point(ix, iy)
        self._drag_mode = "create"
        self._drag_start_screen = pos
        return True

    def handle_mouse_move(
        self,
        event: QMouseEvent,
        mapper: CoordinateMapper,
    ) -> bool:
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            if self._drag_mode is not None:
                self.handle_mouse_release(event, mapper)
            return False

        if self._drag_mode is None or self._drag_start_screen is None:
            return False

        pos = event.position()
        scr_pt = Point(pos.x(), pos.y())
        img_pt = mapper.screen_to_image(scr_pt)

        if (
            self._drag_mode == "move"
            and self._selected_id is not None
            and self._drag_orig_rect is not None
        ):
            orig = self._drag_orig_rect
            start_img = mapper.screen_to_image(
                Point(self._drag_start_screen.x(), self._drag_start_screen.y())
            )
            dx = int(round(img_pt.x - start_img.x))
            dy = int(round(img_pt.y - start_img.y))

            nx = max(0, orig.x + dx)
            ny = max(0, orig.y + dy)
            if self._image_size is not None:
                nx = min(nx, int(self._image_size.width) - orig.width)
                ny = min(ny, int(self._image_size.height) - orig.height)

            new_rect = Rect(max(0, nx), max(0, ny), orig.width, orig.height)
            self.update_sprite_rect(self._selected_id, new_rect)
            return True

        elif (
            self._drag_mode == "create"
            and self._create_start_img is not None
            and self._image_size is not None
        ):
            x1 = self._create_start_img.x
            y1 = self._create_start_img.y
            x2 = max(0.0, min(img_pt.x, float(self._image_size.width)))
            y2 = max(0.0, min(img_pt.y, float(self._image_size.height)))

            min_x = int(min(x1, x2))
            min_y = int(min(y1, y2))
            w = max(1, int(abs(x2 - x1)))
            h = max(1, int(abs(y2 - y1)))

            # Para previsualizar mientras se arrastra
            if self.selected_sprite is not None and getattr(self, "_creating_temp", False):
                self.update_sprite_rect(self.selected_sprite.id, Rect(min_x, min_y, w, h))
            elif w > 4 and h > 4:
                # Crear nuevo sprite temporal
                self.add_sprite(Rect(min_x, min_y, w, h))
                self._creating_temp = True
            return True

        return False

    def handle_mouse_release(
        self,
        event: QMouseEvent,
        mapper: CoordinateMapper,
    ) -> bool:
        if self._drag_mode is not None:
            self._drag_mode = None
            self._drag_start_screen = None
            self._drag_orig_rect = None
            self._create_start_img = None
            if hasattr(self, "_creating_temp"):
                delattr(self, "_creating_temp")
            self.sprites_changed.emit()
            return True
        return False

    def handle_key_press(self, event: QKeyEvent) -> bool:
        if event.key() == Qt.Key.Key_Delete or event.key() == Qt.Key.Key_Backspace:
            return self.remove_selected()
        return False

    def get_cursor(self) -> Qt.CursorShape | None:
        if self._drag_mode == "move":
            return Qt.CursorShape.SizeAllCursor
        if self._drag_mode == "create":
            return Qt.CursorShape.CrossCursor
        return None

    # ---------------------------------------------------------------- pintura
    def paint_overlay(self, painter: QPainter, mapper: CoordinateMapper) -> None:
        """Dibuja las cajas delimitadoras de todos los sprites y sus pivotes."""
        if not self._sprites:
            return

        painter.save()
        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)

        for s in self._sprites:
            is_selected = s.id == self._selected_id
            border_color = COLOR_SEL_BORDER if is_selected else COLOR_UNSEL_BORDER
            fill_color = COLOR_SEL_FILL if is_selected else COLOR_UNSEL_FILL
            pen_width = 2.5 if is_selected else 1.2

            # Mapear coordenadas a pantalla
            tl = mapper.image_to_screen(Point(float(s.rect.x), float(s.rect.y)))
            br = mapper.image_to_screen(Point(float(s.rect.right), float(s.rect.bottom)))
            screen_rect = QRectF(tl.x, tl.y, br.x - tl.x, br.y - tl.y)

            # Relleno y contorno
            painter.setPen(QPen(border_color, pen_width))
            painter.setBrush(QBrush(fill_color))
            painter.drawRect(screen_rect)

            # Etiqueta con el nombre del sprite
            badge_text = f" {s.name} ({s.rect.width}x{s.rect.height}) "
            fm = painter.fontMetrics()
            tw = fm.horizontalAdvance(badge_text) + 6
            th = fm.height() + 2

            badge_rect = QRectF(screen_rect.left(), max(0.0, screen_rect.top() - th), tw, th)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(COLOR_BADGE_BG))
            painter.drawRoundedRect(badge_rect, 3, 3)

            painter.setPen(COLOR_SEL_BORDER if is_selected else COLOR_BADGE_TXT)
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, badge_text)

            # Dibujar punto de pivote
            piv_px, piv_py = s.pivot.pixel_coords(s.rect.width, s.rect.height)
            pivot_img = Point(s.rect.x + piv_px, s.rect.y + piv_py)
            pivot_screen = mapper.image_to_screen(pivot_img)

            p_rad = 4.0 if is_selected else 3.0
            painter.setPen(QPen(COLOR_PIVOT, 1.5))
            painter.setBrush(QBrush(COLOR_PIVOT))
            painter.drawEllipse(QPointF(pivot_screen.x, pivot_screen.y), p_rad, p_rad)

            # Pequeña cruz sobre el pivote
            cross_len = 6.0
            painter.drawLine(
                QPointF(pivot_screen.x - cross_len, pivot_screen.y),
                QPointF(pivot_screen.x + cross_len, pivot_screen.y),
            )
            painter.drawLine(
                QPointF(pivot_screen.x, pivot_screen.y - cross_len),
                QPointF(pivot_screen.x, pivot_screen.y + cross_len),
            )

        painter.restore()
