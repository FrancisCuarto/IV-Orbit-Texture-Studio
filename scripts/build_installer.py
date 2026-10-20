"""Script de construcción del ejecutable y del instalador de IV Orbit Texture Studio.

Genera:
1. ``dist/IVOrbitTextureStudio/IVOrbitTextureStudio.exe`` (versión portable lista para usar)
2. ``dist/IV_Orbit_Texture_Studio_Setup.exe`` (instalador gráfico completo para Windows)

Uso:
    uv run python scripts/build_installer.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

ROOT_DIR = Path(__file__).resolve().parent.parent
BUILD_DIR = ROOT_DIR / "build"
DIST_DIR = ROOT_DIR / "dist"
APP_BUNDLE_NAME = "IVOrbitTextureStudio"
INSTALLER_NAME = "IV_Orbit_Texture_Studio_Setup"


def generate_icon(target_ico: Path) -> None:
    """Genera un icono .ico multirresolución para el ejecutable y el instalador."""
    target_ico.parent.mkdir(parents=True, exist_ok=True)
    size = 256
    img = Image.new("RGBA", (size, size), (22, 27, 34, 255))
    draw = ImageDraw.Draw(img)

    # Marco y cuadrícula de atlas
    draw.rounded_rectangle((16, 16, 240, 240), radius=28, fill=(28, 35, 45, 255))
    draw.rounded_rectangle((24, 24, 232, 232), radius=20, outline=(68, 76, 86, 255), width=4)
    draw.line((128, 24, 128, 232), fill=(52, 60, 70, 255), width=3)
    draw.line((24, 128, 232, 128), fill=(52, 60, 70, 255), width=3)

    # Bloques de textura simulados dentro del atlas
    draw.rectangle((36, 36, 118, 118), fill=(45, 95, 145, 190))
    draw.rectangle((138, 36, 220, 96), fill=(60, 140, 95, 190))
    draw.rectangle((36, 138, 108, 220), fill=(155, 95, 55, 190))

    # Cuadrilátero de perspectiva cian
    pts = [(54, 62), (206, 42), (190, 204), (44, 186)]
    for i in range(4):
        p1 = pts[i]
        p2 = pts[(i + 1) % 4]
        draw.line((p1[0], p1[1], p2[0], p2[1]), fill=(0, 215, 255, 255), width=9)

    # Manijas de las 4 esquinas en amarillo
    r = 16
    for x, y in pts:
        draw.ellipse(
            (x - r, y - r, x + r, y + r),
            fill=(255, 215, 0, 255),
            outline=(20, 24, 32, 255),
            width=4,
        )

    img.save(
        target_ico,
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )


def build_application_bundle(icon_path: Path) -> Path:
    """Empaqueta la aplicación principal con PyInstaller (--onedir)."""
    print("==> [1/3] Compilando aplicación principal con PyInstaller...")
    entry_script = ROOT_DIR / "src" / "iv_orbit_texture_studio" / "main.py"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        "--name",
        APP_BUNDLE_NAME,
        "--icon",
        str(icon_path),
        "--paths",
        str(ROOT_DIR / "src"),
        "--exclude-module",
        "pytest",
        "--exclude-module",
        "mypy",
        "--exclude-module",
        "ruff",
        "--exclude-module",
        "tkinter",
        str(entry_script),
    ]
    subprocess.run(cmd, cwd=ROOT_DIR, check=True)
    bundle_dir = DIST_DIR / APP_BUNDLE_NAME
    if not (bundle_dir / f"{APP_BUNDLE_NAME}.exe").is_file():
        raise RuntimeError(f"No se generó el ejecutable esperado en {bundle_dir}")
    return bundle_dir


def create_payload_zip(bundle_dir: Path, payload_zip: Path) -> None:
    """Comprime el directorio de la aplicación en payload.zip para el instalador."""
    print("==> [2/3] Empaquetando archivos en payload.zip...")
    if payload_zip.exists():
        payload_zip.unlink()

    files = [p for p in bundle_dir.rglob("*") if p.is_file()]
    with zipfile.ZipFile(payload_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for file_path in files:
            rel = file_path.relative_to(bundle_dir)
            zf.write(file_path, arcname=str(rel))


def build_setup_exe(icon_path: Path, payload_zip: Path) -> Path:
    """Compila el instalador gráfico autónomo IV_Orbit_Texture_Studio_Setup.exe."""
    print("==> [3/3] Generando instalador IV_Orbit_Texture_Studio_Setup.exe...")
    installer_script = ROOT_DIR / "scripts" / "installer_gui.py"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        INSTALLER_NAME,
        "--icon",
        str(icon_path),
        "--add-data",
        f"{payload_zip};.",
        "--add-data",
        f"{icon_path};.",
        "--exclude-module",
        "PySide6",
        "--exclude-module",
        "numpy",
        "--exclude-module",
        "cv2",
        "--exclude-module",
        "PIL",
        "--exclude-module",
        "pytest",
        str(installer_script),
    ]
    subprocess.run(cmd, cwd=ROOT_DIR, check=True)

    # Limpiar archivos .spec temporales de la raíz
    for spec_file in ROOT_DIR.glob("*.spec"):
        spec_file.unlink(missing_ok=True)

    setup_exe = DIST_DIR / f"{INSTALLER_NAME}.exe"
    if not setup_exe.is_file():
        raise RuntimeError(f"No se generó el instalador esperado: {setup_exe}")
    return setup_exe


def main() -> int:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    icon_path = BUILD_DIR / "app_icon.ico"
    generate_icon(icon_path)

    quick = "--installer-only" in sys.argv
    payload_zip = BUILD_DIR / "payload.zip"
    bundle_dir = DIST_DIR / APP_BUNDLE_NAME

    if quick and bundle_dir.is_dir() and payload_zip.is_file():
        print("==> Reusando payload.zip existente para recompilar únicamente el instalador...")
        setup_target = DIST_DIR / f"{INSTALLER_NAME}.exe"
        if setup_target.exists():
            setup_target.unlink()
    else:
        # Limpiar compilaciones previas si existen
        shutil.rmtree(bundle_dir, ignore_errors=True)
        setup_target = DIST_DIR / f"{INSTALLER_NAME}.exe"
        if setup_target.exists():
            setup_target.unlink()

        bundle_dir = build_application_bundle(icon_path)
        create_payload_zip(bundle_dir, payload_zip)

    setup_exe = build_setup_exe(icon_path, payload_zip)

    size_mb = setup_exe.stat().st_size / (1024 * 1024)
    print("\n============================================================")
    print("  COMPILACIÓN EXITOSA")
    print(f"  • Instalador: {setup_exe} ({size_mb:.1f} MB)")
    print(f"  • Portable:   {bundle_dir / (APP_BUNDLE_NAME + '.exe')}")
    print("============================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
