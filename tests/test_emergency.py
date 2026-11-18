import ctypes
from ctypes import wintypes

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from quietreader.desktop.hotkey import GlobalHotkey
from quietreader.domain.models import Settings
from quietreader.keys import binding_error
from quietreader.persistence.store import StateStore
from quietreader.ui.settings import SettingsDialog
from quietreader.ui.window import MainWindow


def test_emergency_binding_saved_and_conflicts_checked(tmp_path):
    settings = Settings.from_dict({"emergency_key": "Ctrl+Shift+Q"})
    assert settings.emergency_key == "Ctrl+Shift+Q"
    store = StateStore(tmp_path)
    store.state["settings"] = settings.to_dict()
    store.save()
    assert StateStore(tmp_path).state["settings"]["emergency_key"] == "Ctrl+Shift+Q"
    values = settings.to_dict()
    values["emergency_key"] = values["hotkey"]
    assert binding_error(values)
    values.update(hotkey="Return", emergency_key="Enter")
    assert binding_error(values)
    legacy = Settings.from_dict({"next_key": "Ctrl+Alt+Q"})
    assert legacy.next_key == "Ctrl+Alt+Q"
    assert legacy.emergency_key != legacy.next_key


def test_emergency_quits_despite_close_to_tray_without_waiting(app, tmp_path, monkeypatch):
    exits = []
    monkeypatch.setattr("quietreader.ui.window.os._exit", exits.append)
    window = MainWindow(StateStore(tmp_path), enable_system=False)
    window.show()
    window.pool.waitForDone = lambda *args: (_ for _ in ()).throw(AssertionError("must not wait"))
    window.emergency_exit()
    assert exits == [0]
    assert window.closed and window.quitting
    assert not window.isVisible()
    assert window.store.path.exists()


def test_local_keys_work_and_emergency_still_exits_on_save_failure(app, tmp_path, monkeypatch):
    exits = []
    monkeypatch.setattr("quietreader.ui.window.os._exit", exits.append)
    window = MainWindow(StateStore(tmp_path), enable_system=False)
    window.show()
    window.activateWindow()
    app.processEvents()
    QTest.keyClick(window.reader, Qt.Key.Key_R, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
    assert window.isMinimized()
    window.reveal()
    window.save_state = lambda: (_ for _ in ()).throw(OSError("disk unavailable"))
    QTest.keyClick(window.reader, Qt.Key.Key_Q, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
    assert exits == [0]
    assert not window.isVisible()


def test_global_hotkeys_dispatch_distinct_actions(app):
    calls = []
    first = GlobalHotkey(app, lambda: calls.append("visibility"), identifier=0x5152)
    second = GlobalHotkey(app, lambda: calls.append("exit"), identifier=0x5153)
    # Exercise native dispatch without reserving keys in the user's session.
    first.registered = second.registered = True
    message = wintypes.MSG()
    message.message = 0x0312
    message.wParam = 0x5153
    assert not first.nativeEventFilter(None, ctypes.addressof(message))[0]
    assert second.nativeEventFilter(None, ctypes.addressof(message))[0]
    assert calls == ["exit"]
    first.registered = second.registered = False
    first.close()
    second.close()


def test_preferences_offer_recordable_emergency_key(app):
    dialog = SettingsDialog(Settings(language="en"))
    assert dialog.fields["emergency_key"].sequence == "Ctrl+Alt+Q"
    assert dialog.values().emergency_key == "Ctrl+Alt+Q"


def test_global_shortcuts_pause_only_during_capture(app, tmp_path, monkeypatch):
    from PySide6.QtCore import QTimer
    calls = []

    class Hotkey:
        def configure(self, enabled, key):
            calls.append(enabled)
            return ""

        def close(self):
            pass

    window = MainWindow(StateStore(tmp_path), enable_system=False)
    window.hotkey = Hotkey()
    window.emergency_hotkey = Hotkey()
    window.apply_settings(Settings(global_hotkey=True))
    window.show()
    calls.clear()
    recorded = []

    def edit():
        dialog = app.activeModalWidget()

        def press():
            recorded.extend(calls[-2:])
            QTest.keyClick(app.activeModalWidget(), Qt.Key.Key_Q, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)

        QTimer.singleShot(20, press)
        dialog.fields["emergency_key"].click()
        dialog.accept()

    QTimer.singleShot(20, edit)
    window.show_settings()
    assert recorded == [False, False]
    assert calls[-2:] == [True, True]
    window.shutdown()
