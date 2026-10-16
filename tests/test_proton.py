import sys
from dataclasses import replace
from types import SimpleNamespace

import pytest

from reloaded_linux_manager import proton
from reloaded_linux_manager.proton import command
from reloaded_linux_manager.steam import Game


def test_launch_argv_is_not_shell(tmp_path):
    game = Game(
        "123456",
        "Example Game",
        tmp_path,
        tmp_path,
        tmp_path,
        tmp_path / "steamapps/compatdata/123456/pfx",
        "GE-Proton",
    )
    exe = tmp_path / "a;touch unsafe.exe"
    assert command(game, exe, ["protontricks-launch"]) == [
        "protontricks-launch",
        "--appid",
        "123456",
        str(exe),
    ]
    with pytest.raises(ValueError):
        command(replace(game, prefix=tmp_path / "custom"), exe, ["launcher"])
    with pytest.raises(ValueError):
        command(replace(game, prefix=None), exe, ["launcher"])


def test_process_log_has_timestamps_boundaries_and_rotation(tmp_path, monkeypatch):
    script = "print('info: '+ 'x'*2200000);print('warning: example')"
    monkeypatch.setattr(proton, "command", lambda *args: [sys.executable, "-c", script])
    game = SimpleNamespace(name="Game", appid="1", steam=tmp_path)
    path = tmp_path / "process.log"
    proton.run(game, tmp_path / "Reloaded-II.exe", [], log_path=path)
    combined = path.with_suffix(".log.1").read_text() + path.read_text()
    assert "Launch started: Game (Steam 1)" in combined
    assert "Launch ended: exit code 0" in combined
    assert "warning: example" in combined
    assert combined[:4].isdigit() and combined[4] == "-"
    assert path.stat().st_size < 2 * 1024**2
    assert path.with_suffix(".log.1").stat().st_size < 2 * 1024**2
    monkeypatch.setattr(proton, "command", lambda *args: [sys.executable, "-c", "raise SystemExit(7)"])
    with pytest.raises(RuntimeError, match="code 7"):
        proton.run(game, tmp_path / "Reloaded-II.exe", [], log_path=path)
    assert "Launch ended: exit code 7" in path.read_text()
