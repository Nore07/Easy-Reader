"""Check native preference themes and wheel scrolling without editing values."""
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QAbstractSpinBox

from quietreader.domain.models import Settings
from quietreader.persistence.store import StateStore
from quietreader.ui.settings import SettingsDialog
from quietreader.ui.theme import colors
from quietreader.ui.window import MainWindow


def main():
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    output = Path("artifacts")
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="quietreader-preferences-") as temp:
        window = MainWindow(StateStore(Path(temp)), enable_system=False)
        window.apply_settings(Settings(theme="dark", language="zh_CN", floating=True, opacity=0, background_color="#ffffff", text_color="#ffffff"))
        window.show()
        dialog = SettingsDialog(window.settings, window)
        dialog.show()
        QTest.qWait(100)
        assert dialog.scroll.widget().grab().toImage().pixelColor(1, 1).name() == colors("dark")["paper"]
        dialog.grab().save(str(output / "preferences-dark-zh.png"))
        fields = [dialog.language, dialog.theme, dialog.font] + [field for field in dialog.fields.values() if isinstance(field, QAbstractSpinBox)]
        for field in fields:
            field.setFocus()
            dialog.scroll.ensureWidgetVisible(field)
            app.processEvents()
            before = field.value() if isinstance(field, QAbstractSpinBox) else field.currentIndex()
            previous_scroll = dialog.scroll.verticalScrollBar().value()
            center = field.rect().center()
            event = QWheelEvent(QPointF(center), QPointF(field.mapToGlobal(center)), QPoint(), QPoint(0, -120), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.ScrollUpdate, False)
            app.sendEvent(field, event)
            app.processEvents()
            assert (field.value() if isinstance(field, QAbstractSpinBox) else field.currentIndex()) == before
            bar = dialog.scroll.verticalScrollBar()
            assert bar.value() > previous_scroll or previous_scroll == bar.maximum(), (type(field).__name__, previous_scroll, bar.value(), bar.maximum())
        dialog.language.setCurrentIndex(dialog.language.findData("en"))
        dialog.scroll.verticalScrollBar().setValue(0)
        QTest.qWait(50)
        dialog.grab().save(str(output / "preferences-dark-en.png"))
        dialog.theme.setCurrentIndex(dialog.theme.findData("light"))
        QTest.qWait(50)
        assert dialog.scroll.widget().grab().toImage().pixelColor(1, 1).name() == colors("light")["paper"]
        dialog.grab().save(str(output / "preferences-light-preview.png"))
        assert window.settings.theme == "dark"
        size = dialog.fields["font_size"]
        previous = size.value()
        QTest.keyClick(size, Qt.Key.Key_Up)
        assert size.value() == previous + 1
        dialog.reject()
        window.shutdown()
    print("Native dark preferences, English layout, live theme preview, wheel scroll without edits and keyboard edits: PASS")


if __name__ == "__main__":
    main()
