import io
import json
import struct
import zlib
import zipfile

import pytest

from quietreader.content.local import load_book
from quietreader.domain.models import Book, Section
from quietreader.persistence.store import StateStore
from quietreader.ui.window import MainWindow


def _png(width=12, height=18):
    def chunk(tag, payload):
        return struct.pack("!I", len(payload)) + tag + payload + struct.pack("!I", zlib.crc32(tag + payload))

    rows = b"".join(b"\0" + b"\x31\x77\xa4" * width for _ in range(height))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack("!2I5B", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b"")


def _metadata_epub(version="epub3", cover_payload=None):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", '<container><rootfiles><rootfile full-path="OEBPS/book.opf"/></rootfiles></container>')
        if version == "epub3":
            cover_item = '<item id="cover" href="Images/cover.png" media-type="image/png" properties="cover-image"/>' if cover_payload is not None else ""
            cover_meta = ""
        else:
            cover_item = '<item id="cover" href="Images/cover.png" media-type="image/png"/>' if cover_payload is not None else ""
            cover_meta = '<meta name="cover" content="cover"/>' if cover_payload is not None else ""
        package = f'''<package xmlns:dc="http://purl.org/dc/elements/1.1/"><metadata>
          <dc:title>山间来信</dc:title><dc:creator>林作者</dc:creator><dc:language>zh-CN</dc:language>
          <dc:identifier id="BookId">urn:isbn:9780000000001</dc:identifier><dc:publisher>静读出版社</dc:publisher>
          <dc:date>2026-02-03</dc:date><dc:description>关于山中书信的故事。</dc:description>{cover_meta}
          </metadata><manifest><item id="one" href="Text/one.xhtml" media-type="application/xhtml+xml"/>{cover_item}</manifest>
          <spine><itemref idref="one"/></spine></package>'''
        archive.writestr("OEBPS/book.opf", package)
        archive.writestr("OEBPS/Text/one.xhtml", "<html><body><p>正文。</p></body></html>")
        if cover_payload is not None:
            archive.writestr("OEBPS/Images/cover.png", cover_payload)
    return output.getvalue()


@pytest.mark.parametrize("version", ["epub3", "epub2"])
def test_epub_metadata_and_cover_variants(tmp_path, version):
    path = tmp_path / "metadata.epub"
    path.write_bytes(_metadata_epub(version, _png()))

    book = load_book(path)

    assert book.title == "山间来信"
    assert book.author == "林作者"
    assert book.language == "zh-CN"
    assert book.identifier == "urn:isbn:9780000000001"
    assert book.publisher == "静读出版社"
    assert book.publication_date == "2026-02-03"
    assert book.description == "关于山中书信的故事。"
    assert book.cover == _png()


@pytest.mark.parametrize("payload", [None, b"broken cover"])
def test_missing_or_invalid_cover_falls_back_to_metadata(tmp_path, payload):
    path = tmp_path / "metadata.epub"
    path.write_bytes(_metadata_epub("epub3", payload))

    book = load_book(path)

    assert book.title == "山间来信"
    assert book.cover == b""


def test_state_adds_bounded_bookmarks_and_reads_legacy_state(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps({"version": 1, "settings": {}, "books": [], "positions": {}}), encoding="utf-8")
    store = StateStore(tmp_path)
    assert store.state["bookmarks"] == {}

    store.state["bookmarks"] = {"book": [{"section_id": "one", "offset": 12, "label": "第 1 章 · 2", "note": "稍后重读", "created": "2026-11-18T00:00:00+00:00"}]}
    store.save()
    loaded = StateStore(tmp_path)
    assert loaded.state["bookmarks"]["book"][0]["note"] == "稍后重读"


def test_bookmark_state_rejects_invalid_records_and_bounds_notes(tmp_path):
    store = StateStore(tmp_path)
    store.state["bookmarks"] = {
        "book": [
            {"section_id": "one", "offset": -1, "label": "bad", "note": "x"},
            {"section_id": "two", "offset": 2, "label": "good", "note": "笔记" * 700},
        ]
    }
    store.save()

    records = StateStore(tmp_path).state["bookmarks"]["book"]

    assert len(records) == 1
    assert records[0]["section_id"] == "two"
    assert len(records[0]["note"]) == 1000


def test_bookmarks_restore_position_and_notes_after_restart(app, tmp_path):
    store = StateStore(tmp_path)
    book = Book("book", "book.txt", "阅读测试", sections=[
        Section("one", "第一章", "第一页正文。"),
        Section("two", "第二章", "第二页正文。" * 8),
    ])
    window = MainWindow(store, enable_system=False)
    window.show()
    window._loaded(book)
    window.open_section(1, 7)
    window.add_bookmark()
    assert window.bookmarks.count() == 1
    window.set_bookmark_note(0, "这里有一个线索")
    store.save()
    window.open_section(0)
    window._bookmark_activated(window.bookmarks.item(0))
    assert (window.section_index, window.reader.offset) == (1, 7)
    window.shutdown()

    restored = StateStore(tmp_path)
    assert restored.state["bookmarks"]["book"][0]["note"] == "这里有一个线索"
    reopened = MainWindow(restored, enable_system=False)
    reopened.show()
    reopened._loaded(book)
    assert reopened.bookmarks.count() == 1
    assert reopened.book_info.cover_image is None
    reopened.bookmarks.setCurrentRow(0)
    reopened.remove_bookmark()
    restored.save()
    assert StateStore(tmp_path).state["bookmarks"] == {}
    reopened.shutdown()


def test_book_info_shows_epub3_cover_and_retranslates_metadata(app, tmp_path):
    path = tmp_path / "metadata.epub"
    path.write_bytes(_metadata_epub("epub3", _png()))
    book = load_book(path)
    window = MainWindow(StateStore(tmp_path / "state"), enable_system=False)
    window.show()
    window._loaded(book)

    assert window.book_info.cover_image is not None
    assert "山间来信" in window.book_info.details.text()
    window.apply_settings(window.settings.__class__(language="en"))
    assert "Title: 山间来信" in window.book_info.details.text()
    assert window.tabs.tabText(0) == "Reading"
    assert window.reading_tabs.tabText(1) == "Bookmarks"
    window.shutdown()
