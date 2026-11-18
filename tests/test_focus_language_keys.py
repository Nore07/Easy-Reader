import ctypes
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from quietreader.domain.models import Book, Section, Settings
from quietreader.keys import normalize_binding, windows_hotkey
from quietreader.i18n import tr
from quietreader.desktop import window_effects
from quietreader.persistence.store import StateStore
from quietreader.ui.key_capture import KeyCaptureDialog
from quietreader.ui.settings import SettingsDialog
from quietreader.ui.theme import colors, stylesheet
from quietreader.ui.window import MainWindow


def test_new_preferences_and_arbitrary_bindings_roundtrip(tmp_path):
    settings = Settings.from_dict(dict(text_color="#aBcDef", language="en", next_key="J", previous_key="Ctrl+K", next_chapter_key="Alt+J", previous_chapter_key="Alt+K", focus_key="F8", hotkey="Alt+F9"))
    assert settings.text_color == "#abcdef"
    assert settings.language == "en"
    assert settings.next_key == "J"
    assert settings.previous_key == "Ctrl+K"
    assert settings.next_chapter_key == "Alt+J"
    assert settings.previous_chapter_key == "Alt+K"
    assert settings.focus_key == "F8"
    assert settings.hotkey == "Alt+F9"
    store = StateStore(tmp_path)
    store.state["settings"] = settings.to_dict()
    store.save()
    assert StateStore(tmp_path).state["settings"]["text_color"] == "#abcdef"
    assert Settings.from_dict({"text_color": "red; bad", "language": "xx"}).language == "system"


def test_bindings_reserved_conflicts_and_windows_translation():
    assert normalize_binding("Ctrl+J") == "Ctrl+J"
    assert normalize_binding("Ctrl+K, Ctrl+J") == ""
    assert Settings.from_dict(dict(next_key="Esc")).next_key == "PgDown"
    assert Settings.from_dict(dict(next_key="J", previous_key="J")).next_key == "PgDown"
    assert windows_hotkey("Alt+F9") == (1, 0x78)
    assert windows_hotkey("Ctrl+Alt+Left") == (3, 0x25)


def test_legacy_shortcuts_keep_existing_binding_when_chapter_keys_are_added():
    settings = Settings.from_dict({"next_key": "Ctrl+PgDown", "previous_key": "Ctrl+PgUp"})

    assert settings.next_key == "Ctrl+PgDown"
    assert settings.previous_key == "Ctrl+PgUp"
    assert settings.next_chapter_key != settings.next_key
    assert settings.previous_chapter_key != settings.previous_key


def test_key_capture_physical_keys_and_cancel(app):
    dialog = KeyCaptureDialog("en")
    dialog.show()
    QTest.keyClick(dialog, Qt.Key.Key_J, Qt.KeyboardModifier.ControlModifier)
    assert dialog.result() == dialog.DialogCode.Accepted
    assert dialog.sequence == "Ctrl+J"
    canceled = KeyCaptureDialog("en")
    canceled.show()
    QTest.keyClick(canceled, Qt.Key.Key_Escape)
    assert canceled.result() == canceled.DialogCode.Rejected
    assert canceled.sequence == ""


def test_focus_only_text_escape_and_language_preserve_position(app, tmp_path):
    window = MainWindow(StateStore(tmp_path), enable_system=False)
    window.show()
    book = Book("test", "unused.txt", "原书标题", sections=[Section("one", "第一章", "书籍中的文字。\n" * 400)])
    window._loaded(book)
    window.apply_settings(Settings(language="en", text_color="#ff3355", next_key="J", previous_key="K"))
    assert window.open_button.text() == "Open"
    assert window.book_title.text() == "原书标题"
    QTest.keyClick(window.reader, Qt.Key.Key_J)
    assert window.reader.page == 1
    anchor = window.reader.offset
    window.toggle_focus()
    app.processEvents()
    assert window.focus_mode
    assert window.reader.hasFocus()
    assert all(w.isHidden() for w in window.chrome_widgets)
    assert all(not w.isVisible() for w in window.findChildren(QWidget) if w not in (window.surface, window.reader))
    assert not window.book_title.isVisible()
    assert window.reader.offset == anchor
    rendered = window.grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
    assert bytes((255, 51, 85, 255)) in bytes(rendered.constBits())
    QTest.keyClick(window.reader, Qt.Key.Key_Escape)
    app.processEvents()
    assert not window.focus_mode
    assert window.open_button.isVisible()
    assert window.brand.isVisible()
    assert not window.settings.floating
    assert window.reader.offset == anchor
    window.apply_settings(Settings(language="zh_CN"))
    assert window.open_button.text() == "打开"
    assert window.reader.offset == anchor
    window.shutdown()


def test_focus_restores_floating_preferences_and_does_not_start_focused(app, tmp_path):
    window = MainWindow(StateStore(tmp_path), enable_system=False)
    window.show()
    window._loaded(Book("one", "none.txt", "Test", sections=[Section("one", "One", "Text " * 1000)]))
    settings = Settings(floating=True, opacity=0.25, text_color="#123456", language="en")
    window.apply_settings(settings)
    window.toggle_sidebar()
    assert window.sidebar.isVisible()
    window.toggle_focus()
    window.save_state()
    assert window.store.state["settings"]["opacity"] == 0.25
    window.toggle_focus()
    assert window.settings.floating
    assert window.sidebar.isVisible()
    window.shutdown()
    again = MainWindow(StateStore(tmp_path), enable_system=False)
    assert not again.focus_mode
    assert again.settings.opacity == 0.25
    again.shutdown()


def test_focus_suppresses_native_window_border_and_restores_it(app, tmp_path, monkeypatch):
    import quietreader.ui.window as window_module

    calls = []
    monkeypatch.setattr(
        window_module,
        "set_window_border_hidden",
        lambda target, hidden: calls.append((target, hidden)),
        raising=False,
    )
    window = MainWindow(StateStore(tmp_path), enable_system=False)
    window.show()
    window._loaded(Book("one", "none.txt", "Test", sections=[Section("one", "One", "Text " * 100)]))

    window.toggle_focus()
    assert calls[-1] == (window, True)
    window.toggle_focus()
    assert calls[-1] == (window, False)

    window.shutdown()


def test_transparent_reader_surface_has_no_inner_frame():
    transparent = stylesheet(colors("dark"), 0)

    assert "QWidget#surface { background: rgba(32,43,40,0); border: none; border-radius: 0; }" in transparent


def test_native_border_helper_hides_and_restores_dwm_border(monkeypatch):
    values = []

    def set_attribute(hwnd, attribute, value, size):
        color = ctypes.cast(value, ctypes.POINTER(ctypes.c_uint32)).contents.value
        values.append((hwnd.value, attribute, color, size))
        return 0

    monkeypatch.setattr(window_effects.sys, "platform", "win32")
    monkeypatch.setattr(
        window_effects.ctypes,
        "windll",
        SimpleNamespace(dwmapi=SimpleNamespace(DwmSetWindowAttribute=set_attribute)),
        raising=False,
    )

    class NativeHandle:
        def winId(self):
            return 0x1234

    class Window:
        def windowHandle(self):
            return NativeHandle()

    window = Window()
    assert window_effects.set_window_border_hidden(window, True)
    assert window_effects.set_window_border_hidden(window, False)
    assert values == [(0x1234, 34, 0xFFFFFFFE, 4), (0x1234, 34, 0xFFFFFFFF, 4)]


def test_recording_button_combination_and_focus_toggle_key(app, tmp_path):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    dialog = SettingsDialog(Settings(language="en"))
    dialog.show()
    QTimer.singleShot(20, lambda: QTest.keyClick(QApplication.activeModalWidget(), Qt.Key.Key_L, Qt.KeyboardModifier.AltModifier))
    dialog.fields["next_key"].click()
    assert dialog.fields["next_key"].sequence == "Alt+L"
    dialog.reject()
    window = MainWindow(StateStore(tmp_path), enable_system=False)
    window.show()
    window._loaded(Book("one", "none.txt", "Test", sections=[Section("one", "One", "Text " * 500)]))
    values = Settings(language="en", next_key="Alt+L", previous_key="K", focus_key="F8")
    window.apply_settings(values)
    QTest.keyClick(window.reader, Qt.Key.Key_L, Qt.KeyboardModifier.AltModifier)
    assert window.reader.page == 1
    QTest.keyClick(window.reader, Qt.Key.Key_F8)
    assert window.focus_mode
    QTest.keyClick(window.reader, Qt.Key.Key_F8)
    assert not window.focus_mode
    window.shutdown()


def test_settings_english_and_custom_text_color(app):
    dialog = SettingsDialog(Settings(language="en"))
    assert dialog.windowTitle() == "Reading preferences · QuietReader"
    dialog.set_text_color(QColor("#112233"))
    assert dialog.values().text_color == "#112233"
    assert dialog.fields["next_key"].sequence == "PgDown"
    assert dialog.fields["next_chapter_key"].sequence == "Ctrl+PgDown"
    assert dialog.fields["previous_chapter_key"].sequence == "Ctrl+PgUp"
    assert tr("打开", "en") == "Open"
    dialog.reset_defaults()
    assert dialog.values().text_color == ""
