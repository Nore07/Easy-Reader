"""Exercise the local bookshelf lifecycle in a native Qt window."""
import json
from pathlib import Path
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))

from PySide6.QtWidgets import QApplication

from quietreader.content.local import load_book
from quietreader.library.shelf import UNCLASSIFIED
from quietreader.persistence.store import StateStore
from quietreader.ui.window import MainWindow


def main():
    app = QApplication([])
    app.setQuitOnLastWindowClosed(False)
    with tempfile.TemporaryDirectory(prefix="quietreader-shelf-") as temp:
        folder = Path(temp)
        data = folder / "app-data"
        original = folder / "示例书.txt"
        original.write_text("第一章\n书架操作与阅读状态迁移。\n第二章\n原始文件保留。", encoding="utf-8")
        window = MainWindow(StateStore(data), enable_system=False)
        window.resize(900, 680)
        window.show()
        app.processEvents()

        window.add_book_paths([original])
        record = window.store.state["books"][0]
        managed = Path(record["path"])
        assert managed.is_file() and managed.parent == window.shelf_manager.unclassified
        assert original.is_file() and window.shelf.all_books.count() == 1

        window._loaded(load_book(managed))
        window.open_section(0, 4)
        window.add_bookmark()
        old_id = window.book.id
        assert window.create_shelf_category("小说") is not None
        window.move_shelf_book(old_id, "小说")
        moved_id = window.book.id
        assert Path(window.book.path).parent == window.shelf_manager.category_path("小说")
        assert window.store.state["positions"][moved_id]["offset"] == 4
        assert window.store.state["bookmarks"][moved_id]
        assert original.is_file()

        window.delete_shelf_category("小说", delete_books=False)
        unclassified_id = window.book.id
        assert Path(window.book.path).parent == window.shelf_manager.unclassified
        assert window.store.state["positions"][unclassified_id]["offset"] == 4
        assert window.store.state["bookmarks"][unclassified_id]
        assert window.shelf_manager.category_for_path(window.book.path) == UNCLASSIFIED

        window.create_shelf_category("待删除")
        window.move_shelf_book(unclassified_id, "待删除")
        deleted_id = window.book.id
        deleted_copy = Path(window.book.path)
        window.delete_shelf_category("待删除", delete_books=True)
        assert not deleted_copy.exists() and original.is_file()
        assert window.book is None
        assert deleted_id not in window.store.state["positions"]
        assert deleted_id not in window.store.state["bookmarks"]
        assert not window.store.state["books"]

        state_path = data / "state.json"
        window.shutdown()
        saved = json.loads(state_path.read_text(encoding="utf-8"))
        assert saved["books"] == []
    print("Bookshelf add, copy, move, category deletion and state remapping: PASS")


if __name__ == "__main__":
    main()
