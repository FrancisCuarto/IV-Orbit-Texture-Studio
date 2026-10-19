"""Panel de control para la preparación de texturas, filtros y generación seamless."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from iv_orbit_texture_studio.core.document import TexturePrepSettings
from iv_orbit_texture_studio.exporters.image_exporter import export_dialog_filter, export_image
from iv_orbit_texture_studio.imaging.transforms import process_texture_pipeline
from iv_orbit_texture_studio.tools.texture_prep.tool import TexturePrepTool

if TYPE_CHECKING:
    from iv_orbit_texture_studio.imaging.image_io import LoadedImage

logger = logging.getLogger(__name__)


class TexturePrepPanel(QWidget):
    """Panel lateral de control para filtros de color, seamless y mosaico."""

    texture_exported = Signal(Path)
    prep_modified = Signal()

    def __init__(self, tool: TexturePrepTool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tool = tool
        self._source_image: LoadedImage | None = None
        self._updating = False

        self._setup_ui()
        self._tool.settings_changed.connect(self._sync_ui_from_settings)
        self.setMinimumWidth(320)
        self._update_ui_state()

    def set_source_image(self, image: LoadedImage | None) -> None:
        self._source_image = image
        self._tool.set_source_image(image)
        self._update_ui_state()

    def get_settings(self) -> TexturePrepSettings:
        return self._tool.settings

    def set_settings(self, settings: TexturePrepSettings) -> None:
        self._tool.set_settings(settings)
        self._sync_ui_from_settings()

    # ---------------------------------------------------------------------- UI
    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(10)

        # 1. Grupo: Filtros de Color y Tono
        group_color = QGroupBox(self.tr("Ajustes de Color e Iluminación"))
        form_color = QFormLayout(group_color)

        # Brillo
        self._slider_bright, self._spin_bright = self._create_slider_spin(-100, 100, 0, "%")
        self._slider_bright.valueChanged.connect(self._on_values_changed)
        h_bright = QHBoxLayout()
        h_bright.addWidget(self._slider_bright)
        h_bright.addWidget(self._spin_bright)
        form_color.addRow(self.tr("Brillo:"), h_bright)

        # Contraste
        self._slider_contrast, self._spin_contrast = self._create_slider_spin(-100, 100, 0, "%")
        self._slider_contrast.valueChanged.connect(self._on_values_changed)
        h_contrast = QHBoxLayout()
        h_contrast.addWidget(self._slider_contrast)
        h_contrast.addWidget(self._spin_contrast)
        form_color.addRow(self.tr("Contraste:"), h_contrast)

        # Saturación
        self._slider_sat, self._spin_sat = self._create_slider_spin(-100, 100, 0, "%")
        self._slider_sat.valueChanged.connect(self._on_values_changed)
        h_sat = QHBoxLayout()
        h_sat.addWidget(self._slider_sat)
        h_sat.addWidget(self._spin_sat)
        form_color.addRow(self.tr("Saturación:"), h_sat)

        # Nivelación de iluminación
        self._slider_eq, self._spin_eq = self._create_slider_spin(0, 100, 0, "%")
        self._slider_eq.valueChanged.connect(self._on_values_changed)
        h_eq = QHBoxLayout()
        h_eq.addWidget(self._slider_eq)
        h_eq.addWidget(self._spin_eq)
        form_color.addRow(self.tr("Aplanar luz:"), h_eq)

        # Balance de color RGB
        h_rgb = QHBoxLayout()
        self._spin_red = QDoubleSpinBox()
        self._spin_red.setRange(0.0, 3.0)
        self._spin_red.setSingleStep(0.05)
        self._spin_red.setValue(1.0)
        self._spin_red.valueChanged.connect(self._on_values_changed)

        self._spin_green = QDoubleSpinBox()
        self._spin_green.setRange(0.0, 3.0)
        self._spin_green.setSingleStep(0.05)
        self._spin_green.setValue(1.0)
        self._spin_green.valueChanged.connect(self._on_values_changed)

        self._spin_blue = QDoubleSpinBox()
        self._spin_blue.setRange(0.0, 3.0)
        self._spin_blue.setSingleStep(0.05)
        self._spin_blue.setValue(1.0)
        self._spin_blue.valueChanged.connect(self._on_values_changed)

        h_rgb.addWidget(QLabel("R:"))
        h_rgb.addWidget(self._spin_red)
        h_rgb.addWidget(QLabel("G:"))
        h_rgb.addWidget(self._spin_green)
        h_rgb.addWidget(QLabel("B:"))
        h_rgb.addWidget(self._spin_blue)
        form_color.addRow(self.tr("Balance RGB:"), h_rgb)

        self._btn_reset_color = QPushButton(self.tr("Restablecer ajustes"))
        self._btn_reset_color.clicked.connect(self._reset_filters)
        form_color.addRow("", self._btn_reset_color)

        layout.addWidget(group_color)

        # 2. Grupo: Generación Seamless
        group_seamless = QGroupBox(self.tr("Generación sin costuras (Seamless)"))
        v_seamless = QVBoxLayout(group_seamless)

        self._chk_seamless = QCheckBox(self.tr("Habilitar textura sin costuras (Seamless)"))
        self._chk_seamless.setChecked(False)
        self._chk_seamless.toggled.connect(self._on_values_changed)
        v_seamless.addWidget(self._chk_seamless)

        form_seamless = QFormLayout()
        self._slider_blend, self._spin_blend = self._create_slider_spin(2, 45, 20, "%")
        self._slider_blend.valueChanged.connect(self._on_values_changed)
        h_blend = QHBoxLayout()
        h_blend.addWidget(self._slider_blend)
        h_blend.addWidget(self._spin_blend)
        form_seamless.addRow(self.tr("Margen de mezcla:"), h_blend)
        v_seamless.addLayout(form_seamless)

        layout.addWidget(group_seamless)

        # 3. Grupo: Mosaico y Repetición (Tiling)
        group_tiling = QGroupBox(self.tr("Previsualización en Mosaico (Tiling)"))
        v_tiling = QVBoxLayout(group_tiling)

        self._chk_tiled = QCheckBox(self.tr("Previsualizar mosaico repetido en el lienzo"))
        self._chk_tiled.setChecked(False)
        self._chk_tiled.toggled.connect(self._on_tiled_toggled)
        v_tiling.addWidget(self._chk_tiled)

        form_tiling = QFormLayout()
        h_grid = QHBoxLayout()
        self._spin_grid_x = QSpinBox()
        self._spin_grid_x.setRange(1, 8)
        self._spin_grid_x.setValue(3)
        self._spin_grid_x.valueChanged.connect(self._on_values_changed)

        self._spin_grid_y = QSpinBox()
        self._spin_grid_y.setRange(1, 8)
        self._spin_grid_y.setValue(3)
        self._spin_grid_y.valueChanged.connect(self._on_values_changed)

        h_grid.addWidget(QLabel("X:"))
        h_grid.addWidget(self._spin_grid_x)
        h_grid.addWidget(QLabel("Y:"))
        h_grid.addWidget(self._spin_grid_y)
        form_tiling.addRow(self.tr("Repeticiones:"), h_grid)
        v_tiling.addLayout(form_tiling)

        layout.addWidget(group_tiling)

        # 4. Grupo: Exportación
        group_export = QGroupBox(self.tr("Exportación"))
        v_export = QVBoxLayout(group_export)

        self._btn_export = QPushButton(self.tr("Exportar textura preparada…"))
        self._btn_export.setStyleSheet(
            "QPushButton { background-color: #0d6efd; color: white; "
            "font-weight: bold; padding: 6px; border-radius: 4px; }\n"
            "QPushButton:hover { background-color: #0b5ed7; }\n"
            "QPushButton:disabled { background-color: #444444; color: #888888; }"
        )
        self._btn_export.clicked.connect(self.export_texture)
        v_export.addWidget(self._btn_export)

        layout.addWidget(group_export)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    # ----------------------------------------------------------------- helpers
    def _create_slider_spin(
        self, min_val: int, max_val: int, default: int, suffix: str = ""
    ) -> tuple[QSlider, QSpinBox]:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(default)

        spin = QSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(default)
        if suffix:
            spin.setSuffix(f" {suffix}")
        spin.setMinimumWidth(65)

        slider.valueChanged.connect(spin.setValue)
        spin.valueChanged.connect(slider.setValue)
        return slider, spin

    def _update_ui_state(self) -> None:
        has_image = self._source_image is not None
        self._slider_bright.setEnabled(has_image)
        self._spin_bright.setEnabled(has_image)
        self._slider_contrast.setEnabled(has_image)
        self._spin_contrast.setEnabled(has_image)
        self._slider_sat.setEnabled(has_image)
        self._spin_sat.setEnabled(has_image)
        self._slider_eq.setEnabled(has_image)
        self._spin_eq.setEnabled(has_image)
        self._spin_red.setEnabled(has_image)
        self._spin_green.setEnabled(has_image)
        self._spin_blue.setEnabled(has_image)
        self._btn_reset_color.setEnabled(has_image)
        self._btn_export.setEnabled(has_image)
        self._chk_seamless.setEnabled(has_image)
        self._slider_blend.setEnabled(has_image and self._chk_seamless.isChecked())
        self._spin_blend.setEnabled(has_image and self._chk_seamless.isChecked())
        self._chk_tiled.setEnabled(has_image)
        self._spin_grid_x.setEnabled(has_image and self._chk_tiled.isChecked())
        self._spin_grid_y.setEnabled(has_image and self._chk_tiled.isChecked())

    def _sync_ui_from_settings(self) -> None:
        self._updating = True
        s = self._tool.settings
        self._slider_bright.setValue(int(round(s.brightness * 100)))
        self._slider_contrast.setValue(int(round(s.contrast * 100)))
        self._slider_sat.setValue(int(round(s.saturation * 100)))
        self._slider_eq.setValue(int(round(s.equalize_light * 100)))
        self._spin_red.setValue(s.red_gain)
        self._spin_green.setValue(s.green_gain)
        self._spin_blue.setValue(s.blue_gain)
        self._chk_seamless.setChecked(s.seamless_enabled)
        self._slider_blend.setValue(int(round(s.seamless_blend * 100)))
        self._chk_tiled.setChecked(self._tool.is_tiled_view)
        self._spin_grid_x.setValue(s.tiling_grid_x)
        self._spin_grid_y.setValue(s.tiling_grid_y)
        self._updating = False
        self._update_ui_state()

    def _on_values_changed(self) -> None:
        if self._updating:
            return
        settings = TexturePrepSettings(
            brightness=self._slider_bright.value() / 100.0,
            contrast=self._slider_contrast.value() / 100.0,
            saturation=self._slider_sat.value() / 100.0,
            equalize_light=self._slider_eq.value() / 100.0,
            red_gain=self._spin_red.value(),
            green_gain=self._spin_green.value(),
            blue_gain=self._spin_blue.value(),
            seamless_enabled=self._chk_seamless.isChecked(),
            seamless_blend=self._slider_blend.value() / 100.0,
            tiling_grid_x=self._spin_grid_x.value(),
            tiling_grid_y=self._spin_grid_y.value(),
        )
        self._tool.set_settings(settings)
        self._update_ui_state()
        self.prep_modified.emit()

    def _on_tiled_toggled(self, checked: bool) -> None:
        self._tool.set_tiled_view(checked)
        self._update_ui_state()
        self.prep_modified.emit()

    def _reset_filters(self) -> None:
        self.set_settings(TexturePrepSettings())
        self.prep_modified.emit()

    # ------------------------------------------------------------- exportación
    def export_texture(self) -> None:
        """Exporta la textura preparada (con filtros y seamless aplicados)."""
        if self._source_image is None or self._tool.processed_pixels is None:
            return

        default_name = f"{self._source_image.path.stem}_prepared.png"
        start_dir = str(self._source_image.path.parent / default_name)

        target_str, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Exportar textura preparada"),
            start_dir,
            export_dialog_filter(),
        )
        if not target_str:
            return

        target_path = Path(target_str)
        try:
            # Exportar la textura procesada sin repetición de mosaico
            if not self._tool.is_tiled_view:
                out_pixels = self._tool.processed_pixels
            else:
                out_pixels = process_texture_pipeline(
                    self._source_image.pixels,
                    self._tool.settings,
                    tiled=False,
                )
            export_image(out_pixels, target_path, overwrite=True)
            msg = self.tr("La textura se guardó exitosamente en:\n{path}").format(
                path=target_path.name
            )
            QMessageBox.information(
                self,
                self.tr("Textura exportada"),
                msg,
            )
            self.texture_exported.emit(target_path)
        except Exception as exc:
            logger.exception("Error al exportar textura preparada: %s", exc)
            QMessageBox.critical(self, self.tr("Error al exportar"), str(exc))
