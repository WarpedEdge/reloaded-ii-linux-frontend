import vdf

from reloaded_linux_manager.steam import discover, roots


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(vdf.dumps(value))


def fixture(tmp_path):
    home = tmp_path / "home"
    steam = home / ".local/share/Steam"
    library = tmp_path / "external disk"
    (steam / "steamapps").mkdir(parents=True)
    (library / "steamapps").mkdir(parents=True)
    put(
        steam / "steamapps/libraryfolders.vdf",
        {"libraryfolders": {"0": {"path": str(steam)}, "1": {"path": str(library)}}},
    )
    put(
        library / "steamapps/appmanifest_123456.acf",
        {"AppState": {"appid": "123456", "name": "Example Game", "installdir": "Example Game"}},
    )
    put(
        steam / "config/config.vdf",
        {
            "InstallConfigStore": {
                "Software": {"Valve": {"Steam": {"CompatToolMapping": {"123456": {"name": "GE-Proton"}}}}}
            }
        },
    )
    return home, steam, library


def test_external_library_prefix_tool_and_launch_options(tmp_path):
    home, steam, library = fixture(tmp_path)
    prefix = library / "steamapps/compatdata/123456/pfx"
    (prefix / "drive_c").mkdir(parents=True)
    (prefix / "system.reg").touch()
    put(
        steam / "userdata/1/config/localconfig.vdf",
        {
            "UserLocalConfigStore": {
                "Software": {"Valve": {"Steam": {"apps": {"123456": {"LaunchOptions": "-foo"}}}}}
            }
        },
    )
    games, warnings = discover({}, home)
    assert not warnings
    assert len(games) == 1
    assert games[0].prefix == prefix
    assert games[0].tool == "GE-Proton"
    assert games[0].launch_options == ("-foo",)
    assert games[0].directory == library / "steamapps/common/Example Game"


def test_no_prefix_is_created(tmp_path):
    home, _, library = fixture(tmp_path)
    games, _ = discover({}, home)
    assert games[0].prefix is None
    assert not (library / "steamapps/compatdata").exists()


def test_flatpak_and_duplicate_symlink_roots(tmp_path):
    native = tmp_path / ".local/share/Steam"
    (native / "steamapps").mkdir(parents=True)
    (tmp_path / ".steam").mkdir()
    (tmp_path / ".steam/root").symlink_to(native)
    flatpak = tmp_path / ".var/app/com.valvesoftware.Steam/.local/share/Steam"
    (flatpak / "steamapps").mkdir(parents=True)
    assert set(roots(tmp_path)) == {native, flatpak}


def test_ambiguous_prefix_requires_selection(tmp_path):
    home, steam, library = fixture(tmp_path)
    for root in (steam, library):
        p = root / "steamapps/compatdata/123456/pfx"
        (p / "drive_c").mkdir(parents=True)
        (p / "system.reg").touch()
    games, warnings = discover({}, home)
    assert games[0].prefix is None
    assert "multiple prefixes" in warnings[0]


def test_manifest_traversal_rejected(tmp_path):
    home, steam, library = fixture(tmp_path)
    put(
        library / "steamapps/appmanifest_123456.acf",
        {"AppState": {"appid": "123456", "installdir": "../../../elsewhere"}},
    )
    games, warnings = discover({}, home)
    assert not games and warnings


def test_manual_executable_and_manifest_resolve_same_game(tmp_path, monkeypatch):
    from reloaded_linux_manager.steam import resolve_manual_game

    home, root, library = fixture(tmp_path)
    executable = library / "steamapps/common/Example Game/bin/game.exe"
    executable.parent.mkdir(parents=True)
    executable.touch()
    monkeypatch.setattr("pathlib.Path.home", lambda: home)
    settings = {"steam_roots": [str(root)]}
    exe_game = resolve_manual_game(executable, settings)
    manifest_game = resolve_manual_game(library / "steamapps/appmanifest_123456.acf", settings)
    assert exe_game == manifest_game
    assert exe_game.appid == "123456"
    assert exe_game.prefix is None


def test_manual_nonsteam_executable_never_gets_fake_prefix(tmp_path):
    import pytest

    from reloaded_linux_manager.steam import resolve_manual_game

    exe = tmp_path / "not-steam.exe"
    exe.touch()
    with pytest.raises(ValueError, match="outside a Steam library"):
        resolve_manual_game(exe, {})
    assert not (tmp_path / "drive_c").exists()
