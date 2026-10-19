"""Panel de control lateral para la generación y exportación de mapas PBR y normales."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from iv_orbit_texture_studio.core.document import PbrSettings
from iv_orbit_texture_studio.exporters.image_exporter import export_dialog_filter, export_image
from iv_orbit_texture_studio.tools.pbr.tool import PbrTool

if TYPE_CHECKING:
    from iv_orbit_texture_studio.imaging.image_io import LoadedImage

logger = logging.getLogger(__name__)


class PbrPanel(QWidget):
    """Panel de configuración para mapas de normales, relieve, rugosidad, AO y empaquetado."""

    map_exported = Signal(Path)
    maps_batch_exported = Signal(list)
    pbr_modified = Signal()

    def __init__(self, tool: PbrTool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tool = tool
        self._source_image: LoadedImage | None = None
        self._updating: bool = False

        self._setup_ui()
        self._tool.settings_changed.connect(self._sync_ui_from_settings)
        self.setMinimumWidth(330)
        self._update_ui_state()

    def set_source_image(self, image: LoadedImage | None) -> None:
        self._source_image = image
        self._tool.set_source_image(image)
        self._update_ui_state()

    def get_settings(self) -> PbrSettings:
        return self._tool.settings

    def set_settings(self, settings: PbrSettings) -> None:
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

        # 1. Selector de mapa visualizado en el lienzo
        group_view = QGroupBox(self.tr("Vista en Lienzo"))
        v_view = QVBoxLayout(group_view)
        self._combo_map_type = QComboBox()
        self._combo_map_type.addItem(self.tr("Mapa de Normales (Tangente)"), "normal")
        self._combo_map_type.addItem(self.tr("Mapa de Altura / Relieve (Height)"), "height")
        self._combo_map_type.addItem(self.tr("Mapa de Rugosidad (Roughness)"), "roughness")
        self._combo_map_type.addItem(self.tr("Oclusión Ambiental (AO)"), "ao")
        self._combo_map_type.addItem(self.tr("Empaquetado PBR (ORM / RMA)"), "orm")
        self._combo_map_type.addItem(self.tr("Textura Original (Difusa / Albedo)"), "diffuse")
        self._combo_map_type.currentIndexChanged.connect(self._on_map_type_changed)
        v_view.addWidget(self._combo_map_type)
        layout.addWidget(group_view)

        # 2. Grupo: Mapa de Normales
        group_norm = QGroupBox(self.tr("Mapa de Normales"))
        form_norm = QFormLayout(group_norm)

        # Intensidad / Strength
        h_strength = QHBoxLayout()
        self._slider_norm_str, self._spin_norm_str = self._create_slider_spin(1, 100, 20, "x")
        self._slider_norm_str.valueChanged.connect(self._on_values_changed)
        h_strength.addWidget(self._slider_norm_str)
        h_strength.addWidget(self._spin_norm_str)
        form_norm.addRow(self.tr("Intensidad:"), h_strength)

        # Formato (OpenGL vs DirectX)
        self._combo_norm_format = QComboBox()
        self._combo_norm_format.addItem(self.tr("OpenGL (+Y - Blender, Godot)"), True)
        self._combo_norm_format.addItem(self.tr("DirectX (-Y - Unreal Engine)"), False)
        self._combo_norm_format.currentIndexChanged.connect(self._on_values_changed)
        form_norm.addRow(self.tr("Formato:"), self._combo_norm_format)

        # Suavizado previo
        self._spin_norm_blur = QSpinBox()
        self._spin_norm_blur.setRange(0, 5)
        self._spin_norm_blur.setValue(0)
        self._spin_norm_blur.setSuffix(" px")
        self._spin_norm_blur.valueChanged.connect(self._on_values_changed)
        form_norm.addRow(self.tr("Filtro de ruido:"), self._spin_norm_blur)

        # Inversión de ejes
        h_inv = QHBoxLayout()
        self._chk_inv_x = QCheckBox(self.tr("Invertir X (R)"))
        self._chk_inv_x.toggled.connect(self._on_values_changed)
        self._chk_inv_y = QCheckBox(self.tr("Invertir Y (G)"))
        self._chk_inv_y.toggled.connect(self._on_values_changed)
        h_inv.addWidget(self._chk_inv_x)
        h_inv.addWidget(self._chk_inv_y)
        form_norm.addRow("", h_inv)

        layout.addWidget(group_norm)

        # 3. Grupo: Mapa de Altura (Height / Bump)
        group_height = QGroupBox(self.tr("Mapa de Altura (Height)"))
        form_height = QFormLayout(group_height)

        h_hcontrast = QHBoxLayout()
        self._slider_h_contrast, self._spin_h_contrast = self._create_slider_spin(10, 300, 100, "%")
        self._slider_h_contrast.valueChanged.connect(self._on_values_changed)
        h_hcontrast.addWidget(self._slider_h_contrast)
        h_hcontrast.addWidget(self._spin_h_contrast)
        form_height.addRow(self.tr("Contraste:"), h_hcontrast)

        h_hbright = QHBoxLayout()
        self._slider_h_bright, self._spin_h_bright = self._create_slider_spin(-100, 100, 0, "%")
        self._slider_h_bright.valueChanged.connect(self._on_values_changed)
        h_hbright.addWidget(self._slider_h_bright)
        h_hbright.addWidget(self._spin_h_bright)
        form_height.addRow(self.tr("Brillo base:"), h_hbright)

        self._spin_h_blur = QSpinBox()
        self._spin_h_blur.setRange(0, 5)
        self._spin_h_blur.setValue(0)
        self._spin_h_blur.setSuffix(" px")
        self._spin_h_blur.valueChanged.connect(self._on_values_changed)
        form_height.addRow(self.tr("Suavizado:"), self._spin_h_blur)

        self._chk_h_invert = QCheckBox(self.tr("Invertir altura (hendiduras claras)"))
        self._chk_h_invert.toggled.connect(self._on_values_changed)
        form_height.addRow("", self._chk_h_invert)

        layout.addWidget(group_height)

        # 4. Grupo: Mapa de Rugosidad (Roughness)
        group_rough = QGroupBox(self.tr("Mapa de Rugosidad (Roughness)"))
        form_rough = QFormLayout(group_rough)

        h_base_rough = QHBoxLayout()
        self._slider_base_rough, self._spin_base_rough = self._create_slider_spin(0, 100, 50, "%")
        self._slider_base_rough.valueChanged.connect(self._on_values_changed)
        h_base_rough.addWidget(self._slider_base_rough)
        h_base_rough.addWidget(self._spin_base_rough)
        form_rough.addRow(self.tr("Rugosidad base:"), h_base_rough)

        h_detail_rough = QHBoxLayout()
        self._slider_detail_rough, self._spin_detail_rough = self._create_slider_spin(
            0, 100, 30, "%"
        )
        self._slider_detail_rough.valueChanged.connect(self._on_values_changed)
        h_detail_rough.addWidget(self._slider_detail_rough)
        h_detail_rough.addWidget(self._spin_detail_rough)
        form_rough.addRow(self.tr("Detalle textura:"), h_detail_rough)

        self._chk_rough_invert = QCheckBox(self.tr("Invertir (Modo Suavidad / Glossiness)"))
        self._chk_rough_invert.toggled.connect(self._on_values_changed)
        form_rough.addRow("", self._chk_rough_invert)

        layout.addWidget(group_rough)

        # 5. Grupo: Oclusión Ambiental (AO)
        group_ao = QGroupBox(self.tr("Oclusión Ambiental (AO)"))
        form_ao = QFormLayout(group_ao)

        h_ao_str = QHBoxLayout()
        self._slider_ao_str, self._spin_ao_str = self._create_slider_spin(0, 300, 150, "%")
        self._slider_ao_str.valueChanged.connect(self._on_values_changed)
        h_ao_str.addWidget(self._slider_ao_str)
        h_ao_str.addWidget(self._spin_ao_str)
        form_ao.addRow(self.tr("Intensidad sombras:"), h_ao_str)

        self._spin_ao_rad = QSpinBox()
        self._spin_ao_rad.setRange(1, 15)
        self._spin_ao_rad.setValue(5)
        self._spin_ao_rad.setSuffix(" px")
        self._spin_ao_rad.valueChanged.connect(self._on_values_changed)
        form_ao.addRow(self.tr("Radio cavidad:"), self._spin_ao_rad)

        layout.addWidget(group_ao)

        # 6. Grupo: Empaquetado y Metálico
        group_pack = QGroupBox(self.tr("Empaquetado y Metálico"))
        form_pack = QFormLayout(group_pack)

        h_metal = QHBoxLayout()
        self._slider_metal, self._spin_metal = self._create_slider_spin(0, 100, 0, "%")
        self._slider_metal.valueChanged.connect(self._on_values_changed)
        h_metal.addWidget(self._slider_metal)
        h_metal.addWidget(self._spin_metal)
        form_pack.addRow(self.tr("Metálico:"), h_metal)

        self._combo_pack_fmt = QComboBox()
        self._combo_pack_fmt.addItem("ORM (R: Occlusion, G: Roughness, B: Metallic)", "ORM")
        self._combo_pack_fmt.addItem("RMA (R: Roughness, G: Metallic, B: Occlusion)", "RMA")
        self._combo_pack_fmt.currentIndexChanged.connect(self._on_values_changed)
        form_pack.addRow(self.tr("Formato pack:"), self._combo_pack_fmt)

        layout.addWidget(group_pack)

        # 7. Botón de restablecimiento
        self._btn_reset = QPushButton(self.tr("Restablecer ajustes PBR"))
        self._btn_reset.clicked.connect(self._reset_settings)
        layout.addWidget(self._btn_reset)

        # 8. Grupo de Exportación
        group_export = QGroupBox(self.tr("Exportación PBR"))
        v_export = QVBoxLayout(group_export)

        self._btn_export_active = QPushButton(self.tr("Exportar mapa visible actual…"))
        self._btn_export_active.clicked.connect(self.export_active_map)
        v_export.addWidget(self._btn_export_active)

        self._btn_export_all = QPushButton(self.tr("Exportar set PBR completo (todos)…"))
        self._btn_export_all.setStyleSheet(
            "QPushButton { background-color: #0d6efd; color: white; "
            "font-weight: bold; padding: 6px; border-radius: 4px; }\n"
            "QPushButton:hover { background-color: #0b5ed7; }\n"
            "QPushButton:disabled { background-color: #444444; color: #888888; }"
        )
        self._btn_export_all.clicked.connect(self.export_all_maps)
        v_export.addWidget(self._btn_export_all)

        layout.addWidget(group_export)

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    # ----------------------------------------------------------------- helpers
    def _create_slider_spin(
        self, min_val: int, max_val: int, init_val: int, suffix: str
    ) -> tuple[QSlider, QSpinBox]:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        slider.setValue(init_val)

        spin = QSpinBox()
        spin.setRange(min_val, max_val)
        spin.setValue(init_val)
        spin.setSuffix(f" {suffix}")
        spin.setFixedWidth(75)

        slider.valueChanged.connect(spin.setValue)
        spin.valueChanged.connect(slider.setValue)
        return slider, spin

    def _update_ui_state(self) -> None:
        has_image = self._source_image is not None
        self._combo_map_type.setEnabled(has_image)
        self._slider_norm_str.setEnabled(has_image)
        self._spin_norm_str.setEnabled(has_image)
        self._combo_norm_format.setEnabled(has_image)
        self._spin_norm_blur.setEnabled(has_image)
        self._chk_inv_x.setEnabled(has_image)
        self._chk_inv_y.setEnabled(has_image)

        self._slider_h_contrast.setEnabled(has_image)
        self._spin_h_contrast.setEnabled(has_image)
        self._slider_h_bright.setEnabled(has_image)
        self._spin_h_bright.setEnabled(has_image)
        self._spin_h_blur.setEnabled(has_image)
        self._chk_h_invert.setEnabled(has_image)

        self._slider_base_rough.setEnabled(has_image)
        self._spin_base_rough.setEnabled(has_image)
        self._slider_detail_rough.setEnabled(has_image)
        self._spin_detail_rough.setEnabled(has_image)
        self._chk_rough_invert.setEnabled(has_image)

        self._slider_ao_str.setEnabled(has_image)
        self._spin_ao_str.setEnabled(has_image)
        self._spin_ao_rad.setEnabled(has_image)

        self._slider_metal.setEnabled(has_image)
        self._spin_metal.setEnabled(has_image)
        self._combo_pack_fmt.setEnabled(has_image)

        self._btn_reset.setEnabled(has_image)
        self._btn_export_active.setEnabled(has_image)
        self._btn_export_all.setEnabled(has_image)

    def _sync_ui_from_settings(self) -> None:
        self._updating = True
        s = self._tool.settings

        self._slider_norm_str.setValue(int(round(s.normal_strength * 10)))
        idx_fmt = self._combo_norm_format.findData(s.format_opengl)
        if idx_fmt >= 0:
            self._combo_norm_format.setCurrentIndex(idx_fmt)
        self._spin_norm_blur.setValue(s.normal_blur)
        self._chk_inv_x.setChecked(s.invert_x)
        self._chk_inv_y.setChecked(s.invert_y)

        self._slider_h_contrast.setValue(int(round(s.height_contrast * 100)))
        self._slider_h_bright.setValue(int(round(s.height_brightness * 100)))
        self._spin_h_blur.setValue(s.height_blur)
        self._chk_h_invert.setChecked(s.height_invert)

        self._slider_base_rough.setValue(int(round(s.base_roughness * 100)))
        self._slider_detail_rough.setValue(int(round(s.roughness_detail * 100)))
        self._chk_rough_invert.setChecked(s.roughness_invert)

        self._slider_ao_str.setValue(int(round(s.ao_strength * 100)))
        self._spin_ao_rad.setValue(s.ao_radius)

        self._slider_metal.setValue(int(round(s.metallic * 100)))
        idx_pack = self._combo_pack_fmt.findData(s.packing_format)
        if idx_pack >= 0:
            self._combo_pack_fmt.setCurrentIndex(idx_pack)

        self._updating = False
        self._update_ui_state()

    def _on_map_type_changed(self, index: int) -> None:
        map_type = self._combo_map_type.itemData(index)
        if map_type:
            self._tool.set_active_map_type(str(map_type))

    def _on_values_changed(self) -> None:
        if self._updating:
            return
        settings = PbrSettings(
            normal_strength=self._slider_norm_str.value() / 10.0,
            format_opengl=bool(self._combo_norm_format.currentData()),
            normal_blur=self._spin_norm_blur.value(),
            invert_x=self._chk_inv_x.isChecked(),
            invert_y=self._chk_inv_y.isChecked(),
            height_contrast=self._slider_h_contrast.value() / 100.0,
            height_brightness=self._slider_h_bright.value() / 100.0,
            height_invert=self._chk_h_invert.isChecked(),
            height_blur=self._spin_h_blur.value(),
            base_roughness=self._slider_base_rough.value() / 100.0,
            roughness_detail=self._slider_detail_rough.value() / 100.0,
            roughness_invert=self._chk_rough_invert.isChecked(),
            roughness_contrast=1.0,
            ao_strength=self._slider_ao_str.value() / 100.0,
            ao_radius=self._spin_ao_rad.value(),
            ao_contrast=1.0,
            metallic=self._slider_metal.value() / 100.0,
            packing_format=str(self._combo_pack_fmt.currentData()),
        )
        self._tool.set_settings(settings)
        self._update_ui_state()
        self.pbr_modified.emit()

    def _reset_settings(self) -> None:
        self.set_settings(PbrSettings())
        self.pbr_modified.emit()

    # ------------------------------------------------------------- exportación
    def export_active_map(self) -> None:
        """Exporta el mapa actualmente seleccionado en el combo."""
        if self._source_image is None or self._tool.processed_pixels is None:
            return

        map_name = self._tool.active_map_type
        default_name = f"{self._source_image.path.stem}_{map_name}.png"
        start_dir = str(self._source_image.path.parent / default_name)

        target_str, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Exportar mapa {name}").format(name=map_name),
            start_dir,
            export_dialog_filter(),
        )
        if not target_str:
            return

        target_path = Path(target_str)
        try:
            export_image(self._tool.processed_pixels, target_path, overwrite=True)
            QMessageBox.information(
                self,
                self.tr("Mapa exportado"),
                self.tr("El mapa se guardó exitosamente en:\n{path}").format(path=target_path.name),
            )
            self.map_exported.emit(target_path)
        except Exception as exc:
            logger.exception("Error al exportar mapa PBR: %s", exc)
            QMessageBox.critical(self, self.tr("Error al exportar"), str(exc))

    def export_all_maps(self) -> None:
        """Exporta el conjunto PBR completo (_normal, _height, _roughness, _ao, _orm)."""
        if self._source_image is None:
            return

        stem = self._source_image.path.stem
        suggested = str(self._source_image.path.parent / f"{stem}_PBR")

        target_dir = QFileDialog.getExistingDirectory(
            self,
            self.tr("Seleccionar carpeta de destino para el set PBR"),
            suggested,
        )
        if not target_dir:
            return

        out_dir = Path(target_dir)
        exported_files: list[Path] = []
        maps_to_export = [
            ("normal", f"{stem}_normal.png"),
            ("height", f"{stem}_height.png"),
            ("roughness", f"{stem}_roughness.png"),
            ("ao", f"{stem}_ao.png"),
            ("orm", f"{stem}_{self._tool.settings.packing_format.lower()}.png"),
        ]

        try:
            for map_key, filename in maps_to_export:
                pixels = self._tool.get_map(map_key)
                if pixels is not None:
                    file_path = out_dir / filename
                    export_image(pixels, file_path, overwrite=True)
                    exported_files.append(file_path)

            QMessageBox.information(
                self,
                self.tr("Set PBR exportado"),
                self.tr("Se exportaron exitosamente {count} mapas en:\n{dir}").format(
                    count=len(exported_files), dir=out_dir.name
                ),
            )
            self.maps_batch_exported.emit(exported_files)
        except Exception as exc:
            logger.exception("Error durante la exportación en lote del set PBR: %s", exc)
            QMessageBox.critical(self, self.tr("Error al exportar"), str(exc))
