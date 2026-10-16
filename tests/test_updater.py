"""No live network or downloaded executable is used by updater tests."""

import hashlib
import io
from urllib.error import HTTPError

import pytest

from reloaded_linux_manager import updater


def image(content=b"new"):
    return b"\x7fELF\x02\x01\x01\x00AI\x02" + b"\x00" * 7 + b"\x3e\x00" + content


def asset(data):
    return {
        "name": updater.ASSET_NAME,
        "size": len(data),
        "digest": "sha256:" + hashlib.sha256(data).hexdigest(),
        "browser_download_url": updater.PROJECT_URL + "/releases/download/v0.2/" + updater.ASSET_NAME,
    }


def test_version_comparison_and_stable_release(tmp_path, monkeypatch):
    import json

    data = {"tag_name": "v0.2", "draft": False, "prerelease": False, "assets": [asset(image())]}
    monkeypatch.setattr(updater, "request", lambda _: io.BytesIO(json.dumps(data).encode()))
    monkeypatch.setattr(updater.platform, "machine", lambda: "x86_64")
    assert updater.check_update("0.1.0")["status"] == "available"
    assert updater.check_update("0.2.0")["status"] == "current"
    assert updater.check_update("0.10.0")["status"] == "current"
    data["prerelease"] = True
    assert updater.check_update("0.1")["status"] == "current"


def test_no_public_release_is_not_a_startup_error(monkeypatch):
    def missing(_):
        raise HTTPError(updater.API, 404, "Not Found", {}, None)

    monkeypatch.setattr(updater, "request", missing)
    assert updater.check_update()["status"] == "unavailable"


def test_update_preserves_filename_backup_and_execute_permission(tmp_path, monkeypatch):
    current, new = image(b"old"), image(b"new")
    path = tmp_path / "same-name.AppImage"
    path.write_bytes(current)
    path.chmod(0o755)
    monkeypatch.setattr(updater, "request", lambda _: io.BytesIO(new))
    result = updater.install_update(path, asset(new))
    assert path.read_bytes() == new
    assert path.name == "same-name.AppImage"
    assert path.stat().st_mode & 0o111
    assert (tmp_path / "same-name.AppImage.previous").read_bytes() == current
    assert result["path"] == str(path)


@pytest.mark.parametrize("payload", [b"corrupt", image(b"bad"), image(b"longer than expected")])
def test_bad_download_never_replaces_current_appimage(tmp_path, monkeypatch, payload):
    path = tmp_path / "manager.AppImage"
    original = image(b"old")
    path.write_bytes(original)
    monkeypatch.setattr(updater, "request", lambda _: io.BytesIO(payload))
    with pytest.raises(ValueError):
        updater.install_update(path, asset(image()))
    assert path.read_bytes() == original
    assert not list(tmp_path.glob(".rlm-update-*"))


def test_external_appimage_change_during_download_is_preserved(tmp_path, monkeypatch):
    path = tmp_path / "manager.AppImage"
    path.write_bytes(image(b"old"))
    external = image(b"external change")

    def request(_):
        path.write_bytes(external)
        return io.BytesIO(image())

    monkeypatch.setattr(updater, "request", request)
    with pytest.raises(ValueError, match="changed during download"):
        updater.install_update(path, asset(image()))
    assert path.read_bytes() == external


def test_unofficial_asset_and_missing_digest_rejected():
    data = asset(image())
    data["browser_download_url"] = "https://example.com/manager.AppImage"
    with pytest.raises(ValueError):
        updater.validate_asset(data)
    data = asset(image())
    data.pop("digest")
    with pytest.raises(ValueError):
        updater.validate_asset(data)


def test_running_inode_stays_valid_while_original_path_is_replaced(tmp_path, monkeypatch):
    path = tmp_path / "manager.AppImage"
    old, new = image(b"old running image"), image(b"new image")
    path.write_bytes(old)
    monkeypatch.setattr(updater, "request", lambda _: io.BytesIO(new))
    with path.open("rb") as running:
        updater.install_update(path, asset(new))
        assert running.read() == old
        assert path.read_bytes() == new


def test_correct_checksum_cannot_make_a_non_appimage_installable(tmp_path, monkeypatch):
    path = tmp_path / "manager.AppImage"
    old = image(b"original")
    path.write_bytes(old)
    bad = b"not an AppImage"
    monkeypatch.setattr(updater, "request", lambda _: io.BytesIO(bad))
    with pytest.raises(ValueError, match="not a type-2 AppImage"):
        updater.install_update(path, asset(bad))
    assert path.read_bytes() == old
