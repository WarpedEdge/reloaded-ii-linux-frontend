"""Update only this manager from its configured GitHub project, preserving its launch path."""

import fcntl
import hashlib
import json
import os
import platform
import re
import shutil
import tempfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from . import __version__
from .releases import github_error_message
from .storage import digest

REPOSITORY = "WarpedEdge/reloaded-ii-linux-frontend"
PROJECT_URL = "https://github.com/" + REPOSITORY
API = "https://api.github.com/repos/" + REPOSITORY + "/releases/latest"
ASSET_NAME = "Reloaded-Linux-Manager-x86_64.AppImage"


def request(url):
    return urlopen(
        Request(
            url,
            headers={
                "User-Agent": "Reloaded-Linux-Manager/" + __version__,
                "Accept": "application/vnd.github+json",
            },
        ),
        timeout=20,
    )


def version_tuple(value):
    if not re.fullmatch(r"v?\d+(?:\.\d+){1,2}", value):
        raise ValueError("Unsupported release version: " + str(value))
    parts = tuple(int(p) for p in value.removeprefix("v").split("."))
    return parts + (0,) * (3 - len(parts))


def check_update(current=__version__):
    try:
        with request(API) as response:
            raw = response.read(1024**2 + 1)
        if len(raw) > 1024**2:
            raise ValueError("Release metadata exceeds size limit")
        data = json.loads(raw)
    except HTTPError as exc:
        if exc.code == 404:
            return {
                "status": "unavailable",
                "message": "No public manager release is available yet (repository or release not publicly accessible).",
            }
        raise RuntimeError(github_error_message(exc)) from exc
    if data.get("draft") or data.get("prerelease"):
        return {"status": "current", "message": "No newer stable manager release available."}
    version = data.get("tag_name", "")
    if version_tuple(version) <= version_tuple(current):
        return {"status": "current", "message": "Reloaded Linux Manager is up to date."}
    if platform.machine().lower() not in ("x86_64", "amd64"):
        return {
            "status": "unavailable",
            "message": "Automatic updates currently support x86_64 AppImages only.",
        }
    asset = next((a for a in data.get("assets", []) if a.get("name") == ASSET_NAME), None)
    if not asset:
        return {
            "status": "unavailable",
            "message": f"Manager {version} is published, but its Linux AppImage is not available yet.",
        }
    validate_asset(asset)
    return {
        "status": "available",
        "version": version,
        "asset": asset,
        "message": f"Reloaded Linux Manager {version} is available.",
    }


def validate_asset(asset):
    if asset.get("name") != ASSET_NAME or not asset.get("browser_download_url", "").startswith(
        PROJECT_URL + "/releases/download/"
    ):
        raise ValueError("Update does not come from the manager’s GitHub release assets.")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", asset.get("digest") or ""):
        raise ValueError("Release has no GitHub SHA-256 digest; update cannot be verified.")
    if not 0 < int(asset.get("size", 0)) <= 512 * 1024**2:
        raise ValueError("Unexpected manager update size.")


def is_appimage(path):
    with Path(path).open("rb") as stream:
        header = stream.read(20)
    return (
        header[:4] == b"\x7fELF"
        and header[4:6] == b"\x02\x01"
        and header[8:11] == b"AI\x02"
        and header[18:20] == b"\x3e\x00"
    )


def install_update(target, asset, report=lambda _: None):
    """Same-directory staging, digest validation, backup, then atomic replacement.

    The old process continues from its existing inode. No downloaded code runs here.
    """
    validate_asset(asset)
    target = Path(target).absolute()
    if target.is_symlink() or not target.is_file() or not is_appimage(target):
        raise ValueError("Update requires the original, writable manager AppImage file (not a symlink).")
    lock_path = target.with_name("." + target.name + ".update.lock")
    with lock_path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Another manager update is already running.") from exc
        original = digest(target)
        mode = target.stat().st_mode & 0o777
        fd, staging_name = tempfile.mkstemp(prefix=".rlm-update-", dir=target.parent)
        staged = Path(staging_name)
        backup_stage = None
        try:
            report("Downloading manager update…")
            checksum, size, last_percent = hashlib.sha256(), 0, -1
            expected_size = int(asset["size"])
            with os.fdopen(fd, "wb") as output, request(asset["browser_download_url"]) as response:
                while chunk := response.read(256 * 1024):
                    size += len(chunk)
                    if size > expected_size:
                        raise ValueError("Update exceeds declared asset size.")
                    checksum.update(chunk)
                    output.write(chunk)
                    percent = size * 100 // expected_size
                    if percent != last_percent:
                        report(f"Downloading manager update: {percent}%")
                        last_percent = percent
                output.flush()
                os.fsync(output.fileno())
            if size != expected_size or checksum.hexdigest() != asset["digest"][7:]:
                raise ValueError("Update failed SHA-256/size validation. Current AppImage was preserved.")
            if not is_appimage(staged):
                raise ValueError("Downloaded asset is not a type-2 AppImage.")
            if digest(target) != original:
                raise ValueError("AppImage changed during download; update cancelled.")
            os.chmod(staged, mode | 0o100)
            fd, name = tempfile.mkstemp(prefix=".rlm-previous-", dir=target.parent)
            backup_stage = Path(name)
            with os.fdopen(fd, "wb") as output, target.open("rb") as source:
                shutil.copyfileobj(source, output)
                output.flush()
                os.fsync(output.fileno())
            if digest(backup_stage) != original or digest(target) != original:
                raise ValueError("AppImage changed while preparing its backup; update cancelled.")
            os.chmod(backup_stage, mode)
            backup = target.with_name(target.name + ".previous")
            os.replace(backup_stage, backup)
            os.replace(staged, target)
            report("Manager updated. The AppImage path and application shortcut are unchanged.")
            return {"path": str(target), "backup": str(backup)}
        finally:
            staged.unlink(missing_ok=True)
            if backup_stage:
                backup_stage.unlink(missing_ok=True)
