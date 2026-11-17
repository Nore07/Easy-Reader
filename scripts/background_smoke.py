"""Exercise native desktop sampling against an app-owned solid-color window."""
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from quietreader.domain.models import Settings
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
        backdrop.setGeometry(rect.x() + 40, rect.y() + 40, 800, 600)
        backdrop.show()
        window = MainWindow(StateStore(Path(temp)), enable_system=False)
        window.show()
        window.reader.set_text("清晨的风穿过树林，落在安静的书页上。\n" * 30)
        dialog = SettingsDialog(window.settings, window)
        chosen = []
        errors = []
        dialog.picker.selected.connect(lambda color: chosen.append(color.name()))
        dialog.picker.failed.connect(errors.append)

        def select():
            try:
                point = backdrop.mapToGlobal(QPoint(120, 120))
                overlay = next(o for o in dialog.picker.overlays if o.geometry().contains(point))
                QTest.mouseClick(overlay, Qt.MouseButton.LeftButton, pos=point - overlay.geometry().topLeft())
            except Exception as error:
                errors.append(type(error).__name__)
                dialog.picker.cancel()
            dialog.accept()

        QTimer.singleShot(80, dialog.picker.begin)
        QTimer.singleShot(600, select)
        assert dialog.exec() == QDialog.DialogCode.Accepted
        assert not errors, errors
        assert chosen == ["#3498db"], chosen
        assert window.windowOpacity() == 1
        assert dialog.values().background_color == "#3498db"
        window.apply_settings(Settings(floating=True, opacity=0, background_color="#3498db"))
        QTest.qWait(100)
        point = window.reader.mapTo(window, QPoint(1, 1))
        assert window.grab().toImage().pixelColor(point).alpha() == 0
        window.grab().save(str(output / "transparent-floating.png"))
        window.apply_settings(Settings(floating=True, opacity=1, background_color="#3498db"))
        QTest.qWait(100)
        window.grab().save(str(output / "picked-background.png"))
        window.save_state()
        assert StateStore(Path(temp)).state["settings"]["background_color"] == "#3498db"
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
    print("Native desktop sampling, modal selection/cancel, zero alpha and color persistence: PASS")


if __name__ == "__main__":
    main()
