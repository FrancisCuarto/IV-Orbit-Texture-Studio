"""Herramienta interactiva de lienzo para composición y ordenamiento manual de texturas en el Atlas.

Permite visualizar el lienzo del atlas final, seleccionar texturas individuales y arrastrarlas
libremente con el ratón para ubicarlas en cualquier posición (X, Y), con soporte de ajuste
magnético (snapping) con guías visuales, detección de solapamientos, auto-empaquetado,
transformaciones (rotar / voltear / duplicar) y un historial de Deshacer/Rehacer basado en
instantáneas.

Atajos de teclado (con el lienzo enfocado, en el Compositor de Atlas):

* Flechas: mover 1 px (con ``Shift``: 10 px).
* ``Ctrl+D``: duplicar la textura seleccionada.
* ``R`` / ``Shift+R``: rotar 90° horario / antihorario.
* ``H`` / ``V``: voltear horizontal / vertical.
* ``Supr`` / ``Retroceso``: eliminar.  ``Esc``: deseleccionar.
* Mantener ``Alt`` mientras se arrastra desactiva el ajuste magnético.
"""

from __future__ import annotations

import logging
import math
import re
import uuid
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QKeyEvent, QMouseEvent, QPainter, QPen

from iv_orbit_texture_studio.core.atlas_item import AtlasItem
from iv_orbit_texture_studio.core.region import Pivot, Rect
from iv_orbit_texture_studio.imaging.atlas import auto_pack_atlas_items, composite_atlas_items
from iv_orbit_texture_studio.ui.canvas.coordinate_mapper import CoordinateMapper, Point

RgbaArray = NDArray[np.uint8]
logger = logging.getLogger(__name__)

COLOR_SELECTION = QColor(0, 210, 255, 240)
COLOR_SELECTION_FILL = QColor(0, 210, 255, 25)
COLOR_HOVER = QColor(255, 215, 0, 180)
COLOR_OVERLAP = QColor(255, 60, 60, 220)
COLOR_OUT_OF_BOUNDS = QColor(255, 140, 0, 230)
COLOR_ATLAS_BORDER = QColor(100, 150, 240, 200)
COLOR_GUIDE = QColor(255, 0, 200, 220)
COLOR_BADGE_BG = QColor(20, 24, 32, 220)
COLOR_BADGE_TXT = QColor(255, 255, 255, 240)
SNAP_THRESHOLD_PX = 8.0
"""Distancia de ajuste magnético, en píxeles de *pantalla* (independiente del zoom)."""

MAX_ATLAS_DIM = 16384
MIN_ATLAS_DIM = 32
MIN_ITEM_DIM = 4


@dataclass(frozen=True, slots=True)
class _ItemState:
    id: str
    name: str
    pixels: RgbaArray
    x: int
    y: int
    pivot: Pivot
    source_pixels: RgbaArray | None = None


@dataclass(frozen=True, slots=True)
class AtlasSnapshot:
    """Instantánea inmutable del estado completo del atlas (para Deshacer/Rehacer).

    Los arreglos de píxeles se comparten por referencia: la herramienta nunca los modifica
    in situ (rotar/voltear/escalar generan arreglos nuevos), por lo que las instantáneas son
    baratas.
    """

    items: tuple[_ItemState, ...]
    width: int
    height: int
    selected_id: str | None

    def same_content(self, other: AtlasSnapshot) -> bool:
        """Compara el contenido relevante (ignora la selección)."""
        if self.width != other.width or self.height != other.height:
            return False
        if len(self.items) != len(other.items):
            return False
        for a, b in zip(self.items, other.items, strict=True):
            if (
                a.id != b.id
                or a.name != b.name
                or a.x != b.x
                or a.y != b.y
                or a.pivot != b.pivot
                or a.pixels is not b.pixels
                or a.pixels.shape != b.pixels.shape
                or a.source_pixels is not b.source_pixels
            ):
                return False
        return True


def _next_pot(value: int) -> int:
    p = 1
    while p < value:
        p <<= 1
    return p


class AtlasTool(QObject):
    """Herramienta de lienzo para acomodar texturas interactivamente dentro del Atlas."""

    atlas_changed = Signal()
    item_selected = Signal(str)  # item_id o ""
    item_moved = Signal(str, int, int)  # item_id, nuevo x, nuevo y
    item_resized = Signal(str, int, int)  # item_id, nuevo ancho, nuevo alto
    edit_committed = Signal(object, object, str, object)  # before, after, texto, merge_key

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
        self._drag_moved: bool = False
        self._drag_before: AtlasSnapshot | None = None
        self._drag_start_item_pos: tuple[int, int] = (0, 0)
        self._drag_start_mouse_pos: tuple[float, float] = (0.0, 0.0)
        self._guides: list[tuple[str, int]] = []  # ("v", x) / ("h", y)

        # Estado de redimensionamiento libre con manijas (esquinas y bordes)
        self._is_resizing: bool = False
        self._resize_moved: bool = False
        self._active_handle: str | None = None
        self._hover_handle: str | None = None
        self._resize_before: AtlasSnapshot | None = None
        self._resize_start_rect: tuple[int, int, int, int] = (0, 0, 0, 0)
        self._resize_start_mouse: tuple[float, float] = (0.0, 0.0)
        self._resize_start_ratio: float = 1.0
        self._lock_aspect_ratio: bool = False

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
        return self._find(self._selected_id)

    @property
    def composite_pixels(self) -> RgbaArray:
        if self._composite_cache is None:
            self.rebuild_composite()
        assert self._composite_cache is not None
        return self._composite_cache

    @property
    def is_dragging(self) -> bool:
        return self._is_dragging

    @property
    def is_resizing(self) -> bool:
        return self._is_resizing

    @property
    def lock_aspect_ratio(self) -> bool:
        return self._lock_aspect_ratio

    @lock_aspect_ratio.setter
    def lock_aspect_ratio(self, val: bool) -> None:
        self._lock_aspect_ratio = bool(val)

    def _find(self, item_id: str) -> AtlasItem | None:
        for item in self._items:
            if item.id == item_id:
                return item
        return None

    # --------------------------------------------------------- análisis/estado
    def overlapping_ids(self) -> set[str]:
        """IDs de las texturas que se solapan con al menos otra."""
        result: set[str] = set()
        for i in range(len(self._items)):
            ri = self._items[i].rect
            for j in range(i + 1, len(self._items)):
                if ri.intersects(self._items[j].rect):
                    result.add(self._items[i].id)
                    result.add(self._items[j].id)
        return result

    def out_of_bounds_ids(self) -> set[str]:
        """IDs de las texturas que quedan (total o parcialmente) fuera del lienzo."""
        return {
            it.id
            for it in self._items
            if it.x < 0
            or it.y < 0
            or it.x + it.width > self._atlas_width
            or it.y + it.height > self._atlas_height
        }

    def unique_name(self, base: str, exclude_id: str | None = None) -> str:
        """Devuelve ``base`` o ``base_2``, ``base_3``… si ya existe otra textura con ese nombre."""
        base = base.strip() or "textura"
        taken = {it.name for it in self._items if it.id != exclude_id}
        if base not in taken:
            return base
        stem = re.sub(r"_\d+$", "", base) or base
        n = 2
        while f"{stem}_{n}" in taken:
            n += 1
        return f"{stem}_{n}"

    # ------------------------------------------------------------- historial
    def snapshot(self) -> AtlasSnapshot:
        return AtlasSnapshot(
            items=tuple(
                _ItemState(
                    it.id,
                    it.name,
                    it.pixels,
                    it.x,
                    it.y,
                    it.pivot,
                    it.source_pixels,
                )
                for it in self._items
            ),
            width=self._atlas_width,
            height=self._atlas_height,
            selected_id=self._selected_id,
        )

    def restore(self, snap: object) -> None:
        """Restaura una instantánea (usado por Deshacer/Rehacer)."""
        assert isinstance(snap, AtlasSnapshot)
        self._is_dragging = False
        self._is_resizing = False
        self._active_handle = None
        self._hover_handle = None
        self._guides = []
        self._items = [
            AtlasItem(
                id=s.id,
                name=s.name,
                pixels=s.pixels,
                x=s.x,
                y=s.y,
                pivot=s.pivot,
                source_pixels=s.source_pixels,
            )
            for s in snap.items
        ]
        self._atlas_width = snap.width
        self._atlas_height = snap.height
        sel = snap.selected_id
        if sel is not None and self._find(sel) is None:
            sel = None
        self._selected_id = sel
        self._hovered_id = None
        self.rebuild_composite()
        self.item_selected.emit(sel or "")
        self.atlas_changed.emit()

    def _commit(self, before: AtlasSnapshot, text: str, merge_key: str | None = None) -> None:
        after = self.snapshot()
        if not before.same_content(after):
            self.edit_committed.emit(before, after, text, merge_key)

    # ----------------------------------------------------------------- gestión
    def set_atlas_dimensions(self, width: int, height: int) -> None:
        """Establece las dimensiones del lienzo del atlas."""
        w = max(MIN_ATLAS_DIM, min(width, MAX_ATLAS_DIM))
        h = max(MIN_ATLAS_DIM, min(height, MAX_ATLAS_DIM))
        if self._atlas_width != w or self._atlas_height != h:
            before = self.snapshot()
            self._atlas_width = w
            self._atlas_height = h
            self.rebuild_composite()
            self.atlas_changed.emit()
            self._commit(before, f"Cambiar lienzo a {w}×{h}")

    def set_items(self, items: list[AtlasItem]) -> None:
        """Reemplaza la lista completa de texturas del atlas (no se registra en el historial)."""
        self._items = list(items)
        if self._selected_id is not None and self._find(self._selected_id) is None:
            self._selected_id = self._items[0].id if self._items else None
            self.item_selected.emit(self._selected_id or "")
        self.rebuild_composite()
        self.atlas_changed.emit()

    def find_free_position(self, width: int, height: int, spacing: int = 2) -> tuple[int, int]:
        """Busca la posición libre más arriba/izquierda donde quepa un rectángulo ``w×h``.

        Usa como candidatos las esquinas derechas e inferiores de las texturas existentes
        (heurística *bottom-left*). Si no cabe en el lienzo actual devuelve una posición
        debajo de todo el contenido (el lienzo se ampliará después).
        """
        if not self._items:
            return (0, 0)
        rects = [it.rect for it in self._items]
        candidates: set[tuple[int, int]] = {(0, 0)}
        for r in rects:
            candidates.add((r.right + spacing, r.y))
            candidates.add((r.x, r.bottom + spacing))
            candidates.add((0, r.bottom + spacing))
            candidates.add((r.right + spacing, 0))

        def free(cx: int, cy: int) -> bool:
            cand = Rect(cx, cy, width + spacing, height + spacing)
            return not any(cand.intersects(r) for r in rects)

        for cx, cy in sorted(candidates, key=lambda p: (p[1], p[0])):
            if cx < 0 or cy < 0:
                continue
            if cx + width > self._atlas_width or cy + height > self._atlas_height:
                continue
            if free(cx, cy):
                return (cx, cy)

        # No cabe: debajo de todo
        bottom = max(r.bottom for r in rects)
        return (0, bottom + spacing)

    def add_item(self, item: AtlasItem, auto_place: bool = True) -> None:
        """Añade una textura al atlas, ubicándola en un hueco libre y ampliando el lienzo."""
        before = self.snapshot()
        item.name = self.unique_name(item.name)
        if auto_place:
            item.x, item.y = self.find_free_position(item.width, item.height)
            self._grow_to_fit_with(item)

        self._items.append(item)
        self._selected_id = item.id
        self.rebuild_composite()
        self.item_selected.emit(item.id)
        self.atlas_changed.emit()
        self._commit(before, f"Añadir '{item.name}' al atlas")

    def _grow_to_fit_with(self, item: AtlasItem) -> None:
        need_w = item.x + item.width
        need_h = item.y + item.height
        if need_w > self._atlas_width:
            self._atlas_width = min(MAX_ATLAS_DIM, _next_pot(need_w))
        if need_h > self._atlas_height:
            self._atlas_height = min(MAX_ATLAS_DIM, _next_pot(need_h))

    def remove_item(self, item_id: str) -> None:
        """Elimina una textura del atlas por su ID."""
        before = self.snapshot()
        idx = next((i for i, it in enumerate(self._items) if it.id == item_id), None)
        if idx is None:
            return
        removed = self._items.pop(idx)
        if self._selected_id == item_id:
            if self._items:
                self._selected_id = self._items[min(idx, len(self._items) - 1)].id
            else:
                self._selected_id = None
            self.item_selected.emit(self._selected_id or "")
        if self._hovered_id == item_id:
            self._hovered_id = None
        self.rebuild_composite()
        self.atlas_changed.emit()
        self._commit(before, f"Eliminar '{removed.name}'")

    def select_item(self, item_id: str | None) -> None:
        """Selecciona una textura por su ID."""
        if self._selected_id != item_id:
            self._selected_id = item_id
            self.item_selected.emit(item_id or "")
            self.atlas_changed.emit()

    def clear(self) -> None:
        """Borra todas las texturas del atlas."""
        before = self.snapshot()
        self._items.clear()
        self._selected_id = None
        self._hovered_id = None
        self.rebuild_composite()
        self.item_selected.emit("")
        self.atlas_changed.emit()
        self._commit(before, "Vaciar atlas")

    def rename_item(self, item_id: str, new_name: str) -> str | None:
        """Renombra una textura garantizando nombres únicos. Devuelve el nombre final."""
        item = self._find(item_id)
        if item is None or not new_name.strip():
            return None
        final = self.unique_name(new_name.strip(), exclude_id=item_id)
        if final != item.name:
            before = self.snapshot()
            item.name = final
            self.atlas_changed.emit()
            self._commit(before, f"Renombrar a '{final}'")
        return final

    def set_item_position(self, item_id: str, x: int, y: int) -> None:
        """Mueve una textura a ``(x, y)`` (ediciones consecutivas se fusionan en el historial)."""
        item = self._find(item_id)
        if item is None or (item.x == x and item.y == y):
            return
        before = self.snapshot()
        item.x, item.y = x, y
        self.rebuild_composite()
        self.item_moved.emit(item.id, x, y)
        self.atlas_changed.emit()
        self._commit(before, f"Mover '{item.name}'", merge_key=f"move:{item.id}")

    def nudge_selected(self, dx: int, dy: int) -> bool:
        item = self.selected_item
        if item is None:
            return False
        self.set_item_position(item.id, item.x + dx, item.y + dy)
        return True

    def duplicate_selected(self) -> AtlasItem | None:
        """Duplica la textura seleccionada y la ubica en un hueco libre."""
        src = self.selected_item
        if src is None:
            return None
        dup = AtlasItem(
            id=uuid.uuid4().hex[:12],
            name=src.name,
            pixels=src.pixels,
            x=src.x,
            y=src.y,
            pivot=src.pivot,
            source_pixels=src.source_pixels,
        )
        self.add_item(dup, auto_place=True)
        return dup

    def set_item_size(self, item_id: str, width: int, height: int) -> None:
        """Cambia el tamaño de una textura remuestreando sus píxeles."""
        item = self._find(item_id)
        if item is None:
            return
        w = max(MIN_ITEM_DIM, min(width, MAX_ATLAS_DIM))
        h = max(MIN_ITEM_DIM, min(height, MAX_ATLAS_DIM))
        if item.width == w and item.height == h:
            return
        before = self.snapshot()
        item.resize_pixels(w, h)
        self.rebuild_composite()
        self.item_resized.emit(item.id, w, h)
        self.atlas_changed.emit()
        self._commit(
            before, f"Redimensionar '{item.name}' a {w}×{h}", merge_key=f"resize:{item.id}"
        )

    def reset_item_size(self, item_id: str) -> None:
        """Restaura el tamaño original de la textura a partir de source_pixels."""
        item = self._find(item_id)
        if item is None:
            return
        before = self.snapshot()
        orig_w, orig_h = item.reset_to_source_size()
        self.rebuild_composite()
        self.item_resized.emit(item.id, orig_w, orig_h)
        self.atlas_changed.emit()
        self._commit(before, f"Restablecer tamaño original de '{item.name}' ({orig_w}×{orig_h})")

    def _transform_selected(self, fn_name: str, text: str) -> bool:
        item = self.selected_item
        if item is None:
            return False
        before = self.snapshot()

        def _apply(arr: RgbaArray) -> RgbaArray:
            if fn_name == "rot_cw":
                res = np.rot90(arr, k=-1)
            elif fn_name == "rot_ccw":
                res = np.rot90(arr, k=1)
            elif fn_name == "flip_h":
                res = arr[:, ::-1]
            else:
                res = arr[::-1, :]
            res = np.ascontiguousarray(res)
            res.setflags(write=False)
            return res

        new = _apply(item.pixels)
        cx = item.x + item.width / 2.0
        cy = item.y + item.height / 2.0
        item.pixels = new
        if item.source_pixels is not None:
            item.source_pixels = _apply(item.source_pixels)
        item.x = int(round(cx - item.width / 2.0))
        item.y = int(round(cy - item.height / 2.0))
        self.rebuild_composite()
        self.atlas_changed.emit()
        self._commit(before, f"{text} '{item.name}'")
        return True

    def rotate_selected(self, clockwise: bool = True) -> bool:
        if clockwise:
            return self._transform_selected("rot_cw", "Rotar 90° horario")
        return self._transform_selected("rot_ccw", "Rotar 90° antihorario")

    def flip_selected(self, horizontal: bool = True) -> bool:
        if horizontal:
            return self._transform_selected("flip_h", "Voltear horizontal")
        return self._transform_selected("flip_v", "Voltear vertical")

    def fit_canvas_to_content(self, power_of_two: bool = True) -> None:
        """Ajusta el lienzo al contenido actual (sin mover texturas)."""
        if not self._items:
            return
        need_w = max(MIN_ATLAS_DIM, max(it.x + it.width for it in self._items))
        need_h = max(MIN_ATLAS_DIM, max(it.y + it.height for it in self._items))
        if power_of_two:
            need_w, need_h = _next_pot(need_w), _next_pot(need_h)
        self.set_atlas_dimensions(need_w, need_h)

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
        before = self.snapshot()
        result = auto_pack_atlas_items(
            self._items,
            padding=padding,
            spacing=spacing,
            max_width=MAX_ATLAS_DIM,
            max_height=MAX_ATLAS_DIM,
            power_of_two=power_of_two,
            square=square,
        )
        self._atlas_width = result.width
        self._atlas_height = result.height
        self.rebuild_composite()
        self.atlas_changed.emit()
        self._commit(before, "Auto-empaquetar atlas")

    def rebuild_composite(self) -> None:
        """Reconstruye el mapa composite RGBA con las posiciones actuales."""
        result = composite_atlas_items(self._items, self._atlas_width, self._atlas_height)
        self._composite_cache = result.image

    # ---------------------------------------------------------- eventos de ratón
    def _hit_test(self, px: float, py: float) -> AtlasItem | None:
        """Busca el item en (px, py) de arriba a abajo (orden inverso de lista)."""
        for item in reversed(self._items):
            if item.x <= px < item.x + item.width and item.y <= py < item.y + item.height:
                return item
        return None

    def _get_handle_at(self, screen_pt: Point, mapper: CoordinateMapper) -> str | None:
        """Determina si screen_pt cae sobre una manija de esquina, un borde o el cuerpo."""
        selected = self.selected_item
        if selected is None:
            return None

        sel_rect = self._screen_rect(mapper, selected.rect)

        # 1. Manijas de las 4 esquinas (prioridad alta)
        corner_tol = 10.0
        corners = (
            ("nw", sel_rect.left(), sel_rect.top()),
            ("ne", sel_rect.right(), sel_rect.top()),
            ("se", sel_rect.right(), sel_rect.bottom()),
            ("sw", sel_rect.left(), sel_rect.bottom()),
        )
        for name, cx, cy in corners:
            if math.hypot(screen_pt.x - cx, screen_pt.y - cy) <= corner_tol:
                return name

        # 2. Bordes (arriba, abajo, izquierda, derecha)
        edge_tol = 7.0
        x_in_range = (sel_rect.left() - 4.0) <= screen_pt.x <= (sel_rect.right() + 4.0)
        y_in_range = (sel_rect.top() - 4.0) <= screen_pt.y <= (sel_rect.bottom() + 4.0)

        if x_in_range:
            if abs(screen_pt.y - sel_rect.top()) <= edge_tol:
                return "n"
            if abs(screen_pt.y - sel_rect.bottom()) <= edge_tol:
                return "s"

        if y_in_range:
            if abs(screen_pt.x - sel_rect.left()) <= edge_tol:
                return "w"
            if abs(screen_pt.x - sel_rect.right()) <= edge_tol:
                return "e"

        # 3. Interior del elemento
        if sel_rect.contains(QPointF(screen_pt.x, screen_pt.y)):
            return "move"

        return None

    def handle_mouse_press(self, event: QMouseEvent, mapper: CoordinateMapper) -> bool:
        if event.button() != Qt.MouseButton.LeftButton:
            return False

        pos = event.position()
        screen_pt = Point(pos.x(), pos.y())
        img_pt = mapper.screen_to_image(screen_pt)

        # 1. Si hay una textura seleccionada, verificar si se hizo clic en una manija o borde
        handle = self._get_handle_at(screen_pt, mapper)
        selected = self.selected_item
        if selected is not None and handle in ("nw", "ne", "se", "sw", "n", "s", "w", "e"):
            self._is_resizing = True
            self._active_handle = handle
            self._resize_moved = False
            self._resize_before = self.snapshot()
            self._resize_start_rect = (selected.x, selected.y, selected.width, selected.height)
            self._resize_start_mouse = (img_pt.x, img_pt.y)
            self._resize_start_ratio = selected.width / max(1.0, float(selected.height))
            self.atlas_changed.emit()
            return True

        # 2. Hit test sobre las texturas
        hit = self._hit_test(img_pt.x, img_pt.y)
        if hit is not None:
            self._selected_id = hit.id
            self._is_dragging = True
            self._drag_moved = False
            self._drag_before = self.snapshot()
            self._drag_start_item_pos = (hit.x, hit.y)
            self._drag_start_mouse_pos = (img_pt.x, img_pt.y)
            self._hover_handle = "move"
            self.item_selected.emit(hit.id)
            self.atlas_changed.emit()
            return True

        # Clic fuera de cualquier textura deselecciona
        if self._selected_id is not None:
            self._selected_id = None
            self._hover_handle = None
            self.item_selected.emit("")
            self.atlas_changed.emit()
        return False

    def mouse_press(self, pos: QPointF, mapper: CoordinateMapper, event: QMouseEvent) -> bool:
        """Alias retrocompatible."""
        return self.handle_mouse_press(event, mapper)

    def _snap(self, item: AtlasItem, new_x: int, new_y: int, threshold: float) -> tuple[int, int]:
        """Ajuste magnético a bordes del lienzo y de otras texturas; registra guías."""
        self._guides = []
        w, h = item.width, item.height

        best_dx: tuple[float, int, int] | None = None  # (dist, x, guía)
        best_dy: tuple[float, int, int] | None = None

        def consider_x(target_x: int, guide: int) -> None:
            nonlocal best_dx
            d = abs(new_x - target_x)
            if d <= threshold and (best_dx is None or d < best_dx[0]):
                best_dx = (d, target_x, guide)

        def consider_y(target_y: int, guide: int) -> None:
            nonlocal best_dy
            d = abs(new_y - target_y)
            if d <= threshold and (best_dy is None or d < best_dy[0]):
                best_dy = (d, target_y, guide)

        # Bordes del lienzo
        consider_x(0, 0)
        consider_x(self._atlas_width - w, self._atlas_width)
        consider_y(0, 0)
        consider_y(self._atlas_height - h, self._atlas_height)

        for other in self._items:
            if other.id == item.id:
                continue
            o = other.rect
            # Solo consideramos vecinos cercanos en el eje perpendicular
            near_v = new_y < o.bottom + threshold and new_y + h > o.y - threshold
            near_h = new_x < o.right + threshold and new_x + w > o.x - threshold
            if near_v:
                consider_x(o.right, o.right)  # izquierda ↔ derecha del otro
                consider_x(o.x - w, o.x)  # derecha ↔ izquierda del otro
                consider_x(o.x, o.x)  # alinear izquierdas
                consider_x(o.right - w, o.right)  # alinear derechas
            if near_h:
                consider_y(o.bottom, o.bottom)
                consider_y(o.y - h, o.y)
                consider_y(o.y, o.y)
                consider_y(o.bottom - h, o.bottom)

        if best_dx is not None:
            new_x = best_dx[1]
            self._guides.append(("v", best_dx[2]))
        if best_dy is not None:
            new_y = best_dy[1]
            self._guides.append(("h", best_dy[2]))
        return new_x, new_y

    def handle_mouse_move(self, event: QMouseEvent, mapper: CoordinateMapper) -> bool:
        pos = event.position()
        screen_pt = Point(pos.x(), pos.y())
        img_pt = mapper.screen_to_image(screen_pt)

        # Caso A: Redimensionando libremente con manijas
        if self._is_resizing and (event.buttons() & Qt.MouseButton.LeftButton):
            item = self.selected_item
            if item is None or self._active_handle is None:
                self._is_resizing = False
                return False

            dx = img_pt.x - self._resize_start_mouse[0]
            dy = img_pt.y - self._resize_start_mouse[1]
            shift_pressed = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            keep_aspect = shift_pressed or self._lock_aspect_ratio

            sx, sy, sw, sh = self._resize_start_rect
            ratio = self._resize_start_ratio
            handle = self._active_handle

            new_x, new_y = sx, sy
            new_w, new_h = sw, sh

            if handle == "e":
                new_w = max(MIN_ITEM_DIM, int(round(sw + dx)))
                if keep_aspect:
                    new_h = max(MIN_ITEM_DIM, int(round(new_w / ratio)))
            elif handle == "w":
                new_w = max(MIN_ITEM_DIM, int(round(sw - dx)))
                new_x = sx + (sw - new_w)
                if keep_aspect:
                    new_h = max(MIN_ITEM_DIM, int(round(new_w / ratio)))
            elif handle == "s":
                new_h = max(MIN_ITEM_DIM, int(round(sh + dy)))
                if keep_aspect:
                    new_w = max(MIN_ITEM_DIM, int(round(new_h * ratio)))
            elif handle == "n":
                new_h = max(MIN_ITEM_DIM, int(round(sh - dy)))
                new_y = sy + (sh - new_h)
                if keep_aspect:
                    new_w = max(MIN_ITEM_DIM, int(round(new_h * ratio)))
            elif handle == "se":
                new_w = max(MIN_ITEM_DIM, int(round(sw + dx)))
                if keep_aspect:
                    new_h = max(MIN_ITEM_DIM, int(round(new_w / ratio)))
                else:
                    new_h = max(MIN_ITEM_DIM, int(round(sh + dy)))
            elif handle == "sw":
                new_w = max(MIN_ITEM_DIM, int(round(sw - dx)))
                new_x = sx + (sw - new_w)
                if keep_aspect:
                    new_h = max(MIN_ITEM_DIM, int(round(new_w / ratio)))
                else:
                    new_h = max(MIN_ITEM_DIM, int(round(sh + dy)))
            elif handle == "ne":
                new_w = max(MIN_ITEM_DIM, int(round(sw + dx)))
                if keep_aspect:
                    new_h = max(MIN_ITEM_DIM, int(round(new_w / ratio)))
                else:
                    new_h = max(MIN_ITEM_DIM, int(round(sh - dy)))
                new_y = sy + (sh - new_h)
            elif handle == "nw":
                new_w = max(MIN_ITEM_DIM, int(round(sw - dx)))
                new_x = sx + (sw - new_w)
                if keep_aspect:
                    new_h = max(MIN_ITEM_DIM, int(round(new_w / ratio)))
                else:
                    new_h = max(MIN_ITEM_DIM, int(round(sh - dy)))
                new_y = sy + (sh - new_h)

            if new_w != item.width or new_h != item.height or new_x != item.x or new_y != item.y:
                self._resize_moved = True
                item.x = new_x
                item.y = new_y
                item.resize_pixels(new_w, new_h)
                self.rebuild_composite()
                self.item_resized.emit(item.id, new_w, new_h)
                self.item_moved.emit(item.id, new_x, new_y)
                self.atlas_changed.emit()
            return True

        # Caso B: Arrastrando para mover
        if self._is_dragging and (event.buttons() & Qt.MouseButton.LeftButton):
            item = self.selected_item
            if item is None:
                self._is_dragging = False
                return False

            dx = img_pt.x - self._drag_start_mouse_pos[0]
            dy = img_pt.y - self._drag_start_mouse_pos[1]
            new_x = int(round(self._drag_start_item_pos[0] + dx))
            new_y = int(round(self._drag_start_item_pos[1] + dy))

            if event.modifiers() & Qt.KeyboardModifier.AltModifier:
                self._guides = []
            else:
                zoom = mapper.zoom if mapper.zoom > 0 else 1.0
                new_x, new_y = self._snap(item, new_x, new_y, SNAP_THRESHOLD_PX / zoom)

            if item.x != new_x or item.y != new_y:
                if not self._drag_moved:
                    # Al empezar a arrastrar, traer la textura al frente
                    self._drag_moved = True
                    self._items.remove(item)
                    self._items.append(item)
                item.x = new_x
                item.y = new_y
                self.rebuild_composite()
                self.item_moved.emit(item.id, new_x, new_y)
                self.atlas_changed.emit()
            return True

        # Caso C: Solo movimiento del cursor (hover sobre manijas o elementos)
        new_handle = self._get_handle_at(screen_pt, mapper)
        if new_handle in ("nw", "ne", "se", "sw", "n", "s", "w", "e"):
            new_hover = self._selected_id
        else:
            hit = self._hit_test(img_pt.x, img_pt.y)
            new_hover = hit.id if hit is not None else None

        if self._hover_handle != new_handle or self._hovered_id != new_hover:
            self._hover_handle = new_handle
            self._hovered_id = new_hover
            self.atlas_changed.emit()

        return False

    def mouse_move(self, pos: QPointF, mapper: CoordinateMapper, event: QMouseEvent) -> bool:
        """Alias retrocompatible."""
        return self.handle_mouse_move(event, mapper)

    def handle_mouse_release(self, event: QMouseEvent, mapper: CoordinateMapper) -> bool:
        if self._is_resizing:
            self._is_resizing = False
            self._active_handle = None
            before = self._resize_before
            self._resize_before = None
            item = self.selected_item
            if before is not None and self._resize_moved and item is not None:
                self._commit(before, f"Redimensionar '{item.name}' a {item.width}×{item.height}")
            self.atlas_changed.emit()
            return True

        if self._is_dragging:
            self._is_dragging = False
            self._guides = []
            before = self._drag_before
            self._drag_before = None
            item = self.selected_item
            if before is not None and self._drag_moved and item is not None:
                self._commit(before, f"Mover '{item.name}'")
            self.atlas_changed.emit()
            return True
        return False

    def mouse_release(self, pos: QPointF, mapper: CoordinateMapper, event: QMouseEvent) -> bool:
        """Alias retrocompatible."""
        return self.handle_mouse_release(event, mapper)

    def handle_key_press(self, event: QKeyEvent) -> bool:
        key = event.key()
        mods = event.modifiers()
        shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)

        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and self._selected_id is not None:
            self.remove_item(self._selected_id)
            return True

        if key == Qt.Key.Key_Escape and self._selected_id is not None:
            self.select_item(None)
            return True

        step = 10 if shift else 1
        arrows = {
            Qt.Key.Key_Left: (-step, 0),
            Qt.Key.Key_Right: (step, 0),
            Qt.Key.Key_Up: (0, -step),
            Qt.Key.Key_Down: (0, step),
        }
        if key in arrows and not ctrl:
            ddx, ddy = arrows[Qt.Key(key)]
            return self.nudge_selected(ddx, ddy)

        if ctrl and key == Qt.Key.Key_D:
            return self.duplicate_selected() is not None
        if ctrl:
            return False

        if key == Qt.Key.Key_R:
            return self.rotate_selected(clockwise=not shift)
        if key == Qt.Key.Key_H:
            return self.flip_selected(horizontal=True)
        if key == Qt.Key.Key_V:
            return self.flip_selected(horizontal=False)
        return False

    def key_press(self, event: QKeyEvent) -> bool:
        """Alias retrocompatible."""
        return self.handle_key_press(event)

    def get_cursor(self) -> Qt.CursorShape | None:
        handle = self._active_handle if self._is_resizing else self._hover_handle
        if handle in ("nw", "se"):
            return Qt.CursorShape.SizeFDiagCursor
        if handle in ("ne", "sw"):
            return Qt.CursorShape.SizeBDiagCursor
        if handle in ("n", "s"):
            return Qt.CursorShape.SizeVerCursor
        if handle in ("w", "e"):
            return Qt.CursorShape.SizeHorCursor
        if self._is_dragging:
            return Qt.CursorShape.ClosedHandCursor
        if handle == "move" or self._hovered_id is not None:
            return Qt.CursorShape.OpenHandCursor
        return None

    # ------------------------------------------------------------- renderizado
    @staticmethod
    def _screen_rect(mapper: CoordinateMapper, rect: Rect) -> QRectF:
        tl = mapper.image_to_screen(Point(float(rect.x), float(rect.y)))
        br = mapper.image_to_screen(Point(float(rect.right), float(rect.bottom)))
        return QRectF(tl.x, tl.y, br.x - tl.x, br.y - tl.y)

    def paint_overlay(self, painter: QPainter, mapper: CoordinateMapper) -> None:
        """Dibuja bordes del atlas, contornos de selección, manijas de transformación,
        guías y etiquetas.
        """
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        # 1. Borde del límite del Atlas
        atlas_rect = self._screen_rect(mapper, Rect(0, 0, self._atlas_width, self._atlas_height))
        painter.setPen(QPen(COLOR_ATLAS_BORDER, 1.5, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(atlas_rect)

        # 2. Contorno sutil de todas las texturas + hover
        for it in self._items:
            if it.id == self._hovered_id and it.id != self._selected_id:
                painter.setPen(QPen(COLOR_HOVER, 1.5))
                painter.drawRect(self._screen_rect(mapper, it.rect))

        # 3. Solapamientos (rojo) y fuera de límites (naranja)
        overlapping = self.overlapping_ids()
        oob = self.out_of_bounds_ids()
        for it in self._items:
            if it.id in overlapping:
                painter.setPen(QPen(COLOR_OVERLAP, 1.5, Qt.PenStyle.DotLine))
                painter.drawRect(self._screen_rect(mapper, it.rect))
            elif it.id in oob:
                painter.setPen(QPen(COLOR_OUT_OF_BOUNDS, 1.5, Qt.PenStyle.DashDotLine))
                painter.drawRect(self._screen_rect(mapper, it.rect))

        # 4. Guías de ajuste magnético
        if self._guides:
            painter.setPen(QPen(COLOR_GUIDE, 1.0, Qt.PenStyle.DashLine))
            vp = painter.viewport()
            for kind, value in self._guides:
                if kind == "v":
                    sx = mapper.image_to_screen(Point(float(value), 0.0)).x
                    painter.drawLine(QPointF(sx, 0.0), QPointF(sx, float(vp.height())))
                else:
                    sy = mapper.image_to_screen(Point(0.0, float(value))).y
                    painter.drawLine(QPointF(0.0, sy), QPointF(float(vp.width()), sy))

        # 5. Rectángulo de selección activa y manijas de transformación libre
        selected = self.selected_item
        if selected is not None:
            sel_rect = self._screen_rect(mapper, selected.rect)
            painter.setPen(QPen(COLOR_SELECTION, 2.0))
            painter.setBrush(QBrush(COLOR_SELECTION_FILL))
            painter.drawRect(sel_rect)

            cur_handle = self._active_handle if self._is_resizing else self._hover_handle

            # Puntos medios de los 4 bordes
            midpoints = {
                "n": ((sel_rect.left() + sel_rect.right()) / 2.0, sel_rect.top()),
                "s": ((sel_rect.left() + sel_rect.right()) / 2.0, sel_rect.bottom()),
                "w": (sel_rect.left(), (sel_rect.top() + sel_rect.bottom()) / 2.0),
                "e": (sel_rect.right(), (sel_rect.top() + sel_rect.bottom()) / 2.0),
            }

            # Dibujar manijas de bordes
            for name, (mx, my) in midpoints.items():
                is_active = cur_handle == name
                pw = 10.0 if name in ("n", "s") else 6.0
                ph = 6.0 if name in ("n", "s") else 10.0
                fill = COLOR_HOVER if is_active else COLOR_SELECTION
                painter.setPen(QPen(QColor(15, 20, 28, 240), 1.5))
                painter.setBrush(QBrush(fill))
                painter.drawRoundedRect(QRectF(mx - pw / 2.0, my - ph / 2.0, pw, ph), 1.5, 1.5)

            # Manijas de las 4 esquinas (cuadrados destacados)
            corners = {
                "nw": (sel_rect.left(), sel_rect.top()),
                "ne": (sel_rect.right(), sel_rect.top()),
                "se": (sel_rect.right(), sel_rect.bottom()),
                "sw": (sel_rect.left(), sel_rect.bottom()),
            }
            corner_size = 8.0
            corner_half = corner_size / 2.0

            for name, (cx, cy) in corners.items():
                is_active = cur_handle == name
                fill = COLOR_HOVER if is_active else COLOR_SELECTION
                painter.setPen(QPen(QColor(15, 20, 28, 240), 1.5))
                painter.setBrush(QBrush(fill))
                painter.drawRect(
                    QRectF(cx - corner_half, cy - corner_half, corner_size, corner_size)
                )

            # Badge con información (Nombre | WxH | X, Y | Pistas)
            font = QFont("Segoe UI", 9)
            font.setBold(True)
            painter.setFont(font)
            if self._is_resizing:
                info_text = (
                    f" ⤢ {selected.name} | {selected.width}×{selected.height} px "
                    f"| X:{selected.x} Y:{selected.y} (Shift: conservar proporción) "
                )
            else:
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
