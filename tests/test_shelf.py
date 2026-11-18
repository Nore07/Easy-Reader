from pathlib import Path

import pytest

from quietreader.library.shelf import ShelfError, ShelfManager


def test_add_copies_into_unclassified_without_touching_original(tmp_path):
    manager = ShelfManager(tmp_path / "app-data")
    original = tmp_path / "My Book.txt"
    original.write_text("本地原书", encoding="utf-8")

    first = manager.add_book(original)
    second = manager.add_book(original)

    assert first.parent == manager.unclassified
    assert first.read_text(encoding="utf-8") == "本地原书"
    assert second != first and second.exists()
    assert original.read_text(encoding="utf-8") == "本地原书"


@pytest.mark.parametrize("name", ["", "   ", "未分类", "../outside", "a/b", "bad:name", "CON", "trailing."])
def test_reject_unsafe_or_reserved_category_names(tmp_path, name):
    manager = ShelfManager(tmp_path / "app-data")

    with pytest.raises(ShelfError):
        manager.create_category(name)


def test_category_move_uses_safe_unique_paths(tmp_path):
    manager = ShelfManager(tmp_path / "app-data")
    category = manager.create_category("科幻")
    source = tmp_path / "Novel.epub"
    source.write_bytes(b"epub")
    first = manager.add_book(source)
    conflict = category / first.name
    conflict.write_bytes(b"existing")

    moved = manager.move_book(first, "科幻")
    returned = manager.move_book(moved, "未分类")

    assert moved.parent == category and moved.name != conflict.name
    assert conflict.read_bytes() == b"existing"
    assert not first.exists() and not moved.exists()
    assert returned.parent == manager.unclassified
    assert returned.read_bytes() == b"epub"
    assert source.read_bytes() == b"epub"


def test_classifying_legacy_external_book_copies_and_preserves_source(tmp_path):
    manager = ShelfManager(tmp_path / "app-data")
    manager.create_category("历史")
    source = tmp_path / "legacy.txt"
    source.write_text("旧版本阅读记录", encoding="utf-8")

    managed = manager.move_book(source, "历史")

    assert managed.parent == manager.category_path("历史")
    assert managed.read_text(encoding="utf-8") == "旧版本阅读记录"
    assert source.read_text(encoding="utf-8") == "旧版本阅读记录"


def test_delete_category_moves_books_to_unclassified(tmp_path):
    manager = ShelfManager(tmp_path / "app-data")
    category = manager.create_category("历史")
    book = category / "story.txt"
    book.write_text("book", encoding="utf-8")

    moved = manager.delete_category("历史", delete_books=False)

    assert moved == {book: manager.unclassified / "story.txt"}
    assert moved[book].read_text(encoding="utf-8") == "book"
    assert not category.exists()
    assert manager.categories() == []


def test_delete_category_removes_its_book_files(tmp_path):
    manager = ShelfManager(tmp_path / "app-data")
    category = manager.create_category("废弃")
    book = category / "story.epub"
    book.write_bytes(b"book")

    deleted = manager.delete_category("废弃", delete_books=True)

    assert deleted == {book: None}
    assert not book.exists() and not category.exists()


def test_category_delete_refuses_nested_content_before_moving_books(tmp_path):
    manager = ShelfManager(tmp_path / "app-data")
    category = manager.create_category("复杂")
    book = category / "story.txt"
    book.write_text("book", encoding="utf-8")
    (category / "unexpected").mkdir()

    with pytest.raises(ShelfError):
        manager.delete_category("复杂", delete_books=False)

    assert book.exists() and book.parent == category
    assert manager.category_path("复杂") == category
