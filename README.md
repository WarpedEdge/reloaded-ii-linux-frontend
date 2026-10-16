# Reloaded Linux Manager

An experimental, native Python/PySide6 companion that installs and opens **official Windows Reloaded-II** in an installed Steam game's existing Proton prefix. The manager itself needs no Wine or Proton. It does not modify, fork, or replace Reloaded-II.

The first vertical slice includes Steam discovery, validated official release downloads, per-prefix installation, upstream runtime installation, one-button Protontricks launching, guided registration, import-based ASI deployment, launch-option generation, diagnostics, and reversible ASI removal. FFT mod loading has been reported working by the user; independent end-to-end and distribution testing remain incomplete. See [validation evidence](docs/VALIDATION.md).

## Run from source

Requires Linux x86_64, Python 3.11+, a graphical session and the host libraries needed by Qt, plus libarchive for ASI archive decoding (bundled in AppImage builds). Install [Protontricks](https://github.com/Matoking/protontricks#installation) separately, either natively or as `com.github.Matoking.protontricks` via Flatpak. Steam and Proton are required only for Windows applications/games.

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/reloaded-linux-manager
```

No root privileges, system package changes, Docker or Distrobox are required during normal use. A Flatpak Steam installation is supported; the **manager is not sandboxed**. If using Flatpak Protontricks, grant that application access to the relevant Steam library and manager download cache with Flatseal. The manager does not change Flatpak permissions automatically.

## Use with FFT

Selecting a game checks its setup and shows one recommended action. Refresh, Add game, Settings and About live in the top toolbar. The library is alphabetical, with local art, application-menu/Steam icons, and embedded EXE icons where available; right-click to favorite a game and pin it above the rest. Progress is shown at the top right (green complete, red failed, blue pending). **Ready** means registration, managed loader files, Steam launch options passed configuration checks, not that every mod is compatible. Activity, Logs and readable Setup details appear in the lower panel. Steam runtimes and Proton packages are hidden from the picker.

1. Install FINAL FANTASY TACTICS - The Ivalice Chronicles (App ID `1004640`), select Proton in Steam, and launch it once. Exit the game.
2. Open this manager, select FFT, and review its detected library, prefix, and compatibility tool. Refresh after changing Steam settings.
3. Click **Set up Reloaded-II**. Review the action dialog. The manager downloads `Release.zip` and `Setup-Linux.exe` from the official release, verifies GitHub's SHA-256 and asset sizes, installs inside `pfx/drive_c/ReloadedLinuxManager/Reloaded-II`, and runs the official dependencies-only installer in this game's Proton environment.
4. Click **Open Reloaded-II**. Use its Add Application interface to register `FFT_enhanced.exe` and/or `FFT_classic.exe` from the game directory displayed here. Under the normal Wine Z: mapping the path is `Z:\` followed by the Linux absolute path, with backslashes. Manage mods in Reloaded-II itself; close it before deploying.
5. Click **Deploy ASI Loader** and select the registered executable. Deployment validates the initialized Reloaded configuration, exact application registration, executable imports, and supplied official assets. Existing DLL/ASI conflicts stop the operation without overwriting them.
6. Click **Steam launch options**. Paste the current options from Steam Properties → General, review the merged result, click Copy, and paste it back into Steam. This manager never writes Steam's local configuration. Refresh and use **Check Setup** to inspect detected settings.
7. Install and enable compatible mods using Reloaded-II. FFT's utility loader is [Nenkai's fftivc.utility.modloader](https://github.com/Nenkai/fftivc.utility.modloader); follow its instructions and dependency resolution. This manager does not install third-party mods.
8. Exit Reloaded-II and the native manager, then launch FFT normally through Steam. Verify mods in game. The manager need not remain open.

Read-only checks on the locally installed FFT Classic and Enhanced executables found both are x64 and import `version.dll`; deployment still checks each selected executable rather than hardcoding that name. Both executables share a directory; deploy once for that directory and register both in Reloaded-II if using both.

## Application-menu shortcuts

**Add Reloaded-II to applications** installs `Reloaded-II-GAMENAME.desktop` under `$XDG_DATA_HOME/applications` (normally `~/.local/share/applications`). Game names are sanitized; separate Steam installations with colliding names get a distinguishing suffix. The launcher opens the real Windows manager directly through the selected game's system/Flatpak Protontricks environment, without opening this native manager.

**Add manager to applications** installs `Reloaded-Linux-Manager.desktop` in the same location, pointing to the original AppImage. Neither button asks for a save location. Source runs use the local built AppImage or ask you to locate it. Reloaded-II shortcuts use the official Windows launcher’s embedded R icon with the game’s artwork badged at the bottom right, copied to persistent user data. The manager uses the supplied Linux-Reloaded-Manager artwork for its window, AppImage and application-menu launcher. Reinstall Reloaded-II refreshes an existing managed shortcut’s icon.

Each application button switches to Remove when its managed shortcut exists, and back to Add after removal. Only tracked, unchanged entries are replaced or removed. Unrelated and externally edited entries are preserved with an explanation. Reinstall Reloaded-II refreshes an existing game shortcut; Reset ASI Deployment keeps the game's application shortcut. Disconnect preserves mods; a full reset moves them into a backup. No operation deletes the Proton prefix. Old shortcuts saved onto the desktop by earlier development builds are not silently removed.

## Logs and setup checks

Logs, Activity and Setup details highlight errors in red and warnings or pending checks in yellow. **Clear logs** asks before clearing the manager logs and the recent Reloaded-II log files shown for the selected game; mods, saved configuration and the prefix are preserved. Close the game and Reloaded-II before clearing their logs.

Setup turns green automatically when its configuration checks pass; no manual verification is required. Logs has separate Manager, Protontricks and Reloaded-II sources, with a file selector for game logs. A highlighted source button indicates unread content. Configuration checks cannot prove every mod works, and logs can only report failures that were recorded.

The Ready text explains that games can be launched from Reloaded-II, this frontend, or Steam. Reset ASI Deployment resets the manager’s loader files while keeping Reloaded-II, mods, saves and the Windows environment. Steam launch options remain under your control and may need manual cleanup.

## Manager updates and About

About identifies WarpedEdge, manager version **0.1**, the project link and the selected game's installed Reloaded-II version. The manager checks published stable releases from [WarpedEdge/reloaded-ii-linux-frontend](https://github.com/WarpedEdge/reloaded-ii-linux-frontend) at startup, with a manual check in About. Settings can disable startup checks. Reloaded-II offers its own updates inside its Windows launcher; Reinstall Reloaded-II remains available for recovery.

When a newer stable manager release offers `Reloaded-Linux-Manager-x86_64.AppImage`, the app prompts before downloading. It checks the release asset's GitHub SHA-256, size, ELF architecture and AppImage type, stages it next to the current file, backs up the current file as `YOUR-APPIMAGE.AppImage.previous`, and atomically replaces the original path. Existing application-menu entries continue working because the path and filename stay the same. The app then offers to restart. Downloads, validation and replacement run outside the GUI thread.

The AppImage and its containing folder must be writable; symlink targets are not updated automatically. Failed/corrupt downloads preserve the current image. A `.previous` file is retained for manual recovery if the next version cannot run on the host. Settings, favorites, game data and shortcut names are preserved. No other application or mod is updated by this mechanism.

**Live update limitation:** anonymous GitHub requests currently return 404 for the repository/latest release. The app reports that no public release is available. The update pipeline is covered by local fixtures, but a live v0.1 → v0.2 update needs a public published release with the matching asset. Draft releases are intentionally not offered. Before tagging a release, update both `__version__` and the package version; CI verifies they match the tag.

## Existing installations, repair, and removal

- Existing Reloaded configuration pointing to another installation is detected and **blocks automatic installation**. Migration/adoption needs additional testing. This prevents taking over another manager's setup.
- Repair and Update run the same validated, backed-up installation pipeline. The default is the latest official release; the installed version is shown in About. Mods, apps, profiles and user configuration are excluded from release replacement. Releases lacking GitHub asset SHA-256 digests are rejected.
- ASI deployment refuses existing supported proxy DLLs or ASI plugins. Review conflicting loaders manually; this version does not offer an overwrite path.
- Reset ASI Deployment rolls back unchanged ASI files created by this manager. It preserves Reloaded-II, mods, runtimes and the entire prefix. Remove the related override in Steam yourself if no longer needed.
- Install failures roll back manager-written files. Backups and transaction journals live under `$XDG_STATE_HOME/reloaded-linux-manager/games/` (normally `~/.local/state/...`). `Transaction.rollback()` is available to developers for recovering an installation transaction; there is not yet a GUI for arbitrary historical rollback. Upstream Windows runtime/registry changes cannot be undone by these file journals.
- If another program changes a managed file, rollback reports a conflict and preserves it. No repair operation deletes or resets a prefix.

Use the Logs tab to read manager, Protontricks and recent Reloaded-II logs inside the app. Open folder opens the directory for the selected log source. Historical Protontricks output is explicitly labelled when timestamps are unavailable. Log reads are bounded; Refresh logs loads recent output. Setup details explains detected paths, versions and checks instead of exposing raw internal JSON. `manager.log` rotates; `process.log` captures upstream output. Review/redact local usernames, paths, Steam account identifiers or other sensitive output before sharing logs.

## Steam discovery and limitations

Native and Flatpak Steam roots are probed, then `libraryfolders.vdf` and `appmanifest_*.acf` provide the libraries and game paths, including external drives. Steam compatibility mappings and user launch options are read only. Tool names are displayed where configured; Steam automatic selection is explicitly unresolved. Protontricks resolves the actual tool/runtime at launch, including installed custom tools.

Settings contains startup update checks, an explained download-cache location and readable log-detail levels. Advanced game discovery hides the rarely needed extra Steam/library folder controls behind an explanatory section. Protontricks is detected automatically. Add game manually accepts a Windows `.exe` or a real Steam app manifest, matches executables to their Steam manifest, and asks for the owning Steam root only when needed. All file/folder dialogs show hidden entries such as `.local` and `.steam`, have larger text/navigation controls, and retain a Look in dropdown that also accepts pasted paths (press Enter to navigate). Executables outside a Steam manifest-backed library and non-Steam shortcut prefixes remain unsupported; no App IDs or prefixes are invented. Select Existing Prefix helps diagnose custom locations; launching a custom/cross-library prefix is deliberately blocked because `--appid` cannot guarantee routing to it. Uninitialized or ambiguous prefixes are never synthesized. Native Linux titles and Steam runtime/tool manifests may appear in the library; selecting one does not imply Proton support.

The UI remains responsive during discovery, downloads, extraction and child processes. Mutating actions are serialized. While Reloaded-II runs, other actions are disabled; close Reloaded-II to continue. Standard Qt mouse and keyboard navigation remains available.

## AppImage

The GitHub Actions workflow builds x86_64 AppImages on Ubuntu 22.04 and creates **draft** GitHub releases for version tags. A local AppImage built on Bazzite/glibc 2.43 passes offscreen Qt and bundled ASI-decoding smoke tests; it has not passed the full distribution matrix. Prefer the older-baseline CI build for distribution. To build locally:

```bash
.venv/bin/pip install -e '.[dev]'
# Obtain appimagetool from https://github.com/AppImage/appimagetool
# Verify its checksum, then provide its absolute executable path:
PATH="$PWD/.venv/bin:$PATH" APPIMAGETOOL=/absolute/path/appimagetool.AppImage packaging/build-appimage.sh
```

The output is `dist/Reloaded-Linux-Manager-x86_64.AppImage`, plus SHA256SUMS. Make the artifact executable and launch it. If FUSE is unavailable, use `./Reloaded-Linux-Manager-x86_64.AppImage --appimage-extract-and-run`.

AppImage bundles Python, Qt and application dependencies, **not** the kernel, glibc, graphics drivers, all X11/Wayland libraries, Steam, Proton or Protontricks. The CI baseline is glibc 2.35 (Ubuntu 22.04); bundled wheels may impose additional requirements. Builds made on newer systems can need newer glibc. X11/Wayland Qt plugins still depend on host display libraries; `QT_QPA_PLATFORM=xcb` is a fallback when XWayland is available. ARM, old Debian/Ubuntu releases, and 32-bit systems are not supported. Bazzite, SteamOS, Fedora, Ubuntu, Debian, Mint, Arch, EndeavourOS and openSUSE remain validation targets, not compatibility promises.

## Development

```bash
.venv/bin/pytest -q
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
```

Tests use isolated temporary Steam libraries and prefixes; they never run Proton or alter the real game. The Qt smoke test uses the offscreen platform. See [research and architecture](docs/RESEARCH.md) for source links, automation boundaries and design decisions, and [validation](docs/VALIDATION.md) for pending real-world tests.

Written by WarpedEdge. Code is MIT licensed. Upstream binaries are downloaded from their official project and retain their own licenses; they are not bundled in this repository or the manager AppImage. This is an independent companion project.

Protontricks output is timestamped and grouped by launch start/end, including exit codes. It rotates at 2 MiB per file with two backups (about 6 MiB total). Normal information and Wine fixme output stay neutral; detected warnings are yellow and errors red. Clear logs also clears those backups.

While the manager runs, it retains the newest three Reloaded-II text logs for the selected game. Older files detected as open or modified within the past minute are deferred until a later cleanup. Archive files and mods/configuration are preserved. Launches while the manager is closed are cleaned up when it next checks that game.

## Appearance and settings

Settings has Appearance, General and Advanced tabs. Appearance offers 15 themes with live previews: Dark (default), Light, OLED, Plum, Forest, Cyberpunk, Ivalice (FFT), Amethyst, Mocha, Noir, Pip-Boy, Stardew, Tokyo Night and two Breeze-inspired palettes. Save persists the theme for future launches; Cancel restores your previous theme. Themes also adjust readable setup status colors, log highlighting and dialogs. General contains update checks, the download cache and log detail. Advanced contains optional Steam/library discovery folders.

To add a built-in theme, add a named color-token palette in `src/reloaded_linux_manager/themes.py`. Its preview and selector appear automatically; no settings-layout changes are needed. Run the theme tests to check text contrast and saved/preview behavior. This initial version provides built-in themes; arbitrary theme-file importing and editing are not included.

## Reinstall, disconnect and full reset

More actions provides distinct operations, each with a tooltip:

- **Reinstall Reloaded-II** downloads the latest official release and reinstalls program files/prerequisites while keeping mods, settings and registration. It may also update the installed release.
- **Reset ASI Deployment…** rolls back manager-deployed ASI files and keeps the game's application shortcut. Reloaded-II and mods remain installed.
- **Reset All** returns the selected game to the first setup step. After confirmation, it moves the managed installation (including mods/profiles) and Reloaded-II configuration into `PREFIX/drive_c/ReloadedLinuxManager/ResetBackups/ID`, restores game files changed by ASI deployment, removes the game shortcut and clears setup state. The backup location appears in Activity. External/shared configurations and conflicting loader files stop the reset for review.
- **Restore last full reset…** restores the saved installation, settings, loader integration and game shortcut. A new setup or changed loader files are preserved instead of overwritten.

Close the game and Reloaded-II before reset/restore. All operations keep the game, saves, Proton prefix, installed Windows runtimes and manager application shortcut. Steam launch options are not edited; review/remove the old Reloaded-II override in Steam when disconnecting or resetting. Other launch parameters are preserved. Full reset backups remain until you remove them; they can be large if you installed many mods.

## Dependency downloads and Steam settings

On the first launch through the manager, a reminder asks you to select your game in Reloaded-II after adding mods and leave it open for a moment so required dependencies can download. Wait for downloads/popups to finish before closing it. There is no separate dependency checklist or dependency-based launch blocking.

The Steam launch options dialog reads Steam's saved per-account settings, preserves existing parameters and shows whether the required ASI override is detected. It can reread these settings with **Check Steam settings**; Steam may take a moment to save a recent edit. Multiple saved values can belong to different accounts and must be reviewed. The manager never writes Steam configuration files.

Copying the generated options advances the setup handoff, with a reminder to paste into Steam → Properties → General → Launch Options. The progress label says **Launch options copied** until the saved value is detected; it does not claim that copying changed Steam. The override syntax is generally `WINEDLLOVERRIDES="DLLNAME=n,b" %command%`, but DLLNAME depends on the deployed loader/game.

Reset All cannot reconstruct the pre-runtime state of existing prefixes: there is no record proving which shared VC++/.NET components were already there. It therefore keeps Windows runtimes and does not claim to uninstall them or reset the whole prefix.

Theme previews use equal-sized cards. Component styles cover tabs, menus, inputs, scrollbars and primary/disabled buttons instead of depending on desktop defaults. Cyberpunk uses cyan text, red outlines and yellow primary actions. Ivalice uses FFT-inspired gray-olive menu panels, dark ink and raised borders. Its palette does not add a game-scene backdrop. Setup progress uses larger bold markers and separate, high-contrast status colors, including a green-toned Pip-Boy variant.

The runtime-removal requirements and current limitations are documented in [docs/RUNTIME_REMOVAL.md](docs/RUNTIME_REMOVAL.md).
