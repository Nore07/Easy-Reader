"""Verify semantic EPUB formatting in a native Windows Qt reading window."""
from pathlib import Path
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / "src"), str(root / "tests")]

from PySide6.QtGui import QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QApplication

from quietreader.content.local import load_book
from quietreader.persistence.store import StateStore
from quietreader.ui.reader import qt_offset
from quietreader.ui.window import MainWindow
from test_epub_formatting import _semantic_epub


def formatted_at(view, sample, start_at=0):
    start = view.text.index(sample, start_at)
    cursor = QTextCursor(view.document)
    cursor.setPosition(qt_offset(view.text, start))
    cursor.setPosition(qt_offset(view.text, start + len(sample)), QTextCursor.MoveMode.KeepAnchor)
    return cursor


def main():
    if sys.platform != "win32":
        raise SystemExit("Windows only")
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    output = root / "artifacts"
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="quietreader-format-") as temp:
        folder = Path(temp)
        path = folder / "semantic.epub"
        _semantic_epub(path)
        window = MainWindow(StateStore(folder / "state"), enable_system=False)
        window.resize(1000, 720)
        window.show()
        window._loaded(load_book(path))
        app.processEvents()
        view = window.reader
        assert formatted_at(view, "加粗").charFormat().fontWeight() >= QFont.Weight.Bold
        assert formatted_at(view, "斜体").charFormat().fontItalic()
        assert formatted_at(view, "删除").charFormat().fontStrikeOut()
        assert formatted_at(view, "print(1)").charFormat().font().family() == "Consolas"
        assert formatted_at(view, "2", view.text.index("print(1)")).charFormat().verticalAlignment() == QTextCharFormat.VerticalAlignment.AlignSuperScript
        for page in range(view.page_count):
            view.go_page(page)
            app.processEvents()
            window.grab().save(str(output / f"epub-semantic-formatting-page-{page + 1}.png"))
        window.shutdown()
    print("EPUB heading, emphasis, list, quote, code and scripts: PASS")


if __name__ == "__main__":
    main()
