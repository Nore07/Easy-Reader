from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QWidget

from quietreader.desktop.color_picker import DesktopColorPicker, ScreenSample
from quietreader.domain.models import Book, Section, Settings
from quietreader.persistence.store import StateStore
from quietreader.ui.settings import SettingsDialog
from quietreader.ui.theme import colors
from quietreader.ui.window import MainWindow


def sample():
    image = QImage(800, 600, QImage.Format.Format_RGB32)
    image.fill(QColor("#123456"))
    image.setPixelColor(400, 200, QColor("#abcdef"))
    return ScreenSample(image, QRect(-400, 100, 400, 300))


def test_picker_scaled_screen_negative_coordinates():
    screen = sample()
    assert screen.color_at(QPoint(-200, 200)).name() == "#abcdef"
    assert not screen.color_at(QPoint(0, 200)).isValid()


def test_picker_selection_and_cancel_restore_windows(app):
    main = QWidget()
    main.show()
    owner = QDialog(main)
    owner.show()
    picker = DesktopColorPicker(owner, capture=lambda: [sample()])
    selected = []
    picker.selected.connect(lambda color: selected.append(color.name()))
    picker.begin()
    assert owner.windowOpacity() == 0
    QTest.qWait(250)
    assert len(picker.overlays) == 1
    QTest.mouseClick(picker.overlays[0], Qt.MouseButton.LeftButton, pos=QPoint(200, 100))
    assert selected == ["#abcdef"]
    assert owner.windowOpacity() == 1
    assert main.windowOpacity() == 1
    assert not picker.overlays
    picker.begin()
    QTest.qWait(250)
    QTest.keyClick(picker.overlays[0], Qt.Key.Key_Escape)
    assert selected == ["#abcdef"]
    assert owner.windowOpacity() == 1
    owner.close()
    main.close()


def test_focus_mode_uses_transparency_color_and_overlay_controls(app, tmp_path):
    window = MainWindow(StateStore(tmp_path), enable_system=False)
    window.show()
    window._loaded(Book("test", "unused.txt", "Test", sections=[Section("one", "One", "Text " * 100)]))
    window.apply_settings(Settings(opacity=0))
    window.toggle_focus()
    app.processEvents()
    point = window.reader.mapTo(window, QPoint(1, 1))
    assert window.grab().toImage().pixelColor(point).alpha() == 0
    assert window.windowOpacity() == 1
    assert window.focus_mode
    assert not hasattr(window, "float_button")
    window.apply_settings(Settings(background_color="#111111", opacity=1, always_on_top=True))
    point = window.reader.mapTo(window, QPoint(1, 1))
    assert window.grab().toImage().pixelColor(point).name() == "#111111"
    assert window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    assert colors("light", "#111111")["ink"] == "#f5f5f5"
    window.toggle_focus()
    window.shutdown()


def test_settings_choose_reset_and_zero_opacity(app):
    dialog = SettingsDialog(Settings())
    dialog.fields["opacity"].setValue(0)
    dialog.set_background_color(QColor("#efabcd"))
    assert dialog.values().background_color == "#efabcd"
    assert dialog.values().opacity == 0
    dialog.reset_defaults()
    assert dialog.values().background_color == ""
    assert dialog.values().opacity == Settings().opacity


def test_capture_failure_and_early_cancel_restore_owner(app):
    owner = QDialog()
    owner.show()
    picker = DesktopColorPicker(owner, capture=lambda: [])
    errors = []
    picker.failed.connect(errors.append)
    picker.begin()
    QTest.qWait(250)
    assert errors
    assert owner.windowOpacity() == 1
    assert not picker.active
    errors.clear()
    picker.begin()
    picker.cancel()
    QTest.qWait(250)
    assert not errors
    assert not picker.overlays
    assert owner.windowOpacity() == 1
    owner.close()
