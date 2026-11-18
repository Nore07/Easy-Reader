"""Verify EPUB 2/3 navigation against a native Windows Qt window."""
from pathlib import Path
import sys
import tempfile
import time

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / "src"), str(root / "tests")]

from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from quietreader.domain.models import Settings
from quietreader.persistence.store import StateStore
from quietreader.ui.reader import qt_offset
from quietreader.ui.window import MainWindow
from test_content import epub_with_navigation


def wait_loaded(app, window):
    deadline = time.monotonic() + 10
    while window.loading and time.monotonic() < deadline:
        app.processEvents()
        QTest.qWait(20)
    assert window.book and not window.loading


def click_link(view, link):
    position = qt_offset(view.text, link.start + 1)
    block = view.document.findBlock(position)
    line = block.layout().lineForTextPosition(position - block.position())
    x = view.settings.padding + line.cursorToX(position - block.position())[0]
    y = view.settings.padding + view.document.documentLayout().blockBoundingRect(block).top() + line.y() + line.height() / 2
    QTest.mouseClick(view, Qt.MouseButton.LeftButton, pos=QPoint(round(x), round(y)))


def main():
    if sys.platform != "win32":
        raise SystemExit("Windows only")
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    output = root / "artifacts"
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="quietreader-navigation-") as temp:
        folder = Path(temp)
        book_path = folder / "navigation.epub"
        book_path.write_bytes(epub_with_navigation())
        window = MainWindow(StateStore(folder / "state"), enable_system=False)
        window.resize(1120, 820)
        window.show()
        window.load_path(book_path)
        wait_loaded(app, window)

        assert window.chapters.count() == 2
        assert window.pages.count() == 1 and window.reading_tabs.isTabVisible(2)
        assert window.landmarks.count() == 1 and window.reading_tabs.isTabVisible(3)
        note_index = next(i for i, section in enumerate(window.book.sections) if section.source_path == "OEBPS/Text/two.xhtml")
        first = window.book.sections[0]
        click_link(window.reader, first.links[0])
        assert window.section_index == note_index and window.reader.offset == window.book.sections[note_index].anchors["note"]

        window._chapter_activated(window.chapters.item(1))
        assert window.section_index == note_index
        window._page_activated(window.pages.item(0))
        assert "page-12" in window.book.sections[window.section_index].anchors

        window.apply_settings(Settings(next_chapter_key="Alt+J", previous_chapter_key="Alt+K"))
        QTest.keyClick(window.reader, Qt.Key.Key_J, Qt.KeyboardModifier.AltModifier)
        assert window.section_index == note_index
        QTest.keyClick(window.reader, Qt.Key.Key_K, Qt.KeyboardModifier.AltModifier)
        assert window.section_index == 0
        window.turn_chapter(1)
        assert window.section_index == note_index
        window.turn_chapter(-1)
        assert window.section_index == 0
        assert window.previous_chapter.isEnabled() is False

        window.reading_tabs.setCurrentIndex(0)
        window.reading_tabs.setCurrentIndex(3)
        QTest.qWait(80)
        window.grab().save(str(output / "epub-page-list.png"))
        window.reading_tabs.setCurrentIndex(0)
        window.grab().save(str(output / "epub-hierarchical-toc.png"))
        window.shutdown()
    print("EPUB3 nested TOC, internal links, page-list, chapter buttons and configurable keys: PASS")


if __name__ == "__main__":
    main()
