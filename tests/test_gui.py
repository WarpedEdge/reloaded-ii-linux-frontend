"""Offscreen smoke test: real Qt controls with discovery dispatched through a worker."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication

from reloaded_linux_manager.gui import Window


def test_native_window(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr("reloaded_linux_manager.steam.discover", lambda _: ([], []))
    app = QApplication.instance() or QApplication([])
    window = Window()
    from PySide6.QtCore import QThreadPool

    QThreadPool.globalInstance().waitForDone(5000)
    app.processEvents()
    assert window.windowTitle() == "Reloaded Linux Manager"
    assert "No Steam games" in window.output.toPlainText()
    window.close()


def test_game_selection_shows_one_guided_action(tmp_path, monkeypatch):
    from PySide6.QtCore import QThreadPool

    from reloaded_linux_manager.steam import Game

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    fft = Game("1004640", "FFT", tmp_path, tmp_path, tmp_path, None, "Proton")
    tool = Game("228980", "Steamworks Common Redistributables", tmp_path, tmp_path, tmp_path, None, "")
    monkeypatch.setattr("reloaded_linux_manager.steam.discover", lambda _: ([tool, fft], []))
    app = QApplication.instance() or QApplication([])
    window = Window()
    for _ in range(20):
        QThreadPool.globalInstance().waitForDone(5000)
        app.processEvents()
        if not window.workers:
            break
    assert window.library.count() == 1
    assert window.game.appid == "1004640"
    assert window.primary.text() == "Launch game in Steam"
    assert window.primary.isEnabled()
    assert not window.open_button.isEnabled()
    assert not window.technical.isHidden()
    assert not window.output.isHidden()
    assert window.deploy_button.minimumHeight() == 48
    assert window.options_button.minimumHeight() == 48
    assert window.output.maximumHeight() > 180
    window.close()


def test_hidden_folders_available_in_file_and_directory_pickers(tmp_path):
    from PySide6.QtCore import QDir
    from PySide6.QtWidgets import QFileDialog

    from reloaded_linux_manager.gui import file_dialog

    _app = QApplication.instance() or QApplication([])
    for directory in (False, True):
        dialog = file_dialog(
            None, "Game", tmp_path, "Steam game (*.exe *.EXE appmanifest_*.acf)", directory=directory
        )
        assert dialog.testOption(QFileDialog.DontUseNativeDialog)
        assert dialog.filter() & QDir.Hidden
        assert "*.exe" in dialog.nameFilters()[0]
        dialog.close()


def test_progress_uses_done_failed_and_pending_colors():
    from reloaded_linux_manager.gui import step_markup

    markup = step_markup({"stage": 3, "failed_step": 3})
    assert "#77d994" in markup and "✓" in markup
    assert "#ff8994" in markup and "✗" in markup
    assert "#83b8ff" in markup
