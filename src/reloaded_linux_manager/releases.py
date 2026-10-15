"""Official GitHub assets, verified cache, and bounded ZIP extraction."""

import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

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
    with request(API + endpoint) as stream:
        data = json.load(stream)
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
