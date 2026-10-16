from reloaded_linux_manager import icons
from reloaded_linux_manager.steam import Game


def test_local_icon_is_preferred_and_missing_art_is_optional(tmp_path):
    folder = tmp_path / "game"
    folder.mkdir()
    game = Game("1", "Game", folder, tmp_path, tmp_path, None, "")
    assert icons.game_icon(game) is None
    icon = folder / "icon.png"
    icon.write_bytes(b"local icon fixture")
    assert icons.game_icon(game) == str(icon)


def test_application_menu_icon_by_steam_id_and_name(tmp_path, monkeypatch):
    data = tmp_path / "data"
    applications = data / "applications"
    applications.mkdir(parents=True)
    folder = tmp_path / "game"
    folder.mkdir()
    icon = data / "icons/hicolor/256x256/apps/special-game.png"
    icon.parent.mkdir(parents=True)
    icon.write_bytes(b"icon fixture")
    monkeypatch.setattr(icons, "data_roots", lambda: [data])
    desktop = applications / "game.desktop"
    desktop.write_text(
        "[Desktop Entry]\nName=Different display name\nExec=steam steam://rungameid/1422450\nIcon=special-game\n"
    )
    game = Game("1422450", "Deadlock", folder, tmp_path, tmp_path, None, "")
    assert icons.game_icon(game) == str(icon)
    desktop.write_text("[Desktop Entry]\nName=Dead lock\nExec=/never/execute/this\nIcon=" + str(icon) + "\n")
    assert icons.application_icon(game) == str(icon)


def test_steam_icon_theme_fallback_without_desktop_entry(tmp_path, monkeypatch):
    data = tmp_path / "data"
    monkeypatch.setattr(icons, "data_roots", lambda: [data])
    path = data / "icons/hicolor/128x128/apps/steam_icon_1422450.png"
    path.parent.mkdir(parents=True)
    path.touch()
    game = Game("1422450", "Deadlock", tmp_path, tmp_path, tmp_path, None, "")
    assert icons.application_icon(game) == str(path)


def test_x64_executables_and_nested_steam_art_are_discovered(tmp_path, monkeypatch):
    from PySide6.QtGui import QColor, QImage

    game_folder = tmp_path / "game"
    (game_folder / "x64").mkdir(parents=True)
    (game_folder / "x64/game.exe").touch()
    game = Game("123", "Game", game_folder, tmp_path, tmp_path / "steam", None, "")
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setattr(icons, "application_icon", lambda _: None)
    monkeypatch.setattr(
        icons, "embedded_icon", lambda path: b"icon fixture" if path.parent.name == "x64" else None
    )
    assert icons.game_icon(game).endswith(".ico")
    (game_folder / "x64/game.exe").unlink()
    art = game.steam / "appcache/librarycache/123/hash/library_capsule.jpg"
    art.parent.mkdir(parents=True)
    image = QImage(100, 150, QImage.Format_RGB32)
    image.fill(QColor("blue"))
    assert image.save(str(art))
    result = icons.game_icon(game)
    assert result.endswith(".png")
    assert QImage(result).size().width() == 256


def test_shortcut_badge_is_generated_per_game(tmp_path, monkeypatch):
    from PySide6.QtGui import QColor, QImage

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    base, badge = tmp_path / "base.png", tmp_path / "badge.png"
    image = QImage(256, 256, QImage.Format_ARGB32)
    image.fill(QColor("red"))
    image.save(str(base))
    image.fill(QColor("blue"))
    image.save(str(badge))
    monkeypatch.setattr(icons, "reloaded_icon", lambda _: str(base))
    monkeypatch.setattr(icons, "game_icon", lambda _: str(badge))
    game = Game("1", "Game", tmp_path, tmp_path, tmp_path, None, "")
    first_icon = icons.shortcut_icon(game)
    output = QImage(first_icon)
    assert output.pixelColor(230, 20).name() == "#ff0000"
    assert output.pixelColor(200, 200).name() == "#0000ff"
    assert output.pixelColor(50, 200).name() == "#ff0000"
    assert output.pixelColor(140, 200).name() == "#0000ff"
    image.fill(QColor("green"))
    image.save(str(badge))
    assert icons.shortcut_icon(game) != first_icon


def test_library_uses_largest_ico_artwork(tmp_path, monkeypatch):
    import struct

    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtGui import QColor, QImage

    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    payloads = []
    for size, color in [(16, "red"), (128, "blue")]:
        image = QImage(size, size, QImage.Format_ARGB32)
        image.fill(QColor(color))
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        assert image.save(buffer, "PNG")
        payloads.append((size, bytes(buffer.data())))
    offset = 6 + 16 * len(payloads)
    headers = []
    for size, data in payloads:
        headers.append(struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(data), offset))
        offset += len(data)
    icon = tmp_path / "game.ico"
    icon.write_bytes(struct.pack("<HHH", 0, 1, 2) + b"".join(headers) + b"".join(p[1] for p in payloads))
    monkeypatch.setattr(icons, "game_icon", lambda _: str(icon))
    game = Game("1", "Game", tmp_path, tmp_path, tmp_path, None, "")
    displayed = QImage(icons.library_icon(game))
    assert displayed.width() == 128
    assert displayed.pixelColor(64, 64).name() == "#0000ff"
