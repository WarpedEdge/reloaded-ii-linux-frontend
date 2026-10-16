"""Readable local diagnostics; never expose raw internal journals as configuration UI."""

import logging
import os
import time
from pathlib import Path

from . import service, shortcuts
from .integration import config_files
from .storage import read_json, state_home


def tail(path, limit=128 * 1024):
    try:
        with path.open("rb") as stream:
            stream.seek(0, 2)
            size = stream.tell()
            stream.seek(max(0, size - limit))
            text = stream.read(limit).decode("utf-8", errors="replace")
        return ("[Showing the end of this log]\n" if size > limit else "") + text
    except OSError as exc:
        return "Could not read this log: " + str(exc)


def log_files(game=None):
    files = [state_home() / "manager.log", state_home() / "process.log"]
    if game:
        upstream = []
        for config in config_files(game):
            upstream.extend(
                p
                for p in (config.parent / "Logs").rglob("*")
                if p.is_file() and p.suffix.lower() in (".txt", ".log")
            )
        files += sorted(upstream, key=lambda p: p.stat().st_mtime, reverse=True)[:3]
    return files


def setup_details(game):
    state = read_json(service.metadata(game), {})
    registry = read_json(shortcuts.registry_path(), {})
    lines = [
        game.name,
        "",
        f"Steam App ID: {game.appid}",
        f"Proton selection: {game.tool}",
        f"Game folder: {game.directory}",
        f"Steam folder: {game.steam}",
        f"Windows environment: {game.prefix or 'Not found'}",
        f"Reloaded-II version: {state.get('version', 'Not installed by this manager')}",
        f"Application-menu shortcut: {registry.get(game.key, {}).get('path', 'Not created')}",
        "",
        "Detected Reloaded-II configuration files:",
    ]
    lines += [str(p) for p in config_files(game)] or [
        "None yet — open Reloaded-II to initialize its settings."
    ]
    lines += [
        "",
        "Setup checks:",
        *service.diagnostics(game),
        "",
    ]
    return "\n".join(lines)


def clear_logs(game=None):
    """Clear the displayed log files, keeping active logging handles valid."""
    files = [*log_files(game), *state_home().glob("manager.log.*"), *state_home().glob("process.log.*")]
    # Validate the entire set before clearing anything.
    if any(p.is_symlink() for p in files):
        raise ValueError("A log is a symbolic link; no logs were cleared.")
    for path in dict.fromkeys(files):
        if path.is_file():
            with path.open("wb"):
                pass
    return "Displayed logs cleared. Mods and settings were kept."


def log_catalog(game=None):
    """Separate sources for the viewer; metadata snapshots drive unread indicators."""

    def entry(path, label):
        try:
            stat = path.stat()
            stamp = [stat.st_ino, stat.st_size, stat.st_mtime_ns]
        except OSError:
            stamp = None
        return {"path": str(path), "label": label, "stamp": stamp}

    prune_game_logs(game)
    paths = log_files(game)
    return {
        "manager": [entry(paths[0], "Manager")],
        "proton": [entry(paths[1], "Protontricks")],
        "game": [entry(p, p.name) for p in paths[2:]],
    }


def open_file_ids():
    """Protect logs currently open in this user's processes, including Wine."""
    opened = set()
    try:
        for process in Path("/proc").iterdir():
            if not process.name.isdigit():
                continue
            try:
                if process.stat().st_uid != os.getuid():
                    continue
                for fd in (process / "fd").iterdir():
                    try:
                        stat = fd.stat()
                        opened.add((stat.st_dev, stat.st_ino))
                    except (FileNotFoundError, PermissionError):
                        pass
            except (FileNotFoundError, PermissionError):
                pass
    except OSError:
        return None  # Cannot establish safety; defer pruning.
    return opened


def prune_game_logs(game):
    """Keep three newest Reloaded-II logs, deferring active/recent files."""
    if not game:
        return []
    files = []
    for config in config_files(game):
        root = config.parent / "Logs"
        for path in root.rglob("*"):
            if path.suffix.lower() not in (".txt", ".log") or path.is_symlink():
                continue
            try:
                if path.is_file():
                    files.append((path, path.stat()))
            except FileNotFoundError:
                pass
    files.sort(key=lambda item: item[1].st_mtime_ns, reverse=True)
    if len(files) <= 3:
        return []
    opened = open_file_ids()
    if opened is None:
        return []
    removed = []
    for path, stat in files[3:]:
        if (stat.st_dev, stat.st_ino) in opened or time.time() - stat.st_mtime < 60:
            continue
        try:
            current = path.lstat()
            if (current.st_ino, current.st_size, current.st_mtime_ns) != (
                stat.st_ino,
                stat.st_size,
                stat.st_mtime_ns,
            ):
                continue
            path.unlink()
            removed.append(path)
        except FileNotFoundError:
            pass
        except OSError as exc:
            logging.warning("Could not prune Reloaded-II log %s: %s", path.name, exc)
    return removed
