# Reloaded Linux Manager

A native Linux frontend for setting up and opening the official Windows **Reloaded-II** launcher for Steam games running through Proton.

- Find installed Steam games, including games on external drives.
- Install official Reloaded-II releases in each game's existing Proton prefix.
- Open Reloaded-II in the selected game's Windows environment.
- Deploy its ASI loader and generate Steam launch options.
- Read logs, reinstall Reloaded-II, or reset the selected game's setup.

The manager uses the same setup checks for every game. It does not decide which games or mods support Reloaded-II. Check the game's modding instructions before setting it up. Install and manage mods in Reloaded-II itself.

The manager runs natively with Python and PySide6. It does not modify or replace Reloaded-II. Version **0.1** is under development; see [testing and limitations](docs/VALIDATION.md).

## Requirements

- Linux x86_64 with a graphical desktop.
- Steam and an installed game configured to use Proton.
- [Protontricks](https://github.com/Matoking/protontricks#installation), installed natively or as `com.github.Matoking.protontricks` through Flatpak.

Normal use requires no root access or system changes. Native and Flatpak Steam installations are supported. The manager itself is not sandboxed. Flatpak Protontricks may need permission to access the Steam library and download cache; the manager does not change these permissions.

## Run the AppImage

Download `Reloaded-Linux-Manager-x86_64.AppImage` from the project's [releases](https://github.com/WarpedEdge/reloaded-ii-linux-frontend/releases), when available. Make it executable and open it:

```bash
chmod +x Reloaded-Linux-Manager-x86_64.AppImage
./Reloaded-Linux-Manager-x86_64.AppImage
```

If FUSE is unavailable, run it with `--appimage-extract-and-run`.

## Set up a game

1. Choose Proton in the game's Steam Properties → Compatibility. Launch the game through Steam once, then close it. This creates its Windows environment.
2. Open the manager and select the game. Check the detected Steam, game and prefix paths. Use Refresh after changing Steam settings.
3. Click **Set up Reloaded-II** and review the changes. The manager downloads the official release, checks its SHA-256 hashes and file sizes, and runs the official Windows prerequisite installer through Protontricks.
4. Click **Open Reloaded-II**. Choose Add Application in its window and select your game's Windows executable. Install and enable compatible mods there, following their instructions.
5. You may need to launch the game once from inside Reloaded-II so it can download missing mod dependencies. Wait for downloads and popups to finish, then close the game and Reloaded-II.
6. Click **Deploy ASI Loader** and select the executable you registered. The manager checks its DLL imports and deploys the official loader files. Existing loader conflicts stop deployment for review.
7. Click **Steam launch options**, review the generated value, then copy and paste it into Steam → game Properties → General → Launch Options. Existing parameters are kept when they can be merged safely. Use **Check Steam settings** to read the saved value.
8. Launch the game from Reloaded-II, this app, or Steam. Check that your mods work in game. The native manager does not need to stay open.

**Ready** means the setup checks passed. It does not prove that every enabled mod works. Copying launch options advances the instructions, but the manager shows a reminder until it detects the saved Steam setting. It never edits Steam configuration files.

Each setup installs Reloaded-II under `PREFIX/drive_c/ReloadedLinuxManager/Reloaded-II`. The manager reads Reloaded-II's application registration; it does not write guessed registration files.

## Library and settings

Games are sorted by name. Right-click a game to favorite it and keep it at the top. Icons come from local artwork, Steam's cache, application-menu entries or executable resources. A fallback icon appears when artwork cannot be found.

**Add game** accepts a Windows `.exe` or Steam app manifest. The executable must belong to a Steam library with a valid manifest. File dialogs show hidden folders and accept pasted paths.

Settings has three tabs:

- **Appearance:** choose a theme and preview it. Save keeps the choice; Cancel restores the previous theme. The Ivalice theme is inspired by FINAL FANTASY TACTICS menu colors.
- **General:** control startup update checks, the download cache and log detail.
- **Advanced:** add Steam installation or library folders if automatic discovery misses them.

## Application shortcuts

**Add Reloaded-II to applications** creates `Reloaded-II-GAMENAME.desktop` under `$XDG_DATA_HOME/applications`, normally `~/.local/share/applications`. It opens Reloaded-II directly in that game's Proton environment. Its icon combines the Reloaded-II icon with the game's artwork.

**Add manager to applications** creates `Reloaded-Linux-Manager.desktop` in the same location. It points to the AppImage, so keep that file at the same path. Updates replace it at that path, preserving the shortcut. Source runs use a local built AppImage or ask you to locate one.

Each button changes to Remove when its shortcut exists. The manager only replaces or removes shortcuts it created and that have not been changed externally.

## Logs and setup details

The lower panel has Activity, Logs and Setup details tabs. Logs has separate Manager, Protontricks and Reloaded-II sources. A highlighted source button means it has unread content. **Open folder** opens that source's directory. Errors are red and warnings are yellow.

Protontricks output includes timestamps, launch boundaries and exit codes. Its log rotates at 2 MiB with two backups. Older output without timestamps is labelled. The manager keeps the three newest Reloaded-II text logs for the selected game; files still open or recently changed are left until a later check. Logs created while the manager is closed are cleaned up when it next checks that game.

**Clear logs** asks before clearing saved manager and Protontricks logs and the recent Reloaded-II logs displayed for the selected game. It preserves mods, settings and the Proton prefix. Close Reloaded-II and the game before clearing their logs. Review usernames, paths and account information before sharing logs in an issue.

## Reinstall and reset

Close Reloaded-II and the game before changing their setup. More actions includes:

- **Select existing prefix:** choose a prefix different from the detected one. Launching through an unsupported custom location may still be blocked because Protontricks cannot guarantee the correct routing.
- **Reinstall Reloaded-II:** install the latest official program files and prerequisites while keeping mods, profiles, settings and registration.
- **Reset ASI Deployment:** undo the manager's loader-file changes. Keep Reloaded-II and its mods. Review the related Steam DLL override yourself.
- **Reset All:** move the managed Reloaded-II installation, mods and configuration into a backup, undo ASI deployment, remove the game's shortcut and clear its setup state. Activity shows the backup path.
- **Restore last full reset:** restore that backup. A new setup or conflicting file changes stop restoration rather than being overwritten.

These actions keep the game, saves, Proton prefix, installed Windows runtimes and manager shortcut. **Reset All does not uninstall shared VC++ or .NET runtimes.** The manager has no record proving which components existed before setup. See [runtime removal limits](docs/RUNTIME_REMOVAL.md).

Existing Reloaded-II configurations pointing to another installation block automatic setup. Changed loader files and unrelated shortcuts are preserved. File changes made by the manager have backups; Windows runtime and registry changes made by the official installer cannot be undone by those backups. Full-reset backups remain until you remove them and can use substantial disk space.

## Downloads and updates

Reloaded-II files come from its [official releases](https://github.com/Reloaded-Project/Reloaded-II/releases). Cached downloads are checked by SHA-256 and size before use. Release information is cached for an hour and can be reused if GitHub rate-limits a later request. Without cached release information, setup must wait until GitHub allows requests again. An expired cached release may be older than the latest release.

The manager checks its own stable GitHub releases at startup unless disabled in Settings. **Check for updates** is also available in About. If a matching x86_64 AppImage is available, the app asks before downloading, checks its hash, size and format, then replaces the current AppImage and offers to restart. The old file is kept as `.previous`. The AppImage and its directory must be writable. A live update between published manager versions still needs testing.

Reloaded-II handles its own update prompts inside the Windows launcher. The native manager's reinstall action is available for recovery.

## Run from source

Use Python 3.11 or newer, the host libraries required by Qt, and libarchive for ASI extraction:

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/reloaded-linux-manager
```

Restart after changing source files. **An AppImage contains a separate bundled copy of the code and must be rebuilt after changes.**

Run the checks:

```bash
.venv/bin/pytest -q
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
```

Tests use temporary libraries and prefixes. They do not launch real games or install Windows runtimes. See [source research](docs/RESEARCH.md) for the upstream interfaces used by the manager.

## Build an AppImage

Install the development dependencies above. Obtain and verify [appimagetool](https://github.com/AppImage/appimagetool), then run:

```bash
PATH="$PWD/.venv/bin:$PATH" APPIMAGETOOL=/absolute/path/appimagetool.AppImage packaging/build-appimage.sh
```

The output is `dist/Reloaded-Linux-Manager-x86_64.AppImage` and `dist/SHA256SUMS`. Close the old app and reopen the rebuilt file to test changes.

The GitHub Actions workflow builds on Ubuntu 22.04 and creates draft releases for version tags. Update the package and application versions together before tagging; CI checks that they match.

AppImage bundles Python, Qt and application dependencies, including libarchive. It still depends on the host kernel, glibc, graphics drivers and some display libraries. It does not bundle Steam, Proton or Protontricks. The CI build targets glibc 2.35; local builds on newer systems may require newer glibc. X11 and Wayland need testing on each target desktop. `QT_QPA_PLATFORM=xcb` can be used with XWayland if the Wayland plugin cannot load.

Bazzite, SteamOS, Fedora, Ubuntu, Debian, Linux Mint, Arch, EndeavourOS and openSUSE are testing targets, not guaranteed compatible systems. ARM and 32-bit systems are unsupported. Non-Steam prefixes, automatic prefix creation and automatic migration from other managers are unsupported.

## Credits

Written by **WarpedEdge**. The manager's code is MIT licensed. Reloaded-II and its binaries retain their own licenses and are downloaded from the official project rather than bundled here. This is an independent frontend.
