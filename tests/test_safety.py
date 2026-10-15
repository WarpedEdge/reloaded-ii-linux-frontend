import hashlib
import stat
import zipfile

import pytest

from reloaded_linux_manager.integration import merge_options
from reloaded_linux_manager.releases import download, extract_zip
from reloaded_linux_manager.storage import Transaction


@pytest.mark.parametrize("name", ["../escape", "/tmp/escape", "C:/escape", "dir\\escape", "dir/../../escape"])
def test_archive_traversal_rejected(tmp_path, name):
    archive = tmp_path / "a.zip"
    with zipfile.ZipFile(archive, "w") as out:
        out.writestr(name, "bad")
    with pytest.raises(ValueError):
        extract_zip(archive, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_archive_symlink_rejected(tmp_path):
    archive = tmp_path / "a.zip"
    with zipfile.ZipFile(archive, "w") as out:
        info = zipfile.ZipInfo("link")
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        out.writestr(info, "/etc")
    with pytest.raises(ValueError):
        extract_zip(archive, tmp_path / "out")


def test_archive_crc_and_files(tmp_path):
    archive = tmp_path / "a.zip"
    with zipfile.ZipFile(archive, "w") as out:
        out.writestr("Loader/file.dll", b"MZdata")
    extract_zip(archive, tmp_path / "out")
    assert (tmp_path / "out/Loader/file.dll").read_bytes() == b"MZdata"


def test_preserve_and_restore_config_and_external_edits(tmp_path):
    config = tmp_path / "config.json"
    config.write_bytes(b"original mods and profiles")
    new = tmp_path / "new.dll"
    transaction = Transaction(tmp_path / "backups", "test")
    transaction.put(config, b"updated")
    transaction.put(new, b"dll")
    new.write_bytes(b"external mod")
    assert Transaction.rollback(transaction.root) == [str(new)]
    assert config.read_bytes() == b"original mods and profiles"
    assert new.read_bytes() == b"external mod"
    assert Transaction.rollback(transaction.root) == [str(new)]


def test_override_preserves_parameters_and_other_overrides():
    original = 'MANGOHUD=1 WINEDLLOVERRIDES="dxgi=n;version=b;d3d11=n" %command% -windowed'
    result = merge_options(original, "version.dll")
    assert result == 'MANGOHUD=1 WINEDLLOVERRIDES="dxgi=n;d3d11=n;version=n,b" %command% -windowed'
    assert merge_options(result, "version") == result
    assert merge_options("", "winmm") == 'WINEDLLOVERRIDES="winmm=n,b" %command%'


def test_grouped_override_and_complex_input():
    assert (
        merge_options('WINEDLLOVERRIDES="version,dxgi=b" %command%', "version")
        == 'WINEDLLOVERRIDES="dxgi=b;version=n,b" %command%'
    )
    for value in [
        "-foo",
        'WINEDLLOVERRIDES="$VALUE" %command%',
        "WINEDLLOVERRIDES=a=b WINEDLLOVERRIDES=c=n %command%",
    ]:
        with pytest.raises(ValueError):
            merge_options(value, "version")


def test_verified_cache_and_corruption(tmp_path, monkeypatch):
    import io

    import reloaded_linux_manager.releases as releases

    data = b"official payload"
    asset = {
        "name": "Release.zip",
        "size": len(data),
        "digest": "sha256:" + hashlib.sha256(data).hexdigest(),
        "browser_download_url": "https://github.com/Reloaded-Project/Reloaded-II/releases/download/test/Release.zip",
    }
    monkeypatch.setattr(releases, "request", lambda _: io.BytesIO(data))
    path = download(asset, tmp_path)
    path.write_bytes(b"corrupt")
    assert download(asset, tmp_path).read_bytes() == data
    monkeypatch.setattr(releases, "request", lambda _: io.BytesIO(b"bad"))
    path.unlink()
    with pytest.raises(ValueError):
        download(asset, tmp_path)
    assert not list(tmp_path.glob("*.partial"))
