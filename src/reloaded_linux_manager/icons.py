"""Local game art, Steam's cached icons, then a bounded Windows EXE icon extraction."""

import hashlib
import struct

import pefile

from .storage import atomic_write, cache_home


def embedded_icon(executable):
    if executable.stat().st_size > 256 * 1024**2:
        return None
    with pefile.PE(str(executable), fast_load=True) as pe:
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_RESOURCE"]])
        resources = getattr(pe, "DIRECTORY_ENTRY_RESOURCE", None)
        if resources is None:
            return None
        types = {entry.id: entry for entry in resources.entries}
        if 14 not in types or 3 not in types:
            return None
        group = types[14].directory.entries[0].directory.entries[0].data.struct
        if not 6 <= group.Size <= 4096:
            return None
        data = pe.get_data(group.OffsetToData, group.Size)
        reserved, kind, count = struct.unpack_from("<HHH", data)
        if reserved or kind != 1 or not 0 < count <= 64 or len(data) < 6 + count * 14:
            return None
        available = {entry.id: entry for entry in types[3].directory.entries}
        payloads, headers = [], []
        offset = 6 + count * 16
        for index in range(count):
            width, height, colors, zero, planes, bits, _, resource_id = struct.unpack_from(
                "<BBBBHHIH", data, 6 + index * 14
            )
            if resource_id not in available:
                return None
            resource = available[resource_id].directory.entries[0].data.struct
            if not 0 < resource.Size <= 4 * 1024**2 or offset + resource.Size > 8 * 1024**2:
                return None
            block = pe.get_data(resource.OffsetToData, resource.Size)
            if len(block) != resource.Size:
                return None
            headers.append(
                struct.pack("<BBBBHHII", width, height, colors, zero, planes, bits, len(block), offset)
            )
            payloads.append(block)
            offset += len(block)
        return struct.pack("<HHH", 0, 1, count) + b"".join(headers) + b"".join(payloads)


def game_icon(game):
    """Called in discovery worker; Qt only receives an existing path on the GUI thread."""
    try:
        if not game.directory.is_dir():
            return None
        local = list(game.directory.iterdir())[:500]
        candidates = [
            p
            for p in local
            if p.suffix.lower() == ".ico"
            or p.stem.lower() in ("icon", "gameicon", "logo")
            and p.suffix.lower() in (".png", ".jpg")
        ]
        cached = game.steam / "appcache/librarycache"
        candidates += sorted(cached.glob(game.appid + "*icon*"))
        candidates += sorted((cached / game.appid).glob("*icon*"))
        for candidate in candidates:
            if candidate.is_file() and 0 < candidate.stat().st_size <= 4 * 1024**2:
                return str(candidate)
        fallback = application_icon(game)
        if fallback:
            return fallback
        executables = sorted(
            (
                p
                for p in [
                    *local,
                    *game.directory.glob("*/Binaries/Win64/*.exe"),
                    *game.directory.glob("Binaries/Win64/*.exe"),
                    *game.directory.glob("bin/*.exe"),
                    *game.directory.glob("x64/*.exe"),
                    *game.directory.glob("x86/*.exe"),
                    *game.directory.glob("bin/x64/*.exe"),
                ]
                if p.suffix.lower() == ".exe"
            ),
            key=lambda p: ("fft_enhanced" not in p.stem.lower(), p.name),
        )[:3]
        for executable in executables:
            stamp = f"{executable}:{executable.stat().st_mtime_ns}:{executable.stat().st_size}"
            destination = cache_home() / "icons" / (hashlib.sha256(stamp.encode()).hexdigest() + ".ico")
            if destination.is_file():
                return str(destination)
            try:
                data = embedded_icon(executable)
                if data:
                    atomic_write(destination, data)
                    return str(destination)
            except (pefile.PEFormatError, KeyError, IndexError, struct.error, AttributeError):
                continue
    except OSError:
        return None
    try:
        return cached_library_art(game)
    except OSError:
        return None


def data_roots():
    import os
    from pathlib import Path

    return [
        Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")),
        *[Path(p) for p in os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":") if p],
        Path.home() / ".local/share/flatpak/exports/share",
        Path("/var/lib/flatpak/exports/share"),
    ]


def theme_icon_path(name):
    from pathlib import Path

    if not name or "/" in name or "\\" in name or name in (".", ".."):
        return None
    roots = [Path.home() / ".icons", *[p / "icons" for p in data_roots()]]
    for root in roots:
        for size in ("256x256", "128x128", "64x64", "48x48", "32x32", "scalable"):
            for ext in (".png", ".svg", ".xpm", ".ico"):
                candidate = root / "hicolor" / size / "apps" / (name + ext)
                if candidate.is_file():
                    return str(candidate)
    for root in data_roots():
        for ext in (".png", ".svg", ".xpm"):
            candidate = root / "pixmaps" / (name + ext)
            if candidate.is_file():
                return str(candidate)
    return None


def application_icon(game):
    """Read desktop-menu metadata only; never execute its Exec field."""
    import configparser
    import re
    from pathlib import Path

    direct = theme_icon_path("steam_icon_" + game.appid)
    if direct:
        return direct

    def normalize(value):
        return "".join(c for c in value.casefold() if c.isalnum())

    for root in data_roots():
        for entry in (root / "applications").rglob("*.desktop"):
            try:
                if entry.stat().st_size > 256 * 1024:
                    continue
                parser = configparser.ConfigParser(interpolation=None, strict=False)
                parser.read(entry, encoding="utf-8")
                section = parser["Desktop Entry"]
                if section.get("Hidden", "").lower() == "true":
                    continue
                command = section.get("Exec", "")
                matches = re.search(
                    r"steam://(?:rungameid|run)/" + re.escape(game.appid) + r"(?!\d)", command
                )
                if not matches and normalize(section.get("Name", "")) != normalize(game.name):
                    continue
                icon = section.get("Icon", "")
                path = Path(icon).expanduser()
                if path.is_absolute() and path.is_file():
                    return str(path)
                if icon and "/" not in icon:
                    return theme_icon_path(icon) or "theme:" + icon
            except (OSError, UnicodeError, configparser.Error, KeyError):
                continue
    return None


def reloaded_icon(game):
    """Persist the official Windows launcher's own icon outside any AppImage mount/cache."""
    import os
    from pathlib import Path

    executable = game.install / "Reloaded-II.exe"
    try:
        data = embedded_icon(executable)
        if data:
            target = (
                Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
                / "reloaded-linux-manager/icons/Reloaded-II.ico"
            )
            atomic_write(target, data)
            return str(target)
    except (OSError, pefile.PEFormatError, KeyError, IndexError, struct.error, AttributeError):
        pass
    return None


def manager_icon():
    """Keep the chosen manager artwork at a permanent path for desktop launchers."""
    import os
    import sys
    from pathlib import Path

    source = (
        Path(sys._MEIPASS) / "reloaded-linux-manager.png"
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parents[2] / "packaging/reloaded-linux-manager.png"
    )
    if not source.is_file():
        return "applications-system"
    target = (
        Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
        / "reloaded-linux-manager/icons/reloaded-linux-manager.png"
    )
    atomic_write(target, source.read_bytes())
    return str(target)


def cached_library_art(game):
    """Handle hashed Steam artwork names and the newer hash subdirectories."""
    from pathlib import Path

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QImageReader

    root = game.steam / "appcache/librarycache" / game.appid
    candidates = []
    if not root.is_dir():
        return None
    for path in [*root.glob("*"), *root.glob("*/*")][:100]:
        if not path.is_file() or not 0 < path.stat().st_size <= 4 * 1024**2:
            continue
        reader = QImageReader(str(path))
        size = reader.size()
        if not 0 < size.width() <= 4096 or not 0 < size.height() <= 4096:
            continue
        ratio = abs(size.width() - size.height()) / max(size.width(), size.height())
        candidates.append((ratio, -min(size.width(), size.height()), str(path)))
    if not candidates:
        return None
    source = Path(min(candidates)[2])
    stamp = f"{source}:{source.stat().st_mtime_ns}:{source.stat().st_size}"
    target = cache_home() / "icons" / (hashlib.sha256(stamp.encode()).hexdigest() + ".png")
    if not target.is_file():
        image = QImageReader(str(source)).read()
        side = min(image.width(), image.height())
        image = image.copy((image.width() - side) // 2, (image.height() - side) // 2, side, side)
        image = image.scaled(256, 256, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        target.parent.mkdir(parents=True, exist_ok=True)
        if not image.save(str(target), "PNG"):
            return None
    return str(target)


def shortcut_icon(game):
    """Compose a per-game badge with QImage, which is safe in the setup worker."""
    import os
    from pathlib import Path

    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QImage, QPainter, QPen

    base_path = reloaded_icon(game)
    art = game_icon(game)
    if not base_path or not art or art.startswith("theme:"):
        return base_path

    base, badge = highest_resolution_image(base_path), highest_resolution_image(art)
    if base.isNull() or badge.isNull():
        return base_path
    canvas = QImage(256, 256, QImage.Format_ARGB32_Premultiplied)
    canvas.fill(Qt.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    painter.drawImage(QRectF(0, 0, 256, 256), base)
    painter.setBrush(QColor("#1b222c"))
    painter.setPen(QPen(QColor("#e0e5ee"), 2))
    painter.drawRoundedRect(QRectF(127, 127, 128, 128), 14, 14)
    badge = badge.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    painter.drawImage(
        QRectF(
            132 + (120 - badge.width()) / 2, 132 + (120 - badge.height()) / 2, badge.width(), badge.height()
        ),
        badge,
    )
    painter.end()
    target = (
        Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
        / "reloaded-linux-manager/icons"
        / ("Reloaded-II-" + game.key + "-" + hashlib.sha256(canvas.constBits()).hexdigest()[:16] + ".png")
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    if not canvas.save(str(target), "PNG"):
        return base_path
    return str(target)


def highest_resolution_image(path):
    """Select the same artwork frame for the library and shortcut badge."""
    from PySide6.QtGui import QImage, QImageReader

    reader = QImageReader(path)
    count = min(reader.imageCount(), 64)
    best, area = 0, 0
    for index in range(max(1, count)):
        reader.jumpToImage(index)
        size = reader.size()
        if 0 < size.width() <= 4096 and 0 < size.height() <= 4096 and size.width() * size.height() > area:
            best, area = index, size.width() * size.height()
    if not area:
        return QImage()
    reader.jumpToImage(best)
    return reader.read()


def library_icon(game):
    """Flatten multi-resolution icons so Qt cannot substitute different small artwork."""
    path = game_icon(game)
    if not path or path.startswith("theme:"):
        return path
    image = highest_resolution_image(path)
    if image.isNull():
        return path
    digest = hashlib.sha256(image.constBits()).hexdigest()
    target = cache_home() / "icons" / ("artwork-" + digest + ".png")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() or image.save(str(target), "PNG"):
        return str(target)
    return path
