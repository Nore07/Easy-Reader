from pathlib import Path

from quietreader.content.local import load_book
from quietreader.library.shelf import UNCLASSIFIED, ShelfManager, book_id_for_path
from quietreader.persistence.store import StateStore
from quietreader.ui.window import MainWindow


def _record(path, title):
    return {"id": book_id_for_path(path), "path": str(path), "title": title, "author": "", "encoding": "", "last_read": ""}


def test_sidebar_splits_reading_and_shelf_and_add_copies_source(app, tmp_path):
    data = tmp_path / "app-data"
    window = MainWindow(StateStore(data), enable_system=False)
    original = tmp_path / "Book.txt"
    original.write_text("第一章\n书架测试正文。", encoding="utf-8")

    window.add_book_paths([original])

    assert [window.tabs.tabText(i) for i in range(window.tabs.count())] == ["阅读", "书架", "资料"]
    assert [window.reading_tabs.tabText(i) for i in range(2)] == ["目录", "书签"]
    assert window.open_button.text() == "添加书籍"
    assert original.exists()
    assert len(window.store.state["books"]) == 1
    record = window.store.state["books"][0]
    assert Path(record["path"]).parent == window.shelf_manager.unclassified
    assert window.shelf.all_books.count() == 1
    assert window.shelf.recent.count() == 0
    window.shutdown()


def test_moving_open_book_remaps_position_bookmarks_and_recent(app, tmp_path):
    data = tmp_path / "app-data"
    window = MainWindow(StateStore(data), enable_system=False)
    source = tmp_path / "Story.txt"
    source.write_text("第一章\n故事内容" * 30, encoding="utf-8")
    managed_path = window.shelf_manager.add_book(source)
    book = load_book(managed_path)
    old_id = book.id
    window.store.state["positions"][old_id] = {"section_id": book.sections[0].id, "offset": 7}
    window.store.state["bookmarks"][old_id] = [{"section_id": book.sections[0].id, "offset": 5, "label": "位置", "note": "线索", "created": ""}]
    window._loaded(book)
    original = Path(source)
    window.create_shelf_category("小说")

    window.move_shelf_book(old_id, "小说")

    new_id = book_id_for_path(book.path)
    assert new_id != old_id
    assert book.id == new_id
    assert Path(book.path).parent == window.shelf_manager.category_path("小说")
    assert original.exists()
    assert old_id not in window.store.state["positions"]
    assert window.store.state["positions"][new_id]["offset"] == 7
    assert window.store.state["bookmarks"][new_id][0]["note"] == "线索"
    assert window.store.state["last_book"] == new_id
    assert window.shelf.all_books.count() == 1
    window.shutdown()


def test_delete_category_and_keep_books_remaps_to_unclassified(app, tmp_path):
    window = MainWindow(StateStore(tmp_path / "app-data"), enable_system=False)
    folder = window.create_shelf_category("历史")
    source = tmp_path / "Old.txt"
    source.write_text("旧书", encoding="utf-8")
    managed = window.shelf_manager.add_book(source)
    managed = window.shelf_manager.move_book(managed, "历史")
    book = load_book(managed)
    old_id = book.id
    window.store.state["positions"][old_id] = {"section_id": book.sections[0].id, "offset": 2}
    window.store.state["bookmarks"][old_id] = [{"section_id": book.sections[0].id, "offset": 1, "label": "留存", "note": "", "created": ""}]
    window._loaded(book)

    window.delete_shelf_category("历史", delete_books=False)

    new_id = book_id_for_path(book.path)
    assert not folder.exists()
    assert Path(book.path).parent == window.shelf_manager.unclassified
    assert book.path != str(managed)
    assert book.id == new_id
    assert window.store.state["positions"][new_id]["offset"] == 2
    assert window.store.state["bookmarks"][new_id][0]["label"] == "留存"
    assert window.shelf_manager.category_for_path(book.path) == UNCLASSIFIED
    window.shutdown()


def test_delete_category_with_books_removes_records_and_clears_open_book(app, tmp_path):
    window = MainWindow(StateStore(tmp_path / "app-data"), enable_system=False)
    folder = window.create_shelf_category("临时")
    source = tmp_path / "Temp.txt"
    source.write_text("临时内容", encoding="utf-8")
    managed = window.shelf_manager.move_book(source, "临时")
    book = load_book(managed)
    window._loaded(book)
    book_id = book.id
    window.store.state["positions"][book_id] = {"section_id": book.sections[0].id, "offset": 4}
    window.store.state["bookmarks"][book_id] = [{"section_id": book.sections[0].id, "offset": 2, "label": "临时书签", "note": "", "created": ""}]

    window.delete_shelf_category("临时", delete_books=True)

    assert not folder.exists()
    assert not managed.exists()
    assert window.store.state["books"] == []
    assert book_id not in window.store.state["positions"]
    assert book_id not in window.store.state["bookmarks"]
    assert window.book is None
    assert window.shelf.all_books.count() == 0
    window.shutdown()


def test_removing_a_shelf_book_deletes_copy_not_original(app, tmp_path):
    original = tmp_path / "Book.txt"
    original.write_text("original", encoding="utf-8")
    window = MainWindow(StateStore(tmp_path / "app-data"), enable_system=False)
    managed = window.shelf_manager.add_book(original)
    record = _record(managed, "Book")
    window.store.state["books"] = [record]
    window._refresh_shelf()

    window.remove_shelf_book(record["id"])

    assert original.read_text(encoding="utf-8") == "original"
    assert not managed.exists()
    assert window.store.state["books"] == []
    window.shutdown()
