# Reloaded Linux Manager

An experimental, native Python/PySide6 companion that installs and opens **official Windows Reloaded-II** in an installed Steam game's existing Proton prefix. The manager itself needs no Wine or Proton. It does not modify, fork, or replace Reloaded-II.

The first vertical slice includes Steam discovery, validated official release downloads, per-prefix installation, upstream runtime installation, one-button Protontricks launching, guided registration, import-based ASI deployment, launch-option generation, diagnostics, and reversible ASI removal. **In-game mod loading and distribution compatibility are not yet validated.** See [validation evidence](docs/VALIDATION.md).

## Run from source

Requires Linux x86_64, Python 3.11+, a graphical session and the host libraries needed by Qt, plus libarchive for ASI archive decoding (bundled in AppImage builds). Install [Protontricks](https://github.com/Matoking/protontricks#installation) separately, either natively or as `com.github.Matoking.protontricks` via Flatpak. Steam and Proton are required only for Windows applications/games.

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/reloaded-linux-manager
```

No root privileges, system package changes, Docker or Distrobox are required during normal use. A Flatpak Steam installation is supported; the **manager is not sandboxed**. If using Flatpak Protontricks, grant that application access to the relevant Steam library and manager download cache with Flatseal. The manager does not change Flatpak permissions automatically.

## Use with FFT

Selecting a game automatically checks its setup and shows one recommended action with a short checklist. Open Reloaded-II, Deploy ASI loader, Steam launch options and More actions have equal-width buttons. Technical paths appear below the game ID, progress is shown at the top right (green complete, red failed, blue pending), and Activity stays open by default. Buttons highlight on hover and show a pointer cursor. Steam runtimes and Proton packages are hidden from the game picker.

1. Install FINAL FANTASY TACTICS - The Ivalice Chronicles (App ID `1004640`), select Proton in Steam, and launch it once. Exit the game.
2. Open this manager, select FFT, and review its detected library, prefix, and compatibility tool. Refresh after changing Steam settings.
3. Click **Set up Reloaded-II**. Review the action dialog. The manager downloads `Release.zip` and `Setup-Linux.exe` from the official release, verifies GitHub's SHA-256 and asset sizes, installs inside `pfx/drive_c/ReloadedLinuxManager/Reloaded-II`, and runs the official dependencies-only installer in this game's Proton environment.
4. Click **Open Reloaded-II**. Use its Add Application interface to register `FFT_enhanced.exe` and/or `FFT_classic.exe` from the game directory displayed here. Under the normal Wine Z: mapping the path is `Z:\` followed by the Linux absolute path, with backslashes. Manage mods in Reloaded-II itself; close it before deploying.
5. Click **Deploy ASI Loader** and select the registered executable. Deployment validates the initialized Reloaded configuration, exact application registration, executable imports, and supplied official assets. Existing DLL/ASI conflicts stop the operation without overwriting them.
6. Click **Steam launch options**. Paste the current options from Steam Properties → General, review the merged result, click Copy, and paste it back into Steam. This manager never writes Steam's local configuration. Refresh and use **Check Setup** to inspect detected settings.
7. Install and enable compatible mods using Reloaded-II. FFT's utility loader is [Nenkai's fftivc.utility.modloader](https://github.com/Nenkai/fftivc.utility.modloader); follow its instructions and dependency resolution. This manager does not install third-party mods.
8. Exit Reloaded-II and the native manager, then launch FFT normally through Steam. Verify mods in game. The manager need not remain open.

Read-only checks on the locally installed FFT Classic and Enhanced executables found both are x64 and import `version.dll`; deployment still checks each selected executable rather than hardcoding that name. Both executables share a directory; deploy once for that directory and register both in Reloaded-II if using both.

## Desktop shortcuts

**Create Reloaded-II desktop shortcut** saves a game-specific `.desktop` launcher that opens the real Windows manager directly through Protontricks, without opening the native manager. System and Flatpak Protontricks are supported; its Steam root and App ID are included explicitly.

**Create manager AppImage shortcut** points to the original manager AppImage, never its temporary mount directory. When running from source, it uses the local built AppImage or asks you to select one. Both buttons offer a Save dialog, defaulting to your desktop. Existing shortcuts are backed up before replacement, and new launchers are made executable. Your desktop environment may still ask you to **Allow Launching** or mark a launcher as trusted. Keep the AppImage, Steam library and Reloaded-II in the same locations after creating the shortcuts. Generic system icons are used for now.

## Existing installations, repair, and removal

- Existing Reloaded configuration pointing to another installation is detected and **blocks automatic installation**. Migration/adoption needs additional testing. This prevents taking over another manager's setup.
- Repair and Update run the same validated, backed-up installation pipeline. Choose `latest` or a release tag in Settings. Mods, apps, profiles and user configuration are excluded from release replacement. Releases lacking GitHub asset SHA-256 digests are rejected.
- ASI deployment refuses existing supported proxy DLLs or ASI plugins. Review conflicting loaders manually; this version does not offer an overwrite path.
- Remove Integration rolls back unchanged ASI files created by this manager. It preserves Reloaded-II, mods, runtimes and the entire prefix. Remove the related override in Steam yourself if no longer needed.
- Install failures roll back manager-written files. Backups and transaction journals live under `$XDG_STATE_HOME/reloaded-linux-manager/games/` (normally `~/.local/state/...`). `Transaction.rollback()` is available to developers for recovering an installation transaction; there is not yet a GUI for arbitrary historical rollback. Upstream Windows runtime/registry changes cannot be undone by these file journals.
- If another program changes a managed file, rollback reports a conflict and preserves it. No repair operation deletes or resets a prefix.

Use More actions → View logs to open the state directory. `manager.log` rotates; `process.log` captures upstream output. Review/redact local usernames, paths, Steam account identifiers or other sensitive output before sharing logs.

## Steam discovery and limitations

Native and Flatpak Steam roots are probed, then `libraryfolders.vdf` and `appmanifest_*.acf` provide the libraries and game paths, including external drives. Steam compatibility mappings and user launch options are read only. Tool names are displayed where configured; Steam automatic selection is explicitly unresolved. Protontricks resolves the actual tool/runtime at launch, including installed custom tools.

Settings accepts extra Steam/library roots, cache location, release tag, a custom `protontricks-launch` executable and logging level. Add game manually accepts a Windows `.exe` or a real Steam app manifest, matches executables to their Steam manifest, and asks for the owning Steam root only when needed. All file/folder dialogs show hidden entries such as `.local` and `.steam`. Executables outside a Steam manifest-backed library and non-Steam shortcut prefixes remain unsupported; no App IDs or prefixes are invented. Select Existing Prefix helps diagnose custom locations; launching a custom/cross-library prefix is deliberately blocked because `--appid` cannot guarantee routing to it. Uninitialized or ambiguous prefixes are never synthesized. Native Linux titles and Steam runtime/tool manifests may appear in the library; selecting one does not imply Proton support.

The UI remains responsive during discovery, downloads, extraction and child processes. Mutating actions are serialized. While Reloaded-II runs, other actions are disabled; close Reloaded-II to continue. Controller use benefits from standard Qt focus/tab navigation and large buttons, but full gamepad navigation is not implemented.

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

Code is MIT licensed. Upstream binaries are downloaded from their official project and retain their own licenses; they are not bundled in this repository or the manager AppImage. This is an independent companion project.
