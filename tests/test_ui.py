import time

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from quietreader.persistence.store import StateStore
from quietreader.ui.window import MainWindow


def wait_loaded(app, window):
    deadline = time.monotonic() + 10
    while window.loading and time.monotonic() < deadline:
        app.processEvents()
        QTest.qWait(10)
    assert not window.loading
    assert window.book is not None


def test_import_paging_reflow_and_restart(app, tmp_path):
    file = tmp_path / "山间来信.txt"
    file.write_text("第一章 山林\n" + "清晨的风穿过树林，落在泛黄的书页上。\n" * 300 + "\n第二章 归途\n你好。", encoding="utf-8")
    store = StateStore(tmp_path / "state")
    window = MainWindow(store, enable_system=False)
    window.show()
    assert not window.sidebar.isHidden()
    window.load_path(file)
    wait_loaded(app, window)
    assert window.reader.page_count > 1
    assert window.encoding_bar.isHidden()
    QTest.keyClick(window.reader, Qt.Key.Key_PageDown)
    app.processEvents()
    assert window.reader.page == 1
    anchor = window.reader.offset
    window.resize(700, 620)
    QTest.qWait(200)
    app.processEvents()
    assert window.reader.offset == anchor
    window.save_state()
    book_id = window.book.id
    assert store.state["positions"][book_id]["offset"] == anchor
    window.shutdown()
    again = MainWindow(StateStore(tmp_path / "state"), enable_system=False)
    again.show()
    again.restore_last()
    wait_loaded(app, again)
    assert again.reader.offset == anchor
    again.shutdown()


def test_font_settings_and_epub(app, tmp_path):
    from test_content import epub_bytes
    from quietreader.domain.models import Settings
    file = tmp_path / "one.epub"
    file.write_bytes(epub_bytes())
    window = MainWindow(StateStore(tmp_path / "state"), enable_system=False)
    window.show()
    window.load_path(file)
    wait_loaded(app, window)
    assert window.book.title == "山间来信"
    window.apply_settings(Settings(font_size=26, theme="dark"))
    assert window.reader.settings.font_size == 26
    assert window.reader.page_count >= 1
    assert window.chapters.count() == 1
    window.shutdown()


def test_hotkey_conflict_remains_visible_after_import(app, tmp_path):
    class UnavailableHotkey:
        def configure(self, enabled, key):
            return "全局快捷键注册失败，已被其他程序占用。"

        def close(self):
            pass

    file = tmp_path / "book.txt"
    file.write_text("本地阅读。", encoding="utf-8")
    window = MainWindow(StateStore(tmp_path / "state"), enable_system=False)
    window.hotkey = UnavailableHotkey()
    window.show()
    window.apply_settings(window.settings)
    window.load_path(file)
    wait_loaded(app, window)
    assert "注册失败" in window.hotkey_notice.text()
    assert not window.hotkey_notice.isHidden()
    window.shutdown()
