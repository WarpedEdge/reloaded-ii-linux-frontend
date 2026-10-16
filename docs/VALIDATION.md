# Validation record

## Verified in this development environment

Host: Bazzite 44.20261002.0, x86_64, glibc 2.43. This is a local build, not the older Ubuntu 22.04 CI build. Its portability to older glibc systems is not established.

- Python 3.14.7 source execution with PySide6 6.12.0, vdf 3.4, pefile 2024.8.26 and libarchive-c 5.3.
- 58 automated tests: external/native/Flatpak library discovery, duplicate Steam symlinks, prefix missing/ambiguity, manifest traversal, launch argv safety, ZIP traversal/symlink rejection, extraction, corrupt cache replacement/checksum rejection, option preservation/idempotence, configuration rollback and conflict preservation, installation rollback on subprocess failure, preserving user mods, preventing takeover of another installation, retrying failed first installs, official ASI member selection/copy/rollback, a BCJ2 regression fixture, and loader conflicts.
- Native Qt window smoke-tested offscreen with asynchronous discovery.
- Real local Steam discovery finds FFT App ID 1004640, its external library, initialized prefix, and configured proton_experimental mapping.
- Actual local FFT Classic/Enhanced executables inspected read-only with pefile: both x64 and import version.dll.
- Official Release.zip 1.31.0 downloaded to a temporary test cache, SHA-256/size validated and safely extracted. Actual uppercase X64/X86 layout and ASILoader32.dll/ASILoader64.dll archive members verified. Runtimeconfig requires .NET 9.
- Official Setup-Linux.exe 1.31.0 downloaded and validated against GitHub's SHA-256 and size (8,097,792 bytes), without executing it.
- Built a 68 MiB local AppImage using PyInstaller and verified appimagetool. Its FUSE-free Qt smoke test passes on this Bazzite host with the offscreen platform.
- The packaged application successfully decodes both the synthetic BCJ2 fixture and the real official x64 ASI member (3,615,648 bytes), using bundled libarchive. Source extraction also validates the real x86 member (5,413,776 bytes).
- Ruff lint/format, all 58 tests and Python compilation pass.
- Existing live game/prefix, mods and Reloaded installation were not modified. Existing configuration belongs to another integration, which setup detects and refuses to replace.

## Still required before claiming the definition of done

Use a test Steam account/library with a legitimately installed FFT and initialized Proton prefix that does not contain another manager's configuration. Do not reset an existing user prefix as a shortcut.

1. Start the source app/AppImage under X11 and Wayland; discover FFT on internal storage and an external library.
2. Test system and Flatpak Protontricks, including inaccessible-cache/library failures and correctly scoped filesystem permissions.
3. Run Setup; verify official dependency installation, actual Windows .NET 9 x64/x86 and VC runtime availability. Check upstream message boxes/errors, not only exit status.
4. Open the real Windows Reloaded GUI; register FFT Enhanced and Classic, close and reopen it. Confirm settings and enabled mods persist.
5. Deploy ASI, paste generated Steam launch options, refresh and inspect. Confirm existing options remain intact.
6. Install Nenkai's loader and compatible mods in Reloaded-II; verify both game modes through a normal Steam launch with the native manager closed.
7. Test repair/update with real mods/profiles, interrupted networking, corrupted downloads, unwritable destinations, active processes and game updates. Confirm backups and content-aware rollback; upstream registry/runtime changes are outside rollback scope.
8. Remove integration and verify normal game launch; ensure modified third-party files are preserved and reported.
9. Build on Ubuntu 22.04 CI; run AppImage on Bazzite, SteamOS (desktop and game modes), Fedora, Ubuntu, Debian, Mint, Arch, EndeavourOS and openSUSE. Check FUSE-free execution, Qt plugin loading, certificates/TLS and subprocess environment isolation.

A successful unit test or file hash does not verify that Windows mods execute. The app never reports full setup success based solely on these checks.

## Guided interface update

Game selection now runs a read-only setup inspection in a worker and shows one next action. Missing prefixes, fresh installs, registration, loader deployment, Steam options and existing foreign integrations have distinct guidance. Registration is not marked complete merely because the launcher created its own configuration. Maintenance tools and technical details are collapsed, Steam support packages are hidden from the picker, and an explicit high-contrast palette avoids unreadable inherited desktop colors. Added tests cover next-action states, existing setup protection, tool filtering and collapsed GUI defaults. The FFT existing-integration view was visually checked with an offscreen screenshot; live desktop/controller interaction remains unverified.

## Layout, manual picker and desktop shortcuts

The user reports successfully loading the utility loader and a test mod through Steam after a clean setup. An earlier screenshot reported the missing Reloaded.Memory.SigScan.ReloadedII dependency; the later successful run does not establish the cause of the earlier launch failures. No live game, mod, prefix or Steam settings were changed while implementing these interface refinements.

The refined layout was checked in an offscreen screenshot against the current FFT setup. Four equal-width action buttons sit below the main action; paths and Activity are always visible; progress occupies a small top-right panel. Hover/pressed/focus styles and enabled-button pointer cursors cover dialogs as well as the main window.

Additional automated tests cover .exe/manifest resolution to the same Steam game, rejection of executables without Steam metadata, hidden-file picker filters, status colors, desktop argument escaping, game-specific launcher commands, shortcut backups and permanent AppImage targets. The generated .desktop format also passed desktop-file-validate, and a real gio launch of a harmless argument-capture program preserved spaces, literal percent signs, dollar signs, backticks, quotes, backslashes and semicolons. This validation did not launch a game or write a shortcut onto the user's desktop.

The new shortcut buttons still need user testing with the real Windows GUI and the desktop environment's trust prompt. Window layout and pointer feedback have not been tested on every supported desktop or Steam Deck screen size. Launch links now report whether the desktop accepted the Steam URI; that acceptance is not proof that the game started or mods loaded.

## Application-menu and updater refinement

The UI now has a top toolbar, alphabetically sorted icons and persistent favorites, a green Ready state after configuration checks, in-app log and Setup details tabs, simpler Settings and an About dialog identifying WarpedEdge/version 0.1.0. The local FFT icon was successfully extracted/displayed without modifying its executable. File dialogs retain hidden entries, support typed Look in paths, and use labelled navigation buttons. Offscreen snapshots were inspected against the live installed FFT configuration; no game/prefix/mod changes were made.

Application-menu shortcuts now use stable per-game names and a stable manager name under XDG_DATA_HOME/applications. Tests cover repeated installation, safe removal, name sanitization and preservation of unrelated/externally modified entries. Repair refreshes tracked shortcuts and reports conflicts; it does not remove working entries. Readable log-tail tests cover bounded reads.

Updater tests cover version ordering, ignoring prereleases, a missing public release, pinned repository/asset validation, missing digests, successful atomic replacement with a previous-image backup, size/hash corruption, invalid AppImage formats, concurrent external file edits and preservation of an already-open old inode. The current real built AppImage passes the header/architecture check. No downloaded future-version executable was run by tests. Anonymous access to the repository/latest-release API returns HTTP 404, so a live published-release update and automatic restart into v0.2 remain unverified. The app handles that condition without a startup error dialog. CI now prevents tag/package/manager version mismatches.


## Icon, log and wording refinement

Read-only checks now resolve Deadlock’s actual steam_icon_1422450 application-menu art and AION 2’s nested executable icon. The official Reloaded-II executable’s R icon was extracted to persistent user data and successfully decoded by Qt. No game binaries or shortcut entries were modified during these checks; existing entries receive their new icon when recreated/refreshed through the manager. The main app’s branding remains unchanged pending a chosen Linux design.

Navigation uses high-contrast, double-resolution Qt-drawn glyphs with tooltips. The main layout and picker were checked in offscreen snapshots. Steam/Game ordering, the game’s Reloaded-II version, toolbar version label, About text, launch guidance and Reset game setup label were updated. Clear logs operates only after confirmation and only on log files. Tests verify that mods and configuration survive clearing. Log highlighting tests verify red error and yellow warning formatting without interpreting log text as HTML.

Setup now turns green automatically when configuration checks pass. Manual playtest confirmation was removed at the user's request; this does not assert that every mod executed or that silent failures can be diagnosed automatically.

Additional icon tests cover x64 executables, Steam's nested hash-named artwork folders and the bottom-right game badge on Reloaded-II shortcut icons. Live read-only lookup resolves FFXII and Lepton artwork. Log-panel tests cover separate sources, marking displayed content read and highlighting new content. The toolbar version is a non-clickable bordered label and About displays 0.1.

All 73 automated tests pass. Game/mod execution and cross-distribution desktop behavior still require real-system testing.

Library icons now use the same largest artwork frame as shortcut badges. A multi-frame ICO regression test verifies that small alternate artwork cannot replace the selected image.

Log maintenance tests cover timestamps, launch boundaries, exit codes, bounded Protontricks rotation, keeping three newest game logs, protecting detected open files and preserving configuration/archives. Live FFT cleanup removed 13 older text logs and retained the latest three.

The log viewer labels historical untimestamped Protontricks output and opens the selected source directory. Tests cover each folder target and removal of redundant menu entries. Reloaded-II update prompts are documented in its official FAQ; Repair remains available in the manager.

Shortcut controls now toggle Add/Remove using tracked file existence. A GUI test covers installation, selected-game removal, independent manager state and externally deleted shortcuts. Existing ownership/digest protections remain in force.

Tabbed settings and five built-in themes were inspected in dark/light offscreen screenshots. Tests cover live preview, Cancel rollback, saved-theme restoration, unknown-theme fallback, preservation of unrelated settings and contrast of primary text/status colors across all palettes. All themes share token-based widget styling. Desktop-specific rendering and Steam Deck sizing still need real-device checks.

Reinstall/disconnect labels now explain their actual scopes through tooltips. Full-reset tests verify backing up mods/configuration, restoring overwritten original game DLLs, preserving saves/prefix/manager shortcut, successful restoration, refusing external configs and changed loaders, avoiding overwrite of a new setup, and rolling back a simulated mid-reset move failure. No live game was reset. Shutdown now stops log polling and waits for outstanding workers before Qt teardown; the packaged smoke test must finish without deleted-signal errors.
