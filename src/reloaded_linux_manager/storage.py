"""Atomic manager settings and reversible, content-checked file transactions."""

import copy
import hashlib
import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path


def config_home():
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "reloaded-linux-manager"


def state_home():
    return Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state")) / "reloaded-linux-manager"


def cache_home():
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "reloaded-linux-manager"


def read_json(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def atomic_write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".rlm-")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def write_json(path, value):
    atomic_write(path, (json.dumps(value, indent=2) + "\n").encode())


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class Transaction:
    """Persist undo records BEFORE mutations; never undo externally changed content."""

    def __init__(self, root: Path, label: str):
        self.root = root / uuid.uuid4().hex
        self.root.mkdir(parents=True)
        self.record = {"label": label, "files": []}
        self.save()

    def save(self):
        write_json(self.root / "transaction.json", self.record)

    def put(self, target: Path, data: bytes):
        if target.is_symlink():
            raise ValueError(f"Refusing to replace symlink: {target}")
        backup = None
        if target.exists():
            backup = str(len(self.record["files"])) + ".bak"
            shutil.copy2(target, self.root / backup)
        entry = {"path": str(target.absolute()), "backup": backup, "sha256": hashlib.sha256(data).hexdigest()}
        self.record["files"].append(entry)
        self.save()
        atomic_write(target, data)

    @staticmethod
    def rollback(folder: Path):
        record = read_json(folder / "transaction.json")
        conflicts = []
        for entry in reversed(record["files"]):
            path = Path(entry["path"])
            if entry.get("undone"):
                continue
            if path.is_symlink() or (path.exists() and digest(path) != entry["sha256"]):
                conflicts.append(str(path))
                continue
            if entry["backup"]:
                atomic_write(path, (folder / entry["backup"]).read_bytes())
            else:
                path.unlink(missing_ok=True)
            entry["undone"] = True
            write_json(folder / "transaction.json", record)
        return conflicts


DEFAULTS = {
    "steam_roots": [],
    "libraries": [],
    "cache": str(cache_home()),
    "release": "latest",
    "protontricks_launch": "",
    "prefixes": {},
    "log_level": "INFO",
    "favorites": [],
    "check_updates": True,
    "theme": "dark",
}


def load_settings():
    settings = copy.deepcopy(DEFAULTS) | read_json(config_home() / "settings.json", {})
    settings.pop("controller_navigation", None)
    return settings


def save_settings(settings):
    settings = settings.copy()
    settings.pop("controller_navigation", None)
    path = config_home() / "settings.json"
    if path.exists():
        shutil.copy2(path, path.with_suffix(".json.bak"))
    write_json(path, settings)
