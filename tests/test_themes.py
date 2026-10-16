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
    assert themes.colors()["success"] in step_markup({"stage": 6})
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
        ]:
            a, b = sorted((luminance(palette[foreground]), luminance(palette[background])))
            assert (b + 0.05) / (a + 0.05) >= 4.5, (key, foreground, background)
    themes.apply("unknown")
    assert themes.colors() == themes.THEMES["dark"]
