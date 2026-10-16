"""Freedesktop launchers; no shell scripts or temporary AppImage mount paths.

Exec quoting follows https://specifications.freedesktop.org/desktop-entry/latest/exec-variables.html
"""

import os
import shutil
from pathlib import Path

from . import icons, proton
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
        f"Reloaded-II — {game.name}",
        [env, f"STEAM_DIR={game.steam}", "DOTNET_ROOT=", *argv],
        icon=icons.shortcut_icon(game) or "applications-games",
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
    return desktop_entry("Reloaded Linux Manager", [str(path)], icons.manager_icon())


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


def applications_home():
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "applications"


def registry_path():
    return state_home() / "shortcuts.json"


def game_shortcut_name(game):
    import re

    name = re.sub(r"[^\w.-]+", "-", game.name, flags=re.UNICODE).strip(".-")[:120] or game.appid
    return f"Reloaded-II-{name}.desktop"


def install_menu_shortcut(contents, *, game=None):
    """Only replace tracked entries; keep unrelated application launchers intact."""
    from .storage import digest, read_json, write_json

    registry = read_json(registry_path(), {})
    key = game.key if game else "manager"
    name = game_shortcut_name(game) if game else "Reloaded-Linux-Manager.desktop"
    target = applications_home() / name
    entry = registry.get(key, {})
    # Same display names in distinct Steam installs must not overwrite each other.
    if any(k != key and e["path"] == str(target) for k, e in registry.items()):
        target = target.with_name(target.stem + "-" + game.key + ".desktop")
    if target.exists() or target.is_symlink():
        if target.is_symlink() or entry.get("path") != str(target) or digest(target) != entry.get("sha256"):
            raise ValueError(
                "An unrelated or externally changed application shortcut exists at " + str(target)
            )
    save_shortcut(target, contents)
    old = registry.get(key)
    registry[key] = {"path": str(target), "sha256": digest(target)}
    write_json(registry_path(), registry)
    # Clean up a previously managed filename after a game display-name change.
    if old and old["path"] != str(target):
        previous = Path(old["path"])
        if (
            previous.parent == applications_home()
            and previous.is_file()
            and not previous.is_symlink()
            and digest(previous) == old["sha256"]
        ):
            previous.unlink()
    return "Application-menu shortcut installed: " + str(target)


def remove_menu_shortcut(game=None):
    from .storage import digest, read_json, write_json

    registry = read_json(registry_path(), {})
    key = game.key if game else "manager"
    entry = registry.get(key)
    if not entry:
        return "No managed application-menu shortcut to remove."
    target = Path(entry["path"])
    if target.parent != applications_home() or target.is_symlink():
        raise ValueError("Shortcut path is no longer a managed application entry; nothing removed.")
    if target.exists():
        if digest(target) != entry["sha256"]:
            raise ValueError(
                "Shortcut was changed outside this manager; preserved for review: " + str(target)
            )
        target.unlink()
    registry.pop(key)
    write_json(registry_path(), registry)
    return "Application-menu shortcut removed: " + str(target)


def refresh_game_shortcut(game, settings):
    from .storage import read_json

    if game.key in read_json(registry_path(), {}):
        return install_menu_shortcut(reloaded_entry(game, settings), game=game)
    return None


def menu_shortcut_exists(game=None):
    """Report a tracked application entry; removal still verifies its ownership digest."""
    from .storage import read_json

    entry = read_json(registry_path(), {}).get(game.key if game else "manager")
    if not entry:
        return False
    path = Path(entry["path"])
    return path.parent == applications_home() and (path.exists() or path.is_symlink())
