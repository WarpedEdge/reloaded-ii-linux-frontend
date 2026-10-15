"""Native Qt interface. Filesystem/network/process operations run on worker threads."""

import argparse
import html
import json
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PySide6.QtCore import (
    QDir,
    QEvent,
    QObject,
    QRunnable,
    QStandardPaths,
    Qt,
    QThreadPool,
    QTimer,
    QUrl,
    Signal,
)
from PySide6.QtGui import QColor, QDesktopServices, QIcon, QPalette
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import proton, service, shortcuts, steam
from .integration import deploy, extract_asi, merge_options
from .storage import load_settings, read_json, save_settings, state_home, write_json

BUTTON_STYLE = """
QPushButton, QToolButton {
    background: #2c3848; color: #edf2f8; border: 1px solid #56657a;
    border-radius: 5px; padding: 7px 10px;
}
QPushButton:hover, QToolButton:hover { background: #405976; border-color: #8fc5ff; }
QPushButton:pressed, QToolButton:pressed { background: #1a395b; border-color: #acd4ff; }
QPushButton:focus, QToolButton:focus { border: 2px solid #8fc5ff; }
QPushButton:disabled, QToolButton:disabled { background: #252e3a; color: #8997aa; border-color: #394657; }
QPushButton#primaryAction { background: #2766b0; color: white; font-weight: 600; }
QPushButton#primaryAction:hover { background: #347fd2; border-color: #b3dbff; }
QPushButton#primaryAction:pressed { background: #194b86; }
QPushButton#primaryAction:disabled { background: #333e4c; color: #aab5c3; }
QGroupBox { border: 1px solid #3c4b5f; border-radius: 6px; margin-top: 8px; padding: 9px; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; }
"""

STEP_LABELS = (
    "Find Proton environment",
    "Install Reloaded-II",
    "Add game in Reloaded-II",
    "Enable Steam loading",
    "Apply launch options",
    "Test mods in game",
)


def step_markup(guide, failure=None):
    stage = guide.get("stage", -1)
    failure = guide.get("failed_step", failure)
    rows = []
    for index, label in enumerate(STEP_LABELS):
        if index == failure:
            color, mark = "#ff8994", "✗"
        elif 0 <= index < stage:
            color, mark = "#77d994", "✓"
        else:
            color, mark = "#83b8ff", "→" if index == stage else "•"
        rows.append(f'<span style="color:{color}">{mark} &nbsp;{html.escape(label)}</span>')
    return "<br/>".join(rows)


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
        self.resize(650, 460)
        self.settings = settings.copy()
        layout = QFormLayout(self)
        self.fields = {}
        for key, label in [
            ("steam_roots", "Additional Steam roots (one per line)"),
            ("libraries", "Additional library roots (one per line)"),
        ]:
            field = QPlainTextEdit("\n".join(settings[key]))
            field.setMaximumHeight(90)
            self.fields[key] = field
            layout.addRow(label, field)
        for key, label in [
            ("cache", "Download cache"),
            ("release", "Release tag (or latest)"),
            ("protontricks_launch", "protontricks-launch executable (optional)"),
        ]:
            field = QLineEdit(settings[key])
            self.fields[key] = field
            layout.addRow(label, field)
        self.level = QComboBox()
        self.level.addItems(["INFO", "DEBUG", "WARNING"])
        self.level.setCurrentText(settings["log_level"])
        layout.addRow("Logging verbosity", self.level)
        layout.addRow(
            QLabel(
                "Proton tool selection is owned by Steam. Change it in game Properties → Compatibility.\n"
                "Updates are explicit: choose a release tag, then click Update. No background updates."
            )
        )
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def value(self):
        for key, field in self.fields.items():
            self.settings[key] = (
                [line.strip() for line in field.toPlainText().splitlines() if line.strip()]
                if isinstance(field, QPlainTextEdit)
                else field.text().strip()
            )
        self.settings["log_level"] = self.level.currentText()
        return self.settings


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = load_settings()
        self.games = []
        self.visible = []
        self.workers = set()
        self.busy = False
        self.guide = None
        self.inspection = 0
        self.failures = {}
        self.pending_game_key = None
        self.setWindowTitle("Reloaded Linux Manager")
        self.resize(1240, 840)
        self.setStyleSheet(BUTTON_STYLE)
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        heading = QLabel("Reloaded Linux Manager")
        heading.setStyleSheet("font-size: 25px; font-weight: 600; padding: 8px")
        outer.addWidget(heading)
        outer.addWidget(QLabel("Choose a game. We’ll guide you through the next step."))
        tools = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search installed games or App ID…")
        self.search.textChanged.connect(self.filter_games)
        tools.addWidget(self.search)
        self.actions = []
        for label, action in [
            ("Refresh", self.refresh),
            ("Add game manually", self.manual),
            ("Settings", self.settings_dialog),
        ]:
            button = QPushButton(label)
            button.clicked.connect(action)
            self.actions.append(button)
            tools.addWidget(button)
        outer.addLayout(tools)
        splitter = QSplitter()
        self.library = QListWidget()
        self.library.setMinimumWidth(240)
        self.library.setMaximumWidth(360)
        self.library.setWordWrap(True)
        self.library.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.library.setSpacing(6)
        self.library.currentRowChanged.connect(self.details)
        splitter.addWidget(self.library)
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
        self.technical.setStyleSheet("color: #b8c4d4; font-size: 12px")
        summary.addWidget(self.technical)
        summary.addStretch()
        header.addLayout(summary, 3)
        progress_box = QGroupBox("Setup progress")
        progress_box.setMaximumWidth(260)
        progress_layout = QVBoxLayout(progress_box)
        self.steps = QLabel(step_markup({}))
        self.steps.setTextFormat(Qt.RichText)
        self.steps.setStyleSheet("line-height: 1.5; font-size: 12px")
        progress_layout.addWidget(self.steps)
        header.addWidget(progress_box, 1, Qt.AlignTop)
        panel.addLayout(header)
        self.next_heading = QLabel("Choose a game to get started")
        self.next_heading.setWordWrap(True)
        self.next_heading.setStyleSheet("font-size: 19px; font-weight: 600; margin-top: 20px")
        panel.addWidget(self.next_heading)
        self.next_text = QLabel("Select a game from your library on the left.")
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
        for label, action in [
            ("Check setup", self.check),
            ("Launch game", self.launch_game),
            ("Repair installation", self.setup),
            ("Update Reloaded-II", self.setup),
            ("Select existing prefix", self.select_prefix),
            ("Remove integration", self.remove),
            ("View configuration", self.configuration),
            ("View logs", self.logs),
        ]:
            self.more_menu.addAction(label, action)
        self.more.setMenu(self.more_menu)
        self.actions.append(self.more)
        self.more.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        secondary.addWidget(self.more, 1)
        for button in (self.open_button, self.deploy_button, self.options_button, self.more):
            button.setMinimumHeight(48)
            button.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        panel.addLayout(secondary)
        shortcut_row = QHBoxLayout()
        self.reloaded_shortcut = QPushButton("Create Reloaded-II desktop shortcut")
        self.reloaded_shortcut.clicked.connect(self.create_reloaded_shortcut)
        self.actions.append(self.reloaded_shortcut)
        shortcut_row.addWidget(self.reloaded_shortcut, 1)
        self.manager_shortcut = QPushButton("Create manager AppImage shortcut")
        self.manager_shortcut.clicked.connect(self.create_manager_shortcut)
        self.actions.append(self.manager_shortcut)
        shortcut_row.addWidget(self.manager_shortcut, 1)
        for button in (self.reloaded_shortcut, self.manager_shortcut):
            button.setMinimumHeight(40)
        panel.addLayout(shortcut_row)
        panel.addWidget(QLabel("Activity"))
        self.progress = QProgressBar()
        self.progress.hide()
        panel.addWidget(self.progress)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        self.output.setPlaceholderText(
            "Setup steps and diagnostics appear here. Setup remains pending until verified in game."
        )
        self.output.setMinimumHeight(150)
        panel.addWidget(self.output, 1)
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

    def message(self, text):
        self.output.appendPlainText(text)
        self.statusBar().showMessage(text)
        logging.info(text)

    def error(self, text):
        self.message("FAILED: " + text)
        QMessageBox.warning(self, "Action could not complete", text)

    def refresh(self):
        def done(result):
            self.games, warnings = result
            self.filter_games()
            for warning in warnings:
                self.message(warning)
            if not self.games:
                self.message(
                    "No Steam games found. Add a Steam root in Settings or select a game's appmanifest manually."
                )

        self.work(lambda _: steam.discover(self.settings), done)

    def filter_games(self):
        text = self.search.text().lower()
        selected = self.pending_game_key or (self.game.key if self.game else None)
        self.pending_game_key = None
        self.visible = [
            g for g in self.games if text in (g.name + " " + g.appid).lower() and not steam.is_support_tool(g)
        ]
        self.library.clear()
        for game in self.visible:
            self.library.addItem(game.name)
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
        self.more.setEnabled(bool(game) and not self.busy)
        if not game:
            self.title.setText("Select a Steam game")
            self.info.clear()
            self.next_heading.setText("Choose a game to get started")
            self.next_text.setText("Search for a game, then select it from the library on the left.")
            self.primary.setText("Select a game")
            self.steps.setText(step_markup({}))
            self.technical.clear()
            return
        self.title.setText(game.name)
        self.title.setTextFormat(Qt.PlainText)
        self.info.setText(f"Steam game {game.appid} · {game.tool}")
        self.technical.setText(
            f"Game: {game.directory}\nSteam root: {game.steam}\n"
            f"Prefix: {game.prefix or 'Not initialized or ambiguous'}"
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
            self.next_heading.setText(guide["heading"])
            self.next_text.setText(guide["text"])
            self.primary.setText(guide["button"])
            self.primary.setEnabled(not self.busy)
            self.open_button.setEnabled(not self.busy and guide["stage"] >= 2)
            self.deploy_button.setEnabled(not self.busy and guide["stage"] >= 3)
            self.options_button.setEnabled(not self.busy and guide["stage"] >= 4)
            self.reloaded_shortcut.setEnabled(not self.busy and guide["stage"] >= 2)
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

    def setup(self):
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
            self.work(lambda report: service.install(game, self.settings, report), failure_step=1)

    def open_reloaded(self):
        game = self.game
        if not game:
            return

        def launch(report):
            executable = game.install / "Reloaded-II.exe"
            if not executable.is_file():
                raise ValueError("Use Setup Reloaded-II first.")
            report(
                "Reloaded-II is running. Add your game using its executable path, manage mods, then close it to continue here."
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
                    "Integration already managed. Use Check Setup or Remove Integration before redeploying."
                )
            state["asi"] = deploy(game, Path(filename), service.backups(game))
            write_json(service.metadata(game), state)
            return "ASI files deployed and hashed. Copy Steam launch options next; in-game verification is still required."

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
        layout.addWidget(
            QLabel(
                "Paste current launch options from Steam Properties → General.\n"
                "Detected values can belong to different Steam accounts. Review before copying."
            )
        )
        current = QLineEdit(game.launch_options[0] if len(game.launch_options) == 1 else "")
        result = QPlainTextEdit()
        result.setReadOnly(True)
        layout.addWidget(current)
        layout.addWidget(result)
        copy = QPushButton("Copy generated options")
        layout.addWidget(copy)

        def update():
            try:
                result.setPlainText(merge_options(current.text(), dll))
                copy.setEnabled(True)
            except ValueError as exc:
                result.setPlainText(str(exc))
                copy.setEnabled(False)

        current.textChanged.connect(update)
        copy.clicked.connect(lambda: QApplication.clipboard().setText(result.toPlainText()))
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

    def shortcut_destination(self, filename):
        desktop = QStandardPaths.writableLocation(QStandardPaths.DesktopLocation) or str(Path.home())
        return choose_path(
            self, "Save desktop shortcut", Path(desktop) / filename, "Desktop shortcut (*.desktop)", save=True
        )

    def create_reloaded_shortcut(self):
        game = self.game
        if not game:
            return
        destination = self.shortcut_destination(f"Reloaded-II-{game.appid}.desktop")
        if destination:
            self.work(
                lambda _: shortcuts.save_shortcut(destination, shortcuts.reloaded_entry(game, self.settings))
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
        destination = self.shortcut_destination("Reloaded-Linux-Manager.desktop")
        if destination:
            self.work(lambda _: shortcuts.save_shortcut(destination, shortcuts.manager_entry(image)))

    def settings_dialog(self):
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec():
            self.settings = dialog.value()
            save_settings(self.settings)
            logging.getLogger().setLevel(self.settings["log_level"])
            self.refresh()

    def remove(self):
        game = self.game
        if (
            game
            and QMessageBox.question(
                self,
                "Remove managed ASI integration",
                "Remove only unchanged ASI files deployed by this manager? Reloaded-II, mods, prefixes and runtimes will be preserved.",
            )
            == QMessageBox.Yes
        ):
            self.work(lambda _: service.remove_asi(game))

    def configuration(self):
        if self.game:
            self.message(json.dumps(read_json(service.metadata(self.game), {}), indent=2))
            if self.game.prefix:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.game.install)))

    def logs(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(state_home())))
        self.message(
            "Logs contain local paths and upstream process output. Review/redact usernames and paths before sharing on GitHub."
        )

    def closeEvent(self, event):
        if self.busy:
            QMessageBox.information(
                self,
                "Operation running",
                "Wait for the current operation or close Reloaded-II before exiting, so installation can finish safely.",
            )
            event.ignore()
        else:
            event.accept()


def main():
    parser = argparse.ArgumentParser(description="Native setup companion for official Reloaded-II")
    parser.add_argument("--version", action="version", version="Reloaded Linux Manager 0.1.0")
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
    app.setStyleSheet(BUTTON_STYLE)
    app.button_cursor = ButtonCursor(app)
    app.installEventFilter(app.button_cursor)
    palette = QPalette()
    for role, color in [
        (QPalette.Window, "#1b222c"),
        (QPalette.WindowText, "#edf2f8"),
        (QPalette.Base, "#141b24"),
        (QPalette.AlternateBase, "#232d3a"),
        (QPalette.Text, "#edf2f8"),
        (QPalette.Button, "#2c3848"),
        (QPalette.ButtonText, "#edf2f8"),
        (QPalette.Highlight, "#285e96"),
        (QPalette.HighlightedText, "#ffffff"),
        (QPalette.ToolTipBase, "#edf2f8"),
        (QPalette.ToolTipText, "#141b24"),
        (QPalette.PlaceholderText, "#a8b5c6"),
    ]:
        palette.setColor(role, QColor(color))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor("#8d9aab"))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor("#8d9aab"))
    app.setPalette(palette)
    icon = (
        Path(sys._MEIPASS) / "reloaded-linux-manager.svg"
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parents[2] / "packaging/reloaded-linux-manager.svg"
    )
    if icon.is_file():
        app.setWindowIcon(QIcon(str(icon)))
    window = Window()
    window.show()
    if args.smoke_test:

        def finish_smoke():
            if window.busy:
                QTimer.singleShot(100, finish_smoke)
            else:
                print("Native Qt smoke test passed", flush=True)
                app.quit()

        QTimer.singleShot(100, finish_smoke)
        QTimer.singleShot(30000, lambda: app.exit(1))
    sys.exit(app.exec())
