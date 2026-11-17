"""Real Qt window smoke test. Output is generated locally and never versioned."""
import argparse
import ctypes
import json
from pathlib import Path
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox

from quietreader.domain.models import Settings
from quietreader.persistence.store import StateStore
from quietreader.ui.settings import SettingsDialog
from quietreader.ui.window import MainWindow


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    with tempfile.TemporaryDirectory(prefix="quietreader-test-") as folder:
        directory = Path(folder)
        file = directory / "山间来信.txt"
        text = "清晨，山林从一阵风里醒来。窗外的光越过枝叶，在桌上投下细碎的影子。\n\n一本书安静地摊开，像一条还没有走完的小路。沿着字句往前，时间也慢了下来。\n\n"
        file.write_text("第一章 山间来信\n" + text * 100 + "\n第二章 慢慢归途\n风吹过书页。", encoding="utf-8")
        store = StateStore(directory / "state")
        window = MainWindow(store, enable_system=True)
        window.show()
        QTest.qWait(150)
        window.grab().save(str(args.output / "welcome.png"))
        window.load_path(file)
        deadline = time.monotonic() + 15
        while window.loading and time.monotonic() < deadline:
            app.processEvents()
            QTest.qWait(20)
        assert window.book and not window.loading
        assert window.reader.page_count > 1
        window.reader.setFocus()
        QTest.keyClick(window.reader, Qt.Key.Key_PageDown)
        app.processEvents()
        assert window.reader.page == 1
        anchor = window.reader.offset
        window.grab().save(str(args.output / "reader.png"))
        dialog = SettingsDialog(window.settings, window)
        dialog.show()
        QTest.qWait(100)
        dialog.grab().save(str(args.output / "settings.png"))
        dialog.reject()
        window.apply_settings(Settings(theme="dark", floating=True, opacity=0.8, font_size=22))
        window.resize(470, 600)
        QTest.qWait(150)
        app.processEvents()
        assert window.reader.offset == anchor
        window.grab().save(str(args.output / "floating.png"))
        tray_available = window.tray is not None
        if tray_available:
            window.hide_or_minimize()
            assert not window.isVisible()
            window.toggle_visible()
            assert window.isVisible()
        hotkey_registered = False
        hotkey_dispatch = False
        if window.hotkey:
            error = window.hotkey.configure(True, "Ctrl+Alt+R")
            hotkey_registered = not error
            if hotkey_registered and sys.platform == "win32" and tray_available:
                thread = ctypes.windll.kernel32.GetCurrentThreadId()
                ctypes.windll.user32.PostThreadMessageW(thread, 0x0312, window.hotkey.ID, 0)
                QTest.qWait(100)
                app.processEvents()
                assert not window.isVisible()
                ctypes.windll.user32.PostThreadMessageW(thread, 0x0312, window.hotkey.ID, 0)
                QTest.qWait(100)
                app.processEvents()
                assert window.isVisible()
                hotkey_dispatch = True
            window.hotkey.configure(False, "Ctrl+Alt+R")
        window.save_state()
        window.shutdown()
        again = MainWindow(StateStore(directory / "state"), enable_system=False)
        again.show()
        again.restore_last()
        deadline = time.monotonic() + 15
        while again.loading and time.monotonic() < deadline:
            app.processEvents()
            QTest.qWait(20)
        assert again.book and again.reader.offset == anchor
        again.shutdown()
        report = {"import": True, "paging": True, "reflow_anchor": True, "restart_anchor": True, "tray_available": tray_available, "global_hotkey_registration": hotkey_registered, "native_hotkey_dispatch": hotkey_dispatch, "qt_platform": app.platformName()}
        (args.output / "gui-smoke.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
