from reloaded_linux_manager import views


def test_log_tail_is_bounded_and_shown_as_text(tmp_path):
    path = tmp_path / "manager.log"
    path.write_text("prefix" + "a" * 200000 + "\nlast error")
    text = views.tail(path)
    assert "[Showing the end" in text and text.endswith("last error")
    assert "prefix" not in text and len(text) < 140000


def test_clear_logs_preserves_mods_and_configuration(tmp_path, monkeypatch):
    from reloaded_linux_manager.steam import Game

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    game = Game("1", "Game", tmp_path, tmp_path, tmp_path, tmp_path / "pfx", "")
    config = game.prefix / "drive_c/users/steamuser/AppData/Roaming/Reloaded-Mod-Loader-II/ReloadedII.json"
    config.parent.mkdir(parents=True)
    config.write_text("{}")
    log = config.parent / "Logs/recent.txt"
    log.parent.mkdir()
    log.write_text("error")
    mod = tmp_path / "mod.dll"
    mod.write_bytes(b"mod")
    views.clear_logs(game)
    assert not log.read_bytes()
    assert config.read_text() == "{}"
    assert mod.read_bytes() == b"mod"


def test_retention_keeps_three_and_protects_active_logs(tmp_path, monkeypatch):
    import os
    import time

    from reloaded_linux_manager.steam import Game

    game = Game("1", "Game", tmp_path, tmp_path, tmp_path, tmp_path / "pfx", "")
    config = tmp_path / "ReloadedII.json"
    config.write_text("{}")
    monkeypatch.setattr(views, "config_files", lambda _: [config])
    root = tmp_path / "Logs"
    root.mkdir()
    logs = []
    for index in range(6):
        path = root / f"session-{index}.txt"
        path.write_text("log")
        os.utime(path, (time.time() - 600 + index, time.time() - 600 + index))
        logs.append(path)
    unrelated = root / "OldLogs.zip"
    unrelated.write_bytes(b"archive")
    with logs[0].open():
        views.prune_game_logs(game)
        assert logs[0].exists()
        assert not logs[1].exists() and not logs[2].exists()
    views.prune_game_logs(game)
    assert not logs[0].exists()
    assert all(p.exists() for p in logs[3:])
    assert config.read_text() == "{}" and unrelated.read_bytes() == b"archive"


def test_retention_defers_when_open_files_cannot_be_checked(tmp_path, monkeypatch):
    monkeypatch.setattr(views, "open_file_ids", lambda: None)
    monkeypatch.setattr(views, "config_files", lambda _: [tmp_path / "config.json"])
    root = tmp_path / "Logs"
    root.mkdir()
    for i in range(5):
        (root / f"{i}.log").write_text("keep")
    assert views.prune_game_logs(object()) == []
    assert len(list(root.iterdir())) == 5
