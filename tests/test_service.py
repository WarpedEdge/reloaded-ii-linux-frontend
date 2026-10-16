import zipfile

import pytest

from reloaded_linux_manager import service
from reloaded_linux_manager.steam import Game
from reloaded_linux_manager.storage import read_json, write_json


def prepared(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    library = tmp_path / "library"
    prefix = library / "steamapps/compatdata/1004640/pfx"
    (prefix / "drive_c").mkdir(parents=True)
    (prefix / "system.reg").touch()
    directory = library / "steamapps/common/FFT"
    directory.mkdir(parents=True)
    game = Game("1004640", "FFT", directory, library, tmp_path / "steam", prefix, "GE-Proton")
    archive = tmp_path / "Release.zip"
    with zipfile.ZipFile(archive, "w") as output:
        for name in [
            "Reloaded-II.exe",
            "Loader/X64/Reloaded.Mod.Loader.dll",
            "Loader/X86/Reloaded.Mod.Loader.dll",
            "Loader/Asi/UltimateAsiLoader.7z",
        ]:
            output.writestr(name, b"new official file")
        output.writestr("Mods/user.json", b"must not replace user mod")
    monkeypatch.setattr(service.proton, "detect_launcher", lambda _: ["protontricks-launch"])
    monkeypatch.setattr(
        service.releases, "release", lambda _: ("1.31.0", {"Release.zip": "zip", "Setup-Linux.exe": "exe"})
    )
    monkeypatch.setattr(
        service.releases,
        "download",
        lambda asset, *_: archive if asset == "zip" else tmp_path / "Setup-Linux.exe",
    )
    return game


def test_install_preserves_mods_and_uses_official_dependencies_mode(tmp_path, monkeypatch):
    game = prepared(tmp_path, monkeypatch)
    mod = game.install / "Mods/user.json"
    mod.parent.mkdir(parents=True)
    mod.write_bytes(b"user mod")
    write_json(service.metadata(game), {"installed": True})
    calls = []
    monkeypatch.setattr(service.proton, "run", lambda *args: calls.append(args))
    result = service.install(game, {"cache": str(tmp_path)}, lambda _: None)
    assert "configuration is pending" in result
    assert mod.read_bytes() == b"user mod"
    assert calls[0][3] == [
        "--dependenciesOnly",
        "--nogui",
        "--installdir",
        r"C:\ReloadedLinuxManager\DependencyStaging",
    ]
    assert (game.install / "Loader/X64/Reloaded.Mod.Loader.dll").is_file()
    assert read_json(service.metadata(game))["version"] == "1.31.0"


def test_runtime_failure_rolls_back_manager_files(tmp_path, monkeypatch):
    game = prepared(tmp_path, monkeypatch)
    game.install.mkdir(parents=True)
    exe = game.install / "Reloaded-II.exe"
    exe.write_bytes(b"original")
    write_json(service.metadata(game), {"installed": True, "version": "old"})

    def fail(*args):
        raise RuntimeError("runtime failure")

    monkeypatch.setattr(service.proton, "run", fail)
    with pytest.raises(RuntimeError, match="runtime failure"):
        service.install(game, {"cache": str(tmp_path)}, lambda _: None)
    assert exe.read_bytes() == b"original"
    assert not (game.install / "Loader/X64/Reloaded.Mod.Loader.dll").exists()
    assert read_json(service.metadata(game))["version"] == "old"


def test_existing_other_installation_is_preserved(tmp_path, monkeypatch):
    game = prepared(tmp_path, monkeypatch)
    config = game.prefix / "drive_c/users/steamuser/AppData/Roaming/Reloaded-Mod-Loader-II/ReloadedII.json"
    write_json(config, {"LoaderPath64": "C:/Existing/Loader/X64/Reloaded.Mod.Loader.dll"})
    with pytest.raises(ValueError, match="another installation"):
        service.install(game, {}, lambda _: None)
    assert not game.install.exists()
    assert read_json(config)["LoaderPath64"].startswith("C:/Existing")


def test_first_install_failure_can_be_retried(tmp_path, monkeypatch):
    game = prepared(tmp_path, monkeypatch)

    def fail(*args):
        raise RuntimeError("runtime failure")

    monkeypatch.setattr(service.proton, "run", fail)
    with pytest.raises(RuntimeError):
        service.install(game, {"cache": str(tmp_path)}, lambda _: None)
    assert not read_json(service.metadata(game), {}).get("installed")
    monkeypatch.setattr(service.proton, "run", lambda *args: None)
    service.install(game, {"cache": str(tmp_path)}, lambda _: None)
    assert read_json(service.metadata(game))["installed"]


def test_guide_names_next_action_and_preserves_existing_setup(tmp_path, monkeypatch):
    game = prepared(tmp_path, monkeypatch)
    guide = service.setup_guide(game)
    assert guide["stage"] == 1 and guide["action"] == "setup"
    game.install.mkdir(parents=True)
    (game.install / "Reloaded-II.exe").touch()
    assert service.setup_guide(game)["action"] == "open_reloaded"
    config = game.prefix / "drive_c/users/steamuser/AppData/Roaming/Reloaded-Mod-Loader-II/ReloadedII.json"
    write_json(config, {"LoaderPath64": "C:/Other/Loader/X64/Reloaded.Mod.Loader.dll"})
    guide = service.setup_guide(game)
    assert guide["stage"] == -1 and guide["action"] == "check"
    assert "existing" in guide["heading"].lower()


def test_guide_missing_prefix_explains_steam_first(tmp_path, monkeypatch):
    from dataclasses import replace

    game = replace(prepared(tmp_path, monkeypatch), prefix=None)
    guide = service.setup_guide(game)
    assert guide["action"] == "launch_game"
    assert "Refresh" in guide["text"]


def test_guide_does_not_mark_registration_complete_from_loader_config_alone(tmp_path, monkeypatch):
    game = prepared(tmp_path, monkeypatch)
    game.install.mkdir(parents=True)
    (game.install / "Reloaded-II.exe").touch()
    base = "C:/" + str(game.install.relative_to(game.prefix / "drive_c"))
    config = game.prefix / "drive_c/users/steamuser/AppData/Roaming/Reloaded-Mod-Loader-II/ReloadedII.json"
    write_json(
        config,
        {
            "LoaderPath64": base + "/Loader/X64/Reloaded.Mod.Loader.dll",
            "ApplicationConfigDirectory": base + "/Apps",
        },
    )
    assert service.setup_guide(game)["stage"] == 2


def test_ready_means_verified_configuration_and_changed_asi_is_failed(tmp_path, monkeypatch):
    from dataclasses import replace

    from reloaded_linux_manager.storage import digest

    game = prepared(tmp_path, monkeypatch)
    game = replace(game, launch_options=('WINEDLLOVERRIDES="version=n,b" %command%',))
    game.install.mkdir(parents=True)
    (game.install / "Reloaded-II.exe").touch()
    executable = game.directory / "game.exe"
    executable.touch()
    (game.prefix / "dosdevices").mkdir()
    (game.prefix / "dosdevices/z:").symlink_to("/")
    base = "C:/" + str(game.install.relative_to(game.prefix / "drive_c"))
    config = game.prefix / "drive_c/users/steamuser/AppData/Roaming/Reloaded-Mod-Loader-II/ReloadedII.json"
    write_json(
        config,
        {
            "LoaderPath64": base + "/Loader/X64/Reloaded.Mod.Loader.dll",
            "ApplicationConfigDirectory": base + "/Apps",
        },
    )
    write_json(game.install / "Apps/game/AppConfig.json", {"AppLocation": "Z:" + str(executable)})
    proxy = game.directory / "version.dll"
    proxy.write_bytes(b"official loader fixture")
    write_json(service.metadata(game), {"asi": {"dll": "version", "files": {str(proxy): digest(proxy)}}})
    guide = service.setup_guide(game)
    assert guide["stage"] == 6 and guide["heading"] == "Ready"
    assert "Mod compatibility" in guide["text"]
    assert "OK: Setup checks passed. Ready to launch." in service.diagnostics(game)
    proxy.write_bytes(b"changed")
    guide = service.setup_guide(game)
    assert guide["failed_step"] == 3 and guide["stage"] == 3
