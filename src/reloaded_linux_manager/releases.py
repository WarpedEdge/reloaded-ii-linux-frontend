"""Official GitHub assets, verified cache, and bounded ZIP extraction."""

import hashlib
import json
import logging
import re
import stat
import time
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from .storage import cache_home, read_json, write_json

API = "https://api.github.com/repos/Reloaded-Project/Reloaded-II/releases/"


def request(url):
    return urlopen(
        Request(
            url, headers={"User-Agent": "Reloaded-Linux-Manager/0.1", "Accept": "application/vnd.github+json"}
        ),
        timeout=60,
    )


def release(version="latest"):
    endpoint = "latest" if version == "latest" else "tags/" + quote(version, safe="")
    cached_path = (
        cache_home() / "release-metadata" / (hashlib.sha256(endpoint.encode()).hexdigest() + ".json")
    )
    try:
        cached = read_json(cached_path, {})
        fetched_at = float(cached.get("fetched_at", 0))
        cached_data = cached.get("data")
        if cached_data is not None:
            _release_assets(cached_data)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        cached, cached_data = {}, None
    if cached_data is not None and 0 <= time.time() - fetched_at < 3600:
        return _release_assets(cached_data)
    try:
        with request(API + endpoint) as stream:
            data = json.load(stream)
    except HTTPError as exc:
        if exc.code in (403, 429):
            if cached_data is not None:
                logging.getLogger(__name__).warning(
                    "GitHub HTTP %s; using previously fetched official Reloaded-II release %s. "
                    "Downloaded files still require SHA-256 and size validation.",
                    exc.code,
                    cached_data["tag_name"],
                )
                return _release_assets(cached_data)
            raise RuntimeError(github_error_message(exc)) from exc
        raise
    result = _release_assets(data)
    try:
        write_json(cached_path, {"fetched_at": time.time(), "data": data})
    except OSError:
        logging.getLogger(__name__).warning("Could not cache Reloaded-II release information.")
    return result


def github_error_message(exc):
    """Explain API throttling without treating every forbidden response as a rate limit."""
    headers = exc.headers or {}
    limited = exc.code == 429 or headers.get("X-RateLimit-Remaining") == "0" or headers.get("Retry-After")
    if not limited:
        return f"GitHub refused the request (HTTP {exc.code}); access may be restricted or temporarily rate limited. Try again later."
    retry = "Try again later."
    try:
        if headers.get("Retry-After"):
            retry = f"Try again in {int(headers['Retry-After'])} seconds."
        elif headers.get("X-RateLimit-Reset"):
            reset = datetime.fromtimestamp(int(headers["X-RateLimit-Reset"])).astimezone()
            retry = "Try again after " + reset.strftime("%H:%M:%S %Z") + "."
    except (ValueError, OverflowError, OSError):
        pass
    return "GitHub's API rate limit has been reached. " + retry


def _release_assets(data):
    assets = {a["name"]: a for a in data["assets"]}
    if not {"Release.zip", "Setup-Linux.exe"} <= assets.keys():
        raise ValueError("Release does not provide the official portable ZIP and Linux installer.")
    return data["tag_name"], assets


def download(asset, cache: Path, report=lambda _: None):
    url = asset["browser_download_url"]
    if not url.startswith("https://github.com/Reloaded-Project/Reloaded-II/releases/download/"):
        raise ValueError("Refusing non-official release URL")
    expected = asset.get("digest", "") or ""
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", expected):
        raise ValueError("GitHub did not provide a SHA-256 digest; cannot validate this release asset.")
    size = int(asset["size"])
    if not 0 < size <= 1024**3:
        raise ValueError("Unexpected release size")
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / (expected[7:] + "-" + Path(urlparse(url).path).name)

    def valid(path):
        return (
            path.is_file()
            and path.stat().st_size == size
            and hashlib.sha256(path.read_bytes()).hexdigest() == expected[7:]
        )

    if valid(target):
        report("Verified cached " + asset["name"])
        return target
    partial = target.with_suffix(target.suffix + ".partial")
    try:
        with request(url) as source, partial.open("wb") as output:
            count = 0
            while chunk := source.read(256 * 1024):
                count += len(chunk)
                if count > size:
                    raise ValueError("Download exceeds declared size")
                output.write(chunk)
                report(f"Downloading {asset['name']}: {count * 100 // size}%")
        if not valid(partial):
            raise ValueError("Download failed SHA-256/size validation")
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)
    return target


def extract_zip(archive: Path, destination: Path):
    """Extract only regular files/directories; reject unsafe names, links and ZIP bombs."""
    with zipfile.ZipFile(archive) as source:
        entries = source.infolist()
        if len(entries) > 20000 or sum(i.file_size for i in entries) > 2 * 1024**3:
            raise ValueError("Archive exceeds extraction limits")
        seen = set()
        for item in entries:
            name = item.filename
            path = PurePosixPath(name)
            mode = item.external_attr >> 16
            target = destination / name
            if (
                "\\" in name
                or ":" in name
                or path.is_absolute()
                or ".." in path.parts
                or stat.S_ISLNK(mode)
                or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR))
                or not target.resolve().is_relative_to(destination.resolve())
                or name.casefold() in seen
            ):
                raise ValueError(f"Unsafe archive entry: {name}")
            seen.add(name.casefold())
        destination.mkdir(parents=True, exist_ok=True)
        for item in entries:
            target = destination / item.filename
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open(item) as inp, target.open("xb") as out:
                    import shutil

                    shutil.copyfileobj(inp, out)
