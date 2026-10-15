# Research and implementation decisions

Investigated 2026-10-15. Reloaded-II source checkout: `458987f26bc8d78fdc0f86b73fc0d6fd4b673d01`; live latest release returned `1.31.0`. Upstream source was inspected in a separate temporary checkout, without copying or modifying its runtime.

## Primary sources

- [Official Linux guide](https://reloaded-project.github.io/Reloaded-II/LinuxSetupGuideNew/): run Steam game once, one Reloaded instance per game, use Setup-Linux.exe through Protontricks, register game through Reloaded UI.
- [Extra Linux guide](https://reloaded-project.github.io/Reloaded-II/LinuxSetupGuideNewExtra/): Flatpak filesystem access requirements.
- [Legacy guide / ASI workflow](https://reloaded-project.github.io/Reloaded-II/LinuxSetupGuide/#using-asi-loader): deploy official loader and set override matching the deployed proxy DLL. Old hardcoded runtime versions here should not be reused.
- [Official releases](https://github.com/Reloaded-Project/Reloaded-II/releases): portable Release.zip and Setup-Linux.exe are available. GitHub API currently supplies SHA-256 digests; installation requires these rather than treating CRC as authenticity.
- [Installer CLI](https://github.com/Reloaded-Project/Reloaded-II/blob/458987f26bc8d78fdc0f86b73fc0d6fd4b673d01/source/Reloaded.Mod.Installer.Cli/Cli.cs) and [installer implementation](https://github.com/Reloaded-Project/Reloaded-II/blob/458987f26bc8d78fdc0f86b73fc0d6fd4b673d01/source/Reloaded.Mod.Installer.Lib/MainWindowViewModel.cs): dependencies-only downloads/extracts a temporary latest release to inspect dependencies and delegates installation to its runtime installer. The temporary copy is not the managed installation.
- [Installer settings](https://github.com/Reloaded-Project/Reloaded-II/blob/458987f26bc8d78fdc0f86b73fc0d6fd4b673d01/source/Reloaded.Mod.Installer.Lib/Settings.cs): explicit `--installdir` marks location manually overwritten. Pass it with `--dependenciesOnly` to prevent the later Proton desktop-location override from redirecting the temporary dependency installation. CLI ordering matters: dependenciesOnly must precede nogui. This routing is source-reviewed; actual runtime execution is unverified.
- [ASI deployment source](https://github.com/Reloaded-Project/Reloaded-II/blob/458987f26bc8d78fdc0f86b73fc0d6fd4b673d01/source/Reloaded.Mod.Launcher.Lib/Utility/AsiLoaderDeployer.cs): first supported import in architecture-specific preference order; extract ASILoader32/64.dll from Loader/Asi/UltimateAsiLoader.7z; copy matching bootstrapper as .asi. Native manager handles file deployment only, using supplied upstream binaries. It is deliberately more conservative about existing loaders than upstream.
- [Configuration paths](https://github.com/Reloaded-Project/Reloaded-II/blob/458987f26bc8d78fdc0f86b73fc0d6fd4b673d01/source/Reloaded.Mod.Loader.IO/Paths.cs), [ApplicationConfig](https://github.com/Reloaded-Project/Reloaded-II/blob/458987f26bc8d78fdc0f86b73fc0d6fd4b673d01/source/Reloaded.Mod.Loader.IO/Config/ApplicationConfig.cs), and [bootstrapper config reader](https://github.com/Reloaded-Project/Reloaded-II/blob/458987f26bc8d78fdc0f86b73fc0d6fd4b673d01/source/Reloaded.Mod.Loader.Bootstrapper/LoaderConfig.cpp): bootstrapper needs the prefix's AppData/Roaming/Reloaded-Mod-Loader-II/ReloadedII.json. Opening the real launcher initializes paths. Registration files are read for validation, never guessed or written. Supporting automatic registration needs schema-version fixtures and upstream coordination; guided registration is the supported fallback.
- [Protontricks documentation](https://github.com/Matoking/protontricks#usage): `protontricks-launch --appid APPID PROGRAM [ARGS]`; Flatpak uses `flatpak run --command=protontricks-launch com.github.Matoking.protontricks`. Direct Proton invocation needs correct pressure-vessel/Steam runtime handling and is deferred rather than constructing an unreliable WINEPREFIX-only command.
- [Nenkai utility loader](https://github.com/Nenkai/fftivc.utility.modloader): supports fft_classic.exe and fft_enhanced.exe. Current project targets net9.0-windows. ModConfig declares Reloaded.Memory.SigScan.ReloadedII and reloaded.sharedlib.hooks dependencies. The manager leaves installation/enabling to Reloaded-II.
- [Community Steam Deck guide requested for context](https://steamcommunity.com/sharedfiles/filedetails/?id=3613527941): consulted alongside primary sources; no community executable downloads are used.

## Important boundaries

Setup-Linux's dependencies-only implementation fetches **latest Release.zip internally**, even when the manager installs a selected older tag. Older-version dependency matching is therefore not guaranteed. Zero installer exit status is not proof of success: upstream catches some exceptions and presents message boxes. Report runtime installation as attempted/exited, and keep verification pending. The official 1.31.0 runtimeconfig targets Microsoft.NETCore.App and Microsoft.WindowsDesktop.App 9.0.0; the manager does not assume legacy documentation's .NET 5 is sufficient.

The actual ZIP uses `Loader/X64` and `Loader/X86` (uppercase), while some C# path constructors use lowercase names that Windows resolves case-insensitively. The official ASI 7z archive uses BCJ2, unsupported by py7zr; extraction uses libarchive and reads only the selected regular member into a bounded buffer, without archive-controlled disk paths. AppImage builds bundle libarchive and its resolved dependencies. Native deployment uses the actual archive paths and resolves existing Windows configuration paths case-insensitively through prefix drive mappings.

Read-only local inspection found an existing FFT Reloaded configuration owned by another integration. It is intentionally preserved; running the installation or Windows launcher against it would not be a clean end-to-end test. Automatic migration is deferred.

Steam has no validated public launch-option write interface used here. Read launch options from all local user configs, display ambiguity and let the user paste/copy. Keep unrelated text intact, merge only simple literal WINEDLLOVERRIDES values, refuse shell expansions/ambiguous assignments. Never execute launch-option strings.

## Module boundaries

- `steam.py`: read-only KeyValues discovery and initialized-prefix detection; no shell parsing or prefix creation.
- `releases.py`: official release resolution, SHA-256/size verified cache, bounded ZIP extraction with traversal/link protection.
- `storage.py`: XDG settings and atomic writes, write-ahead backup journals, content-aware rollback.
- `proton.py`: system/Flatpak Protontricks selection and argv-only subprocess execution, existing game environment resolution.
- `integration.py`: extensible game profile map, PE imports, official ASI asset copying, existing registration validation and launch-option merging.
- `service.py`: installation/repair/update, state, diagnostics and integration removal.
- `gui.py`: native Qt controls, serialized workers, progress/error output and guided setup.

No service, background daemon, system modification, prefix deletion, source patch or third-party mod downloader is included.


Desktop launcher generation follows the [freedesktop Exec quoting rules](https://specifications.freedesktop.org/desktop-entry/latest/exec-variables.html) and [string-value escaping rules](https://specifications.freedesktop.org/desktop-entry/latest/value-types.html). Generated launchers invoke executables and quoted arguments directly, without a shell. Reloaded-II launchers use env with STEAM_DIR and the existing Protontricks --appid interface; native-manager launchers target the original AppImage file. Existing shortcut files are protected by the manager's backup journal.
