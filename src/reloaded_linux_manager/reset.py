"""Reversible reset of this manager's per-game installation, never its Proton prefix."""

import os
import uuid
from pathlib import Path

from . import service, shortcuts
from .integration import config_files, windows_path_to_linux
from .storage import atomic_write, digest, read_json, state_home, write_json


def pointer(game):
    return state_home() / "games" / game.key / "last-reset.json"


def full_reset(game, report):
    target = game.install
    if not target.resolve().is_relative_to(game.prefix.resolve()):
        raise ValueError("Reloaded-II installation points outside this prefix; preserved.")
    state = read_json(service.metadata(game), {})
    if target.is_symlink() or (target.exists() and not state.get("installed")):
        raise ValueError("This Reloaded-II installation is not owned by this manager; preserved.")
    if state.get("prefix", str(game.prefix)) != str(game.prefix):
        raise ValueError("Saved setup belongs to another prefix; reset cancelled.")
    folders = [target] if target.exists() else []
    for config in config_files(game):
        data = read_json(config)
        loader = windows_path_to_linux(data.get("LoaderPath64", ""), game.prefix)
        if not loader.is_relative_to(target.resolve()):
            raise ValueError("Another Reloaded-II installation uses this prefix; preserved.")
        for key, value in data.items():
            if key.endswith("Directory") and value:
                directory = windows_path_to_linux(value, game.prefix)
                if not directory.is_relative_to(target.resolve()) and not directory.is_relative_to(
                    config.parent.resolve()
                ):
                    raise ValueError(
                        f"{key} points outside the managed setup. Reset cancelled to preserve it."
                    )
        if config.parent.is_symlink() or not config.parent.resolve().is_relative_to(game.prefix.resolve()):
            raise ValueError("Reloaded-II configuration is linked outside this prefix; preserved.")
        folders.append(config.parent)
    asi = state.get("asi", {})
    if asi and not Path(asi["transaction"]).resolve().is_relative_to(service.backups(game).resolve()):
        raise ValueError("ASI backup location is not managed; reset cancelled.")
    registry = read_json(shortcuts.registry_path(), {})
    shortcut = registry.get(game.key)
    if shortcut:
        path = Path(shortcut["path"])
        if (
            path.parent != shortcuts.applications_home()
            or path.is_symlink()
            or (path.exists() and digest(path) != shortcut["sha256"])
        ):
            raise ValueError("Application shortcut was changed outside this manager; reset cancelled.")
    asi_paths = []
    for name, expected in asi.get("files", {}).items():
        path = Path(name)
        if not path.resolve().is_relative_to(game.directory.resolve()) or path.is_symlink():
            raise ValueError("ASI file is outside this game; reset cancelled.")
        if path.exists() and digest(path) != expected:
            raise ValueError("An ASI file was changed outside this manager; reset cancelled.")
        asi_paths.append(path)
    # Same-prefix renames preserve large mod trees and symlinks without following them.
    root = target.parent / "ResetBackups" / uuid.uuid4().hex
    root.mkdir(parents=True)
    journal = {
        "game": game.key,
        "prefix": str(game.prefix),
        "state": state,
        "moves": [],
        "files": [],
        "complete": False,
    }
    for index, path in enumerate(asi_paths):
        saved = root / f"asi-{index}.bak"
        if path.exists():
            atomic_write(saved, path.read_bytes())
        journal["files"].append({"path": str(path), "backup": saved.name if saved.exists() else None})
    if shortcut and Path(shortcut["path"]).exists():
        atomic_write(root / "shortcut.desktop", Path(shortcut["path"]).read_bytes())
    write_json(root / "reset.json", journal)
    report("Backing up the full Reloaded-II setup to " + str(root))
    try:
        service.remove_asi(game)
        shortcuts.remove_menu_shortcut(game)
        for entry in journal["files"]:
            path = Path(entry["path"])
            entry["after"] = digest(path) if path.exists() else None
        write_json(root / "reset.json", journal)
        for index, source in enumerate(dict.fromkeys(folders)):
            destination = root / f"folder-{index}"
            entry = {"source": str(source), "backup": destination.name}
            journal["moves"].append(entry)
            write_json(root / "reset.json", journal)
            os.replace(source, destination)
        service.metadata(game).unlink(missing_ok=True)
        journal["complete"] = True
        write_json(root / "reset.json", journal)
        write_json(pointer(game), {"backup": str(root)})
    except Exception:
        restore(game, root)
        raise
    return (
        "Reloaded-II setup reset. Ready for a fresh setup. Game, saves and Proton prefix kept.\n"
        "Mods/settings backup: " + str(root) + "\n"
        "Review Steam launch options and remove the old Reloaded-II DLL override if needed; unrelated options are unchanged."
    )


def restore(game, root=None):
    if root is None:
        value = read_json(pointer(game), {})
        if not value:
            raise ValueError("No full-reset backup exists for this game.")
        root = Path(value["backup"])
    root = Path(root)
    if not root.resolve().is_relative_to((game.install.parent / "ResetBackups").resolve()):
        raise ValueError("Reset backup is outside the managed backup folder.")
    journal = read_json(root / "reset.json")
    if journal["game"] != game.key or journal["prefix"] != str(game.prefix):
        raise ValueError("Reset backup belongs to another game or prefix.")
    moves = [(Path(e["source"]), root / e["backup"]) for e in journal["moves"]]
    for source, backup in moves:
        if backup.exists() and (source.exists() or source.is_symlink()):
            raise ValueError("A new setup exists; preserved. Cannot restore over " + str(source))
        if not source.resolve().is_relative_to(game.prefix.resolve()) or not backup.resolve().is_relative_to(
            root.resolve()
        ):
            raise ValueError("Invalid reset backup path.")
    for entry in journal["files"]:
        path = Path(entry["path"])
        if not path.resolve().is_relative_to(game.directory.resolve()) or path.is_symlink():
            raise ValueError("Invalid saved ASI location.")
        current = digest(path) if path.exists() else None
        if "after" in entry and current != entry["after"]:
            raise ValueError("Game loader changed since reset; preserved: " + str(path))
    if (root / "shortcut.desktop").exists():
        # Performs the normal ownership checks before restoring anything else.
        shortcuts.install_menu_shortcut((root / "shortcut.desktop").read_text(), game=game)
    for source, backup in reversed(moves):
        if backup.exists():
            source.parent.mkdir(parents=True, exist_ok=True)
            os.replace(backup, source)
    for entry in journal["files"]:
        path = Path(entry["path"])
        if entry["backup"]:
            atomic_write(path, (root / entry["backup"]).read_bytes())
        else:
            path.unlink(missing_ok=True)
    write_json(service.metadata(game), journal["state"])
    # Re-enable the original ASI rollback record for later disconnect/reset operations.
    asi = journal["state"].get("asi")
    if asi:
        transaction_path = Path(asi["transaction"]) / "transaction.json"
        transaction = read_json(transaction_path)
        for entry in transaction["files"]:
            entry.pop("undone", None)
        write_json(transaction_path, transaction)
    pointer(game).unlink(missing_ok=True)
    return "Reloaded-II setup restored from the full-reset backup."
