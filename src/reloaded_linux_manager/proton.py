"""Use Protontricks to resolve Steam's tool and runtime rather than guessing Wine paths."""

import os
import shutil
import subprocess
from pathlib import Path

FLATPAK_ID = "com.github.Matoking.protontricks"


def detect_launcher(custom=""):
    if custom:
        path = Path(custom).expanduser()
        if not path.is_file() or not os.access(path, os.X_OK):
            raise ValueError("Configured protontricks-launch executable is unavailable.")
        return [str(path)]
    if executable := shutil.which("protontricks-launch"):
        return [executable]
    if flatpak := shutil.which("flatpak"):
        result = subprocess.run([flatpak, "info", FLATPAK_ID], capture_output=True, timeout=15)
        if result.returncode == 0:
            return [flatpak, "run", "--command=protontricks-launch", FLATPAK_ID]
    raise RuntimeError(
        "Install Protontricks (system package or com.github.Matoking.protontricks via Flatpak). "
        "For Flatpak, grant access to the selected Steam library and download cache using Flatseal. "
        "See https://github.com/Matoking/protontricks#installation"
    )


def command(game, executable, launcher, args=()):
    if game.prefix is None:
        raise ValueError("Launch the game once through Steam with Proton first.")
    # Protontricks owns prefix/tool selection. Refuse a manually selected nonstandard prefix:
    # --appid cannot reliably express a custom STEAM_COMPAT_DATA_PATH.
    expected = game.library / f"steamapps/compatdata/{game.appid}/pfx"
    if game.prefix.resolve() != expected.resolve():
        raise ValueError(
            "Custom/cross-library prefix detected. Protontricks --appid cannot safely guarantee this "
            "prefix; use the game's normal Steam environment. Launch automation is disabled."
        )
    return [*launcher, "--appid", game.appid, str(executable), *args]


def run(game, executable, launcher, args=(), log_path=None):
    argv = command(game, executable, launcher, args)
    env = os.environ.copy()
    env["STEAM_DIR"] = str(game.steam)
    env["DOTNET_ROOT"] = ""
    import sys

    if "APPIMAGE" in env or getattr(sys, "frozen", False):
        # Do not inject bundled Qt/Python libraries into Proton or Flatpak.
        if "LD_LIBRARY_PATH_ORIG" in env:
            env["LD_LIBRARY_PATH"] = env["LD_LIBRARY_PATH_ORIG"]
        else:
            env.pop("LD_LIBRARY_PATH", None)
        for variable in ("QT_PLUGIN_PATH", "QML2_IMPORT_PATH", "PYTHONHOME", "PYTHONPATH"):
            env.pop(variable, None)
        env.pop("LD_PRELOAD", None)
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("ab") as stream:
            result = subprocess.run(argv, env=env, stdout=stream, stderr=subprocess.STDOUT)
    else:
        result = subprocess.run(argv, env=env, capture_output=True)
    if result.returncode:
        raise RuntimeError(
            f"Protontricks exited with code {result.returncode}. View Logs for details. "
            "Check Steam is running and Flatpak filesystem permissions."
        )
