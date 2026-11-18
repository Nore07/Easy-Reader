"""Native Windows verification of language, captured keys and text-only focus."""
from dataclasses import replace
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QScrollArea, QWidget

from quietreader.domain.models import Settings
from quietreader.persistence.store import StateStore
from quietreader.ui.settings import SettingsDialog
from quietreader.ui.window import MainWindow


def loaded(app, window):
    end = time.monotonic() + 10
    while window.loading and time.monotonic() < end:
        app.processEvents()
        QTest.qWait(20)
    assert window.book and not window.loading


def main():
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    output = Path("artifacts")
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="quietreader-focus-") as temp:
        folder = Path(temp)
        book = folder / "山间来信.txt"
        book.write_text("第一章 山间来信\n" + "晨光落在书页上，风穿过安静的山林。\n" * 500, encoding="utf-8")
        window = MainWindow(StateStore(folder / "state"), enable_system=True)
        window.show()
        window.load_path(book)
        loaded(app, window)
        dialog = SettingsDialog(replace(window.settings, language="en"), window)
        dialog.fields["opacity"].setValue(0)
        dialog.show()
        dialog.set_text_color(QColor("#cc3366"))
        QTest.qWait(100)
        dialog.grab().save(str(output / "english-preferences.png"))
        dialog.findChild(QScrollArea).verticalScrollBar().setValue(10000)
        QTest.qWait(50)
        dialog.grab().save(str(output / "english-keybindings.png"))
        QTimer.singleShot(40, lambda: QTest.keyClick(app.activeModalWidget(), Qt.Key.Key_J, Qt.KeyboardModifier.ControlModifier))
        dialog.fields["next_key"].click()
        assert dialog.fields["next_key"].sequence == "Ctrl+J"
        dialog.fields["previous_key"].set_sequence("Ctrl+K")
        dialog.fields["focus_key"].set_sequence("F8")
        dialog.language.setCurrentIndex(dialog.language.findData("zh_CN"))
        assert dialog.windowTitle() == "阅读配置 · QuietReader"
        assert dialog.fields["next_key"].sequence == "Ctrl+J"
        dialog.grab().save(str(output / "chinese-keybindings.png"))
        dialog.language.setCurrentIndex(dialog.language.findData("en"))
        dialog.accept()
        window.apply_settings(dialog.values())
        window.reveal()
        QTest.qWait(100)
        assert window.open_button.text() == "Add books"
        assert window.config_button.text() == "Configuration"
        QTest.keyClick(window.reader, Qt.Key.Key_J, Qt.KeyboardModifier.ControlModifier)
        assert window.reader.page == 1
        anchor = window.reader.offset
        window.grab().save(str(output / "english-reader.png"))
        QTest.mouseClick(window.focus_button, Qt.MouseButton.LeftButton)
        QTest.qWait(100)
        assert window.focus_mode and window.reader.hasFocus(), (window.focus_mode, window.reader.hasFocus(), app.activeWindow())
        assert window.reader.offset == anchor
        keep_visible = (window.surface, window.main_pages, window.reader_page, window.reader)
        assert all(not w.isVisible() for w in window.findChildren(QWidget) if w not in keep_visible)
        point = window.reader.mapTo(window, QPoint(1, 1))
        assert window.grab().toImage().pixelColor(point).alpha() == 0
        window.grab().save(str(output / "focus-text-only.png"))
        QTest.keyClick(window.reader, Qt.Key.Key_J, Qt.KeyboardModifier.ControlModifier)
        anchor = window.reader.offset
        QTest.keyClick(window.reader, Qt.Key.Key_Escape)
        QTest.qWait(50)
        assert not window.focus_mode
        assert window.reader.offset == anchor
        QTest.keyClick(window.reader, Qt.Key.Key_F8)
        QTest.qWait(50)
        assert window.focus_mode
        tray_exit = False
        if window.tray:
            assert window.tray_focus_action.text() == "Exit focus mode"
            window.tray_focus_action.trigger()
            tray_exit = True
        else:
            QTest.keyClick(window.reader, Qt.Key.Key_F8)
        assert not window.focus_mode
        window.save_state()
        window.shutdown()
        again = MainWindow(StateStore(folder / "state"), enable_system=False)
        again.show()
        again.restore_last()
        loaded(app, again)
        assert again.settings.language == "en"
        assert again.settings.text_color == "#cc3366"
        assert again.settings.next_key == "Ctrl+J"
        assert again.reader.offset == anchor
        assert not again.focus_mode
        again.resize(470, 600)
        QTest.qWait(100)
        again.grab().save(str(output / "compact-english.png"))
        again.shutdown()
    print(f"Language switching, physical key capture, custom text color, text-only focus, keyboard exit, tray exit={tray_exit}, restart: PASS")


if __name__ == "__main__":
    main()
