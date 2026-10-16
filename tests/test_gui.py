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
    menu_labels = {action.text() for action in window.more_menu.actions()}
    assert not menu_labels.intersection(
        {"View logs", "Setup details", "Check setup", "Launch game", "Update Reloaded-II"}
    )
    assert "Reinstall Reloaded-II…" in menu_labels
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


def test_file_picker_has_editable_path_and_readable_navigation(tmp_path):
    from PySide6.QtWidgets import QComboBox, QToolButton

    from reloaded_linux_manager.gui import file_dialog

    _app = QApplication.instance() or QApplication([])
    dialog = file_dialog(None, "Game", tmp_path)
    location = dialog.findChild(QComboBox, "lookInCombo")
    assert location.isEditable()
    nested = tmp_path / ".local/test"
    nested.mkdir(parents=True)
    location.setEditText(str(nested))
    location.lineEdit().returnPressed.emit()
    assert dialog.directory().absolutePath() == str(nested)
    assert dialog.width() >= 1000
    button = dialog.findChild(QToolButton, "backButton")
    assert button.text() == "Back" and button.minimumHeight() >= 36
    dialog.close()


def test_favorites_sort_before_other_games_and_persist(tmp_path, monkeypatch):
    from PySide6.QtCore import QThreadPool

    from reloaded_linux_manager.steam import Game
    from reloaded_linux_manager.storage import load_settings

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    names = ["Zulu", "bravo", "Alpha"]
    games = [Game(str(i), name, tmp_path, tmp_path, tmp_path, None, "") for i, name in enumerate(names)]
    monkeypatch.setattr("reloaded_linux_manager.steam.discover", lambda _: (games, []))
    app = QApplication.instance() or QApplication([])
    window = Window()
    for _ in range(20):
        QThreadPool.globalInstance().waitForDone(5000)
        app.processEvents()
        if not window.workers:
            break
    assert [g.name for g in window.visible] == ["Alpha", "bravo", "Zulu"]
    window.toggle_favorite(games[0])
    assert [g.name for g in window.visible] == ["Zulu", "Alpha", "bravo"]
    assert games[0].key in load_settings()["favorites"]
    for _ in range(20):
        QThreadPool.globalInstance().waitForDone(5000)
        app.processEvents()
        if not window.workers:
            break
    window.close()


def test_log_severity_colors_keep_plain_text():
    from PySide6.QtWidgets import QPlainTextEdit

    from reloaded_linux_manager.gui import LogHighlighter

    _app = QApplication.instance() or QApplication([])
    text = QPlainTextEdit()
    highlighter = LogHighlighter(text.document())
    text.setPlainText("ERROR: something failed\nWARNING: review this\nOK: file present")
    highlighter.rehighlight()
    block = text.document().firstBlock()
    assert block.layout().formats()[0].format.foreground().color().name() == "#ff8994"
    block = block.next()
    assert block.layout().formats()[0].format.foreground().color().name() == "#f6d36d"
    assert text.toPlainText().startswith("ERROR:")


def test_shortcut_buttons_toggle_and_refresh_after_external_removal(tmp_path, monkeypatch):
    from PySide6.QtCore import QThreadPool

    from reloaded_linux_manager import shortcuts
    from reloaded_linux_manager.steam import Game

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    game = Game("1", "Game", tmp_path, tmp_path, tmp_path, None, "")
    monkeypatch.setattr("reloaded_linux_manager.steam.discover", lambda _: ([game], []))
    app = QApplication.instance() or QApplication([])
    window = Window()

    def drain():
        for _ in range(20):
            QThreadPool.globalInstance().waitForDone(5000)
            app.processEvents()
            if not window.workers:
                break

    drain()
    assert window.reloaded_shortcut.text() == "Add Reloaded-II to applications"
    assert window.manager_shortcut.text() == "Add manager to applications"
    contents = shortcuts.desktop_entry("Example", ["/usr/bin/true"])
    shortcuts.install_menu_shortcut(contents, game=game)
    shortcuts.install_menu_shortcut(contents)
    window.details()
    drain()
    assert window.reloaded_shortcut.text() == "Remove Reloaded-II from applications"
    assert window.reloaded_shortcut.isEnabled()  # Can remove even when the game isn't configured.
    assert window.manager_shortcut.text() == "Remove manager from applications"
    window.reloaded_shortcut.click()
    drain()
    assert not shortcuts.menu_shortcut_exists(game)
    assert shortcuts.menu_shortcut_exists()
    assert window.reloaded_shortcut.text() == "Add Reloaded-II to applications"
    (shortcuts.applications_home() / "Reloaded-Linux-Manager.desktop").unlink()
    window.details()
    drain()
    assert window.manager_shortcut.text() == "Add manager to applications"
    window.log_panel.stop()
    window.close()
