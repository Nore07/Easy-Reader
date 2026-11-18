"""Exercise native desktop sampling against an app-owned solid-color window."""
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from quietreader.desktop.color_picker import capture_screens
from quietreader.domain.models import Book, Section, Settings
from quietreader.persistence.store import StateStore
from quietreader.ui.settings import SettingsDialog
from quietreader.ui.window import MainWindow


def main():
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    output = Path("artifacts")
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="quietreader-background-") as temp:
        backdrop = QWidget()
        backdrop.setStyleSheet("background: #3498db;")
        rect = app.primaryScreen().availableGeometry()
        backdrop.setGeometry(rect)
        backdrop.show()
        window = MainWindow(StateStore(Path(temp)), enable_system=False)
        window.show()
        window._loaded(Book("background", "background.txt", "取色测试", sections=[Section("one", "第一章", "清晨的风穿过树林，落在安静的书页上。\n" * 30)]))
        dialog = SettingsDialog(window.settings, window)
        chosen = []
        expected = []
        errors = []
        dialog.picker.selected.connect(lambda color: chosen.append(color.name()))
        dialog.picker.failed.connect(errors.append)

        def select():
            try:
                point = backdrop.mapToGlobal(QPoint(120, 120))
                overlay = next(o for o in dialog.picker.overlays if o.geometry().contains(point))
                expected.append(overlay.sample.color_at(point).name())
                QTest.mouseClick(overlay, Qt.MouseButton.LeftButton, pos=point - overlay.geometry().topLeft())
            except Exception as error:
                errors.append(type(error).__name__)
                dialog.picker.cancel()
            dialog.accept()

        QTimer.singleShot(80, dialog.picker.begin)
        QTimer.singleShot(600, select)
        assert dialog.exec() == QDialog.DialogCode.Accepted
        assert not errors, errors
        assert chosen == expected, (chosen, expected)
        assert window.windowOpacity() == 1
        assert dialog.values().background_color == expected[0]
        window.apply_settings(Settings(opacity=0, background_color=expected[0]))
        window.toggle_focus()
        QTest.qWait(100)
        point = window.reader.mapTo(window, QPoint(1, 1))
        assert window.grab().toImage().pixelColor(point).alpha() == 0
        local_points = [QPoint(24, 24), QPoint(window.width() - 48, 48)]
        screen_points = [window.mapToGlobal(point) for point in local_points]

        def desktop_color(global_point):
            samples = capture_screens()
            screen = next(sample for sample in samples if sample.geometry.contains(global_point))
            return screen.color_at(global_point).name()

        window.hide()
        QTest.qWait(80)
        before_samples = capture_screens()
        before = []
        for screen_point in screen_points:
            screen = next(sample for sample in before_samples if sample.geometry.contains(screen_point))
            before.append(screen.color_at(screen_point).name())
        window.show()
        window.raise_()
        window.activateWindow()
        QTest.qWait(100)
        after_samples = capture_screens()
        after = []
        for screen_point in screen_points:
            screen = next(sample for sample in after_samples if sample.geometry.contains(screen_point))
            after.append(screen.color_at(screen_point).name())
        assert after == before == ["#3498db"] * len(local_points), f"Transparent desktop composite mismatch: before={before}, after={after}"
        window.grab().save(str(output / "transparent-focus.png"))
        window.apply_settings(Settings(opacity=0.5, background_color="#112233"))
        QTest.qWait(100)
        half_alpha = desktop_color(screen_points[0])
        assert half_alpha not in ("#3498db", "#112233"), half_alpha
        window.apply_settings(Settings(opacity=1, background_color=expected[0]))
        QTest.qWait(100)
        assert desktop_color(screen_points[0]) == expected[0]
        window.grab().save(str(output / "picked-background.png"))
        window.save_state()
        assert StateStore(Path(temp)).state["settings"]["background_color"] == expected[0]
        window.toggle_focus()
        cancel_dialog = SettingsDialog(window.settings, window)

        def cancel():
            cancel_dialog.picker.cancel()
            cancel_dialog.reject()

        QTimer.singleShot(80, cancel_dialog.picker.begin)
        QTimer.singleShot(500, cancel)
        assert cancel_dialog.exec() == QDialog.DialogCode.Rejected
        assert window.windowOpacity() == 1
        window.shutdown()
        backdrop.close()
    print("Native desktop sampling, modal selection/cancel, focus transparency and color persistence: PASS")


if __name__ == "__main__":
    main()
