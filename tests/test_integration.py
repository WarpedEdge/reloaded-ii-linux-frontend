from pathlib import Path

import libarchive
import pytest

from reloaded_linux_manager import integration
from reloaded_linux_manager.steam import Game
from reloaded_linux_manager.storage import Transaction, write_json


def prepared(tmp_path, monkeypatch):
    library = tmp_path / "library"
    prefix = library / "steamapps/compatdata/123456/pfx"
    directory = library / "steamapps/common/Example Game"
    directory.mkdir(parents=True)
    exe = directory / "game.exe"
    exe.touch()
    game = Game("123456", "Example Game", directory, library, tmp_path, prefix, "Proton")
    loader = game.install / "Loader/X64/Reloaded.Mod.Loader.dll"
    loader.parent.mkdir(parents=True)
    loader.touch()
    bootstrap = loader.parent / "Bootstrapper/Reloaded.Mod.Loader.Bootstrapper.dll"
    bootstrap.parent.mkdir()
    bootstrap.write_bytes(b"official bootstrap")
    asi = game.install / "Loader/Asi/UltimateAsiLoader.7z"
    asi.parent.mkdir()
    source = tmp_path / "ASILoader64.dll"
    source.write_bytes(b"official ASI")
    with libarchive.file_writer(str(asi), "7zip") as archive:
        archive.add_files(str(source), pathname="ASILoader64.dll")
    config_dir = prefix / "drive_c/users/steamuser/AppData/Roaming/Reloaded-Mod-Loader-II"
    win_install = "C:/" + str(game.install.relative_to(prefix / "drive_c"))
    write_json(
        config_dir / "ReloadedII.json",
        {
            "LoaderPath64": win_install + "/Loader/x64/Reloaded.Mod.Loader.dll",
            "ApplicationConfigDirectory": win_install + "/Apps",
        },
    )
    write_json(game.install / "Apps/game.exe/AppConfig.json", {"AppLocation": "Z:" + str(exe)})
    (prefix / "dosdevices").mkdir()
    (prefix / "dosdevices/z:").symlink_to("/")
    monkeypatch.setattr(integration, "executable_info", lambda _: (True, "version"))
    return game, exe


def test_official_asset_deployment_and_rollback(tmp_path, monkeypatch):
    game, exe = prepared(tmp_path, monkeypatch)
    result = integration.deploy(game, exe, tmp_path / "backups")
    assert result["dll"] == "version"
    assert (exe.parent / "version.dll").read_bytes() == b"official ASI"
    assert (exe.parent / "Reloaded.Mod.Loader.Bootstrapper.asi").read_bytes() == b"official bootstrap"
    assert Transaction.rollback(Path(result["transaction"])) == []
    assert not (exe.parent / "version.dll").exists()
    assert exe.exists()


def test_conflicting_loader_is_never_overwritten(tmp_path, monkeypatch):
    game, exe = prepared(tmp_path, monkeypatch)
    existing = exe.parent / "WINMM.dll"
    existing.write_bytes(b"other loader")
    with pytest.raises(ValueError, match="Existing DLL/ASI"):
        integration.deploy(game, exe, tmp_path / "backups")
    assert existing.read_bytes() == b"other loader"
    assert not (exe.parent / "version.dll").exists()


def test_username_alias_counts_as_one_config_and_allows_deployment(tmp_path, monkeypatch):
    game, exe = prepared(tmp_path, monkeypatch)
    users = game.prefix / "drive_c/users"
    (users / "deck").symlink_to("steamuser", target_is_directory=True)
    configs = integration.config_files(game)
    assert len(configs) == 1
    assert (
        configs[0].resolve()
        == (users / "steamuser/AppData/Roaming/Reloaded-Mod-Loader-II/ReloadedII.json").resolve()
    )
    result = integration.deploy(game, exe, tmp_path / "backups")
    assert result["dll"] == "version"
    assert (exe.parent / "version.dll").read_bytes() == b"official ASI"


def test_separate_user_configs_remain_distinct(tmp_path, monkeypatch):
    game, exe = prepared(tmp_path, monkeypatch)
    config = integration.config_files(game)[0]
    other = game.prefix / "drive_c/users/deck/AppData/Roaming/Reloaded-Mod-Loader-II/ReloadedII.json"
    other.parent.mkdir(parents=True)
    other.write_bytes(config.read_bytes())
    assert len(integration.config_files(game)) == 2
    with pytest.raises(ValueError, match="register this executable"):
        integration.deploy(game, exe, tmp_path / "backups")


def test_bcj2_compression_regression():
    archive = Path(__file__).parent / "fixtures/asi-bcj2.7z"
    expected = b"MZ - RLM regression fixture, not an executable\n" + b"\xe8\0\0\0\0\xe9\x01\0\0\0" * 100
    assert integration.extract_asi(archive, True) == expected
    with pytest.raises(ValueError, match="does not contain"):
        integration.extract_asi(archive, False)


def test_reclaimed_loader_files_are_removed_by_full_reset(tmp_path, monkeypatch):
    from reloaded_linux_manager import reset, service
    from reloaded_linux_manager.storage import state_home

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    game, exe = prepared(tmp_path, monkeypatch)
    integration.deploy(game, exe, state_home() / "games/old-entry/backups")
    result = integration.deploy(game, exe, service.backups(game), reclaim=True)
    write_json(service.metadata(game), {"installed": True, "asi": result})
    reset.full_reset(game, lambda _: None)
    assert not (exe.parent / "version.dll").exists()
    assert not (exe.parent / "Reloaded.Mod.Loader.Bootstrapper.asi").exists()
    assert exe.exists()
    reset.restore(game)
    assert (exe.parent / "version.dll").read_bytes() == b"official ASI"


def test_reclaim_preserves_unknown_or_changed_loader_files(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    game, exe = prepared(tmp_path, monkeypatch)
    integration.deploy(game, exe, tmp_path / "unmanaged-records")
    with pytest.raises(ValueError, match="No previous manager deployment"):
        integration.reclaim_asi(game, exe, tmp_path / "backups")
    assert (exe.parent / "version.dll").read_bytes() == b"official ASI"
    (exe.parent / "version.dll").write_bytes(b"different loader")
    with pytest.raises(ValueError, match="do not match"):
        integration.reclaim_asi(game, exe, tmp_path / "backups")
    assert (exe.parent / "version.dll").read_bytes() == b"different loader"
