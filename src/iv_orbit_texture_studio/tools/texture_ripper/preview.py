"""Panel de control y previsualización para Texture Ripper."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from iv_orbit_texture_studio.exporters.image_exporter import (
    ExportError,
    export_dialog_filter,
    export_image,
)
from iv_orbit_texture_studio.imaging.image_io import LoadedImage, RgbaArray
from iv_orbit_texture_studio.imaging.perspective import (
    InterpolationMode,
    estimate_rectified_dimensions,
    rectify_perspective,
)
from iv_orbit_texture_studio.tools.texture_ripper.tool import TextureRipperTool
from iv_orbit_texture_studio.ui.qt_image import rgba_array_to_qimage

logger = logging.getLogger(__name__)


class TextureRipperPanel(QWidget):
    """Panel lateral que administra los parámetros de rectificación y exportación."""

    export_requested = Signal(Path)

    def __init__(
        self,
        tool: TextureRipperTool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._tool = tool
        self._source_image: LoadedImage | None = None
        self._rectified_cache: RgbaArray | None = None
        self._updating_dimensions = False

        self._setup_ui()
        self._tool.selection_changed.connect(self._on_selection_changed)
        self.setMinimumWidth(280)

    # ---------------------------------------------------------------------- UI
    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        # 1. Grupo de Selección
        group_sel = QGroupBox(self.tr("Región seleccionada"))
        v_sel = QVBoxLayout(group_sel)

        self._label_status = QLabel(self.tr("Sin selección"))
        self._label_status.setWordWrap(True)
        v_sel.addWidget(self._label_status)

        h_btn_sel = QHBoxLayout()
        self._btn_reset_rect = QPushButton(self.tr("Restablecer"))
        self._btn_reset_rect.setToolTip(self.tr("Ajusta un cuadrilátero inicial centrado"))
        self._btn_reset_rect.clicked.connect(self._tool.reset_to_default)

        self._btn_corners = QPushButton(self.tr("Ajustar a esquinas"))
        self._btn_corners.setToolTip(
            self.tr("Ajusta los 4 vértices exactamente a las 4 esquinas de la imagen")
        )
        self._btn_corners.clicked.connect(self._tool.select_image_corners)

        self._btn_clear = QPushButton(self.tr("Limpiar"))
        self._btn_clear.setToolTip(self.tr("Borra la selección para marcar 4 puntos manualmente"))
        self._btn_clear.clicked.connect(self._tool.clear)

        h_btn_sel.addWidget(self._btn_reset_rect)
        h_btn_sel.addWidget(self._btn_corners)
        h_btn_sel.addWidget(self._btn_clear)
        v_sel.addLayout(h_btn_sel)
        layout.addWidget(group_sel)

        # 2. Grupo de Resolución y Transformación
        group_res = QGroupBox(self.tr("Dimensiones de salida"))
        form_res = QFormLayout(group_res)

        self._spin_width = QSpinBox()
        self._spin_width.setRange(1, 16384)
        self._spin_width.setValue(512)
        self._spin_width.setSuffix(" px")
        self._spin_width.valueChanged.connect(self._on_width_changed)

        self._spin_height = QSpinBox()
        self._spin_height.setRange(1, 16384)
        self._spin_height.setValue(512)
        self._spin_height.setSuffix(" px")
        self._spin_height.valueChanged.connect(self._on_height_changed)

        self._chk_lock_aspect = QCheckBox(self.tr("Bloquear proporción"))
        self._chk_lock_aspect.setChecked(False)

        self._btn_estimate = QPushButton(self.tr("Calcular tamaño estimado"))
        self._btn_estimate.setToolTip(
            self.tr("Calcula las dimensiones óptimas basadas en las longitudes de los lados")
        )
        self._btn_estimate.clicked.connect(self.estimate_dimensions)

        form_res.addRow(self.tr("Ancho:"), self._spin_width)
        form_res.addRow(self.tr("Alto:"), self._spin_height)
        form_res.addRow("", self._chk_lock_aspect)
        form_res.addRow("", self._btn_estimate)

        # Interpolación
        self._combo_interp = QComboBox()
        self._combo_interp.addItem(self.tr("Lanczos4 (Máxima calidad)"), InterpolationMode.LANCZOS4)
        self._combo_interp.addItem(self.tr("Bicúbica (Suave)"), InterpolationMode.CUBIC)
        self._combo_interp.addItem(self.tr("Bilineal (Rápida)"), InterpolationMode.LINEAR)
        self._combo_interp.addItem(
            self.tr("Vecino más cercano (Píxel art)"), InterpolationMode.NEAREST
        )
        self._combo_interp.currentIndexChanged.connect(self._update_preview)
        form_res.addRow(self.tr("Muestreo:"), self._combo_interp)

        layout.addWidget(group_res)

        # 3. Grupo de Previsualización
        group_prev = QGroupBox(self.tr("Previsualización"))
        v_prev = QVBoxLayout(group_prev)

        self._preview_frame = QFrame()
        self._preview_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self._preview_frame.setStyleSheet("background-color: #222222; border-radius: 4px;")
        v_frame = QVBoxLayout(self._preview_frame)
        v_frame.setContentsMargins(4, 4, 4, 4)

        self._label_preview = QLabel(self.tr("Sin previsualización"))
        self._label_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label_preview.setMinimumHeight(160)
        self._label_preview.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        v_frame.addWidget(self._label_preview)

        v_prev.addWidget(self._preview_frame)
        layout.addWidget(group_prev)

        # 4. Botón de Exportación
        self._btn_export = QPushButton(self.tr("Exportar textura…"))
        self._btn_export.setStyleSheet(
            "QPushButton { font-weight: bold; padding: 8px; "
            "background-color: #0e70a0; color: white; border-radius: 4px; }\n"
            "QPushButton:hover { background-color: #1288c4; }\n"
            "QPushButton:disabled { background-color: #444444; color: #888888; }"
        )
        self._btn_export.clicked.connect(self.export_texture)
        layout.addWidget(self._btn_export)

        layout.addStretch(1)
        self._update_ui_state()

    # ------------------------------------------------------------- estado e imagen
    def set_source_image(self, loaded_image: LoadedImage | None) -> None:
        self._source_image = loaded_image
        self._rectified_cache = None
        if loaded_image is not None:
            self.estimate_dimensions()
        self._update_ui_state()
        self._update_preview()

    def estimate_dimensions(self) -> None:
        quad = self._tool.selection.get_quad()
        if quad is not None and self._tool.selection.is_valid():
            try:
                est_w, est_h = estimate_rectified_dimensions(quad)
                self._updating_dimensions = True
                self._spin_width.setValue(est_w)
                self._spin_height.setValue(est_h)
                self._updating_dimensions = False
                self._update_preview()
            except Exception as exc:
                logger.debug("No se pudo estimar dimensiones: %s", exc)

    # ----------------------------------------------------------------- eventos
    def _on_selection_changed(self) -> None:
        self._update_ui_state()
        self._update_preview()

    def _on_width_changed(self, new_width: int) -> None:
        if self._updating_dimensions:
            return
        if self._chk_lock_aspect.isChecked():
            quad = self._tool.selection.get_quad()
            if quad is not None and self._tool.selection.is_valid():
                ew, eh = estimate_rectified_dimensions(quad)
                if ew > 0:
                    aspect = eh / ew
                    self._updating_dimensions = True
                    self._spin_height.setValue(max(1, int(round(new_width * aspect))))
                    self._updating_dimensions = False
        self._update_preview()

    def _on_height_changed(self, new_height: int) -> None:
        if self._updating_dimensions:
            return
        if self._chk_lock_aspect.isChecked():
            quad = self._tool.selection.get_quad()
            if quad is not None and self._tool.selection.is_valid():
                ew, eh = estimate_rectified_dimensions(quad)
                if eh > 0:
                    aspect = ew / eh
                    self._updating_dimensions = True
                    self._spin_width.setValue(max(1, int(round(new_height * aspect))))
                    self._updating_dimensions = False
        self._update_preview()

    def _update_ui_state(self) -> None:
        has_img = self._source_image is not None
        sel = self._tool.selection
        is_complete = sel.state.value == "complete"
        is_valid = sel.is_valid()

        self._btn_reset_rect.setEnabled(has_img)
        self._btn_clear.setEnabled(has_img and sel.count > 0)
        self._btn_estimate.setEnabled(has_img and is_valid)
        self._btn_export.setEnabled(has_img and is_valid)

        if not has_img:
            self._label_status.setText(self.tr("Cargá una imagen primero."))
            self._label_status.setStyleSheet("color: #aaaaaa;")
        elif not is_complete:
            faltan = 4 - sel.count
            self._label_status.setText(
                self.tr("Hacé clic en la imagen para marcar los vértices (faltan {n}).").format(
                    n=faltan
                )
            )
            self._label_status.setStyleSheet("color: #ffd700;")
        elif not is_valid:
            err = sel.validate() or self.tr("Geometría inválida")
            self._label_status.setText(f"⚠ {err}")
            self._label_status.setStyleSheet("color: #ff6666;")
        else:
            self._label_status.setText(self.tr("✓ 4 vértices listos para rectificar."))
            self._label_status.setStyleSheet("color: #66ff88;")

    def _update_preview(self) -> None:
        if self._source_image is None or not self._tool.selection.is_valid():
            self._label_preview.setText(self.tr("Sin previsualización"))
            self._rectified_cache = None
            return

        quad = self._tool.selection.get_quad()
        if quad is None:
            return

        out_w = self._spin_width.value()
        out_h = self._spin_height.value()
        mode: InterpolationMode = self._combo_interp.currentData()

        # Generar previsualización proporcional
        # Para evitar congelamientos si out_w es gigante (ej 4096), previsualizar con límite
        prev_max_dim = 256
        scale = min(1.0, prev_max_dim / max(out_w, out_h))
        pw = max(1, int(round(out_w * scale)))
        ph = max(1, int(round(out_h * scale)))

        try:
            prev_pixels = rectify_perspective(
                self._source_image.pixels,
                quad,
                pw,
                ph,
                interpolation=mode,
            )
            qimg = rgba_array_to_qimage(prev_pixels)
            pixmap = QPixmap.fromImage(qimg)
            self._label_preview.setPixmap(
                pixmap.scaled(
                    self._label_preview.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        except Exception as exc:
            logger.warning("Error en previsualización: %s", exc)
            self._label_preview.setText(self.tr("Error al previsualizar"))

    # ------------------------------------------------------------- exportación
    def _get_save_file_name(self, default_target: Path) -> str | None:
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Exportar textura rectificada"),
            str(default_target),
            export_dialog_filter(),
        )
        return file_path if file_path else None

    def _show_info(self, title: str, message: str) -> None:
        QMessageBox.information(self, title, message)

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)

    @property
    def output_width(self) -> int:
        return self._spin_width.value()

    @property
    def output_height(self) -> int:
        return self._spin_height.value()

    def set_dimensions(self, width: int, height: int) -> None:
        self._updating_dimensions = True
        self._spin_width.setValue(width)
        self._spin_height.setValue(height)
        self._updating_dimensions = False
        self._update_preview()

    @property
    def lock_aspect_ratio(self) -> bool:
        return self._chk_lock_aspect.isChecked()

    def set_lock_aspect_ratio(self, lock: bool) -> None:
        self._chk_lock_aspect.setChecked(lock)

    @property
    def interpolation_mode(self) -> InterpolationMode:
        return InterpolationMode(self._combo_interp.currentData())

    def set_interpolation_mode(self, mode: InterpolationMode) -> None:
        for idx in range(self._combo_interp.count()):
            if self._combo_interp.itemData(idx) == mode:
                self._combo_interp.setCurrentIndex(idx)
                break

    def export_texture(self) -> None:
        if self._source_image is None or not self._tool.selection.is_valid():
            return

        quad = self._tool.selection.get_quad()
        if quad is None:
            return

        out_w = self._spin_width.value()
        out_h = self._spin_height.value()
        mode = InterpolationMode(self._combo_interp.currentData())

        # Diálogo de guardado
        suggested_name = f"{self._source_image.path.stem}_rectified.png"
        default_target = self._source_image.path.parent / suggested_name

        file_path = self._get_save_file_name(default_target)
        if not file_path:
            return

        target = Path(file_path)

        try:
            # Rectificación a resolución completa
            full_rectified = rectify_perspective(
                self._source_image.pixels,
                quad,
                out_w,
                out_h,
                interpolation=mode,
            )
            export_image(full_rectified, target, overwrite=True)
            self._show_info(
                self.tr("Exportación exitosa"),
                self.tr("La textura se guardó correctamente en:\n{path}").format(path=target),
            )
            self.export_requested.emit(target)
        except ExportError as exc:
            logger.exception("Error de exportación: %s", exc)
            self._show_error(self.tr("Error al exportar"), str(exc))
        except Exception as exc:
            logger.exception("Error inesperado al exportar: %s", exc)
            self._show_error(self.tr("Error inesperado"), str(exc))
