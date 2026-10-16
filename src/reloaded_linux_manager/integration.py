"""Source-verified ASI selection. No mod runtime or guessed registration structures."""

import re
from pathlib import Path

import pefile

from .storage import Transaction, digest, read_json

DLL32 = (
    "version",
    "winmm",
    "wininet",
    "vorbisfile",
    "msvfw32",
    "msacm32",
    "xlive",
    "dsound",
    "dinput8",
    "dinput",
    "ddraw",
    "d3d11",
    "d3d9",
    "d3d8",
)
DLL64 = ("version", "winmm", "wininet", "dsound", "dinput8")


def executable_info(path):
    with pefile.PE(str(path), fast_load=True) as pe:
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY["IMAGE_DIRECTORY_ENTRY_IMPORT"]])
        is64 = pe.OPTIONAL_HEADER.Magic == 0x20B
        imports = {d.dll.decode("ascii").lower() for d in getattr(pe, "DIRECTORY_ENTRY_IMPORT", [])}
        name = next((n for n in (DLL64 if is64 else DLL32) if n + ".dll" in imports), None)
        if not name:
            raise ValueError("Executable imports no ASI-compatible DLL documented by Reloaded-II.")
        return is64, name


def merge_options(existing, dll):
    """Preserve exact unrelated text; reject ambiguous shell expressions instead of rewriting them."""
    dll = dll.lower().removesuffix(".dll")
    if dll not in DLL32:
        raise ValueError("Unsupported ASI DLL")
    pattern = r'WINEDLLOVERRIDES=(?:"([^"\n]*)"|\x27([^\x27\n]*)\x27|([^\s]+))'
    matches = list(re.finditer(pattern, existing))
    if len(matches) > 1 or ("WINEDLLOVERRIDES" in existing and not matches):
        raise ValueError("Multiple or complex DLL overrides; merge manually in Steam.")
    if matches:
        match = matches[0]
        value = next(v for v in match.groups() if v is not None)
        if any(char in value for char in "$`\\"):
            raise ValueError("Dynamic overrides must be edited manually in Steam.")
        parts = [p for p in value.split(";") if p]
        updated = []
        for part in parts:
            names, sep, mode = part.partition("=")
            if not sep:
                raise ValueError("Unrecognized DLL override syntax")
            names = [n for n in names.split(",") if n.lower().removeprefix("*").removesuffix(".dll") != dll]
            if names:
                updated.append(",".join(names) + "=" + mode)
        updated.append(dll + "=n,b")
        replacement = 'WINEDLLOVERRIDES="' + ";".join(updated) + '"'
        return existing[: match.start()] + replacement + existing[match.end() :]
    if not existing.strip():
        return f'WINEDLLOVERRIDES="{dll}=n,b" %command%'
    if "%command%" not in existing:
        raise ValueError(
            "Existing options have no %command%; review them manually before adding an environment override."
        )
    return f'WINEDLLOVERRIDES="{dll}=n,b" ' + existing


def config_files(game):
    return (
        list((game.prefix / "drive_c/users").glob("*/AppData/Roaming/Reloaded-Mod-Loader-II/ReloadedII.json"))
        if game.prefix
        else []
    )


def windows_path_to_linux(value, prefix):
    normalized = value.replace("\\", "/")
    if len(normalized) < 3 or normalized[1:3] != ":/":
        raise ValueError("Unsupported relative Windows config path")
    drive = prefix / "dosdevices" / (normalized[0].lower() + ":")
    if not drive.exists():
        if normalized[0].lower() == "c":
            drive = prefix / "drive_c"
        else:
            raise ValueError("Windows drive mapping is unavailable")
    # Windows paths are case insensitive; Linux archive paths are not.
    current = drive.resolve()
    for component in Path(normalized[3:]).parts:
        candidate = current / component
        if not candidate.exists() and current.is_dir():
            matches = [p for p in current.iterdir() if p.name.casefold() == component.casefold()]
            if len(matches) == 1:
                candidate = matches[0]
        current = candidate
    return current.resolve()


def deploy(game, exe, backup_root):
    exe = exe.resolve()
    if not exe.is_relative_to(game.directory.resolve()):
        raise ValueError("Select the game executable inside its Steam installation.")
    configs = config_files(game)
    if len(configs) != 1:
        raise ValueError(
            "Open Reloaded-II once, register this executable, then close it before deploying ASI."
        )
    config = read_json(configs[0])
    # Bootstrapper reads this existing config at runtime. Confirm it targets THIS installation.
    is64, dll = executable_info(exe)
    loader = windows_path_to_linux(config.get("LoaderPath64" if is64 else "LoaderPath32", ""), game.prefix)
    expected = game.install / "Loader" / ("X64" if is64 else "X86") / "Reloaded.Mod.Loader.dll"
    if loader != expected.resolve() or not loader.is_file():
        raise ValueError(
            "Reloaded-II config points to another installation. Open this game's Reloaded-II first."
        )
    appdir = (
        (game.install / "Apps")
        if config.get("UsePortableMode")
        else windows_path_to_linux(config.get("ApplicationConfigDirectory", ""), game.prefix)
    )
    registered = False
    for app in appdir.glob("*/AppConfig.json"):
        data = read_json(app)
        if windows_path_to_linux(data.get("AppLocation", ""), game.prefix) == exe:
            registered = True
            break
    if not registered:
        raise ValueError("Register this exact executable using Add Application in Reloaded-II first.")
    folder = exe.parent
    conflicts = [
        p.name
        for p in folder.iterdir()
        if p.name.lower() in {n + ".dll" for n in DLL32} or p.suffix.lower() == ".asi"
    ]
    conflicts += [
        str(p.relative_to(folder)) for sub in ("scripts", "plugins") for p in (folder / sub).glob("*.asi")
    ]
    if conflicts:
        raise ValueError(
            "Existing DLL/ASI files require manual review; nothing overwritten: " + ", ".join(conflicts)
        )
    bootstrap = (
        game.install
        / "Loader"
        / ("X64" if is64 else "X86")
        / "Bootstrapper/Reloaded.Mod.Loader.Bootstrapper.dll"
    )
    archive = game.install / "Loader/Asi/UltimateAsiLoader.7z"
    if not bootstrap.is_file() or not archive.is_file():
        raise ValueError("Official ASI assets missing. Repair the installation.")
    payload = extract_asi(archive, is64)
    transaction = Transaction(backup_root, "ASI deployment")
    try:
        transaction.put(folder / (dll + ".dll"), payload)
        transaction.put(folder / "Reloaded.Mod.Loader.Bootstrapper.asi", bootstrap.read_bytes())
    except Exception:
        Transaction.rollback(transaction.root)
        raise
    return {
        "dll": dll,
        "exe": str(exe),
        "transaction": str(transaction.root),
        "files": {
            str(p): digest(p)
            for p in (folder / (dll + ".dll"), folder / "Reloaded.Mod.Loader.Bootstrapper.asi")
        },
    }


def extract_asi(archive, is64):
    """Read just the selected regular member; no archive-supplied paths reach disk.

    Upstream's real archive uses BCJ2, which py7zr does not support. libarchive
    supports it and is bundled with AppImage builds.
    """
    try:
        import libarchive
    except (ImportError, OSError, AttributeError) as exc:
        raise RuntimeError(
            "ASI extraction needs libarchive. Use the AppImage with bundled libarchive, "
            "or install libarchive for source execution."
        ) from exc
    member = "ASILoader64.dll" if is64 else "ASILoader32.dll"
    payload = None
    with libarchive.file_reader(str(archive)) as source:
        for entry in source:
            if entry.pathname != member:
                continue
            if (
                payload is not None
                or not entry.isreg
                or entry.issym
                or entry.islnk
                or not 0 < entry.size <= 32 * 1024**2
            ):
                raise ValueError("Invalid official ASI archive member")
            chunks, size = [], 0
            for chunk in entry.get_blocks():
                size += len(chunk)
                if size > 32 * 1024**2:
                    raise ValueError("ASI member exceeds extraction limit")
                chunks.append(chunk)
            payload = b"".join(chunks)
            if len(payload) != entry.size:
                raise ValueError("Incomplete ASI archive member")
    if payload is None:
        raise ValueError("Official archive does not contain " + member)
    return payload
