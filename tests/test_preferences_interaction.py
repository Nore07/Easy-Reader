import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QPalette, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractSpinBox, QComboBox, QScrollArea

from quietreader.domain.models import Settings
from quietreader.persistence.store import StateStore
from quietreader.ui.settings import SettingsDialog
from quietreader.ui.theme import colors
from quietreader.ui.window import MainWindow


def send_wheel(app, widget):
    point = widget.rect().center()
    event = QWheelEvent(QPointF(point), QPointF(widget.mapToGlobal(point)), QPoint(), QPoint(0, -120), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.ScrollUpdate, False)
    app.sendEvent(widget, event)
    app.processEvents()


@pytest.mark.parametrize("theme", ["dark", "light", "sepia"])
def test_preferences_background_matches_theme_independently(app, tmp_path, theme):
    window = MainWindow(StateStore(tmp_path), enable_system=False)
    window.apply_settings(Settings(theme=theme, floating=True, opacity=0, background_color="#ffffff", text_color="#ffffff"))
    window.show()
    dialog = SettingsDialog(window.settings, window)
    dialog.show()
    app.processEvents()
    scroll = dialog.findChild(QScrollArea)
    expected = colors(theme)
    assert scroll.widget().grab().toImage().pixelColor(1, 1).name() == expected["paper"]
    assert scroll.viewport().palette().color(QPalette.ColorRole.Window).name() == expected["paper"]
    assert dialog.title.palette().color(QPalette.ColorRole.WindowText).name() == expected["ink"]
    dialog.theme.setCurrentIndex(dialog.theme.findData("light" if theme == "dark" else "dark"))
    app.processEvents()
    changed = colors(dialog.theme.currentData())
    assert scroll.widget().grab().toImage().pixelColor(1, 1).name() == changed["paper"]
    assert window.settings.theme == theme
    dialog.reject()
    window.shutdown()


@pytest.mark.parametrize("focused", [False, True])
def test_wheel_scrolls_preferences_without_changing_controls(app, focused):
    dialog = SettingsDialog(Settings(language="zh_CN"))
    dialog.resize(710, 500)
    dialog.show()
    app.processEvents()
    scroll = dialog.findChild(QScrollArea)
    assert scroll.verticalScrollBar().maximum() > 0
    fields = [dialog.language, dialog.theme] + [field for field in dialog.fields.values() if isinstance(field, QAbstractSpinBox)]
    for field in fields:
        if focused:
            field.setFocus()
        else:
            dialog.buttons.setFocus()
        app.processEvents()
        getter = field.value if isinstance(field, QAbstractSpinBox) else field.currentIndex
        before = getter()
        targets = [field]
        if field.lineEdit():
            targets.append(field.lineEdit())
        for target in targets:
            scroll.ensureWidgetVisible(field)
            app.processEvents()
            old_scroll = scroll.verticalScrollBar().value()
            send_wheel(app, target)
            assert getter() == before, field
            assert scroll.verticalScrollBar().value() > old_scroll, field
    dialog.reject()


def test_explicit_keyboard_edits_still_work(app):
    from quietreader.ui.layout_panel import LayoutPanel
    panel = LayoutPanel(Settings())
    panel.show()
    dialog = SettingsDialog(Settings())
    dialog.show()
    size = panel.fields["font_size"]
    size.setFocus()
    QTest.keyClick(size, Qt.Key.Key_Up)
    assert size.value() == Settings().font_size + 1
    size.lineEdit().selectAll()
    QTest.keyClicks(size.lineEdit(), "24")
    QTest.keyClick(size, Qt.Key.Key_Return)
    assert size.value() == 24
    dialog.theme.setCurrentIndex(0)
    QTest.keyClick(dialog.theme, Qt.Key.Key_Down)
    assert dialog.theme.currentIndex() == 1
    dialog.reject()
    panel.reject()
