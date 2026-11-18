"""Check EPUB metadata, cover, bookmark notes and position restore in a native Qt window."""
from pathlib import Path
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / "src"), str(root / "tests")]

from PySide6.QtWidgets import QApplication

from quietreader.content.local import load_book
from quietreader.persistence.store import StateStore
from quietreader.ui.window import MainWindow
from test_epub_library import _metadata_epub, _png


def main():
    if sys.platform != "win32":
        raise SystemExit("Windows only")
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    output = root / "artifacts"
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="quietreader-library-") as temp:
        folder = Path(temp)
        path = folder / "metadata.epub"
        path.write_bytes(_metadata_epub("epub3", _png()))
        book = load_book(path)
        store = StateStore(folder / "state")
        window = MainWindow(store, enable_system=False)
        window.resize(1000, 720)
        window.show()
        window._loaded(book)
        app.processEvents()

        assert window.book_info.cover_image is not None
        assert "静读出版社" in window.book_info.details.text()
        assert window.tabs.isTabVisible(4) and window.tabs.isTabVisible(5)
        window.tabs.setCurrentIndex(5)
        app.processEvents()
        window.grab().save(str(output / "epub-book-info.png"))

        window.open_section(0, 2)
        window.add_bookmark()
        window.set_bookmark_note(0, "稍后复查这里")
        window.save_state()
        assert window.bookmarks.count() == 1
        assert "稍后复查这里" in window.bookmarks.item(0).text()
        window.tabs.setCurrentIndex(4)
        app.processEvents()
        window.grab().save(str(output / "epub-bookmarks.png"))
        window.shutdown()

        reopened = MainWindow(StateStore(folder / "state"), enable_system=False)
        reopened.show()
        reopened._loaded(book)
        assert reopened.bookmarks.count() == 1
        reopened.open_section(0, 0)
        reopened._bookmark_activated(reopened.bookmarks.item(0))
        assert reopened.reader.offset == 2
        reopened.bookmarks.setCurrentRow(0)
        reopened.remove_bookmark()
        reopened.save_state()
        assert not StateStore(folder / "state").state["bookmarks"]
        reopened.shutdown()
    print("EPUB metadata, cover, bookmark notes, restore and delete: PASS")


if __name__ == "__main__":
    main()
