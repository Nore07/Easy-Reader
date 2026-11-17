import io
import zipfile

import pytest

from quietreader.content.local import ImportError as BookImportError, decode_text, load_book, parse_txt


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-16", "utf-16-be", "gb18030"])
def test_chinese_encodings(encoding):
    text = "第一章 初见\n\n清晨的山林里，阳光照在安静的小路上。" * 8
    data = text.encode(encoding)
    if encoding == "utf-16-be":
        data = b"\xfe\xff" + data
    assert decode_text(data)[0] == text


def test_ambiguous_encoding_requires_choice():
    with pytest.raises(BookImportError):
        decode_text(b"\x81\x30\xff\x00\x81")


def test_chapters_and_long_text_are_bounded():
    sections = parse_txt("序言\n你好\n第一章 初见\n" + "很长的段落。" * 20000 + "\n第二章 归来\n结束")
    assert any(s.title == "第二章 归来" for s in sections)
    assert max(len(s.text) for s in sections) <= 24000
    assert "".join(s.text for s in sections).count("很长的段落。") == 20000


def test_blank_paragraphs_use_reader_spacing():
    assert parse_txt("第一段\n\n\n第二段")[0].text == "第一段\n第二段"


def epub_bytes(encrypted=False, malicious=False):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as z:
        z.writestr("mimetype", "application/epub+zip")
        z.writestr("META-INF/container.xml", '<container><rootfiles><rootfile full-path="OEBPS/book.opf"/></rootfiles></container>')
        z.writestr("OEBPS/book.opf", '<package xmlns:dc="http://purl.org/dc/elements/1.1/"><metadata><dc:title>山间来信</dc:title><dc:creator>作者</dc:creator></metadata><manifest><item id="one" href="one.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="one"/></spine></package>')
        z.writestr("OEBPS/one.xhtml", '<html><head><script>危险脚本</script></head><body><h1>第一章</h1><p>你好，世界。</p><script>不应出现</script></body></html>')
        if encrypted:
            z.writestr("META-INF/encryption.xml", "<encryption/>")
        if malicious:
            z.writestr("../outside", "no")
    return output.getvalue()


def test_epub_order_metadata_and_no_active_content(tmp_path):
    file = tmp_path / "test.epub"
    file.write_bytes(epub_bytes())
    book = load_book(file)
    assert book.title == "山间来信"
    assert book.author == "作者"
    assert "你好，世界。" in book.sections[0].text
    assert "脚本" not in book.sections[0].text
    assert "不应出现" not in book.sections[0].text


@pytest.mark.parametrize("options", [{"encrypted": True}, {"malicious": True}])
def test_reject_unsafe_epub(tmp_path, options):
    file = tmp_path / "test.epub"
    file.write_bytes(epub_bytes(**options))
    with pytest.raises(BookImportError):
        load_book(file)


def test_empty_missing_and_unsupported(tmp_path):
    file = tmp_path / "empty.txt"
    file.write_bytes(b"")
    for path in [file, tmp_path / "missing.txt", tmp_path / "x.pdf"]:
        with pytest.raises(BookImportError):
            load_book(path)


def test_namespaced_epub_nav_and_entities(tmp_path):
    file = tmp_path / "namespaced.epub"
    source = zipfile.ZipFile(io.BytesIO(epub_bytes()))
    with zipfile.ZipFile(file, "w") as archive:
        for entry in source.infolist():
            data = source.read(entry.filename)
            if entry.filename.endswith(".opf"):
                data = data.replace(b"</manifest>", b'<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/></manifest>')
            if entry.filename.endswith("one.xhtml"):
                data = b'<html xmlns="http://www.w3.org/1999/xhtml"><head><script>bad</script></head><body><p>safe</p></body></html>'
            archive.writestr(entry.filename, data)
        archive.writestr("OEBPS/nav.xhtml", '<html xmlns="http://www.w3.org/1999/xhtml"><body><nav><a href="one.xhtml">来自目录的章节</a></nav></body></html>')
    book = load_book(file)
    assert book.sections[0].title == "来自目录的章节"
    assert "bad" not in book.sections[0].text
    assert "safe" in book.sections[0].text


def test_manual_encoding_and_malformed_bom():
    sample = "第一章\n本地阅读"
    assert decode_text(sample.encode("utf-16-le"), "utf-16-le")[0] == sample
    with pytest.raises(BookImportError):
        decode_text(b"\xff\xfe\x00")
