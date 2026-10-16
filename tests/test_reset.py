from pathlib import Path

import pytest

from reloaded_linux_manager import reset, service, shortcuts
from reloaded_linux_manager.steam import Game
from reloaded_linux_manager.storage import Transaction, digest, read_json, write_json


def setup_game(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    prefix = tmp_path / "library/steamapps/compatdata/1/pfx"
    directory = tmp_path / "game"
    directory.mkdir()
    (directory / "game.exe").write_bytes(b"game")
    game = Game("1", "Game", directory, tmp_path / "library", tmp_path / "steam", prefix, "Proton")
    mod = game.install / "Mods/example/ModConfig.json"
    mod.parent.mkdir(parents=True)
    mod.write_text('{"ModId":"example"}')
    (game.install / "Reloaded-II.exe").write_bytes(b"launcher")
    config = prefix / "drive_c/users/steamuser/AppData/Roaming/Reloaded-Mod-Loader-II/ReloadedII.json"
    write_json(
        config,
        {
            "LoaderPath64": r"C:\ReloadedLinuxManager\Reloaded-II\Loader\x64\Reloaded.Mod.Loader.dll",
            "ModConfigDirectory": r"C:\ReloadedLinuxManager\Reloaded-II\Mods",
        },
    )
    (prefix / "system.reg").write_text("registry")
    save = prefix / "drive_c/users/steamuser/save.dat"
    save.write_bytes(b"save")
    dll = directory / "version.dll"
    dll.write_bytes(b"original game DLL")
    transaction = Transaction(service.backups(game), "ASI")
    transaction.put(dll, b"loader")
    write_json(
        service.metadata(game),
        {
            "installed": True,
            "prefix": str(prefix),
            "version": "1.31.0",
            "asi": {"dll": "version", "transaction": str(transaction.root), "files": {str(dll): digest(dll)}},
        },
    )
    shortcuts.install_menu_shortcut(shortcuts.desktop_entry("Example", ["/usr/bin/true"]), game=game)
    shortcuts.install_menu_shortcut(shortcuts.desktop_entry("Manager", ["/usr/bin/true"]))
    return game, config, dll, save


def test_full_reset_and_restore_keeps_game_prefix_and_mod_backup(tmp_path, monkeypatch):
    game, config, dll, save = setup_game(tmp_path, monkeypatch)
    external = tmp_path / "external-mod"
    external.write_bytes(b"external")
    (game.install / "Mods/linked-mod").symlink_to(external)
    result = reset.full_reset(game, lambda _: None)
    root = Path(read_json(reset.pointer(game))["backup"])
    assert "fresh setup" in result
    assert not game.install.exists() and not config.exists()
    assert not service.metadata(game).exists()
    assert service.setup_guide(game)["stage"] == 1
    assert dll.read_bytes() == b"original game DLL"
    assert save.read_bytes() == b"save"
    assert (game.prefix / "system.reg").read_text() == "registry"
    assert (game.directory / "game.exe").read_bytes() == b"game"
    assert (root / "folder-0/Mods/example/ModConfig.json").is_file()
    assert external.read_bytes() == b"external"
    assert not shortcuts.menu_shortcut_exists(game) and shortcuts.menu_shortcut_exists()
    reset.restore(game)
    assert (game.install / "Mods/example/ModConfig.json").is_file()
    assert config.is_file() and dll.read_bytes() == b"loader"
    assert (game.install / "Mods/linked-mod").is_symlink()
    assert shortcuts.menu_shortcut_exists(game)
    # The original disconnect operation remains reversible after restoration.
    service.remove_asi(game)
    assert dll.read_bytes() == b"original game DLL"


def test_reset_refuses_changed_asi_and_external_config(tmp_path, monkeypatch):
    game, config, dll, _ = setup_game(tmp_path, monkeypatch)
    dll.write_bytes(b"another loader")
    with pytest.raises(ValueError, match="changed outside"):
        reset.full_reset(game, lambda _: None)
    assert game.install.exists() and config.exists()
    dll.write_bytes(b"loader")
    data = read_json(config)
    data["ModConfigDirectory"] = r"C:\SharedMods"
    write_json(config, data)
    with pytest.raises(ValueError, match="outside the managed"):
        reset.full_reset(game, lambda _: None)
    assert dll.read_bytes() == b"loader"


def test_restore_refuses_to_overwrite_fresh_setup(tmp_path, monkeypatch):
    game, _, _, _ = setup_game(tmp_path, monkeypatch)
    reset.full_reset(game, lambda _: None)
    game.install.mkdir()
    (game.install / "new-file").write_bytes(b"new setup")
    with pytest.raises(ValueError, match="new setup exists"):
        reset.restore(game)
    assert (game.install / "new-file").read_bytes() == b"new setup"


def test_failed_reset_restores_moved_folders_and_integration(tmp_path, monkeypatch):
    game, config, dll, _ = setup_game(tmp_path, monkeypatch)
    original = reset.os.replace

    def fail_config_move(source, target):
        if Path(source) == config.parent:
            raise OSError("test disk failure")
        return original(source, target)

    monkeypatch.setattr(reset.os, "replace", fail_config_move)
    with pytest.raises(OSError, match="disk failure"):
        reset.full_reset(game, lambda _: None)
    assert (game.install / "Reloaded-II.exe").is_file()
    assert config.is_file() and dll.read_bytes() == b"loader"
    assert read_json(service.metadata(game))["installed"]
    assert shortcuts.menu_shortcut_exists(game)
