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

# These are original palettes inspired by their names, rather than imported theme assets.
THEMES.update(
    {
        "cyberpunk": THEMES["dark"]
        | dict(
            name="Cyberpunk",
            window="#170b10",
            base="#0c080c",
            button="#301322",
            text="#24f3eb",
            muted="#b9c8ca",
            border="#875338",
            accent="#f4df00",
            selected="#121014",
            hover="#493121",
            pending="#24f3eb",
        ),
        "ivalice": THEMES["light"]
        | dict(
            name="Ivalice (FFT)",
            window="#eee3c7",
            base="#fff8e8",
            button="#d9c9a5",
            text="#302c3b",
            muted="#635b4c",
            border="#97815e",
            accent="#565879",
            hover="#cabb9c",
            selected="#fff8e8",
            success="#32613d",
            warning="#79500c",
            error="#a12c39",
            pending="#3b5676",
        ),
        "amethyst": THEMES["dark"]
        | dict(
            name="Amethyst",
            window="#21172d",
            base="#150f20",
            button="#38264b",
            text="#f0e6ff",
            muted="#c6b2d9",
            border="#7d5b98",
            accent="#7946b1",
            hover="#503665",
            pending="#ccb0ff",
        ),
        "mocha": THEMES["dark"]
        | dict(
            name="Mocha",
            window="#252331",
            base="#191824",
            button="#3c374d",
            text="#ede6f6",
            muted="#c1b7d3",
            border="#746782",
            accent="#be9fdf",
            selected="#231c30",
            hover="#514561",
        ),
        "noir": THEMES["dark"]
        | dict(
            name="Noir",
            window="#1a1a1a",
            base="#111111",
            button="#303030",
            text="#eeeeee",
            muted="#bbbbbb",
            border="#686868",
            accent="#cccccc",
            selected="#181818",
            hover="#484848",
            pending="#d0d0d0",
        ),
        "pipboy": THEMES["dark"]
        | dict(
            name="Pip-Boy",
            window="#061407",
            base="#020903",
            button="#122c13",
            text="#77f58a",
            muted="#9ac69d",
            border="#38753e",
            accent="#72ed80",
            selected="#061407",
            hover="#204226",
            pending="#99ffab",
        ),
        "stardew": THEMES["light"]
        | dict(
            name="Stardew",
            window="#f5e4b7",
            base="#fff6d9",
            button="#e9c58e",
            text="#493222",
            muted="#70513b",
            border="#9b6a43",
            accent="#386445",
            selected="#fff9e8",
            hover="#d9b47d",
            success="#32613d",
            warning="#79500c",
            error="#a12c39",
            pending="#3b5676",
        ),
        "tokyo-night": THEMES["dark"]
        | dict(
            name="Tokyo Night",
            window="#1a1d30",
            base="#131625",
            button="#2a304d",
            text="#dfe5ff",
            muted="#adb9df",
            border="#586994",
            accent="#89a9ff",
            selected="#161c30",
            hover="#3c4568",
            success="#9bdc9f",
            warning="#edce89",
            error="#ff94a8",
            pending="#a5baff",
        ),
        "breeze-dark": THEMES["dark"]
        | dict(
            name="Breeze-inspired Dark",
            window="#24292d",
            base="#191e22",
            button="#343b40",
            text="#eff2f4",
            muted="#bac6cf",
            border="#64757f",
            accent="#176b92",
            hover="#42545f",
        ),
        "breeze-light": THEMES["light"]
        | dict(
            name="Breeze-inspired Light",
            window="#eff0f1",
            base="#ffffff",
            button="#dde3e7",
            text="#232b30",
            muted="#52616b",
            border="#85959f",
            accent="#176b92",
            hover="#c6dde8",
        ),
    }
)

# Component roles are deliberately separate from selection/accent colors.
THEMES["cyberpunk"].update(
    window="#190a0f",
    base="#10070b",
    button="#1e0c12",
    text="#27eee8",
    muted="#91b7ba",
    border="#78283b",
    accent="#f4df00",
    hover="#3c1322",
    primary_hover="#fff16a",
    primary_disabled="#666022",
    primary_disabled_text="#e1d68a",
    radius="3",
    description="Red-black surfaces, cyan type, red outlines and electric yellow actions.",
)
THEMES["ivalice"].update(
    window="#a69a7f",
    base="#b2a68a",
    button="#9d9177",
    text="#201d16",
    muted="#373125",
    border="#4f4738",
    accent="#4d4537",
    selected="#fff8df",
    hover="#c3b69a",
    success="#153a1d",
    warning="#533403",
    error="#78071c",
    pending="#112b74",
    primary_hover="#383126",
    radius="0",
    description="FFT-inspired warm taupe menu panels, dark ink and raised borders.",
)
THEMES["breeze-dark"]["name"] = "Breeze Dark"
THEMES["breeze-light"]["name"] = "Breeze Light"

# Progress has its own high-contrast semantic colors rather than muted theme text.
for _key, _palette in THEMES.items():
    _light = _key in ("light", "ivalice", "stardew", "breeze-light")
    _palette.update(
        progress_success="#006b2d" if _light else "#55f995",
        progress_pending="#164cba" if _light else "#64caff",
        progress_error="#b51636" if _light else "#ff7587",
    )
THEMES["ivalice"].update(progress_success="#003516", progress_pending="#112b74", progress_error="#68031b")
THEMES["pipboy"].update(progress_success="#58ff80", progress_pending="#c2ff81", progress_error="#ff8c8c")


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

    # Explicit component styling avoids desktop-style defaults changing the theme.
    extra = f"""
QPushButton, QToolButton {{ border-radius: {c.get("radius", "5")}px; }}
QPushButton:focus, QToolButton:focus {{ border: 2px solid {c["pending"]}; padding: 6px 9px; }}
QPushButton:disabled, QToolButton:disabled {{ background: {c["base"]}; color: {c["muted"]}; border: 1px solid {c["border"]}; }}
QPushButton#primaryAction:focus {{ border: 2px solid {c["pending"]}; padding: 6px 9px; }}
QPushButton#primaryAction:hover {{ background: {c.get("primary_hover", c["accent"])}; color: {c["selected"]}; }}
QPushButton#primaryAction:disabled {{ background: {c.get("primary_disabled", c["button"])}; color: {c.get("primary_disabled_text", c["muted"])}; border: 1px solid {c["border"]}; }}
QLineEdit, QComboBox, QSpinBox {{ background: {c["base"]}; color: {c["text"]}; border: 1px solid {c["border"]}; border-radius: 3px; padding: 5px 7px; selection-background-color: {c["accent"]}; selection-color: {c["selected"]}; }}
QLineEdit:focus, QComboBox:focus {{ border-color: {c["pending"]}; }}
QPlainTextEdit, QTextEdit, QListWidget, QTreeView {{ background: {c["base"]}; color: {c["text"]}; border: 1px solid {c["border"]}; selection-background-color: {c["accent"]}; selection-color: {c["selected"]}; }}
QListWidget::item {{ padding: 3px; border: 1px solid transparent; }}
QListWidget::item:hover {{ background: {c["hover"]}; }}
QListWidget::item:selected {{ background: {c["accent"]}; color: {c["selected"]}; border-color: {c["border"]}; }}
QTabWidget::pane {{ border: 1px solid {c["border"]}; background: {c["window"]}; }}
QTabBar::tab {{ background: {c["button"]}; color: {c["muted"]}; padding: 7px 12px; border: 1px solid {c["border"]}; border-bottom: 2px solid transparent; margin-right: 2px; }}
QTabBar::tab:selected {{ background: {c["base"]}; color: {c["text"]}; border-bottom: 2px solid {c["accent"]}; }}
QTabBar::tab:hover {{ color: {c["text"]}; background: {c["hover"]}; }}
QMenu {{ background: {c["base"]}; color: {c["text"]}; border: 1px solid {c["border"]}; padding: 4px; }}
QMenu::item {{ padding: 7px 22px; }}
QMenu::item:selected {{ background: {c["accent"]}; color: {c["selected"]}; }}
QMenu::item:disabled {{ color: {c["muted"]}; }}
QToolTip {{ background: {c["base"]}; color: {c["text"]}; border: 1px solid {c["border"]}; padding: 5px; }}
QScrollBar:vertical {{ background: {c["base"]}; width: 13px; margin: 0; }}
QScrollBar:horizontal {{ background: {c["base"]}; height: 13px; margin: 0; }}
QScrollBar::handle {{ background: {c["border"]}; border: 3px solid {c["base"]}; border-radius: 6px; min-height: 25px; min-width: 25px; }}
QScrollBar::handle:hover {{ background: {c["accent"]}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QProgressBar {{ background: {c["base"]}; border: 1px solid {c["border"]}; border-radius: 3px; text-align: center; color: {c["text"]}; min-height: 9px; max-height: 12px; }}
QProgressBar::chunk {{ background: {c["accent"]}; border-radius: 2px; }}

"""
    if key == "ivalice":
        extra += f"""
QLabel#appHeading, QLabel#stageHeading {{ font-family: 'DejaVu Serif'; }}
QWidget#gameSummary, QGroupBox {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #b3a58a, stop:1 #9c9076); border: 3px ridge {c["border"]}; }}
QWidget#gameSummary QLabel {{ color: {c["text"]}; background: transparent; }}
QWidget#gameSummary QLabel#technicalDetails {{ color: {c["muted"]}; }}
QListWidget, QPlainTextEdit, QTextEdit {{ background: {c["base"]}; border: 3px ridge {c["border"]}; }}
QPushButton, QToolButton {{ border: 2px outset {c["border"]}; }}
QPushButton:focus, QToolButton:focus {{ border: 2px outset {c["pending"]}; }}
QPushButton:pressed, QToolButton:pressed {{ border: 2px inset {c["border"]}; }}
QPushButton#primaryAction {{ background: {c["accent"]}; color: {c["selected"]}; }}
"""
    app.setStyleSheet(app.styleSheet() + extra)


def preview_icon(key):
    c = colors(key)
    image = QPixmap(110, 76)
    image.fill(QColor(c["window"]))
    painter = QPainter(image)
    painter.fillRect(7, 8, 96, 12, QColor(c["button"]))
    painter.fillRect(7, 27, 22, 41, QColor(c["base"]))
    painter.fillRect(33, 27, 70, 41, QColor(c["base"]))
    painter.fillRect(36, 29, 58, 5, QColor(c["text"]))
    painter.fillRect(36, 40, 44, 4, QColor(c["muted"]))
    painter.fillRect(36, 53, 65, 15, QColor(c["accent"]))
    painter.end()
    return QIcon(image)
