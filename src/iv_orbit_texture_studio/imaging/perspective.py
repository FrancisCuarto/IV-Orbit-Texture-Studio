"""Rectificación de perspectiva y homografías para extracción de texturas.

Este módulo es independiente de la interfaz gráfica y procesa arreglos NumPy RGBA.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

import cv2
import numpy as np

from iv_orbit_texture_studio.imaging.image_io import RgbaArray
from iv_orbit_texture_studio.ui.canvas.coordinate_mapper import Point


class InterpolationMode(StrEnum):
    """Métodos de interpolación soportados para la rectificación."""

    LANCZOS4 = "lanczos4"
    CUBIC = "cubic"
    LINEAR = "linear"
    NEAREST = "nearest"

    def to_cv2(self) -> int:
        match self:
            case InterpolationMode.LANCZOS4:
                return cv2.INTER_LANCZOS4
            case InterpolationMode.CUBIC:
                return cv2.INTER_CUBIC
            case InterpolationMode.LINEAR:
                return cv2.INTER_LINEAR
            case InterpolationMode.NEAREST:
                return cv2.INTER_NEAREST


class GeometryError(Exception):
    """Error base de validación geométrica."""


class DegenerateQuadError(GeometryError):
    """El cuadrilátero no es convexo, es auto-intersecante o tiene área nula."""


class OutOfBoundsError(GeometryError):
    """Las dimensiones solicitadas exceden los límites permitidos."""


@dataclass(frozen=True, slots=True)
class Quad:
    """Cuadrilátero definido por 4 puntos ordenados en sentido horario.

    Convención de vértices:
    0: Superior-Izquierdo (Top-Left)
    1: Superior-Derecho (Top-Right)
    2: Inferior-Derecho (Bottom-Right)
    3: Inferior-Izquierdo (Bottom-Left)
    """

    p0: Point
    p1: Point
    p2: Point
    p3: Point

    @property
    def top_left(self) -> Point:
        return self.p0

    @property
    def top_right(self) -> Point:
        return self.p1

    @property
    def bottom_right(self) -> Point:
        return self.p2

    @property
    def bottom_left(self) -> Point:
        return self.p3

    @property
    def points(self) -> tuple[Point, Point, Point, Point]:
        return (self.p0, self.p1, self.p2, self.p3)

    def with_vertex(self, index: int, new_point: Point) -> Quad:
        """Devuelve un nuevo Quad reemplazando el vértice en el índice indicado (0..3)."""
        pts = list(self.points)
        if not (0 <= index < 4):
            raise IndexError(f"Índice de vértice inválido: {index}")
        pts[index] = new_point
        return Quad(pts[0], pts[1], pts[2], pts[3])

    def area(self) -> float:
        """Calcula el área del cuadrilátero usando la fórmula de Gauss (Shoelace)."""
        pts = self.points
        total = 0.0
        for i in range(4):
            j = (i + 1) % 4
            total += pts[i].x * pts[j].y - pts[j].x * pts[i].y
        return 0.5 * abs(total)

    def is_convex(self) -> bool:
        """Determina si el cuadrilátero es estrictamente convexo y no degenerado."""
        pts = self.points
        # Verificar finitud
        for p in pts:
            if not (math.isfinite(p.x) and math.isfinite(p.y)):
                return False

        # Verificar duplicados
        for i in range(4):
            for j in range(i + 1, 4):
                if math.isclose(pts[i].x, pts[j].x, abs_tol=1e-5) and math.isclose(
                    pts[i].y, pts[j].y, abs_tol=1e-5
                ):
                    return False

        # Productos cruzados de bordes consecutivos
        signs: list[float] = []
        for i in range(4):
            p_curr = pts[i]
            p_next = pts[(i + 1) % 4]
            p_after = pts[(i + 2) % 4]

            dx1 = p_next.x - p_curr.x
            dy1 = p_next.y - p_curr.y
            dx2 = p_after.x - p_next.x
            dy2 = p_after.y - p_next.y

            cross = dx1 * dy2 - dy1 * dx2
            if abs(cross) < 1e-6:
                # Puntos colineales o ángulo de 180°
                return False
            signs.append(cross)

        # Todos los productos cruzados deben tener estrictamente el mismo signo
        first_positive = signs[0] > 0
        return all((s > 0) == first_positive for s in signs)

    def validate(self) -> None:
        """Valida rigurosamente la geometría del cuadrilátero."""
        if not self.is_convex():
            raise DegenerateQuadError(
                "El cuadrilátero no es válido: debe ser convexo, no auto-intersecante "
                "y sin vértices colineales ni duplicados."
            )
        if self.area() < 1.0:
            raise DegenerateQuadError("El área del cuadrilátero es demasiado pequeña (< 1 px²).")


def order_points_clockwise(points: Sequence[Point]) -> Quad:
    """Ordena 4 puntos arbitrarios en sentido horario: [TL, TR, BR, BL]."""
    if len(points) != 4:
        raise ValueError(f"Se requieren exactamente 4 puntos, recibidos: {len(points)}")

    pts = [(p.x, p.y) for p in points]
    # Suma y diferencia de coordenadas
    # TL suele tener la menor suma (x + y), BR la mayor suma
    # TR suele tener la menor diferencia (y - x), BL la mayor diferencia
    sums = [x + y for x, y in pts]
    diffs = [y - x for x, y in pts]

    tl_idx = int(np.argmin(sums))
    br_idx = int(np.argmax(sums))
    tr_idx = int(np.argmin(diffs))
    bl_idx = int(np.argmax(diffs))

    indices = [tl_idx, tr_idx, br_idx, bl_idx]
    if len(set(indices)) != 4:
        # Fallback basado en el centroide y ángulo polar
        cx = sum(x for x, y in pts) / 4.0
        cy = sum(y for x, y in pts) / 4.0
        sorted_by_angle = sorted(
            points,
            key=lambda p: math.atan2(p.y - cy, p.x - cx),
        )
        # En pantalla (y hacia abajo): el ángulo polar crece en sentido horario.
        # Buscar el punto más cercano a la esquina superior izquierda (menor x + y)
        min_sum_idx = min(range(4), key=lambda i: sorted_by_angle[i].x + sorted_by_angle[i].y)
        ordered = [sorted_by_angle[(min_sum_idx + k) % 4] for k in range(4)]
        return Quad(ordered[0], ordered[1], ordered[2], ordered[3])

    return Quad(points[tl_idx], points[tr_idx], points[br_idx], points[bl_idx])


def estimate_rectified_dimensions(quad: Quad) -> tuple[int, int]:
    """Estima ancho y alto de salida basados en la geometría del cuadrilátero.

    Toma el máximo entre los lados opuestos para preservar la máxima resolución
    disponible en la superficie sin sub-muestrear.
    """
    quad.validate()

    def dist(p1: Point, p2: Point) -> float:
        return math.hypot(p2.x - p1.x, p2.y - p1.y)

    width_top = dist(quad.top_left, quad.top_right)
    width_bottom = dist(quad.bottom_left, quad.bottom_right)
    height_left = dist(quad.top_left, quad.bottom_left)
    height_right = dist(quad.top_right, quad.bottom_right)

    est_w = max(1, int(round(max(width_top, width_bottom))))
    est_h = max(1, int(round(max(height_left, height_right))))
    return est_w, est_h


def rectify_perspective(
    image: RgbaArray,
    quad: Quad,
    output_width: int,
    output_height: int,
    interpolation: InterpolationMode | str = InterpolationMode.LANCZOS4,
) -> RgbaArray:
    """Rectifica la región comprendida en `quad` a una textura frontal de dimensiones
    `output_width x output_height`.


    Parámetros:
        image: Arreglo de entrada (H, W, 4) uint8 en orden RGBA.
        quad: Cuadrilátero con las 4 esquinas seleccionadas.
        output_width: Ancho de salida en píxeles (> 0).
        output_height: Alto de salida en píxeles (> 0).
        interpolation: Método de interpolación de píxeles (InterpolationMode o str).

    Retorna:
        Nuevo arreglo RGBA uint8 con la textura rectificada.
    """
    if output_width <= 0 or output_height <= 0:
        raise ValueError(f"Dimensiones de salida inválidas: {output_width} x {output_height}")

    if isinstance(interpolation, str):
        interpolation = InterpolationMode(interpolation)

    quad.validate()

    # Coordenadas de origen
    src_pts = np.array(
        [
            [quad.top_left.x, quad.top_left.y],
            [quad.top_right.x, quad.top_right.y],
            [quad.bottom_right.x, quad.bottom_right.y],
            [quad.bottom_left.x, quad.bottom_left.y],
        ],
        dtype=np.float32,
    )

    # Coordenadas de destino (mapeando a los límites exactos [0, W - 1] x [0, H - 1])
    dst_pts = np.array(
        [
            [0.0, 0.0],
            [float(output_width - 1), 0.0],
            [float(output_width - 1), float(output_height - 1)],
            [0.0, float(output_height - 1)],
        ],
        dtype=np.float32,
    )

    # Matriz de homografía 3x3
    matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)

    # Rectificación de perspectiva
    rectified = cv2.warpPerspective(
        image,
        matrix,
        (output_width, output_height),
        flags=interpolation.to_cv2(),
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )

    result = np.ascontiguousarray(rectified, dtype=np.uint8)
    return result
