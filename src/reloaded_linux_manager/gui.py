"""Native Qt interface. Filesystem/network/process operations run on worker threads."""

import argparse
import html
import logging
import os
import re
import subprocess
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import (
    QDir,
    QEvent,
    QObject,
    QPointF,
    QRunnable,
    QSize,
    Qt,
    QThreadPool,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QSyntaxHighlighter,
    QTextCharFormat,
)
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import (
    __version__,
    icons,
    proton,
    reset,
    service,
    shortcuts,
    steam,
    themes,
    updater,
    views,
)
from .integration import deploy, extract_asi, merge_options
from .log_panel import LogPanel
from .storage import load_settings, read_json, save_settings, state_home, write_json

STEP_LABELS = (
    "Find Proton environment",
    "Install Reloaded-II",
    "Add game in Reloaded-II",
    "Enable Steam loading",
    "Apply launch options",
    "Ready",
)


def step_markup(guide, failure=None):
    stage = guide.get("stage", -1)
    failure = guide.get("failed_step", failure)
    rows = []
    for index, label in enumerate(STEP_LABELS):
        if index == 4 and guide.get("options_status") == "copied":
            label = "Launch options copied"
        if index == 5 and guide.get("options_status") == "copied":
            label = "Ready after pasting into Steam"
        if index == failure:
            color, mark = themes.colors()["progress_error"], "✗"
        elif 0 <= index < stage:
            color, mark = themes.colors()["progress_success"], "✓"
        else:
            color, mark = themes.colors()["progress_pending"], "→" if index == stage else "•"
        rows.append(
            f'<span style="color:{color}; font-size:13px; font-weight:600;">'
            f'<span style="font-size:16px; font-weight:700;">{mark}</span> &nbsp;{html.escape(label)}</span>'
        )
    return "<br/>".join(rows)


def navigation_icon(name):
    """Theme-independent, high-contrast navigation glyphs at double resolution."""
    pixmap = QPixmap(48, 48)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor(themes.colors()["text"]), 2))
    if name in ("backButton", "forwardButton", "toParentButton"):
        points = {
            "backButton": [(14, 5), (7, 12), (14, 19)],
            "forwardButton": [(10, 5), (17, 12), (10, 19)],
            "toParentButton": [(5, 14), (12, 7), (19, 14)],
        }[name]
        path = QPainterPath(QPointF(*points[0]))
        for point in points[1:]:
            path.lineTo(QPointF(*point))
        painter.drawPath(path)
        if name == "toParentButton":
            painter.drawLine(12, 7, 12, 21)
        else:
            painter.drawLine(7, 12, 18, 12)
    elif name == "newFolderButton":
        path = QPainterPath(QPointF(3, 19))
        for point in [(3, 5), (10, 5), (12, 8), (21, 8), (21, 19), (3, 19)]:
            path.lineTo(QPointF(*point))
        painter.drawPath(path)
        painter.drawLine(12, 10, 12, 17)
        painter.drawLine(8, 14, 16, 14)
    elif name == "listModeButton":
        for y in (6, 12, 18):
            painter.drawLine(3, y, 5, y)
            painter.drawLine(9, y, 21, y)
    else:
        painter.drawRect(3, 4, 18, 16)
        painter.drawLine(3, 9, 21, 9)
        painter.drawLine(9, 4, 9, 20)
        painter.drawLine(3, 14, 21, 14)
    painter.end()
    return QIcon(pixmap)


class LogHighlighter(QSyntaxHighlighter):
    def highlightBlock(self, text):
        color = None
        if re.search(
            r"\b(error|errors|exception|fail|failed|failure|fatal)\b|:err:", text, re.I
        ) and not re.search(r"\b(no|0) errors?\b", text, re.I):
            color = themes.colors()["error"]
        elif re.search(r"\b(warning|warn|pending|unverified|not tested)\b", text, re.I):
            color = themes.colors()["warning"]
        elif text.startswith(("OK:", "VERIFIED")):
            color = themes.colors()["success"]
        if color:
            style = QTextCharFormat()
            style.setForeground(QColor(color))
            self.setFormat(0, len(text), style)


def file_dialog(parent, title, start, pattern="", *, directory=False, save=False):
    """Consistent Qt picker with hidden files visible, including .local and .steam."""
    dialog = QFileDialog(parent, title)
    dialog.setOption(QFileDialog.DontUseNativeDialog, True)
    dialog.setFilter(QDir.AllEntries | QDir.Hidden | QDir.System | QDir.NoDotAndDotDot)
    dialog.setFileMode(
        QFileDialog.Directory if directory else QFileDialog.AnyFile if save else QFileDialog.ExistingFile
    )
    if directory:
        dialog.setOption(QFileDialog.ShowDirsOnly, True)
    if save:
        dialog.setAcceptMode(QFileDialog.AcceptSave)
        dialog.setDefaultSuffix("desktop")
        start = Path(start)
        dialog.setDirectory(str(start.parent))
        dialog.selectFile(start.name)
    else:
        dialog.setDirectory(str(start))
    if pattern:
        dialog.setNameFilter(pattern)
    dialog.resize(1050, 680)
    font = dialog.font()
    font.setPointSize(max(11, font.pointSize()))
    dialog.setFont(font)
    navigation = {
        "backButton": "Back",
        "forwardButton": "Forward",
        "toParentButton": "Up",
        "newFolderButton": "New folder",
        "listModeButton": "List",
        "detailModeButton": "Details",
    }
    for button in dialog.findChildren(QToolButton):
        if button.objectName() in navigation:
            button.setIcon(navigation_icon(button.objectName()))
            button.setText(navigation[button.objectName()])
            button.setToolTip(navigation[button.objectName()])
            button.setToolButtonStyle(Qt.ToolButtonIconOnly)
            button.setIconSize(QSize(24, 24))
            button.setFixedSize(40, 40)
    splitter = dialog.findChild(QSplitter, "splitter")
    if splitter:
        splitter.setSizes([190, 800])
    dialog.setStyleSheet("QFileDialog QTreeView::item, QFileDialog QListView::item { min-height: 26px; }")
    location = dialog.findChild(QComboBox, "lookInCombo")
    if location:
        location.setEditable(True)
        location.setInsertPolicy(QComboBox.NoInsert)
        location.setEditText(dialog.directory().absolutePath())

        def navigate():
            value = Path(location.currentText()).expanduser()
            if value.is_dir():
                dialog.setDirectory(str(value))
            elif value.is_file():
                dialog.setDirectory(str(value.parent))
                dialog.selectFile(value.name)

        location.lineEdit().returnPressed.connect(navigate)
        dialog.directoryEntered.connect(location.setEditText)
    return dialog


def choose_path(parent, title, start, pattern="", **options):
    dialog = file_dialog(parent, title, start, pattern, **options)
    return dialog.selectedFiles()[0] if dialog.exec() else ""


class ButtonCursor(QObject):
    def eventFilter(self, watched, event):
        if isinstance(watched, QAbstractButton) and event.type() in (QEvent.Show, QEvent.EnabledChange):
            watched.setCursor(Qt.PointingHandCursor if watched.isEnabled() else Qt.ArrowCursor)
        return False


class Signals(QObject):
    progress = Signal(str)
    done = Signal(object)
    failed = Signal(str)
    finished = Signal()


class Worker(QRunnable):
    def __init__(self, function):
        super().__init__()
        self.function = function
        self.signals = Signals()

    def run(self):
        try:
            self.signals.done.emit(self.function(self.signals.progress.emit))
        except Exception as exc:
            logging.exception("Operation failed")
            self.signals.failed.emit(str(exc))
        finally:
            self.signals.finished.emit()


class SettingsDialog(QDialog):
    def __init__(self, settings, parent):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(820, 580)
        self.settings = settings.copy()
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, 1)
        appearance = QWidget()
        appearance_layout = QVBoxLayout(appearance)
        appearance_layout.addWidget(
            QLabel("Theme — select a preview to try it. Save keeps your choice; Cancel restores it.")
        )
        grid = QGridLayout()
        self.theme_group = QButtonGroup(self)
        self.theme_buttons = {}
        selected = settings.get("theme", "dark")
        if selected not in themes.THEMES:
            selected = "dark"
        self.original_theme = selected
        for index, (key, palette) in enumerate(themes.THEMES.items()):
            button = QToolButton()
            button.setText(palette["name"])
            button.setIcon(themes.preview_icon(key))
            button.setIconSize(QSize(110, 76))
            button.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            button.setCheckable(True)
            button.setChecked(key == selected)
            button.setFixedSize(164, 124)
            button.setToolTip(palette.get("description", palette["name"]))
            button.setProperty("themeKey", key)
            button.clicked.connect(lambda _=False, name=key: parent.apply_theme(name))
            self.theme_group.addButton(button)
            self.theme_buttons[key] = button
            grid.addWidget(button, index // 3, index % 3, Qt.AlignHCenter)
        cards = QWidget()
        cards.setLayout(grid)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(cards)
        appearance_layout.addWidget(scroll, 1)
        self.tabs.addTab(appearance, "Appearance")
        general = QWidget()
        general_layout = QVBoxLayout(general)
        self.tabs.addTab(general, "General")
        self.rejected.connect(lambda: parent.apply_theme(self.original_theme))
        self.auto_updates = QCheckBox("Check for updates when the app opens")
        self.auto_updates.setChecked(settings.get("check_updates", True))
        general_layout.addWidget(self.auto_updates)
        explanation = QLabel("An available update is offered before anything is downloaded or replaced.")
        explanation.setWordWrap(True)
        general_layout.addWidget(explanation)
        general_layout.addWidget(QLabel("Downloaded installer cache — keeps setup downloads for reuse:"))
        row = QHBoxLayout()
        self.cache = QLineEdit(settings["cache"])
        row.addWidget(self.cache)
        browse = QPushButton("Browse…")

        def browse_cache():
            path = choose_path(self, "Choose download cache folder", self.cache.text(), directory=True)
            if path:
                self.cache.setText(path)

        browse.clicked.connect(browse_cache)
        row.addWidget(browse)
        general_layout.addLayout(row)
        form = QFormLayout()
        self.level = QComboBox()
        for label, value in [
            ("Normal", "INFO"),
            ("Detailed troubleshooting", "DEBUG"),
            ("Warnings and errors", "WARNING"),
        ]:
            self.level.addItem(label, value)
        self.level.setCurrentIndex(max(0, self.level.findData(settings["log_level"])))
        form.addRow("Log detail", self.level)
        general_layout.addLayout(form)
        general_layout.addStretch()
        advanced = QWidget()
        advanced_form = QFormLayout(advanced)
        label = QLabel(
            "Only use these if a game isn't found automatically. A Steam installation folder "
            "contains config and steamapps; a game library folder contains steamapps and your games."
        )
        label.setWordWrap(True)
        advanced_form.addRow(label)
        self.fields = {}
        for key, label in [
            ("steam_roots", "Steam installation folders"),
            ("libraries", "Extra game library folders"),
        ]:
            field = QPlainTextEdit("\n".join(settings[key]))
            field.setMaximumHeight(80)
            self.fields[key] = field
            row = QHBoxLayout()
            row.addWidget(field)
            add = QPushButton("Add folder…")

            def append_folder(_=False, target=field):
                folder = choose_path(self, "Choose folder", Path.home(), directory=True)
                if folder:
                    target.appendPlainText(folder)

            add.clicked.connect(append_folder)
            row.addWidget(add)
            advanced_form.addRow(label, row)
        self.tabs.addTab(advanced, "Advanced")
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def value(self):
        self.settings["theme"] = self.theme_group.checkedButton().property("themeKey")
        self.settings["check_updates"] = self.auto_updates.isChecked()
        self.settings["cache"] = self.cache.text().strip()
        self.settings["log_level"] = self.level.currentData()
        for key, field in self.fields.items():
            self.settings[key] = list(
                dict.fromkeys(line.strip() for line in field.toPlainText().splitlines() if line.strip())
            )
        return self.settings


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.games = []
        self.game_icons = {}
        self.checking_updates = False
        self._details_key = object()
        self.visible = []
        self.workers = set()
        self.busy = False
        self.guide = None
        self.inspection = 0
        self.failures = {}
        self.pending_game_key = None
        self.setWindowTitle("Reloaded Linux Manager")
        available = QApplication.primaryScreen().availableGeometry()
        self.resize(min(1240, available.width() - 20), min(840, available.height() - 40))
        themes.apply(self.settings.get("theme", "dark"))
        root = QWidget()
        root.setObjectName("managerContent")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        topbar = QHBoxLayout()
        heading = QLabel("Reloaded Linux Manager")
        heading.setObjectName("appHeading")
        heading.setStyleSheet("font-size: 23px; font-weight: 600; padding: 8px")
        topbar.addWidget(heading)
        topbar.addStretch()
        version_badge = QLabel("Ver: " + __version__.removesuffix(".0"))
        version_badge.setObjectName("versionBadge")
        version_badge.setToolTip("Manager version")
        topbar.addWidget(version_badge, alignment=Qt.AlignVCenter)
        self.actions = []
        for label, action in [
            ("Refresh", self.refresh),
            ("Add game", self.manual),
            ("Settings", self.settings_dialog),
            ("About", self.about),
        ]:
            button = QPushButton(label)
            button.clicked.connect(action)
            self.actions.append(button)
            topbar.addWidget(button)
        outer.addLayout(topbar)
        splitter = QSplitter()
        sidebar = QWidget()
        sidebar.setMinimumWidth(250)
        sidebar.setMaximumWidth(360)
        library_layout = QVBoxLayout(sidebar)
        library_layout.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search games…")
        self.search.textChanged.connect(self.filter_games)
        library_layout.addWidget(self.search)
        self.library = QListWidget()
        self.library.setMinimumWidth(240)
        self.library.setMaximumWidth(360)
        self.library.setWordWrap(True)
        self.library.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.library.setSpacing(6)
        self.library.currentRowChanged.connect(self.details)
        self.library.setIconSize(QSize(32, 32))
        self.library.setContextMenuPolicy(Qt.CustomContextMenu)
        self.library.customContextMenuRequested.connect(self.game_context_menu)
        library_layout.addWidget(self.library)
        library_hint = QLabel("Right-click a game to favorite it")
        library_hint.setObjectName("libraryHint")
        library_layout.addWidget(library_hint)
        splitter.addWidget(sidebar)
        right = QWidget()
        panel = QVBoxLayout(right)
        header = QHBoxLayout()
        summary = QVBoxLayout()
        self.title = QLabel("Select a Steam game")
        self.title.setWordWrap(True)
        self.title.setStyleSheet("font-size: 20px; font-weight: 600")
        self.title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        summary.addWidget(self.title)
        self.info = QLabel()
        self.info.setWordWrap(True)
        self.info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        summary.addWidget(self.info)
        self.technical = QLabel()
        self.technical.setWordWrap(True)
        self.technical.setTextFormat(Qt.PlainText)
        self.technical.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.technical.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.technical.setObjectName("technicalDetails")
        summary.addWidget(self.technical)
        summary.addStretch()
        header.addLayout(summary, 3)
        progress_box = QGroupBox("Setup progress")
        progress_box.setMaximumWidth(260)
        progress_layout = QVBoxLayout(progress_box)
        self.steps = QLabel(step_markup({}))
        self.steps.setTextFormat(Qt.RichText)
        self.steps.setStyleSheet("line-height: 1.6; font-size: 13px")
        progress_layout.addWidget(self.steps)
        header.addWidget(progress_box, 1, Qt.AlignTop)
        summary_panel = QWidget()
        summary_panel.setObjectName("gameSummary")
        summary_panel.setLayout(header)
        panel.addWidget(summary_panel)
        self.next_heading = QLabel("Choose a game to get started")
        self.next_heading.setWordWrap(True)
        self.next_heading.setObjectName("stageHeading")
        self.next_heading.setStyleSheet("font-size: 19px; font-weight: 600; margin-top: 20px")
        panel.addWidget(self.next_heading)
        self.next_text = QLabel("Select a game from your library on the left.")
        self.next_text.setObjectName("stageDescription")
        self.next_text.setWordWrap(True)
        self.next_text.setTextFormat(Qt.PlainText)
        panel.addWidget(self.next_text)
        self.primary = QPushButton("Select a game")
        self.primary.setMinimumHeight(48)
        self.primary.setObjectName("primaryAction")
        self.primary.clicked.connect(self.next_action)
        self.primary.setEnabled(False)
        self.actions.append(self.primary)
        panel.addWidget(self.primary)
        secondary = QHBoxLayout()
        self.open_button = QPushButton("Open Reloaded-II")
        self.open_button.clicked.connect(self.open_reloaded)
        self.actions.append(self.open_button)
        secondary.addWidget(self.open_button, 1)
        self.deploy_button = QPushButton("Deploy ASI loader")
        self.deploy_button.clicked.connect(self.deploy_asi)
        self.actions.append(self.deploy_button)
        secondary.addWidget(self.deploy_button, 1)
        self.options_button = QPushButton("Steam launch options")
        self.options_button.clicked.connect(self.options)
        self.actions.append(self.options_button)
        secondary.addWidget(self.options_button, 1)
        self.more = QToolButton()
        self.more.setText("More actions")
        self.more.setPopupMode(QToolButton.InstantPopup)
        self.more_menu = QMenu(self.more)
        self.more_menu.setToolTipsVisible(True)
        for label, action, tooltip in [
            (
                "Select Existing Prefix",
                self.select_prefix,
                "Choose an existing prefix that is not what was automatically detected.",
            ),
            (
                "Reinstall Reloaded-II",
                self.reinstall,
                "Reinstalls the latest Reloaded-II. Does not touch mods, profiles or game settings.",
            ),
            (
                "Reset ASI Deployment",
                self.remove,
                "Resets ASI deployment. Does not affect mods or Reloaded-II. Review the related Steam launch option afterward.",
            ),
        ]:
            item = self.more_menu.addAction(label, action)
            item.setToolTip(tooltip)
        self.reset_action = self.more_menu.addAction("Reset All", self.reset_all)
        self.reset_action.setToolTip(
            "Restarts Reloaded-II setup from the beginning. Mods/settings are backed up. Existing Windows runtimes are kept."
        )
        self.restore_action = self.more_menu.addAction("Restore last full reset…", self.restore_reset)
        self.restore_action.setToolTip(
            "Undo the last full reset if no new setup or changed loader files conflict with it."
        )
        self.more.setMenu(self.more_menu)
        self.actions.append(self.more)
        self.more.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        secondary.addWidget(self.more, 1)
        for button in (self.open_button, self.deploy_button, self.options_button, self.more):
            button.setMinimumHeight(48)
            button.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        panel.addLayout(secondary)
        shortcut_row = QHBoxLayout()
        self.reloaded_shortcut = QPushButton("Add Reloaded-II to applications")
        self.reloaded_shortcut.clicked.connect(self.toggle_reloaded_shortcut)
        self.actions.append(self.reloaded_shortcut)
        shortcut_row.addWidget(self.reloaded_shortcut, 1)
        self.manager_shortcut = QPushButton("Add manager to applications")
        self.manager_shortcut.clicked.connect(self.toggle_manager_shortcut)
        self.actions.append(self.manager_shortcut)
        shortcut_row.addWidget(self.manager_shortcut, 1)
        for button in (self.reloaded_shortcut, self.manager_shortcut):
            button.setMinimumHeight(40)
        panel.addLayout(shortcut_row)

        self.progress = QProgressBar()
        self.progress.hide()
        panel.addWidget(self.progress)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.activity_highlighter = LogHighlighter(self.output.document())
        self.output.setPlaceholderText("Actions and setup messages appear here.")
        self.output.setMinimumHeight(150)
        self.tabs = QTabWidget()
        self.tabs.addTab(self.output, "Activity")
        self.log_panel = LogPanel(lambda: self.game, Worker, LogHighlighter, self)
        self.log_panel.clear_requested.connect(self.clear_logs)
        self.logs_output = self.log_panel.text
        self.log_panel.unread_changed.connect(
            lambda unread: self.tabs.setTabText(1, "Logs ●" if unread else "Logs")
        )
        self.tabs.addTab(self.log_panel, "Logs")
        setup_panel = QWidget()
        setup_layout = QVBoxLayout(setup_panel)
        self.setup_output = QPlainTextEdit()
        self.setup_output.setReadOnly(True)
        self.details_highlighter = LogHighlighter(self.setup_output.document())
        setup_layout.addWidget(self.setup_output)
        self.tabs.addTab(setup_panel, "Setup details")
        self.tabs.currentChanged.connect(self.display_tab)
        panel.addWidget(self.tabs, 1)
        splitter.addWidget(right)
        splitter.setStretchFactor(1, 2)
        outer.addWidget(splitter, 1)
        self.statusBar().showMessage("Ready")
        self.refresh()

    @property
    def game(self):
        index = self.library.currentRow()
        return self.visible[index] if 0 <= index < len(self.visible) else None

    def work(self, function, done=None, failure_step=None):
        if self.busy:
            return
        self.busy = True
        for action in self.actions:
            action.setEnabled(False)
        self.library.setEnabled(False)
        self.search.setEnabled(False)
        self.progress.setRange(0, 0)
        self.progress.show()
        worker = Worker(function)
        self.workers.add(worker)
        worker.signals.progress.connect(self.message)
        game_key = self.game.key if self.game else None

        def failed(text):
            if failure_step is not None and game_key:
                self.failures[game_key] = failure_step
            self.error(text)

        def completed(value):
            if failure_step is not None and game_key:
                self.failures.pop(game_key, None)
            (done or (lambda result: self.message(str(result))))(value)

        worker.signals.failed.connect(failed)
        worker.signals.done.connect(completed)
        worker.signals.finished.connect(lambda: self.finished(worker))
        QThreadPool.globalInstance().start(worker)

    def finished(self, worker):
        self.workers.discard(worker)
        self.busy = False
        for action in self.actions:
            action.setEnabled(True)
        self.library.setEnabled(True)
        self.search.setEnabled(True)
        self.progress.hide()
        self.statusBar().showMessage("Ready")
        self.details()
        QTimer.singleShot(0, lambda: self.display_tab(self.tabs.currentIndex()))

    def message(self, text):
        self.output.appendPlainText(text)
        self.statusBar().showMessage(text)
        logging.info(text)

    def error(self, text):
        self.message("FAILED: " + text)
        QMessageBox.warning(self, "Action could not complete", text)

    def refresh(self):
        def done(result):
            self.games, warnings, self.game_icons = result
            self.filter_games()
            for warning in warnings:
                self.message(warning)
            if not self.games:
                self.message(
                    "No Steam games found. Add a Steam root in Settings or select a game's appmanifest manually."
                )

        def load(_):
            games, warnings = steam.discover(self.settings)
            return (
                games,
                warnings,
                {g.key: icons.library_icon(g) for g in games if not steam.is_support_tool(g)},
            )

        self.work(load, done)

    def filter_games(self):
        text = self.search.text().lower()
        selected = self.pending_game_key or (self.game.key if self.game else None)
        self.pending_game_key = None
        self.visible = [
            g for g in self.games if text in (g.name + " " + g.appid).lower() and not steam.is_support_tool(g)
        ]
        self.library.clear()
        favorites = set(self.settings.get("favorites", []))
        self.visible.sort(key=lambda g: (g.key not in favorites, g.name.casefold(), g.key))
        for game in self.visible:
            icon = (
                (
                    QIcon.fromTheme(self.game_icons[game.key][6:])
                    if self.game_icons[game.key].startswith("theme:")
                    else QIcon(self.game_icons[game.key])
                )
                if self.game_icons.get(game.key)
                else QIcon.fromTheme("applications-games")
            )
            item = QListWidgetItem(icon, ("★  " if game.key in favorites else "") + game.name)
            item.setToolTip(game.name)
            self.library.addItem(item)
        if self.visible:
            self.library.setCurrentRow(next((i for i, g in enumerate(self.visible) if g.key == selected), 0))

    def details(self, *_):
        self.inspection += 1
        generation = self.inspection
        game = self.game
        self.guide = None
        self.primary.setEnabled(False)
        self.open_button.setEnabled(False)
        self.deploy_button.setEnabled(False)
        self.options_button.setEnabled(False)
        self.reloaded_shortcut.setEnabled(False)
        game_shortcut = bool(game and shortcuts.menu_shortcut_exists(game))
        self.reloaded_shortcut.setText(
            "Remove Reloaded-II from applications" if game_shortcut else "Add Reloaded-II to applications"
        )
        self.manager_shortcut.setText(
            "Remove manager from applications"
            if shortcuts.menu_shortcut_exists()
            else "Add manager to applications"
        )
        self.manager_shortcut.setEnabled(not self.busy)
        self.log_panel.refresh()
        self.more.setEnabled(bool(game) and not self.busy)
        self.reset_action.setEnabled(bool(game and game.prefix) and not self.busy)
        self.restore_action.setEnabled(bool(game and reset.pointer(game).is_file()) and not self.busy)
        if not game:
            self.title.setText("Select a Steam game")
            self.info.clear()
            self.next_heading.setText("Choose a game to get started")
            self.next_text.setText("Search for a game, then select it from the library on the left.")
            self.primary.setText("Select a game")
            self.steps.setText(step_markup({}))
            self.technical.clear()
            return
        QTimer.singleShot(0, lambda: self.display_tab(self.tabs.currentIndex()))
        self.title.setText(game.name)
        self.title.setTextFormat(Qt.PlainText)
        self.info.setText(f"Steam game {game.appid} · {game.tool}")
        self.technical.setText(
            f"Steam: {game.steam}\nGame: {game.directory}\n"
            f"Prefix: {game.prefix or 'Not initialized or ambiguous'}\n"
            "Reloaded-II: Checking…"
        )
        self.next_heading.setText("Checking your setup…")
        self.next_text.setText("Finding the next step for this game.")
        self.primary.setText("Checking…")
        worker = Worker(lambda _: service.setup_guide(game))
        self.workers.add(worker)

        def done(guide):
            if generation != self.inspection:
                return
            self.guide = guide
            state = read_json(service.metadata(game), {})
            self.technical.setText(
                f"Steam: {game.steam}\nGame: {game.directory}\n"
                f"Prefix: {game.prefix or 'Not initialized or ambiguous'}\n"
                f"Reloaded-II: {state.get('version', 'Not installed by this manager')}"
            )
            self.next_heading.setText(guide["heading"])
            self.next_text.setText(guide["text"])
            self.primary.setText(guide["button"])
            self.primary.setEnabled(not self.busy)
            self.open_button.setEnabled(not self.busy and guide["stage"] >= 2)
            self.deploy_button.setEnabled(not self.busy and guide["stage"] >= 3)
            self.options_button.setEnabled(not self.busy and guide["stage"] >= 4)
            self.reloaded_shortcut.setEnabled(not self.busy and (game_shortcut or guide["stage"] >= 2))
            failure = self.failures.get(game.key)
            if failure is not None and guide["stage"] > failure:
                self.failures.pop(game.key, None)
                failure = None
            self.steps.setText(step_markup(guide, failure))

        def failed(text):
            if generation != self.inspection:
                return
            self.next_heading.setText("Setup needs a closer look")
            self.next_text.setText(text)
            self.guide = {"action": "check"}
            self.steps.setText(step_markup({"failed_step": 0}))
            self.primary.setText("View setup report")
            self.primary.setEnabled(not self.busy)

        worker.signals.done.connect(done)
        worker.signals.failed.connect(failed)
        worker.signals.finished.connect(lambda: self.workers.discard(worker))
        QThreadPool.globalInstance().start(worker)

    def next_action(self):
        if self.guide and not self.busy:
            getattr(self, self.guide["action"])()

    def reinstall(self):
        self.setup(latest=True)

    def setup(self, latest=False):
        game = self.game
        if not game:
            return
        text = (
            "Download the selected official release and install it inside this game's existing Proton prefix. "
            "Changed manager-owned files and Reloaded configuration are backed up. The official installer will "
            "install Windows runtimes; those runtime changes cannot be rolled back by this manager.\n\n"
            "Close the game and Reloaded-II before continuing. Continue?"
        )
        if QMessageBox.question(self, "Install / repair / update", text) == QMessageBox.Yes:
            self.work(
                lambda report: service.install(
                    game, self.settings | ({"release": "latest"} if latest else {}), report
                ),
                failure_step=1,
            )

    def open_reloaded(self):
        game = self.game
        if not game:
            return
        state = read_json(service.metadata(game), {})
        if state.get("installed") and not state.get("dependency_reminder_shown"):
            QMessageBox.information(
                self,
                "Let Reloaded-II finish its downloads",
                "After adding mods, select your game in Reloaded-II and leave it open for a moment. "
                "It downloads required dependencies automatically. Wait for downloads and popups to finish before closing Reloaded-II and launching the game.",
            )
            state["dependency_reminder_shown"] = True
            write_json(service.metadata(game), state)

        def launch(report):
            executable = game.install / "Reloaded-II.exe"
            if not executable.is_file():
                raise ValueError("Use Setup Reloaded-II first.")
            report(
                "Reloaded-II is running. Select your game after adding mods, then leave Reloaded-II open for a moment so it can download all required dependencies. Wait for downloads and popups to finish before closing it."
            )
            proton.run(
                game,
                executable,
                proton.detect_launcher(self.settings["protontricks_launch"]),
                log_path=state_home() / "process.log",
            )
            return "Reloaded-II closed. You can now deploy or check the ASI integration."

        self.work(launch, failure_step=2)

    def launch_game(self):
        if self.game:
            if QDesktopServices.openUrl(QUrl("steam://rungameid/" + self.game.appid)):
                self.message(
                    "Launch request sent to Steam. If the game is still running or closing, wait and try again from Steam."
                )
            else:
                self.error("Could not open the Steam launch link. Check Steam is installed and running.")

    def deploy_asi(self):
        game = self.game
        if not game:
            return
        filename = choose_path(
            self, "Select registered game executable", game.directory, "Windows executable (*.exe *.EXE)"
        )
        if not filename:
            return
        if (
            QMessageBox.question(
                self,
                "Deploy official ASI loader",
                "Close the game and Reloaded-II first. Copy the official loader and bootstrapper beside this executable? Existing DLL/ASI conflicts will stop deployment.",
            )
            != QMessageBox.Yes
        ):
            return

        def action(report):
            if not game.prefix:
                raise ValueError("No initialized Proton prefix.")
            report("Checking executable imports, registration, loader configuration and conflicts…")
            state = read_json(service.metadata(game), {})
            if state.get("asi"):
                raise ValueError(
                    "ASI deployment already exists. Use More actions → Reset ASI Deployment before redeploying."
                )
            state["asi"] = deploy(game, Path(filename), service.backups(game))
            write_json(service.metadata(game), state)
            return "ASI files deployed and hashed. Copy Steam launch options next; finish the remaining configuration checks next."

        self.work(action, failure_step=3)

    def check(self):
        if self.game:
            game = self.game
            self.work(lambda _: "\n".join(service.diagnostics(game)))

    def options(self):
        game = self.game
        if not game:
            return
        state = read_json(service.metadata(game), {})
        dll = state.get("asi", {}).get("dll")
        if not dll:
            self.error("Deploy the ASI loader first so its DLL name can be verified.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Steam launch options")
        dialog.resize(760, 350)
        layout = QVBoxLayout(dialog)
        instructions = QLabel(
            "1. Copy the generated options below.\n"
            "2. In Steam, right-click the game → Properties → General → Launch Options, then paste.\n"
            "3. Use Check Steam settings below to detect the saved value. Steam may take a moment to write it.\n"
            "These options enable the deployed ASI DLL. The app never edits Steam settings directly."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        status = QLabel()
        status.setWordWrap(True)
        layout.addWidget(status)
        accounts = QComboBox()
        layout.addWidget(accounts)
        current = QLineEdit(game.launch_options[0] if len(game.launch_options) == 1 else "")
        current.setPlaceholderText("Existing launch options from Steam (preserved when generating)")
        result = QPlainTextEdit()
        result.setReadOnly(True)
        layout.addWidget(current)
        layout.addWidget(result)
        row = QHBoxLayout()
        copy = QPushButton("Copy options — then paste into Steam")
        recheck = QPushButton("Check Steam settings")
        row.addWidget(copy)
        row.addWidget(recheck)
        layout.addLayout(row)
        notice = QLabel()
        notice.setWordWrap(True)
        layout.addWidget(notice)

        def show_detected(values):
            accounts.blockSignals(True)
            accounts.clear()
            accounts.addItem("Choose a detected Steam value…", None)
            for index, value in enumerate(values):
                accounts.addItem(f"Saved Steam value {index + 1}: {value}", value)
            accounts.setVisible(len(values) > 1)
            accounts.blockSignals(False)
            try:
                correct = bool(values) and all(merge_options(value, dll) == value for value in values)
            except ValueError:
                correct = False
            status.setText(
                "Detected in Steam: the required DLL override is already present."
                if correct
                else "Steam settings detected; the DLL override is missing or differs between saved accounts. Choose/review the current options before copying."
                if values
                else "No saved launch options detected. Copy and paste below; Steam may not have saved recent changes yet."
            )

        def update():
            try:
                result.setPlainText(merge_options(current.text(), dll))
                copy.setEnabled(True)
            except ValueError as exc:
                result.setPlainText(str(exc))
                copy.setEnabled(False)

        def copied():
            QApplication.clipboard().setText(result.toPlainText())
            state = read_json(service.metadata(game), {})
            state["launch_options_copied"] = {"dll": dll, "options": result.toPlainText()}
            write_json(service.metadata(game), state)
            notice.setText(
                "Copied. Paste into Steam → Properties → General → Launch Options. Setup can now continue; copying alone does not change Steam."
            )
            self.details()

        def checked(data):
            games, warnings = data
            updated = next((g for g in games if g.key == game.key), None)
            if updated:
                self.games = games
                self.filter_games()
                show_detected(updated.launch_options)
                if len(updated.launch_options) == 1 and not current.isModified():
                    current.setText(updated.launch_options[0])
            else:
                status.setText("Could not find this game while rereading Steam settings.")
            for warning in warnings:
                self.message(warning)
            recheck.setEnabled(True)

        def check_settings():
            status.setText("Reading Steam’s saved launch options…")
            self.work(lambda _: steam.discover(self.settings), done=checked)

        accounts.currentIndexChanged.connect(
            lambda _: current.setText(accounts.currentData()) if accounts.currentData() is not None else None
        )
        current.textChanged.connect(update)
        copy.clicked.connect(copied)
        recheck.clicked.connect(check_settings)
        show_detected(game.launch_options)
        update()
        dialog.exec()

    def select_prefix(self):
        game = self.game
        if not game:
            return
        folder = choose_path(self, "Select existing pfx directory", Path.home(), directory=True)
        if folder:
            if not steam.initialized(Path(folder)):
                self.error(
                    "This is not an initialized Proton pfx directory (drive_c and system.reg required)."
                )
                return
            self.settings["prefixes"][game.appid] = folder
            save_settings(self.settings)
            self.refresh()

    def manual(self):
        filename = choose_path(
            self,
            "Select game executable or Steam manifest",
            Path.home(),
            "Steam game (*.exe *.EXE appmanifest_*.acf)",
        )
        if filename:
            self.resolve_manual(filename)

    def resolve_manual(self, filename, root=None):
        def resolve(_):
            try:
                return steam.resolve_manual_game(filename, self.settings, root)
            except steam.SteamRootRequired:
                return None

        def done(game):
            if game is None:
                owner = choose_path(
                    self,
                    "Select owning Steam root (contains config and steamapps)",
                    Path.home(),
                    directory=True,
                )
                if owner:
                    QTimer.singleShot(0, lambda: self.resolve_manual(filename, owner))
                return
            self.settings["steam_roots"] = list(
                dict.fromkeys([*self.settings["steam_roots"], str(game.steam)])
            )
            self.settings["libraries"] = list(dict.fromkeys([*self.settings["libraries"], str(game.library)]))
            save_settings(self.settings)
            self.search.clear()
            self.pending_game_key = game.key
            self.message(f"Found {game.name} (Steam {game.appid}) from your selection.")
            QTimer.singleShot(0, self.refresh)

        self.work(resolve, done)

    def toggle_reloaded_shortcut(self):
        if self.game and shortcuts.menu_shortcut_exists(self.game):
            self.remove_game_shortcut()
        else:
            self.create_reloaded_shortcut()

    def toggle_manager_shortcut(self):
        if shortcuts.menu_shortcut_exists():
            self.remove_manager_shortcut()
        else:
            self.create_manager_shortcut()

    def create_reloaded_shortcut(self):
        game = self.game
        if game:
            self.work(
                lambda _: shortcuts.install_menu_shortcut(
                    shortcuts.reloaded_entry(game, self.settings), game=game
                )
            )

    def create_manager_shortcut(self):
        image = shortcuts.find_appimage()
        if image is None:
            filename = choose_path(
                self, "Select the manager AppImage", Path.home(), "AppImage (*.AppImage *.appimage)"
            )
            if not filename:
                return
            image = Path(filename)
        self.work(lambda _: shortcuts.install_menu_shortcut(shortcuts.manager_entry(image)))

    def remove_game_shortcut(self):
        game = self.game
        if game:
            self.work(lambda _: shortcuts.remove_menu_shortcut(game))

    def remove_manager_shortcut(self):
        self.work(lambda _: shortcuts.remove_menu_shortcut())

    def game_context_menu(self, position):
        item = self.library.itemAt(position)
        if item is None or self.busy:
            return
        game = self.visible[self.library.row(item)]
        menu = QMenu(self)
        favorite = game.key in self.settings.get("favorites", [])
        action = menu.addAction("Remove from favorites" if favorite else "Favorite")
        if menu.exec(self.library.viewport().mapToGlobal(position)) == action:
            self.toggle_favorite(game)

    def toggle_favorite(self, game):
        favorites = set(self.settings.get("favorites", []))
        if game.key in favorites:
            favorites.remove(game.key)
        else:
            favorites.add(game.key)
        self.settings["favorites"] = sorted(favorites)
        save_settings(self.settings)
        self.pending_game_key = self.game.key if self.game else game.key
        self.filter_games()

    def apply_theme(self, key):
        themes.apply(key)
        self.steps.setText(
            step_markup(self.guide or {}, self.failures.get(self.game.key) if self.game else None)
        )
        for highlighter in (self.activity_highlighter, self.log_panel.highlighter, self.details_highlighter):
            highlighter.rehighlight()

    def settings_dialog(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self.settings = dialog.value()
            save_settings(self.settings)
            self.apply_theme(self.settings.get("theme", "dark"))
            logging.getLogger().setLevel(self.settings["log_level"])
            self.refresh()

    def remove(self):
        game = self.game
        if (
            game
            and QMessageBox.question(
                self,
                "Reset ASI Deployment",
                "Reset this manager’s ASI deployment? Reloaded-II, mods, the application shortcut, saves and the Windows environment will be kept. You will need to remove the related DLL override from Steam launch options yourself.",
            )
            == QMessageBox.Yes
        ):
            self.work(lambda _: service.remove_asi(game))

    def reset_all(self):
        game = self.game
        if not game:
            return
        answer = QMessageBox.question(
            self,
            "Reset All",
            "Close the game and Reloaded-II first.\n\n"
            "This backs up and removes this game's managed Reloaded-II installation, ALL its mods, "
            "settings and registrations, ASI integration and game application shortcut. "
            "The backup stays inside the Proton prefix under drive_c/ReloadedLinuxManager/ResetBackups.\n\n"
            "The game, saves, Proton prefix, Windows runtimes and manager shortcut are kept. "
            "Steam launch options remain unchanged; review the old DLL override afterward.\n\n"
            "Return this game to the first Reloaded-II setup step?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            self.work(lambda report: reset.full_reset(game, report))

    def restore_reset(self):
        game = self.game
        if (
            game
            and QMessageBox.question(
                self,
                "Restore previous Reloaded-II setup",
                "Close the game and Reloaded-II first. Restore the last full-reset backup? "
                "A new setup or externally changed loader files will be preserved instead of overwritten.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            == QMessageBox.Yes
        ):
            self.work(lambda _: reset.restore(game))

    def display_tab(self, index):
        if self.busy:
            return
        key = self.game.key if self.game else None
        if index == 1:
            self.logs(force=False)
        elif index == 2 and self._details_key != key:
            self.configuration()

    def configuration(self):
        game = self.game
        if self.tabs.currentIndex() != 2:
            self.tabs.setCurrentIndex(2)
            return
        if game:

            def done(text):
                self._details_key = game.key
                self.setup_output.setPlainText(text)

            self.work(lambda _: views.setup_details(game), done)
        else:
            self._details_key = None
            self.setup_output.setPlainText("Choose a game to view its setup details.")

    def logs(self, force=True):
        if self.tabs.currentIndex() != 1:
            self.tabs.setCurrentIndex(1)
            return
        self.log_panel.refresh(force=force)

    def clear_logs(self):
        game = self.game
        if (
            QMessageBox.question(
                self,
                "Clear logs",
                "Close the game and Reloaded-II first. Clear saved manager logs and the recent Reloaded-II logs displayed for this game? This only clears log text; mods and settings are kept.",
            )
            != QMessageBox.Yes
        ):
            return

        def done(text):
            self.output.clear()
            self.log_panel.last_read = None
            self.message(text)
            self.log_panel.refresh(force=True)

        self.work(lambda _: views.clear_logs(game), done)

    def about(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("About Reloaded Linux Manager")
        dialog.resize(570, 330)
        layout = QVBoxLayout(dialog)
        layout.addWidget(
            QLabel(f"Reloaded Linux Manager {__version__.removesuffix('.0')}\nAuthor: WarpedEdge")
        )
        text = QLabel(
            "A native Linux frontend to help set up and launch Reloaded-II for your games.\n"
            "Uses official Reloaded-II through the game’s Steam Proton environment."
        )
        text.setWordWrap(True)
        layout.addWidget(text)
        repository = QPushButton("Open GitHub project")
        repository.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(updater.PROJECT_URL)))
        layout.addWidget(repository)
        check = QPushButton("Check for updates")
        check.clicked.connect(lambda: (dialog.accept(), self.check_updates()))
        layout.addWidget(check)
        close = QDialogButtonBox(QDialogButtonBox.Close)
        close.rejected.connect(dialog.reject)
        layout.addWidget(close)
        dialog.exec()

    def check_updates(self, automatic=False):
        if automatic and not self.settings.get("check_updates", True):
            return
        if self.checking_updates:
            return
        if self.busy:
            QTimer.singleShot(3000, lambda: self.check_updates(automatic))
            return
        self.checking_updates = True
        worker = Worker(lambda _: updater.check_update())
        self.workers.add(worker)

        def done(result):
            self.message(result["message"])
            if result["status"] == "available":
                self.offer_update(result)
            elif not automatic:
                QMessageBox.information(self, "Manager updates", result["message"])

        def failed(text):
            self.message("Update check unavailable: " + text)
            if not automatic:
                QMessageBox.information(self, "Manager updates", text)

        def finished():
            self.checking_updates = False
            self.workers.discard(worker)

        worker.signals.done.connect(done)
        worker.signals.failed.connect(failed)
        worker.signals.finished.connect(finished)
        QThreadPool.globalInstance().start(worker)

    def offer_update(self, release):
        if self.busy:
            QTimer.singleShot(2000, lambda: self.offer_update(release))
            return
        image = shortcuts.find_appimage()
        if image is None:
            QMessageBox.information(
                self,
                "Manager update available",
                release["message"] + " Run the manager AppImage to install updates in-app.",
            )
            return
        if (
            QMessageBox.question(
                self,
                "Manager update available",
                release["message"]
                + "\nDownload and install it now? The current AppImage will be backed up; its filename and application shortcut will stay the same.",
            )
            != QMessageBox.Yes
        ):
            return

        def installed(result):
            self.message("Manager update installed. Previous AppImage: " + result["backup"])
            # Schedule the restart prompt after the worker's finished signal clears busy.
            QTimer.singleShot(0, lambda: self.restart_updated(result["path"]))

        self.work(lambda report: updater.install_update(image, release["asset"], report), installed)

    def restart_updated(self, filename):
        if (
            QMessageBox.question(self, "Update installed", "Restart into the new manager version now?")
            != QMessageBox.Yes
        ):
            return
        env = os.environ.copy()
        original = env.pop("LD_LIBRARY_PATH_ORIG", None)
        env.pop("LD_LIBRARY_PATH", None)
        if original:
            env["LD_LIBRARY_PATH"] = original
        for name in (
            "APPIMAGE",
            "APPDIR",
            "QT_PLUGIN_PATH",
            "QML2_IMPORT_PATH",
            "PYTHONHOME",
            "PYTHONPATH",
            "LIBARCHIVE",
            "LD_PRELOAD",
        ):
            env.pop(name, None)
        env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
        try:
            subprocess.Popen([filename], env=env, start_new_session=True)
        except OSError as exc:
            self.error("Update is installed, but restart failed: " + str(exc))
            return
        self.close()

    def closeEvent(self, event):
        if self.busy:
            QMessageBox.information(
                self,
                "Operation running",
                "Wait for the current operation or close Reloaded-II before exiting, so installation can finish safely.",
            )
            event.ignore()
        else:
            self.log_panel.stop()
            event.accept()


def main():
    parser = argparse.ArgumentParser(description="Native setup companion for official Reloaded-II")
    parser.add_argument("--version", action="version", version=f"Reloaded Linux Manager {__version__}")
    parser.add_argument(
        "--smoke-test", action="store_true", help="Open Qt, discover Steam, and exit without game changes"
    )
    parser.add_argument(
        "--check-asi",
        type=Path,
        metavar="ARCHIVE",
        help="Validate ASI archive decoding without executing its contents",
    )
    args = parser.parse_args()
    if args.check_asi:
        payload = extract_asi(args.check_asi, True)
        print(f"ASI x64 archive decoded: {len(payload)} bytes")
        return
    state_home().mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(state_home() / "manager.log", maxBytes=2 * 1024**2, backupCount=3)
    logging.basicConfig(
        level=load_settings()["log_level"],
        handlers=[handler],
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Reloaded Linux Manager")
    app.setOrganizationName("ReloadedLinuxManager")
    app.setStyle("Fusion")
    app.button_cursor = ButtonCursor(app)
    app.installEventFilter(app.button_cursor)
    themes.apply(load_settings().get("theme", "dark"))
    icon = (
        Path(sys._MEIPASS) / "reloaded-linux-manager.png"
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parents[2] / "packaging/reloaded-linux-manager.png"
    )
    if icon.is_file():
        app.setWindowIcon(QIcon(str(icon)))
    window = Window()
    window.show()
    if args.smoke_test:

        def finish_smoke():
            if window.busy or window.workers or window.log_panel.jobs:
                QTimer.singleShot(100, finish_smoke)
            else:
                window.log_panel.stop()
                print("Native Qt smoke test passed", flush=True)
                app.quit()

        QTimer.singleShot(100, finish_smoke)
        QTimer.singleShot(30000, lambda: app.exit(1))
    if not args.smoke_test:
        QTimer.singleShot(2000, lambda: window.check_updates(automatic=True))
    exit_code = app.exec()
    window.log_panel.stop()
    QThreadPool.globalInstance().waitForDone()
    sys.exit(exit_code)
