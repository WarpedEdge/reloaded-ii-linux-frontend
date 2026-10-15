"""Freedesktop launchers; no shell scripts or temporary AppImage mount paths.

Exec quoting follows https://specifications.freedesktop.org/desktop-entry/latest/exec-variables.html
"""

import os
import shutil
from pathlib import Path

from . import proton
from .storage import Transaction, state_home


def escape_value(value):
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")


def exec_line(argv):
    if not argv or "=" in str(argv[0]):
        raise ValueError("Invalid desktop launcher executable")
    quoted = []
    for arg in map(str, argv):
        if any(c in arg for c in "\n\r\x00"):
            raise ValueError("Launcher paths must not contain line breaks or NUL characters")
        # Desktop string escaping is decoded before the Exec argument quoting layer.
        value = "".join("\\" + c if c in '\\"`$' else c for c in arg)
        quoted.append('"' + escape_value(value.replace("%", "%%")) + '"')
    return " ".join(quoted)


def desktop_entry(name, argv, icon="applications-games"):
    return (
        "[Desktop Entry]\nType=Application\nVersion=1.0\n"
        f"Name={escape_value(name)}\nExec={exec_line(argv)}\nIcon={escape_value(icon)}\n"
        "Terminal=false\nCategories=Game;Utility;\nStartupNotify=true\n"
    )


def reloaded_entry(game, settings):
    exe = game.install / "Reloaded-II.exe"
    if not exe.is_file():
        raise ValueError("Install Reloaded-II for this game before creating its shortcut.")
    launcher = proton.detect_launcher(settings.get("protontricks_launch", ""))
    argv = proton.command(game, exe, launcher)
    env = shutil.which("env")
    if not env:
        raise RuntimeError("The env executable is required to create the Protontricks shortcut.")
    return desktop_entry(
        f"Reloaded-II — {game.name}", [env, f"STEAM_DIR={game.steam}", "DOTNET_ROOT=", *argv]
    )


def find_appimage():
    if value := os.environ.get("APPIMAGE"):
        image = Path(value).absolute()
        if image.is_file():
            return image
    candidate = Path(__file__).resolve().parents[2] / "dist/Reloaded-Linux-Manager-x86_64.AppImage"
    return candidate if candidate.is_file() else None


def manager_entry(appimage):
    path = Path(appimage).absolute()
    if not path.is_file() or not os.access(path, os.X_OK):
        raise ValueError("Select an executable manager AppImage. Make it executable first if needed.")
    if str(path).startswith("/tmp/.mount_"):
        raise ValueError("Select the original AppImage, not its temporary mounted executable.")
    return desktop_entry("Reloaded Linux Manager", [str(path)], "applications-system")


def save_shortcut(path, contents):
    path = Path(path).absolute()
    if path.suffix != ".desktop":
        raise ValueError("Shortcut filename must end in .desktop")
    transaction = Transaction(state_home() / "shortcut-backups", "Desktop shortcut")
    try:
        transaction.put(path, contents.encode("utf-8"))
        path.chmod(0o755)
    except Exception:
        Transaction.rollback(transaction.root)
        raise
    return (
        f"Shortcut saved: {path}\n"
        "Your desktop may ask you to Allow Launching or mark it as trusted. "
        "Keep the AppImage and game installation at their current locations."
    )
