import zipfile

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextCursor, QTextCharFormat

from quietreader.content.local import load_book
from quietreader.domain.models import Section
from quietreader.persistence.store import StateStore
from quietreader.ui.reader import qt_offset
from quietreader.ui.window import MainWindow


def _semantic_epub(path, markup=None):
    markup = markup or '''<html xmlns="http://www.w3.org/1999/xhtml"><body>
      <h1>大标题</h1><h2>标题 <em>标题斜体</em></h2><p>普通 <strong>加粗</strong> 和 <em>斜体</em>，<del>删除</del>。</p>
      <blockquote><p>引用内容</p></blockquote>
      <ol><li>第一项</li><li>第二项 <code>print(1)</code> <sup>2</sup> <sub>x</sub></li></ol>
      <p><u>下划线</u> <mark>标记</mark></p><hr/><script>script-danger</script><style>style-danger</style>
      </body></html>'''
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", '<container><rootfiles><rootfile full-path="book.opf"/></rootfiles></container>')
        archive.writestr("book.opf", '''<package xmlns:dc="http://purl.org/dc/elements/1.1/"><metadata><dc:title>排版测试</dc:title></metadata>
          <manifest><item id="one" href="one.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="one"/></spine></package>''')
        archive.writestr("one.xhtml", markup)


def _format_at(view, sample, start_at=0):
    start = view.text.index(sample, start_at)
    cursor = QTextCursor(view.document)
    cursor.setPosition(qt_offset(view.text, start))
    cursor.setPosition(qt_offset(view.text, start + len(sample)), QTextCursor.MoveMode.KeepAnchor)
    return cursor


def test_epub_semantic_markup_becomes_bounded_text_ranges(tmp_path):
    path = tmp_path / "semantic.epub"
    _semantic_epub(path)

    section = load_book(path).sections[0]

    assert section.text.startswith("大标题")
    assert section.title == "大标题"
    assert "script-danger" not in section.text and "style-danger" not in section.text
    assert "1. 第一项" in section.text and "2. 第二项" in section.text
    styled = {(item.kind, section.text[item.start:item.end]) for item in section.formats}
    assert ("heading", "大标题") in styled
    assert ("bold", "加粗") in styled
    assert ("italic", "斜体") in styled
    assert ("strike", "删除") in styled
    assert any(kind == "quote" and "引用内容" in sample for kind, sample in styled)
    assert ("code", "print(1)") in styled
    assert ("superscript", "2") in styled
    assert ("subscript", "x") in styled
    assert ("underline", "下划线") in styled
    assert ("highlight", "标记") in styled
    rule = next(item for item in section.formats if item.kind == "rule")
    assert section.text[rule.start:rule.end] == "────────────────"


def test_reader_renders_epub_semantic_formats(app, tmp_path):
    path = tmp_path / "semantic.epub"
    _semantic_epub(path)
    book = load_book(path)
    window = MainWindow(StateStore(tmp_path / "state"), enable_system=False)
    window.resize(960, 700)
    window.show()
    window._loaded(book)
    view = window.reader

    assert _format_at(view, "加粗").charFormat().fontWeight() >= QFont.Weight.Bold
    assert _format_at(view, "斜体").charFormat().fontItalic()
    assert _format_at(view, "删除").charFormat().fontStrikeOut()
    assert _format_at(view, "下划线").charFormat().fontUnderline()
    assert _format_at(view, "标记").charFormat().background().style() != 0
    assert _format_at(view, "print(1)").charFormat().font().family() == "Consolas"
    assert _format_at(view, "2", view.text.index("print(1)")).charFormat().verticalAlignment() == QTextCharFormat.VerticalAlignment.AlignSuperScript
    assert _format_at(view, "x").charFormat().verticalAlignment() == QTextCharFormat.VerticalAlignment.AlignSubScript
    heading_font = _format_at(view, "大标题").charFormat().font()
    assert heading_font.pixelSize() > view.settings.font_size
    assert _format_at(view, "标题斜体").charFormat().fontItalic()
    assert _format_at(view, "引用内容").blockFormat().leftMargin() > 0
    rule = next(item for item in book.sections[0].formats if item.kind == "rule")
    assert _format_at(view, view.text[rule.start:rule.end]).blockFormat().alignment() == Qt.AlignmentFlag.AlignHCenter
    window.shutdown()


def test_plain_txt_sections_keep_default_format_model():
    section = Section("plain", "正文", "普通 TXT 正文")
    assert section.formats == []


def test_semantic_ranges_are_clipped_across_long_chapter_chunks(tmp_path):
    content = "分段测试" * 6500
    path = tmp_path / "long-semantic.epub"
    markup = f'<html xmlns="http://www.w3.org/1999/xhtml"><body><p><strong>{content}</strong></p></body></html>'
    _semantic_epub(path, markup)

    sections = load_book(path).sections

    assert len(sections) > 1
    assert "".join(section.text for section in sections) == content
    assert sum(item.end - item.start for section in sections for item in section.formats if item.kind == "bold") == len(content)
    assert all(0 <= item.start < item.end <= len(section.text) for section in sections for item in section.formats)
