"""Asistente gráfico de instalación para IV Orbit Texture Studio en Windows.

Este script es empaquetado junto con ``payload.zip`` en un único ejecutable
``IV_Orbit_Texture_Studio_Setup.exe`` mediante PyInstaller. Permite instalar la
aplicación en el perfil del usuario (sin requerir permisos de administrador),
crear accesos directos en el Escritorio y Menú Inicio, asociar archivos ``.ivtex``
y registrar el desinstalador en Windows.
"""

from __future__ import annotations

import argparse
import contextlib
import os
import subprocess
import sys
import threading
import tkinter as tk
import winreg
import zipfile
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

APP_NAME = "IV Orbit Texture Studio"
APP_VERSION = "0.1.0"
PUBLISHER = "IV Orbit"
EXE_NAME = "IVOrbitTextureStudio.exe"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\IVOrbitTextureStudio"


def _resource_path(filename: str) -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base is not None:
        return Path(base) / filename
    return Path(__file__).resolve().parent.parent / "build" / filename


def _default_install_dir() -> Path:
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / "Programs" / APP_NAME
    return Path.home() / APP_NAME


def _create_shortcut(target_exe: Path, shortcut_path: Path, description: str) -> None:
    """Crea un acceso directo .lnk de Windows usando WScript.Shell."""
    shortcut_path.parent.mkdir(parents=True, exist_ok=True)
    ps_script = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{shortcut_path}'); "
        f"$s.TargetPath = '{target_exe}'; "
        f"$s.WorkingDirectory = '{target_exe.parent}'; "
        f"$s.IconLocation = '{target_exe},0'; "
        f"$s.Description = '{description}'; "
        "$s.Save()"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def _register_file_association(target_exe: Path) -> None:
    """Asocia la extensión .ivtex en el registro del usuario actual (HKCU)."""
    try:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\.ivtex") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "IVOrbit.Project")

        prog_id = r"Software\Classes\IVOrbit.Project"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, prog_id) as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "Proyecto de IV Orbit Texture Studio")

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"{prog_id}\\DefaultIcon") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f'"{target_exe}",0')

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"{prog_id}\\shell\\open\\command") as key:
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, f'"{target_exe}" "%1"')
    except OSError:
        pass


def _write_uninstaller(install_dir: Path, desktop_lnk: Path, start_menu_lnk: Path) -> Path:
    """Genera un script Desinstalar.cmd y registra la aplicación en Windows."""
    uninstall_cmd = install_dir / "Desinstalar.cmd"
    lines = [
        "@echo off",
        "chcp 65001 >nul",
        f"echo Desinstalando {APP_NAME}...",
        f'if exist "{desktop_lnk}" del /f /q "{desktop_lnk}"',
        f'if exist "{start_menu_lnk}" del /f /q "{start_menu_lnk}"',
        f'reg delete "HKCU\\{UNINSTALL_KEY}" /f >nul 2>&1',
        'reg delete "HKCU\\Software\\Classes\\.ivtex" /f >nul 2>&1',
        'reg delete "HKCU\\Software\\Classes\\IVOrbit.Project" /f >nul 2>&1',
        f'start /b "" cmd /c "timeout /t 2 /nobreak >nul & rmdir /s /q ""{install_dir}"""',
    ]
    uninstall_cmd.write_text("\r\n".join(lines), encoding="utf-8")

    try:
        target_exe = install_dir / EXE_NAME
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as key:
            winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
            winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
            winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, PUBLISHER)
            winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(install_dir))
            winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, str(target_exe))
            winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'"{uninstall_cmd}"')
            winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)
    except OSError:
        pass

    return uninstall_cmd


def perform_install(
    install_dir: Path,
    *,
    desktop_shortcut: bool = True,
    start_menu_shortcut: bool = True,
    associate_ivtex: bool = True,
    progress_cb=None,
) -> Path:
    """Extrae payload.zip en ``install_dir`` y configura los accesos directos."""
    payload = _resource_path("payload.zip")
    if not payload.is_file():
        raise FileNotFoundError(f"No se encontró el paquete de instalación: {payload}")

    install_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(payload, "r") as zf:
        members = zf.infolist()
        total = max(len(members), 1)
        for idx, member in enumerate(members, 1):
            zf.extract(member, install_dir)
            if progress_cb is not None:
                progress_cb(int(idx * 90 / total), f"Extrayendo: {Path(member.filename).name}")

    target_exe = install_dir / EXE_NAME
    if not target_exe.is_file():
        raise FileNotFoundError(f"No se encontró el ejecutable tras extraer: {target_exe}")

    desktop_dir = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
    desktop_lnk = desktop_dir / f"{APP_NAME}.lnk"

    appdata = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
    start_menu_dir = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    start_menu_lnk = start_menu_dir / f"{APP_NAME}.lnk"

    if desktop_shortcut:
        if progress_cb is not None:
            progress_cb(93, "Creando acceso directo en el Escritorio…")
        _create_shortcut(target_exe, desktop_lnk, APP_NAME)

    if start_menu_shortcut:
        if progress_cb is not None:
            progress_cb(96, "Creando acceso directo en el Menú Inicio…")
        _create_shortcut(target_exe, start_menu_lnk, APP_NAME)

    if associate_ivtex:
        _register_file_association(target_exe)

    _write_uninstaller(install_dir, desktop_lnk, start_menu_lnk)

    if progress_cb is not None:
        progress_cb(100, "¡Instalación completada!")

    return target_exe


class InstallerApp:
    """Interfaz gráfica del instalador con estilo oscuro."""

    def __init__(self, root: tk.Tk) -> None:
        if sys.platform == "win32":
            with contextlib.suppress(Exception):
                import ctypes

                ctypes.windll.shcore.SetProcessDpiAwareness(1)

        self.root = root
        self.root.title(f"Instalador — {APP_NAME} v{APP_VERSION}")
        self.root.geometry("580x490")
        self.root.minsize(540, 440)
        self.root.resizable(True, True)
        self.root.configure(bg="#161b22")

        icon_path = _resource_path("app_icon.ico")
        if icon_path.is_file():
            with contextlib.suppress(Exception):
                self.root.iconbitmap(str(icon_path))

        self.var_dir = tk.StringVar(value=str(_default_install_dir()))
        self.var_desktop = tk.BooleanVar(value=True)
        self.var_startmenu = tk.BooleanVar(value=True)
        self.var_assoc = tk.BooleanVar(value=True)
        self.var_launch = tk.BooleanVar(value=True)
        self.var_status = tk.StringVar(value="Listo para instalar.")
        self.installed_exe: Path | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        bg = "#161b22"
        card_bg = "#21262d"
        fg = "#f0f6fc"
        muted = "#8b949e"
        accent = "#1f6feb"

        # Encabezado (superior)
        header = tk.Frame(self.root, bg="#0d1117", padx=20, pady=16)
        header.pack(fill=tk.X, side=tk.TOP)
        tk.Label(
            header,
            text=f"🧩 {APP_NAME}",
            font=("Segoe UI", 16, "bold"),
            fg="#58a6ff",
            bg="#0d1117",
            anchor="w",
        ).pack(fill=tk.X)
        tk.Label(
            header,
            text=(
                f"Versión {APP_VERSION}  •  Suite para extraer texturas, "
                "corregir perspectiva y armar Atlas"
            ),
            font=("Segoe UI", 9),
            fg=muted,
            bg="#0d1117",
            anchor="w",
        ).pack(fill=tk.X, pady=(2, 0))

        # Botones inferiores (empaquetados al fondo ANTES del cuerpo para garantizar visibilidad)
        footer = tk.Frame(self.root, bg="#0d1117", padx=20, pady=14)
        footer.pack(fill=tk.X, side=tk.BOTTOM)

        self.btn_cancel = tk.Button(
            footer,
            text="Salir",
            font=("Segoe UI", 10),
            bg=card_bg,
            fg=fg,
            activebackground="#30363d",
            activeforeground=fg,
            relief=tk.FLAT,
            padx=18,
            pady=7,
            cursor="hand2",
            command=self.root.destroy,
        )
        self.btn_cancel.pack(side=tk.RIGHT, padx=(10, 0))

        self.btn_install = tk.Button(
            footer,
            text="▶  Instalar ahora",
            font=("Segoe UI", 10, "bold"),
            bg=accent,
            fg="white",
            activebackground="#388bfd",
            activeforeground="white",
            relief=tk.FLAT,
            padx=22,
            pady=7,
            cursor="hand2",
            command=self._start_install,
        )
        self.btn_install.pack(side=tk.RIGHT)

        # Atajos de teclado convenientes
        self.root.bind(
            "<Return>",
            lambda _e: self._start_install()
            if str(self.btn_install["state"]) != tk.DISABLED
            else None,
        )
        self.root.bind("<Escape>", lambda _e: self.root.destroy())

        # Cuerpo central (entre encabezado y pie)
        body = tk.Frame(self.root, bg=bg, padx=20, pady=14)
        body.pack(fill=tk.BOTH, expand=True)

        # Carpeta de destino
        tk.Label(
            body,
            text="Carpeta de instalación:",
            font=("Segoe UI", 10, "bold"),
            fg=fg,
            bg=bg,
            anchor="w",
        ).pack(fill=tk.X)

        dir_row = tk.Frame(body, bg=bg, pady=6)
        dir_row.pack(fill=tk.X)
        self.entry_dir = tk.Entry(
            dir_row,
            textvariable=self.var_dir,
            font=("Segoe UI", 10),
            bg=card_bg,
            fg=fg,
            insertbackground=fg,
            relief=tk.FLAT,
        )
        self.entry_dir.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5, padx=(0, 8))

        self.btn_browse = tk.Button(
            dir_row,
            text="Examinar…",
            font=("Segoe UI", 9),
            bg=card_bg,
            fg=fg,
            activebackground="#30363d",
            activeforeground=fg,
            relief=tk.FLAT,
            padx=10,
            pady=4,
            command=self._browse_dir,
        )
        self.btn_browse.pack(side=tk.RIGHT)

        # Opciones
        opts = tk.Frame(body, bg=card_bg, padx=14, pady=10)
        opts.pack(fill=tk.X, pady=(8, 12))

        for text, var in (
            ("Crear acceso directo en el Escritorio", self.var_desktop),
            ("Crear acceso directo en el Menú Inicio", self.var_startmenu),
            ("Asociar archivos de proyecto (.ivtex)", self.var_assoc),
            ("Ejecutar IV Orbit Texture Studio al terminar", self.var_launch),
        ):
            cb = tk.Checkbutton(
                opts,
                text=text,
                variable=var,
                font=("Segoe UI", 9),
                bg=card_bg,
                fg=fg,
                selectcolor="#0d1117",
                activebackground=card_bg,
                activeforeground=fg,
                anchor="w",
            )
            cb.pack(fill=tk.X, pady=2)

        # Progreso
        self.progress = ttk.Progressbar(body, orient="horizontal", mode="determinate", maximum=100)
        self.progress.pack(fill=tk.X, pady=(4, 4))

        tk.Label(
            body,
            textvariable=self.var_status,
            font=("Segoe UI", 9),
            fg=muted,
            bg=bg,
            anchor="w",
        ).pack(fill=tk.X)


    def _browse_dir(self) -> None:
        chosen = filedialog.askdirectory(
            parent=self.root,
            title="Seleccionar carpeta de instalación",
            initialdir=self.var_dir.get(),
        )
        if chosen:
            self.var_dir.set(str(Path(chosen) / APP_NAME))

    def _start_install(self) -> None:
        target = Path(self.var_dir.get().strip())
        self.btn_install.configure(state=tk.DISABLED)
        self.btn_browse.configure(state=tk.DISABLED)
        self.entry_dir.configure(state=tk.DISABLED)

        def update_progress(pct: int, msg: str) -> None:
            self.root.after(0, lambda: self._set_progress(pct, msg))

        def worker() -> None:
            try:
                exe = perform_install(
                    target,
                    desktop_shortcut=self.var_desktop.get(),
                    start_menu_shortcut=self.var_startmenu.get(),
                    associate_ivtex=self.var_assoc.get(),
                    progress_cb=update_progress,
                )
                self.installed_exe = exe
                self.root.after(0, self._on_install_success)
            except Exception as exc:
                self.root.after(0, lambda e=exc: self._on_install_error(e))

        threading.Thread(target=worker, daemon=True).start()

    def _set_progress(self, pct: int, msg: str) -> None:
        self.progress["value"] = pct
        self.var_status.set(msg)

    def _on_install_success(self) -> None:
        if self.var_launch.get() and self.installed_exe is not None:
            subprocess.Popen([str(self.installed_exe)], cwd=str(self.installed_exe.parent))
            self.root.destroy()
            return

        messagebox.showinfo(
            "Instalación completada",
            f"{APP_NAME} se instaló correctamente en:\n{self.var_dir.get()}",
            parent=self.root,
        )
        self.btn_cancel.configure(text="Finalizar")

    def _on_install_error(self, exc: Exception) -> None:
        messagebox.showerror("Error en la instalación", str(exc), parent=self.root)
        self.btn_install.configure(state=tk.NORMAL)
        self.btn_browse.configure(state=tk.NORMAL)
        self.entry_dir.configure(state=tk.NORMAL)


def main() -> int:
    parser = argparse.ArgumentParser(description=f"Instalador de {APP_NAME}")
    parser.add_argument("--silent", action="store_true", help="Instalación silenciosa sin GUI")
    parser.add_argument("--dir", type=str, default="", help="Carpeta de instalación personalizada")
    parser.add_argument(
        "--no-shortcuts",
        action="store_true",
        help="No crear accesos directos ni asociaciones de archivo",
    )
    args = parser.parse_args()

    if args.silent:
        target_dir = Path(args.dir) if args.dir else _default_install_dir()
        perform_install(
            target_dir,
            desktop_shortcut=not args.no_shortcuts,
            start_menu_shortcut=not args.no_shortcuts,
            associate_ivtex=not args.no_shortcuts,
        )
        return 0

    root = tk.Tk()
    InstallerApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
