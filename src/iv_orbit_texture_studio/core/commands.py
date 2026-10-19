"""Comandos reversibles para el historial de Deshacer / Rehacer.

Implementa el patrón Command de PySide6 (QUndoCommand) para permitir
deshacer y rehacer cualquier cambio en la selección del cuadrilátero,
dimensiones y parámetros de muestreo.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from PySide6.QtGui import QUndoCommand

from iv_orbit_texture_studio.imaging.perspective import InterpolationMode, Point, Quad

if TYPE_CHECKING:
    pass


class MoveVertexCommand(QUndoCommand):
    """Comando reversible para el movimiento de un vértice del cuadrilátero."""

    def __init__(
        self,
        vertex_index: int,
        old_point: Point,
        new_point: Point,
        apply_fn: Callable[[int, Point], None],
        parent: QUndoCommand | None = None,
    ) -> None:
        super().__init__(f"Mover vértice {vertex_index + 1}", parent)
        self.vertex_index = vertex_index
        self.old_point = old_point
        self.new_point = new_point
        self.apply_fn = apply_fn

    def undo(self) -> None:
        self.apply_fn(self.vertex_index, self.old_point)

    def redo(self) -> None:
        self.apply_fn(self.vertex_index, self.new_point)


class SetQuadCommand(QUndoCommand):
    """Comando reversible para cambiar o restablecer la selección completa."""

    def __init__(
        self,
        old_quad: Quad | None,
        new_quad: Quad | None,
        apply_fn: Callable[[Quad | None], None],
        text: str = "Cambiar selección",
        parent: QUndoCommand | None = None,
    ) -> None:
        super().__init__(text, parent)
        self.old_quad = old_quad
        self.new_quad = new_quad
        self.apply_fn = apply_fn

    def undo(self) -> None:
        self.apply_fn(self.old_quad)

    def redo(self) -> None:
        self.apply_fn(self.new_quad)


class ChangeDimensionsCommand(QUndoCommand):
    """Comando reversible para modificar las dimensiones de salida."""

    def __init__(
        self,
        old_dims: tuple[int, int],
        new_dims: tuple[int, int],
        apply_fn: Callable[[int, int], None],
        parent: QUndoCommand | None = None,
    ) -> None:
        super().__init__(f"Cambiar resolución a {new_dims[0]}x{new_dims[1]}", parent)
        self.old_dims = old_dims
        self.new_dims = new_dims
        self.apply_fn = apply_fn

    def undo(self) -> None:
        self.apply_fn(self.old_dims[0], self.old_dims[1])

    def redo(self) -> None:
        self.apply_fn(self.new_dims[0], self.new_dims[1])


class ChangeInterpolationCommand(QUndoCommand):
    """Comando reversible para cambiar el modo de interpolación."""

    def __init__(
        self,
        old_mode: InterpolationMode,
        new_mode: InterpolationMode,
        apply_fn: Callable[[InterpolationMode], None],
        parent: QUndoCommand | None = None,
    ) -> None:
        super().__init__(f"Cambiar muestreo a {new_mode.name}", parent)
        self.old_mode = old_mode
        self.new_mode = new_mode
        self.apply_fn = apply_fn

    def undo(self) -> None:
        self.apply_fn(self.old_mode)

    def redo(self) -> None:
        self.apply_fn(self.new_mode)
