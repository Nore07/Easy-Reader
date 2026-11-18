from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest

from quietreader.domain.models import Settings
from quietreader.ui.reader import PageView, python_offset, qt_offset


def test_surrogate_pairs_and_measured_pages(app):
    text = "山间🌲来信\n" * 500
    assert python_offset(text, qt_offset(text, 4)) == 4
    view = PageView()
    view.resize(460, 480)
    view.show()
    view.set_text(text)
    app.processEvents()
    assert view.page_count > 1
    assert view.page_offsets == sorted(set(view.page_offsets))
    assert len(view.page_offsets) == view.page_count
    view.go_page(2)
    anchor = view.offset
    assert anchor > 0
    view.apply_settings(Settings(font_size=32, line_height=2.1))
    assert view.offset == anchor
    assert view.page_offsets[view.page] <= anchor
    if view.page + 1 < view.page_count:
        assert anchor < view.page_offsets[view.page + 1]
    view.close()


def test_text_selection_copy_and_focus_keys(app):
    view = PageView()
    view.set_text("原文🌲\n正文")
    view.selection.setPosition(0)
    view.selection.setPosition(qt_offset(view.text, 4), view.selection.MoveMode.KeepAnchor)
    view.copy()
    assert app.clipboard().text() == "原文🌲\n"
    turns = []
    view.turned.connect(turns.append)
    QTest.keyClick(view, Qt.Key.Key_PageDown)
    assert turns == [1]


def test_internal_epub_link_is_activated_when_its_text_is_clicked(app):
    view = PageView()
    view.resize(500, 220)
    link = type("Link", (), {"start": 5, "end": 12, "path": "Text/notes.xhtml", "fragment": "note-1"})()
    view.set_text("Read footnote now")
    view.links = [link]
    view.show()
    app.processEvents()
    assert hasattr(view, "link_activated")
    activated = []
    view.link_activated.connect(activated.append)

    block = view.document.begin()
    line = block.layout().lineAt(0)
    x = view.settings.padding + line.cursorToX(qt_offset(view.text, 8))[0]
    y = view.settings.padding + line.y() + line.height() / 2
    QTest.mouseClick(view, Qt.MouseButton.LeftButton, pos=QPoint(round(x), round(y)))

    assert activated == [link]
    view.close()


def test_paragraph_spacing_is_not_multiplied_by_relayout(app):
    view = PageView()
    view.resize(650, 600)
    view.set_text("山林里的清晨。\n" * 100)
    before = view.document.documentLayout().blockBoundingRect(view.document.begin()).height()
    view.reflow()
    after = view.document.documentLayout().blockBoundingRect(view.document.begin()).height()
    assert after == before
    assert before < 60
