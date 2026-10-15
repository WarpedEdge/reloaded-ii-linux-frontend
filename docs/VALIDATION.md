# Validation record

## Verified in this development environment

Host: Bazzite 44.20261002.0, x86_64, glibc 2.43. This is a local build, not the older Ubuntu 22.04 CI build. Its portability to older glibc systems is not established.

- Python 3.14.7 source execution with PySide6 6.12.0, vdf 3.4, pefile 2024.8.26 and libarchive-c 5.3.
- 37 automated tests: external/native/Flatpak library discovery, duplicate Steam symlinks, prefix missing/ambiguity, manifest traversal, launch argv safety, ZIP traversal/symlink rejection, extraction, corrupt cache replacement/checksum rejection, option preservation/idempotence, configuration rollback and conflict preservation, installation rollback on subprocess failure, preserving user mods, preventing takeover of another installation, retrying failed first installs, official ASI member selection/copy/rollback, a BCJ2 regression fixture, and loader conflicts.
- Native Qt window smoke-tested offscreen with asynchronous discovery.
- Real local Steam discovery finds FFT App ID 1004640, its external library, initialized prefix, and configured proton_experimental mapping.
- Actual local FFT Classic/Enhanced executables inspected read-only with pefile: both x64 and import version.dll.
- Official Release.zip 1.31.0 downloaded to a temporary test cache, SHA-256/size validated and safely extracted. Actual uppercase X64/X86 layout and ASILoader32.dll/ASILoader64.dll archive members verified. Runtimeconfig requires .NET 9.
- Official Setup-Linux.exe 1.31.0 downloaded and validated against GitHub's SHA-256 and size (8,097,792 bytes), without executing it.
- Built a 68 MiB local AppImage using PyInstaller and verified appimagetool. Its FUSE-free Qt smoke test passes on this Bazzite host with the offscreen platform.
- The packaged application successfully decodes both the synthetic BCJ2 fixture and the real official x64 ASI member (3,615,648 bytes), using bundled libarchive. Source extraction also validates the real x86 member (5,413,776 bytes).
- Ruff lint/format, all 37 tests and Python compilation pass.
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
