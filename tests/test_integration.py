from pathlib import Path

import libarchive
import pytest

from reloaded_linux_manager import integration
from reloaded_linux_manager.steam import Game
from reloaded_linux_manager.storage import Transaction, write_json


def prepared(tmp_path, monkeypatch):
    library = tmp_path / "library"
    prefix = library / "steamapps/compatdata/1004640/pfx"
    directory = library / "steamapps/common/FFT"
    directory.mkdir(parents=True)
    exe = directory / "FFT_enhanced.exe"
    exe.touch()
    game = Game("1004640", "FFT", directory, library, tmp_path, prefix, "Proton")
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
    write_json(game.install / "Apps/fft_enhanced.exe/AppConfig.json", {"AppLocation": "Z:" + str(exe)})
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


def test_bcj2_compression_regression():
    archive = Path(__file__).parent / "fixtures/asi-bcj2.7z"
    expected = b"MZ - RLM regression fixture, not an executable\n" + b"\xe8\0\0\0\0\xe9\x01\0\0\0" * 100
    assert integration.extract_asi(archive, True) == expected
    with pytest.raises(ValueError, match="does not contain"):
        integration.extract_asi(archive, False)
