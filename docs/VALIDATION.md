# Testing and limitations

## Automated checks

The tests use temporary Steam libraries, prefixes, settings and logs. They cover:

- Native and Flatpak Steam discovery, external libraries, missing or ambiguous prefixes, and manual executable selection.
- Generic setup instructions for different games, with no game-specific executable hints.
- Safe process arguments, preserved Steam launch parameters and repeated DLL-override generation.
- Download hashes and sizes, release-information caching, rate-limit messages and safe archive extraction.
- Mod/configuration preservation, loader conflicts, failed-install rollback, full reset and backup restoration.
- Shortcut names, argument escaping, icon lookup, Add/Remove controls and externally changed files.
- Log timestamps, rotation, retention, source selection and warning/error colors.
- Theme previews, saved choices, Cancel behavior and text contrast.
- Manager update validation and replacement using local test files.

A passing test does not prove a Windows game or mod runs correctly.

## Local checks

Development builds have been tested on Bazzite x86_64 with glibc 2.43. Source execution uses Python 3.14 and PySide6. These results do not establish compatibility with older systems.

Official Reloaded-II 1.31.0 downloads were checked against GitHub's SHA-256 hashes and sizes. Its portable archive, uppercase X64/X86 folder names and official ASI archive members were inspected. ASI decoding was checked with bundled libarchive, including a BCJ2 test archive.

The built AppImage has passed the offscreen native Qt smoke test and packaged ASI-decoding check. Offscreen rendering does not replace testing on real X11, Wayland or Steam Deck displays.

A user has reported working mod loading through Steam. They also reproduced a missing mod dependency when closing Reloaded-II after enabling a mod, before its dependency was downloaded. Launching once through Reloaded-II resolved that case. The app now includes that instruction; it does not download third-party mods or block launches based on a separate dependency checklist.

## Tests still needed

Use a game with documented Reloaded-II support and a separate test setup. Keep existing games and prefixes intact.

1. Discover games on internal and external drives under native and Flatpak Steam.
2. Test system and Flatpak Protontricks, including permission and missing-tool errors.
3. Install Reloaded-II and check the actual Windows prerequisites. Installer exit status alone does not prove they work.
4. Register the game's executable, enable compatible mods and let Reloaded-II finish dependency downloads. Reopen it and check that settings persist.
5. Deploy ASI, apply Steam launch options and launch from Steam with the native manager closed. Confirm mods work in game.
6. Test reinstall, reset and restore with real mods and profiles. Check interrupted downloads, unwritable destinations, game updates and changed loader files.
7. Test published manager updates and restart between two real release versions. Local update tests use fixtures.
8. Build on Ubuntu 22.04 CI and run on the target distributions listed in the README. Check X11, Wayland, Steam Deck sizing, FUSE-free launch, certificates and subprocess library paths.

The manager uses generic setup checks. Finding a game or showing Ready does not establish that the game supports Reloaded-II or that every enabled mod works.
