import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import QApplication

from reloaded_linux_manager.gui import LogHighlighter, Worker
from reloaded_linux_manager.log_panel import LogPanel


def drain(app, panel):
    for _ in range(30):
        QThreadPool.globalInstance().waitForDone(5000)
        app.processEvents()
        if not panel.jobs:
            break


def test_log_sources_unread_markers_and_new_content(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    folder = tmp_path / "reloaded-linux-manager"
    folder.mkdir()
    manager = folder / "manager.log"
    process = folder / "process.log"
    manager.write_text("manager entry")
    process.write_text("proton error")
    app = QApplication.instance() or QApplication([])
    panel = LogPanel(lambda: None, Worker, LogHighlighter)
    # Hidden panel: unread content should light both source buttons.
    panel.refresh()
    drain(app, panel)
    assert panel.buttons["manager"].property("unread")
    assert panel.buttons["proton"].property("unread")
    panel.show()
    panel.select_source("proton")
    drain(app, panel)
    assert panel.text.toPlainText() == "proton error"
    assert not panel.notice.isHidden()
    assert not panel.buttons["proton"].property("unread")
    assert panel.buttons["manager"].property("unread")
    panel.hide()
    process.write_text("new proton error")
    panel.refresh()
    drain(app, panel)
    assert panel.buttons["proton"].property("unread")
    assert "manager entry" not in panel.text.toPlainText()
    panel.show()
    panel.refresh()
    drain(app, panel)
    assert panel.text.toPlainText() == "new proton error"
    assert not panel.buttons["proton"].property("unread")
    panel.stop()
    panel.close()


def test_open_folder_follows_selected_log_source(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    panel = LogPanel(lambda: None, Worker, LogHighlighter)
    panel.timer.stop()
    monkeypatch.setattr(panel, "refresh", lambda *args, **kwargs: None)
    opened = []
    monkeypatch.setattr(
        "reloaded_linux_manager.log_panel.QDesktopServices.openUrl",
        lambda url: opened.append(url.toLocalFile()) or True,
    )
    for source in ("manager", "proton", "game"):
        folder = tmp_path / source
        folder.mkdir()
        path = folder / "example.log"
        path.write_text("2026-10-15 12:00:00+0000 info: example")
        panel.catalog[source] = [
            {"path": str(path), "label": path.name, "stamp": [1, path.stat().st_size, 1]}
        ]
        panel.select_source(source)
        drain(app, panel)
        panel.folder_button.click()
        assert opened[-1] == str(folder)
        assert panel.notice.isHidden()
    panel.stop()
    panel.close()
