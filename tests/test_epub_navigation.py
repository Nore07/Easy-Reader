from types import SimpleNamespace

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QListWidget

from quietreader.domain.models import Book, Section, Settings
from quietreader.persistence.store import StateStore
from quietreader.ui.window import MainWindow


def test_chapter_controls_skip_spine_chunks_and_follow_toc_and_page_links(app, tmp_path):
    def section(identifier, title, text, path, anchors=None):
        value = Section(identifier, title, text)
        value.source_path = path
        value.anchors = anchors or {}
        return value

    sections = [
        section("one:0", "第一章", "开头正文", "Text/one.xhtml", {"start": 0, "printed-7": 3}),
        section("one:1", "第一章 · 续 1", "本章后续", "Text/one.xhtml"),
        section("two:0", "第二章", "第二章的脚注正文", "Text/two.xhtml", {"note": 4}),
    ]
    nested = SimpleNamespace(label="脚注", path="Text/two.xhtml", fragment="note", children=[], source_offset=-1)
    toc = [SimpleNamespace(label="第一章", path="Text/one.xhtml", fragment="start", children=[nested], source_offset=-1)]
    pages = [SimpleNamespace(label="7", path="Text/one.xhtml", fragment="printed-7", children=[], source_offset=-1)]
    landmarks = [SimpleNamespace(label="正文", path="Text/one.xhtml", fragment="start", children=[], source_offset=-1)]
    book = Book("book", "unused.epub", "测试书", sections=sections)
    book.toc = toc
    book.page_list = pages
    book.landmarks = landmarks
    window = MainWindow(StateStore(tmp_path), enable_system=False)
    window.show()
    window._loaded(book)

    assert hasattr(window, "next_chapter")
    assert window.previous_chapter.isEnabled() is False
    assert window.next_chapter.isEnabled()
    assert isinstance(window.pages, QListWidget)
    assert window.tabs.isTabVisible(3)
    assert [window.chapters.item(i).text().strip() for i in range(window.chapters.count())] == ["第一章", "脚注"]
    window._chapter_activated(window.chapters.item(1))
    assert window.section_index == 2
    assert window.reader.offset == 4
    assert window.open_epub_link(SimpleNamespace(path="Text/two.xhtml", fragment="note"))
    assert window.section_index == 2
    assert window.reader.offset == 4

    window._page_activated(window.pages.item(0))
    assert window.section_index == 0
    assert window.reader.offset == 3

    window.turn_chapter(1)
    assert window.section_index == 2
    window.turn_chapter(-1)
    assert window.section_index == 0
    assert not window.previous_chapter.isEnabled()

    window.apply_settings(Settings(next_chapter_key="Alt+J", previous_chapter_key="Alt+K"))
    QTest.keyClick(window.reader, Qt.Key.Key_J, Qt.KeyboardModifier.AltModifier)
    assert window.section_index == 2
    QTest.keyClick(window.reader, Qt.Key.Key_K, Qt.KeyboardModifier.AltModifier)
    assert window.section_index == 0

    window.shutdown()
