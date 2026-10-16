"""Source-specific log viewer with persistent unread markers and bounded background reads."""

import re
from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QTextCursor
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import views
from .storage import read_json, state_home, write_json


class LogPanel(QWidget):
    unread_changed = Signal(bool)
    clear_requested = Signal()

    def __init__(self, game_provider, worker_class, highlighter_class, parent=None):
        super().__init__(parent)
        self.game_provider = game_provider
        self.worker_class = worker_class
        self.jobs = set()
        self.catalog = {}
        self.scope = object()
        self.selected_source = "manager"
        self.seen_path = state_home() / "log-seen.json"
        self.seen = read_json(self.seen_path, {})
        self.polling = False
        self.last_read = None
        self.reading = None
        self.read_generation = 0
        self.stopped = False
        layout = QVBoxLayout(self)
        controls = QHBoxLayout()
        self.buttons = {}
        self.labels = {"manager": "Manager", "proton": "Protontricks", "game": "Reloaded-II"}
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for key, label in self.labels.items():
            button = QPushButton(label)
            button.setObjectName("logSource")
            button.setCheckable(True)
            button.clicked.connect(lambda _=False, source=key: self.select_source(source))
            self.group.addButton(button)
            self.buttons[key] = button
            controls.addWidget(button)
        self.buttons["manager"].setChecked(True)
        controls.addStretch()
        clear = QPushButton("Clear logs")
        clear.clicked.connect(self.clear_requested.emit)
        controls.addWidget(clear)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(lambda: self.refresh(force=True))
        controls.addWidget(refresh)
        layout.addLayout(controls)
        self.files = QComboBox()
        self.files.currentIndexChanged.connect(lambda: self.read_selected(force=True))
        self.files.hide()
        layout.addWidget(self.files)
        self.path_label = QLabel()
        self.path_label.setWordWrap(True)
        self.path_label.setTextFormat(Qt.PlainText)
        self.path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        path_row = QHBoxLayout()
        path_row.addWidget(self.path_label, 1)
        self.folder_button = QPushButton("Open folder")
        self.folder_button.setEnabled(False)
        self.folder_button.clicked.connect(self.open_folder)
        path_row.addWidget(self.folder_button)
        layout.addLayout(path_row)
        self.notice = QLabel()
        self.notice.setWordWrap(True)
        self.notice.hide()
        layout.addWidget(self.notice)
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.document().setMaximumBlockCount(10000)
        self.highlighter = highlighter_class(self.text.document())
        layout.addWidget(self.text)
        self.timer = QTimer(self)
        self.timer.setInterval(3000)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()

    def run(self, function, done):
        worker = self.worker_class(lambda _: function())
        self.jobs.add(worker)

        def deliver(result):
            if not self.stopped:
                done(result)

        def failed(message):
            self.polling = False
            if not self.stopped:
                self.text.setPlainText("Could not read logs: " + message)

        worker.signals.done.connect(deliver)
        worker.signals.failed.connect(failed)
        worker.signals.finished.connect(lambda: self.jobs.discard(worker))
        QThreadPool.globalInstance().start(worker)

    def refresh(self, force=False):
        if self.stopped:
            return
        game = self.game_provider()
        key = game.key if game else None
        if key != self.scope:
            self.scope = key
            self.catalog = {}
            self.last_read = None
            self.read_generation += 1
            self.text.clear()
            self.path_label.clear()
        if self.polling:
            return
        self.polling = True

        def done(catalog):
            self.polling = False
            if key != self.scope:
                self.refresh(force=force)
                return
            self.catalog = catalog
            self.update_choices()
            self.update_markers()
            if self.isVisible():
                self.read_selected(force=force)

        self.run(lambda: views.log_catalog(game), done)

    def update_choices(self):
        previous = self.files.currentData()
        self.files.blockSignals(True)
        self.files.clear()
        for entry in self.catalog.get(self.selected_source, []):
            self.files.addItem(entry["label"], entry["path"])
        index = self.files.findData(previous)
        self.files.setCurrentIndex(max(0, index))
        self.files.setVisible(self.selected_source == "game" and self.files.count() > 1)
        self.files.blockSignals(False)

    def update_markers(self):
        any_unread = False
        for key, button in self.buttons.items():
            unread = any(
                e["stamp"] and e["stamp"][1] > 0 and self.seen.get(e["path"]) != e["stamp"]
                for e in self.catalog.get(key, [])
            )
            any_unread = any_unread or unread
            button.setText(("● " if unread else "") + self.labels[key])
            button.setProperty("unread", bool(unread))
            button.setToolTip("New or unread log content" if unread else "Read this log source")
            button.style().unpolish(button)
            button.style().polish(button)
        self.unread_changed.emit(bool(any_unread))

    def select_source(self, source):
        self.read_generation += 1
        self.reading = None
        self.selected_source = source
        self.buttons[source].setChecked(True)
        self.update_choices()
        self.read_selected(force=True)
        self.refresh()

    def read_selected(self, force=False):
        path = self.files.currentData()
        entry = next((e for e in self.catalog.get(self.selected_source, []) if e["path"] == path), None)
        if not entry:
            self.read_generation += 1
            self.reading = None
            self.last_read = None
            self.path_label.clear()
            self.folder_button.setEnabled(False)
            self.notice.hide()
            self.text.setPlainText("No logs recorded for this source yet.")
            return
        self.path_label.setText(path)
        self.folder_button.setEnabled(True)
        signature = (self.scope, path, entry["stamp"])
        if not force and signature == self.last_read:
            self.mark_read(path, entry["stamp"])
            return
        if not force and signature == self.reading:
            return
        self.reading = signature
        self.read_generation += 1
        generation = self.read_generation
        stamp = entry["stamp"]

        def done(text):
            if generation != self.read_generation:
                return
            self.reading = None
            self.last_read = signature
            legacy = (
                bool(stamp and stamp[1])
                and self.selected_source == "proton"
                and any(
                    line
                    and not re.match(r"^\d{4}-\d{2}-\d{2} ", line)
                    and not line.startswith("[Showing the end")
                    for line in text.splitlines()
                )
            )
            self.notice.setText(
                "Earlier output has no recorded timestamps. New launches through Open Reloaded-II "
                "in this manager include timestamps; application-menu shortcuts bypass this log capture."
                if legacy
                else ""
            )
            self.notice.setVisible(legacy)
            self.text.setPlainText(text)
            self.text.moveCursor(QTextCursor.End)
            self.mark_read(path, stamp)

        self.run(lambda: views.tail(Path(path)) if stamp else "No log entries yet.", done)

    def open_folder(self):
        path = self.files.currentData()
        if not path:
            return
        folder = Path(path).parent
        if not folder.is_dir():
            QMessageBox.warning(self, "Log folder unavailable", "This log folder does not exist yet.")
        elif not QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder))):
            QMessageBox.warning(self, "Could not open folder", "The desktop could not open the log folder.")

    def mark_read(self, path, stamp):
        if stamp and self.isVisible() and self.seen.get(path) != stamp:
            self.seen[path] = stamp
            try:
                write_json(self.seen_path, self.seen)
            except OSError:
                pass
            self.update_markers()

    def stop(self):
        self.stopped = True
        self.timer.stop()
