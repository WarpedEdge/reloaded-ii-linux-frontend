from dataclasses import replace

import pytest

from reloaded_linux_manager.proton import command
from reloaded_linux_manager.steam import Game


def test_launch_argv_is_not_shell(tmp_path):
    game = Game(
        "1004640",
        "FFT",
        tmp_path,
        tmp_path,
        tmp_path,
        tmp_path / "steamapps/compatdata/1004640/pfx",
        "GE-Proton",
    )
    exe = tmp_path / "a;touch unsafe.exe"
    assert command(game, exe, ["protontricks-launch"]) == [
        "protontricks-launch",
        "--appid",
        "1004640",
        str(exe),
    ]
    with pytest.raises(ValueError):
        command(replace(game, prefix=tmp_path / "custom"), exe, ["launcher"])
    with pytest.raises(ValueError):
        command(replace(game, prefix=None), exe, ["launcher"])
