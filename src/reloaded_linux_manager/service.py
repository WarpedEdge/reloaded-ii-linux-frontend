"""Application operations shared by the Qt UI and tests."""

import os
import shutil
import tempfile
from pathlib import Path

from . import proton, releases
from .integration import config_files, merge_options, windows_path_to_linux
from .storage import Transaction, digest, read_json, state_home, write_json


def metadata(game):
    return state_home() / "games" / game.key / "state.json"


def backups(game):
    return state_home() / "games" / game.key / "backups"


def install(game, settings, report):
    if not game.directory.is_dir():
        raise ValueError("Game installation directory is missing.")
    target = game.install  # Validates initialized prefix.
    if not os.access(game.prefix, os.W_OK):
        raise ValueError("Proton prefix is not writable.")
    previous = read_json(metadata(game), {})
    if previous.get("prefix") and previous["prefix"] != str(game.prefix):
        raise ValueError("Manager state belongs to another prefix; review configuration before proceeding.")
    if target.is_symlink():
        raise ValueError("Refusing installation into a symbolic link.")
    if (
        target.exists()
        and not previous.get("installed")
        and any(p.is_file() or p.is_symlink() for p in target.rglob("*"))
    ):
        raise ValueError("Unmanaged installation at target location; automatic adoption is not supported.")
    for config in config_files(game):
        data = read_json(config)
        existing = windows_path_to_linux(data.get("LoaderPath64", ""), game.prefix)
        if not existing.is_relative_to(target.resolve()):
            raise ValueError(
                "An existing Reloaded-II configuration points to another installation in this prefix. "
                "Automatic adoption/migration is not supported; existing mods and configuration preserved."
            )
    launcher = proton.detect_launcher(settings.get("protontricks_launch", ""))
    # Validate launch routing before downloading or changing anything.
    proton.command(game, target / "Reloaded-II.exe", launcher)
    report("1. Steam game detected: " + game.name)
    report("2. Initialized Proton prefix detected; tool: " + game.tool)
    version, assets = releases.release(settings.get("release", "latest"))
    report("Official release: " + version)
    cache = Path(settings["cache"]).expanduser()
    archive = releases.download(assets["Release.zip"], cache, report)
    installer = releases.download(assets["Setup-Linux.exe"], cache, report)
    report("3. Official downloads validated (GitHub SHA-256 and size)")
    transaction = Transaction(backups(game), f"Install {version}")
    try:
        with tempfile.TemporaryDirectory(prefix="rlm-extract-") as temporary:
            staged = Path(temporary) / "release"
            releases.extract_zip(archive, staged)
            required = [
                "Reloaded-II.exe",
                "Loader/X64/Reloaded.Mod.Loader.dll",
                "Loader/X86/Reloaded.Mod.Loader.dll",
                "Loader/Asi/UltimateAsiLoader.7z",
            ]
            if any(not (staged / file).is_file() for file in required):
                raise ValueError("Release layout is unsupported or incomplete.")
            # Keep all user files, even when a future release happens to include that path.
            protected = {
                "apps",
                "mods",
                "moduserconfigs",
                "userconfigs",
                "profiles",
                "logs",
                "reloadedii.json",
            }
            for file in staged.rglob("*"):
                if file.is_file() and not any(p.lower() in protected for p in file.relative_to(staged).parts):
                    destination = target / file.relative_to(staged)
                    if not destination.resolve().is_relative_to(target.resolve()):
                        raise ValueError("Installation path escapes target through a symlink.")
                    if destination.exists() and digest(destination) == digest(file):
                        continue
                    transaction.put(destination, file.read_bytes())
        report("4. Official Reloaded-II files installed; prior files backed up")
        # Runtime installer may change prefix registry/runtime files. Back up Reloaded config,
        # but do not promise reversal of upstream runtime installation.
        for config in config_files(game):
            shutil.copytree(
                config.parent, transaction.root / ("config-" + config.parents[3].name), dirs_exist_ok=True
            )
        report("5. Running official runtime installer; this may take several minutes…")
        # --installdir marks the location as explicitly supplied. Dependencies-only mode
        # replaces it with an upstream temporary directory; the flag prevents upstream's
        # Proton desktop-location override from redirecting that temporary installation.
        proton.run(
            game,
            installer,
            launcher,
            ["--dependenciesOnly", "--nogui", "--installdir", r"C:\ReloadedLinuxManager\DependencyStaging"],
            state_home() / "process.log",
        )
        state = previous | {
            "installed": True,
            "version": version,
            "runtime_installer": "exited successfully; game validation pending",
            "install_transaction": str(transaction.root),
            "prefix": str(game.prefix),
            "install": str(target),
        }
        write_json(metadata(game), state)
    except Exception:
        conflicts = Transaction.rollback(transaction.root)
        if conflicts:
            report("Rollback preserved externally changed files: " + ", ".join(conflicts))
        raise
    try:
        from .shortcuts import refresh_game_shortcut

        result = refresh_game_shortcut(game, settings)
        if result:
            report(result)
    except (OSError, ValueError, RuntimeError) as exc:
        report("Installation finished, but its application shortcut needs attention: " + str(exc))
    report("6. Open Reloaded-II, add your game executable, and close it. Then use Deploy ASI Loader here.")
    report("7–9. ASI deployment, Steam options, and configuration checks remain pending.")
    return f"Reloaded-II {version} installed. Runtime installer exited successfully. Game configuration is pending."


def diagnostics(game):
    messages = []
    if not game.directory.is_dir():
        messages.append("FAIL: Game directory missing; repair the Steam library path.")
    if game.prefix is None:
        return messages + [
            "FAIL: No unambiguous initialized prefix. Launch through Steam once with Proton, or select the existing prefix."
        ]
    guide = setup_guide(game)
    if guide["stage"] == -1:
        return messages + [guide["heading"], guide["text"], "Existing config: " + str(config_files(game)[0])]
    if not os.access(game.prefix, os.W_OK):
        messages.append("FAIL: Prefix is not writable.")
    state = read_json(metadata(game), {})
    if not (game.install / "Reloaded-II.exe").is_file():
        messages.append("FAIL: Reloaded-II missing. Use Setup / Repair.")
    else:
        messages.append("OK: Reloaded-II executable present.")
    if not config_files(game):
        messages.append("PENDING: Open Reloaded-II to initialize its configuration.")
    if state.get("prefix") and state["prefix"] != str(game.prefix):
        messages.append("FAIL: Manager state belongs to another prefix.")
    for path, expected in state.get("asi", {}).get("files", {}).items():
        p = Path(path)
        if not p.is_file() or digest(p) != expected:
            messages.append("FAIL: Managed ASI file missing or changed: " + p.name)
        else:
            messages.append("OK: Managed ASI verified: " + p.name)
    dll = state.get("asi", {}).get("dll")
    if not dll:
        messages.append("PENDING: ASI loader not deployed by this manager.")
    elif not game.launch_options:
        messages.append("PENDING: No Steam launch options detected. Copy the generated options into Steam.")
    else:
        for option in game.launch_options:
            messages.append(
                "OK: DLL override present."
                if merge_options(option, dll) == option
                else "PENDING: Steam DLL override needs review (may differ between Steam accounts)."
            )
    if guide["stage"] == 6:
        messages.append("OK: Setup checks passed. Ready to launch.")
    else:
        messages.append(
            "PENDING: Complete the remaining setup steps. Logs show recorded launch and loader errors."
        )
    return messages


def remove_asi(game):
    state = read_json(metadata(game), {})
    if not state.get("asi"):
        from .shortcuts import remove_menu_shortcut

        return "No managed ASI integration to remove.\n" + remove_menu_shortcut(game)
    conflicts = Transaction.rollback(Path(state["asi"]["transaction"]))
    if conflicts:
        raise ValueError("Preserved modified files; remove manually after review: " + ", ".join(conflicts))
    from .shortcuts import remove_menu_shortcut

    try:
        shortcut_note = remove_menu_shortcut(game)
    except (OSError, ValueError) as exc:
        shortcut_note = "Application shortcut was preserved and needs review: " + str(exc)
    state.pop("asi")
    state.pop("playtest", None)
    write_json(metadata(game), state)
    return (
        "Managed ASI files removed. Remove its DLL override in Steam if no longer needed. Reloaded-II, mods and runtimes preserved.\n"
        + shortcut_note
    )


def setup_guide(game):
    """Read-only next-action summary. Never infer in-game success from files."""
    if game.prefix is None:
        return {
            "stage": 0,
            "action": "launch_game",
            "button": "Launch game in Steam",
            "heading": "First, launch this game once",
            "text": "Choose Proton in Steam → Properties → Compatibility, launch the game, then close it. "
            "Click Refresh here afterward so we can find its Windows environment.",
        }
    for config in config_files(game):
        data = read_json(config)
        try:
            loader = windows_path_to_linux(data.get("LoaderPath64", ""), game.prefix)
            other = not loader.is_relative_to(game.install.resolve())
        except ValueError:
            other = True
        if other:
            return {
                "stage": -1,
                "action": "check",
                "button": "View setup report",
                "heading": "An existing Reloaded-II setup was found",
                "text": "This game's Windows environment already points to another Reloaded-II installation. "
                "Continue using your existing integration. This version cannot import it yet, "
                "so automatic setup is paused to preserve your mods and settings.",
            }
    if not (game.install / "Reloaded-II.exe").is_file():
        return {
            "stage": 1,
            "action": "setup",
            "button": "Set up Reloaded-II",
            "heading": "Install Reloaded-II for this game",
            "text": "Your game and Proton environment were found. Next, download official Reloaded-II "
            "and install its Windows prerequisites. You'll review the changes before installation.",
        }
    if not registered_game(game):
        return {
            "stage": 2,
            "action": "open_reloaded",
            "button": "Open Reloaded-II",
            "heading": "Add your game in Reloaded-II",
            "text": "In the Reloaded-II window, choose Add Application and select your game's .exe. "
            "For FFT, choose FFT_enhanced.exe or FFT_classic.exe. Then close Reloaded-II to continue here.",
        }
    state = read_json(metadata(game), {})
    if not state.get("asi"):
        return {
            "stage": 3,
            "action": "deploy_asi",
            "button": "Enable loading through Steam",
            "heading": "Connect Reloaded-II to your Steam game",
            "text": "First add your game in Reloaded-II if you haven't already, then close it. "
            "Select that same game .exe next. We'll check its registration and install the official ASI loader.",
        }
    dll = state["asi"]["dll"]
    verified = bool(state["asi"].get("files")) and all(
        Path(p).is_file() and digest(Path(p)) == expected
        for p, expected in state["asi"].get("files", {}).items()
    )
    if not verified:
        return {
            "stage": 3,
            "action": "check",
            "button": "View repair report",
            "heading": "The Steam integration needs attention",
            "failed_step": 3,
            "text": "A loader file is missing or changed. Review the report before repairing or removing anything.",
        }
    try:
        configured = bool(game.launch_options) and all(
            merge_options(o, dll) == o for o in game.launch_options
        )
    except ValueError:
        configured = False
    if not configured:
        return {
            "stage": 4,
            "action": "options",
            "button": "Copy Steam launch options",
            "heading": "One setting to apply in Steam",
            "text": "Copy the generated launch options into Steam → game Properties → General. "
            "Your current options will be preserved. After saving them in Steam, click Refresh here.",
        }
    return {
        "stage": 6,
        "action": "launch_game",
        "button": "Launch game in Steam",
        "heading": "Ready",
        "text": "Open Reloaded-II to install and enable compatible mods. You can launch the game from Reloaded-II, this app, or Steam. "
        "Configuration checks passed. Mod compatibility still depends on the mods you enable.",
    }


def registered_game(game):
    """Only mark registration complete when an existing AppConfig targets this game."""
    for path in config_files(game):
        config = read_json(path)
        try:
            directory = (
                game.install / "Apps"
                if config.get("UsePortableMode")
                else windows_path_to_linux(config.get("ApplicationConfigDirectory", ""), game.prefix)
            )
        except ValueError:
            continue
        for application in directory.glob("*/AppConfig.json"):
            try:
                executable = windows_path_to_linux(read_json(application).get("AppLocation", ""), game.prefix)
                if executable.is_file() and executable.is_relative_to(game.directory.resolve()):
                    return True
            except ValueError:
                continue
    return False
