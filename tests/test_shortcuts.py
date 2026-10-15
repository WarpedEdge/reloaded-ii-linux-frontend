"""Launcher argument preservation, including characters interpreted specially by desktops."""

import os

import pytest

from reloaded_linux_manager import shortcuts
from reloaded_linux_manager.steam import Game


def test_exec_escaping_without_a_shell():
    line = shortcuts.exec_line(["/usr/bin/env", 'literal $HOME `id` "quoted" \\ data 100%'])
    assert line == '"/usr/bin/env" "literal \\\\$HOME \\\\`id\\\\` \\\\"quoted\\\\" \\\\\\\\ data 100%%"'
    for bad in ["line\nbreak", "line\rbreak", "\x00"]:
        with pytest.raises(ValueError):
            shortcuts.exec_line(["/bin/true", bad])


def test_reloaded_shortcut_uses_correct_prefix_launcher_and_env(tmp_path, monkeypatch):
    library = tmp_path / "Steam Library"
    prefix = library / "steamapps/compatdata/1004640/pfx"
    game = Game("1004640", "FFT", tmp_path, library, tmp_path / "steam", prefix, "Proton")
    game.install.mkdir(parents=True)
    (game.install / "Reloaded-II.exe").touch()
    monkeypatch.setattr(
        shortcuts.proton,
        "detect_launcher",
        lambda _: [
            "/usr/bin/flatpak",
            "run",
            "--command=protontricks-launch",
            "com.github.Matoking.protontricks",
        ],
    )
    content = shortcuts.reloaded_entry(game, {})
    assert "STEAM_DIR=" in content and str(game.steam) in content
    assert '"--appid" "1004640"' in content
    assert '"--command=protontricks-launch"' in content
    assert str(game.install / "Reloaded-II.exe") in content
    assert "reloaded-linux-manager" not in content.lower()
    assert "Terminal=false" in content


def test_shortcut_update_backs_up_existing_content(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    target = tmp_path / "manager.desktop"
    target.write_text("existing shortcut")
    content = shortcuts.desktop_entry("Manager\nName=injection", ["/bin/true"])
    shortcuts.save_shortcut(target, content)
    assert "Name=Manager\\nName=injection\n" in target.read_text()
    assert os.access(target, os.X_OK)
    assert any(p.read_text() == "existing shortcut" for p in (tmp_path / "state").rglob("*.bak"))


def test_manager_shortcut_keeps_original_appimage_path(tmp_path, monkeypatch):
    image = tmp_path / "manager with spaces.AppImage"
    image.touch()
    image.chmod(0o755)
    monkeypatch.setenv("APPIMAGE", str(image))
    assert shortcuts.find_appimage() == image
    assert f'Exec="{image}"' in shortcuts.manager_entry(image)
    assert ".mount_" not in shortcuts.manager_entry(image)
