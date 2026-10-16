from reloaded_linux_manager import service
from reloaded_linux_manager.steam import Game
from reloaded_linux_manager.storage import digest, write_json


def game_setup(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    prefix = tmp_path / "prefix"
    directory = prefix / "drive_c/Game"
    directory.mkdir(parents=True)
    (directory / "game.exe").touch()
    game = Game(
        "1",
        "Game",
        directory,
        tmp_path,
        tmp_path,
        prefix,
        "Proton",
        ('WINEDLLOVERRIDES="version=n,b" %command%',),
    )
    (game.install / "Reloaded-II.exe").parent.mkdir(parents=True)
    (game.install / "Reloaded-II.exe").touch()
    write_json(
        prefix / "drive_c/users/steamuser/AppData/Roaming/Reloaded-Mod-Loader-II/ReloadedII.json",
        {
            "LoaderPath64": r"C:\ReloadedLinuxManager\Reloaded-II\Loader\X64\Reloaded.Mod.Loader.dll",
            "UsePortableMode": True,
        },
    )
    write_json(
        game.install / "Apps/game/AppConfig.json",
        {"AppLocation": r"C:\Game\game.exe", "EnabledMods": ["fft.loader"]},
    )
    write_json(
        game.install / "Mods/fft.loader/ModConfig.json",
        {"ModId": "fft.loader", "ModDependencies": ["Reloaded.Memory.SigScan.ReloadedII"]},
    )
    dll = directory / "version.dll"
    dll.write_bytes(b"loader")
    write_json(service.metadata(game), {"asi": {"dll": "version", "files": {str(dll): digest(dll)}}})
    return game


def test_missing_mod_dependencies_no_longer_flag_setup(tmp_path, monkeypatch):
    game = game_setup(tmp_path, monkeypatch)
    guide = service.setup_guide(game)
    assert guide["stage"] == 6 and guide["heading"] == "Ready"
    assert "dependency_issues" not in guide
    assert "leave it open" in guide["text"]


def test_copy_advances_setup_without_claiming_steam_was_changed(tmp_path, monkeypatch):
    from dataclasses import replace

    from reloaded_linux_manager.storage import read_json

    game = replace(game_setup(tmp_path, monkeypatch), launch_options=())
    assert service.setup_guide(game)["stage"] == 4
    state = read_json(service.metadata(game), {})
    state["launch_options_copied"] = {"dll": "version", "options": 'WINEDLLOVERRIDES="version=n,b" %command%'}
    write_json(service.metadata(game), state)
    guide = service.setup_guide(game)
    assert guide["stage"] == 6 and guide["options_status"] == "copied"
    assert "not been detected yet" in guide["text"]
    assert guide["heading"] != "Ready"
    game = replace(game, launch_options=('WINEDLLOVERRIDES="version=n,b" %command%',))
    guide = service.setup_guide(game)
    assert guide["options_status"] == "detected" and guide["heading"] == "Ready"
