"""Read Steam KeyValues files. Never edit Steam's undocumented settings."""

import logging
from dataclasses import dataclass
from pathlib import Path

import vdf

log = logging.getLogger(__name__)


def read_vdf(path):
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8", errors="replace") as stream:
        return vdf.load(stream)


def descend(data, *keys):
    for key in keys:
        data = (
            next((v for k, v in data.items() if k.lower() == key.lower()), {})
            if isinstance(data, dict)
            else {}
        )
    return data


@dataclass(frozen=True)
class Game:
    appid: str
    name: str
    directory: Path
    library: Path
    steam: Path
    prefix: Path | None
    tool: str
    launch_options: tuple[str, ...] = ()

    @property
    def install(self):
        if self.prefix is None:
            raise ValueError(
                "Launch this game through Steam once with Proton, then refresh. No initialized prefix found."
            )
        return self.prefix / "drive_c/ReloadedLinuxManager/Reloaded-II"

    @property
    def key(self):
        import hashlib

        return self.appid + "-" + hashlib.sha256(str(self.steam).encode()).hexdigest()[:10]


def roots(home=None, extra=()):
    home = home or Path.home()
    candidates = [
        home / ".steam/steam",
        home / ".steam/root",
        home / ".local/share/Steam",
        home / ".var/app/com.valvesoftware.Steam/.local/share/Steam",
        *map(Path, extra),
    ]
    return list(dict.fromkeys(p.resolve() for p in candidates if (p / "steamapps").is_dir()))


def libraries(root, extra=()):
    result = [root, *map(Path, extra)]
    data = read_vdf(root / "steamapps/libraryfolders.vdf")
    for value in descend(data, "libraryfolders").values():
        path = value.get("path") if isinstance(value, dict) else value
        if isinstance(path, str) and path.startswith("/"):
            result.append(Path(path))
    return list(dict.fromkeys(p.resolve() for p in result if (p / "steamapps").is_dir()))


def initialized(prefix):
    return (prefix / "drive_c").is_dir() and (prefix / "system.reg").is_file()


def discover(settings, home=None):
    games, warnings = [], []
    for root in roots(home, settings.get("steam_roots", [])):
        try:
            libs = libraries(root, settings.get("libraries", []))
            mapping = descend(
                read_vdf(root / "config/config.vdf"),
                "InstallConfigStore",
                "Software",
                "Valve",
                "Steam",
                "CompatToolMapping",
            )
            options = {}
            for local in sorted((root / "userdata").glob("*/config/localconfig.vdf")):
                try:
                    apps = descend(
                        read_vdf(local), "UserLocalConfigStore", "Software", "Valve", "Steam", "apps"
                    )
                    for appid, data in apps.items():
                        value = descend(data, "LaunchOptions")
                        if isinstance(value, str) and value:
                            options.setdefault(appid, set()).add(value)
                except (ValueError, OSError, SyntaxError) as exc:
                    warnings.append(f"Cannot read Steam user settings: {exc}")
            for library in libs:
                for manifest in sorted((library / "steamapps").glob("appmanifest_*.acf")):
                    try:
                        data = descend(read_vdf(manifest), "AppState")
                        appid = str(data["appid"])
                        if not appid.isdecimal():
                            raise ValueError("Invalid App ID")
                        directory = (library / "steamapps/common" / data["installdir"]).resolve()
                        if not directory.is_relative_to((library / "steamapps/common").resolve()):
                            raise ValueError("Manifest installation path escapes library")
                        override = settings.get("prefixes", {}).get(appid)
                        candidates = (
                            [Path(override)]
                            if override
                            else [p / f"steamapps/compatdata/{appid}/pfx" for p in libs]
                        )
                        found = list(dict.fromkeys(p.resolve() for p in candidates if initialized(p)))
                        prefix = found[0] if len(found) == 1 else None
                        if len(found) > 1:
                            warnings.append(f"{appid}: multiple prefixes; select the actual prefix manually.")
                        tool = mapping.get(appid, mapping.get("0", {})).get(
                            "name", "Steam automatic selection (unresolved)"
                        )
                        games.append(
                            Game(
                                appid,
                                data.get("name", appid),
                                directory,
                                library,
                                root,
                                prefix,
                                tool,
                                tuple(sorted(options.get(appid, []))),
                            )
                        )
                    except (KeyError, ValueError, OSError, SyntaxError) as exc:
                        warnings.append(f"Cannot read {manifest.name}: {exc}")
        except (ValueError, OSError, SyntaxError) as exc:
            warnings.append(f"Cannot read Steam library configuration: {exc}")
    return games, warnings


def is_support_tool(game):
    """Hide Steam runtimes and Proton packages from the game picker, not discovery."""
    name = game.name.lower()
    return (
        game.appid
        in {"228980", "1070560", "1391110", "1493710", "1628350", "1826330", "2180100", "2805730", "4183110"}
        or name.startswith("steam linux runtime")
        or name.startswith("proton ")
        or name.startswith("proton experimental")
        or name.startswith("proton easyanticheat")
    )


class SteamRootRequired(ValueError):
    """A real Steam installation must be selected to associate this library."""


def resolve_manual_game(selection, settings, steam_root=None):
    """Resolve an EXE or manifest through actual Steam metadata, never invent an App ID."""
    selected = Path(selection).resolve()
    if not selected.is_file():
        raise ValueError("Selected file no longer exists.")
    if selected.suffix.lower() == ".exe":
        games, _ = discover(settings)
        matches = [g for g in games if selected.is_relative_to(g.directory.resolve())]
        if steam_root:
            matches = [g for g in matches if g.steam == Path(steam_root).resolve()]
        if len(matches) == 1:
            return matches[0]
        steamapps = next(
            (p for p in selected.parents if p.name == "steamapps" and selected.is_relative_to(p / "common")),
            None,
        )
        if steamapps is None:
            raise ValueError(
                "This executable is outside a Steam library. Add and launch the game in Steam first. "
                "Standalone/non-Steam shortcut prefix discovery is not supported yet."
            )
        matches = []
        for manifest in steamapps.glob("appmanifest_*.acf"):
            data = descend(read_vdf(manifest), "AppState")
            directory = (steamapps / "common" / data.get("installdir", "")).resolve()
            if (
                data.get("installdir")
                and directory.is_relative_to((steamapps / "common").resolve())
                and selected.is_relative_to(directory)
            ):
                matches.append(manifest)
        if len(matches) != 1:
            raise ValueError(
                "Could not associate this executable with one Steam app manifest. Select its appmanifest_*.acf instead."
            )
        selected = matches[0]
    elif not (selected.name.startswith("appmanifest_") and selected.suffix.lower() == ".acf"):
        raise ValueError("Choose a Windows game executable (.exe) or Steam app manifest (.acf).")
    if selected.parent.name != "steamapps":
        raise ValueError("The app manifest must be in its Steam library’s steamapps directory.")
    library = selected.parent.parent
    owners = (
        [Path(steam_root).resolve()]
        if steam_root
        else [root for root in roots(extra=settings.get("steam_roots", [])) if library in libraries(root)]
    )
    if len(owners) != 1:
        raise SteamRootRequired("Choose the Steam installation that owns this game library.")
    root = owners[0]
    if not (root / "steamapps").is_dir() or not (root / "config").is_dir():
        raise ValueError("The Steam root must contain steamapps and config directories.")
    data = descend(read_vdf(selected), "AppState")
    candidate_settings = settings | {"steam_roots": [str(root)], "libraries": [str(library)]}
    games, warnings = discover(candidate_settings)
    matches = [
        g for g in games if g.steam == root and g.library == library and g.appid == str(data.get("appid"))
    ]
    if len(matches) != 1:
        raise ValueError("Unable to load the selected Steam manifest. " + " ".join(warnings))
    return matches[0]
