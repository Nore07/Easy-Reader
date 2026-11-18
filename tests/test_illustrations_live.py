import io
import zipfile
import pytest
from PySide6.QtCore import QByteArray, QBuffer, QIODevice
from PySide6.QtGui import QImage, QColor
from quietreader.content.local import load_book
from quietreader.domain.models import Settings
from quietreader.persistence.store import StateStore
from quietreader.ui.window import MainWindow


@pytest.mark.parametrize("payload,valid", [(b'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="60"><rect width="40" height="60" fill="red"/></svg>', True), (b'<svg xmlns="http://www.w3.org/2000/svg" width="40" height="60"><image href="https://example.invalid/a.png"/></svg>', False), (b'broken image', False)])
def test_image_only_svg_and_invalid_resources(app, tmp_path, payload, valid):
    from test_content import epub_bytes
    from quietreader.content.local import ImportError as BookImportError
    path = tmp_path / "picture.epub"
    with zipfile.ZipFile(io.BytesIO(epub_bytes())) as source, zipfile.ZipFile(path, "w") as target:
        for name in source.namelist():
            target.writestr(name, b'<html><body><img src="art.svg"/></body></html>' if name.endswith("one.xhtml") else source.read(name))
        target.writestr("OEBPS/art.svg", payload)
    if valid:
        book = load_book(path)
        assert book.sections[0].text == "\ufffc"
        assert book.sections[0].images
    else:
        with pytest.raises(BookImportError):
            load_book(path)


def test_epub_inline_image_order_and_render(app, tmp_path, capture_path=None):
    from test_content import epub_bytes
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image = QImage(80, 120, QImage.Format.Format_RGB32)
    image.fill(QColor("#ff0000"))
    for y in range(100, 120):
        for x in range(80):
            image.setPixelColor(x, y, QColor("#0000ff"))
    image.save(buffer, "PNG")
    file = tmp_path / "image.epub"
    with zipfile.ZipFile(io.BytesIO(epub_bytes())) as source, zipfile.ZipFile(file, "w") as target:
        for name in source.namelist():
            content = source.read(name)
            if name.endswith("one.xhtml"):
                content = b'<html><body><p>Before</p><img src="images/a.png"/><p>After</p></body></html>'
            target.writestr(name, content)
        target.writestr("OEBPS/images/a.png", bytes(data))
    book = load_book(file)
    section = book.sections[0]
    assert section.text.index("Before") < section.text.index("\ufffc") < section.text.index("After")
    assert len(section.images) == 1
    window = MainWindow(StateStore(tmp_path / "state"), enable_system=False)
    window.show()
    window._loaded(book)
    assert window.reader.document.characterAt(section.text.index("\ufffc")) == "\ufffc"
    assert window.reader.image_sizes
    rendered = False
    bottom_rendered = False
    for page in range(window.reader.page_count):
        window.reader.go_page(page)
        capture = window.reader.grab().toImage().convertToFormat(QImage.Format.Format_RGBA8888)
        rendered |= bytes((255, 0, 0, 255)) in bytes(capture.constBits())
        bottom_rendered |= bytes((0, 0, 255, 255)) in bytes(capture.constBits())
        if capture_path and bytes((255, 0, 0, 255)) in bytes(capture.constBits()):
            window._update_progress()
            window.grab().save(str(capture_path))
    assert rendered
    assert bottom_rendered
    assert window.reader.page_offsets[-1] <= section.text.index("After")
    window.shutdown()


def test_layout_panel_live_preview_cancel_and_save(app, tmp_path):
    window = MainWindow(StateStore(tmp_path), enable_system=False)
    window.show()
    original = window.settings.font_size
    panel = window.create_layout_panel()
    panel.show()
    panel.fields["font_size"].setValue(30)
    assert window.reader.settings.font_size == 30
    assert window.settings.font_size == original
    panel.reject()
    assert window.reader.settings.font_size == original
    panel = window.create_layout_panel()
    panel.fields["font_size"].setValue(28)
    panel.accept()
    assert window.settings.font_size == 28
    window.shutdown()
