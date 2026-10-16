import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QWidget

from reloaded_linux_manager import themes
from reloaded_linux_manager.gui import SettingsDialog, step_markup
from reloaded_linux_manager.storage import load_settings, save_settings


class PreviewWindow(QWidget):
    def apply_theme(self, key):
        themes.apply(key)


def test_theme_preview_cancel_and_persistence(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    parent = PreviewWindow()
    settings = load_settings()
    settings["custom_future_option"] = "preserve"
    themes.apply("dark")
    dialog = SettingsDialog(settings, parent)
    assert [dialog.tabs.tabText(i) for i in range(dialog.tabs.count())] == [
        "Appearance",
        "General",
        "Advanced",
    ]
    dialog.theme_buttons["light"].click()
    assert app.palette().color(QPalette.Window).name() == themes.THEMES["light"]["window"]
    assert themes.colors()["progress_success"] in step_markup({"stage": 6})
    dialog.reject()
    assert app.property("managerTheme") == "dark"
    assert load_settings()["theme"] == "dark"
    saved = SettingsDialog(settings, parent)
    saved.theme_buttons["plum"].click()
    saved.accept()
    save_settings(saved.value())
    assert load_settings()["theme"] == "plum"
    assert load_settings()["custom_future_option"] == "preserve"
    restored = SettingsDialog(load_settings(), parent)
    assert restored.theme_buttons["plum"].isChecked()
    restored.reject()
    themes.apply("dark")


def test_all_theme_palettes_have_readable_text_and_previews():
    _app = QApplication.instance() or QApplication([])

    def luminance(color):
        channels = QColor(color).getRgbF()[:3]
        linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722)))

    for key, palette in themes.THEMES.items():
        themes.apply(key)
        assert not themes.preview_icon(key).isNull()
        for foreground, background in [
            ("text", "window"),
            ("text", "base"),
            ("muted", "window"),
            ("selected", "accent"),
            ("success", "window"),
            ("warning", "base"),
            ("error", "base"),
            ("progress_success", "window"),
            ("progress_pending", "window"),
            ("progress_error", "window"),
        ]:
            a, b = sorted((luminance(palette[foreground]), luminance(palette[background])))
            assert (b + 0.05) / (a + 0.05) >= 4.5, (key, foreground, background)
    themes.apply("unknown")
    assert themes.colors() == themes.THEMES["dark"]


def test_theme_cards_remain_equal_sized_across_palettes(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    parent = PreviewWindow()
    dialog = SettingsDialog(load_settings(), parent)
    for key in ("ivalice", "cyberpunk", "breeze-dark", "breeze-light"):
        dialog.theme_buttons[key].click()
        app.processEvents()
        assert {(button.width(), button.height()) for button in dialog.theme_buttons.values()} == {(164, 124)}
    dialog.reject()
    themes.apply("dark")


def test_cyberpunk_primary_action_and_fft_menu_styling(tmp_path, monkeypatch):
    from PySide6.QtWidgets import QPushButton

    _app = QApplication.instance() or QApplication([])
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    themes.apply("cyberpunk")
    button = QPushButton("Launch")
    button.setObjectName("primaryAction")
    button.resize(160, 48)
    assert button.grab().toImage().pixelColor(10, 10).name() == themes.THEMES["cyberpunk"]["accent"]
    button.setEnabled(False)
    assert button.grab().toImage().pixelColor(10, 10).name() == themes.THEMES["cyberpunk"]["primary_disabled"]
    themes.apply("ivalice")
    assert themes.colors()["name"] == "Ivalice (FFT)"
    assert "ridge" in _app.styleSheet()
    assert "background-image" not in _app.styleSheet()
    themes.apply("dark")
