"""Named color tokens shared by widgets, status text and settings previews.

Add a palette to THEMES to make it available in Appearance automatically.
"""

from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import QApplication

THEMES = {
    "dark": dict(
        name="Dark",
        window="#1b222c",
        base="#141b24",
        button="#2c3848",
        text="#edf2f8",
        muted="#b8c4d4",
        border="#56657a",
        accent="#2766b0",
        hover="#405976",
        selected="#ffffff",
        success="#77d994",
        warning="#f6d36d",
        error="#ff8994",
        pending="#83b8ff",
    ),
    "light": dict(
        name="Light",
        window="#f2f4f7",
        base="#ffffff",
        button="#e2e7ef",
        text="#172334",
        muted="#4e5e72",
        border="#8b99aa",
        accent="#2464a8",
        hover="#cddced",
        selected="#ffffff",
        success="#22733b",
        warning="#805900",
        error="#b42336",
        pending="#24599a",
    ),
    "oled": dict(
        name="OLED",
        window="#000000",
        base="#080808",
        button="#181818",
        text="#f3f3f3",
        muted="#bcbcbc",
        border="#555555",
        accent="#006a9b",
        hover="#303030",
        selected="#ffffff",
        success="#77d994",
        warning="#f6d36d",
        error="#ff8994",
        pending="#83b8ff",
    ),
    "plum": dict(
        name="Plum",
        window="#251d30",
        base="#1a1423",
        button="#3b2d4b",
        text="#f1e8fa",
        muted="#cab7db",
        border="#786087",
        accent="#7446a4",
        hover="#554066",
        selected="#ffffff",
        success="#8adeac",
        warning="#f5d58c",
        error="#ff9aa9",
        pending="#b7b4ff",
    ),
    "forest": dict(
        name="Forest",
        window="#172923",
        base="#101e19",
        button="#294539",
        text="#ecf5ee",
        muted="#b0cbbd",
        border="#587b6a",
        accent="#27704d",
        hover="#395e4c",
        selected="#ffffff",
        success="#8fe0a4",
        warning="#f6d48b",
        error="#ff9b9b",
        pending="#8fc8ef",
    ),
}


def colors(key=None):
    app = QApplication.instance()
    key = key or (app.property("managerTheme") if app else None)
    return THEMES.get(key, THEMES["dark"])


def apply(key):
    app = QApplication.instance()
    key = key if key in THEMES else "dark"
    c = colors(key)
    app.setProperty("managerTheme", key)
    palette = QPalette()
    for role, token in [
        (QPalette.Window, "window"),
        (QPalette.WindowText, "text"),
        (QPalette.Base, "base"),
        (QPalette.AlternateBase, "button"),
        (QPalette.Text, "text"),
        (QPalette.Button, "button"),
        (QPalette.ButtonText, "text"),
        (QPalette.Highlight, "accent"),
        (QPalette.HighlightedText, "selected"),
        (QPalette.ToolTipBase, "base"),
        (QPalette.ToolTipText, "text"),
        (QPalette.PlaceholderText, "muted"),
    ]:
        palette.setColor(role, QColor(c[token]))
    for role in (QPalette.Text, QPalette.ButtonText, QPalette.WindowText):
        palette.setColor(QPalette.Disabled, role, QColor(c["muted"]))
    app.setPalette(palette)
    app.setStyleSheet(f"""
QPushButton, QToolButton {{ background: {c["button"]}; color: {c["text"]}; border: 1px solid {c["border"]}; border-radius: 5px; padding: 7px 10px; }}
QPushButton:hover, QToolButton:hover {{ background: {c["hover"]}; border-color: {c["pending"]}; }}
QPushButton:pressed, QToolButton:pressed, QToolButton:checked {{ background: {c["accent"]}; color: {c["selected"]}; }}
QPushButton:focus, QToolButton:focus {{ border: 2px solid {c["pending"]}; }}
QPushButton:disabled, QToolButton:disabled {{ color: {c["muted"]}; border-color: {c["button"]}; }}
QPushButton#primaryAction {{ background: {c["accent"]}; color: {c["selected"]}; font-weight: 600; }}
QPushButton#primaryAction:hover {{ background: {c["hover"]}; color: {c["text"]}; }}
QPushButton#primaryAction:disabled {{ background: {c["button"]}; color: {c["muted"]}; }}
QGroupBox {{ border: 1px solid {c["border"]}; border-radius: 6px; margin-top: 8px; padding: 9px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; }}
QLabel#versionBadge {{ border: 1px solid {c["border"]}; border-radius: 5px; background: {c["base"]}; color: {c["muted"]}; padding: 8px 10px; }}
QLabel#technicalDetails {{ color: {c["muted"]}; font-size: 12px; }}
QPushButton#logSource:checked {{ background: {c["accent"]}; color: {c["selected"]}; }}
QPushButton#logSource[unread="true"] {{ border: 2px solid {c["warning"]}; color: {c["warning"]}; background: {c["base"]}; }}
""")


def preview_icon(key):
    c = colors(key)
    image = QPixmap(110, 76)
    image.fill(QColor(c["window"]))
    painter = QPainter(image)
    painter.fillRect(7, 8, 96, 12, QColor(c["button"]))
    painter.fillRect(7, 27, 22, 41, QColor(c["base"]))
    painter.fillRect(36, 29, 58, 5, QColor(c["text"]))
    painter.fillRect(36, 40, 44, 4, QColor(c["muted"]))
    painter.fillRect(36, 53, 65, 15, QColor(c["accent"]))
    painter.end()
    return QIcon(image)
