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


def epub_with_navigation(include_page_list=True):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", '<container><rootfiles><rootfile full-path="OEBPS/book.opf"/></rootfiles></container>')
        archive.writestr("OEBPS/book.opf", '''<package xmlns:dc="http://purl.org/dc/elements/1.1/"><metadata><dc:title>导航测试</dc:title></metadata>
          <manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
          <item id="one" href="Text/one.xhtml" media-type="application/xhtml+xml"/><item id="two" href="Text/two.xhtml" media-type="application/xhtml+xml"/></manifest>
          <spine><itemref idref="one"/><itemref idref="two"/></spine></package>''')
        page_list = '<nav epub:type="page-list"><ol><li><a href="Text/one.xhtml#page-12">12</a></li></ol></nav>' if include_page_list else ""
        archive.writestr("OEBPS/nav.xhtml", f'''<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><body>
          <nav epub:type="toc"><ol><li><a href="Text/one.xhtml#start">第一章</a><ol><li><a href="Text/two.xhtml#note">脚注</a></li></ol></li></ol></nav>
          {page_list}
          <nav epub:type="landmarks"><ol><li><a epub:type="bodymatter" href="Text/one.xhtml#start">正文</a></li></ol></nav>
          </body></html>''')
        long_text = "连续正文" * 6500
        archive.writestr("OEBPS/Text/one.xhtml", f'''<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><body>
          <h1 id="start">第一章</h1><p>阅读<a href="two.xhtml#note">脚注链接</a>。</p><p>{long_text}</p>
          <span id="page-12" epub:type="pagebreak" title="12" role="doc-pagebreak"></span></body></html>''')
        archive.writestr("OEBPS/Text/two.xhtml", '''<html xmlns="http://www.w3.org/1999/xhtml"><body><h1 id="chapter-two">第二章</h1>
          <aside id="note">脚注正文</aside></body></html>''')
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


def test_epub3_toc_page_list_landmarks_and_internal_links_survive_chunking(tmp_path):
    file = tmp_path / "navigation.epub"
    file.write_bytes(epub_with_navigation())

    book = load_book(file)

    assert [(entry.label, entry.path, entry.fragment) for entry in getattr(book, "toc", [])] == [
        ("第一章", "OEBPS/Text/one.xhtml", "start")
    ]
    assert [(entry.label, entry.path, entry.fragment) for entry in book.toc[0].children] == [
        ("脚注", "OEBPS/Text/two.xhtml", "note")
    ]
    assert [(entry.label, entry.path, entry.fragment) for entry in getattr(book, "page_list", [])] == [
        ("12", "OEBPS/Text/one.xhtml", "page-12")
    ]
    assert book.landmarks[0].semantic_type == "bodymatter"

    one_sections = [section for section in book.sections if section.source_path == "OEBPS/Text/one.xhtml"]
    assert len(one_sections) > 1
    page_section = next(section for section in one_sections if "page-12" in section.anchors)
    assert page_section.anchors["page-12"] >= 0
    first = one_sections[0]
    link = next(link for link in first.links if link.path == "OEBPS/Text/two.xhtml")
    assert first.text[link.start:link.end] == "脚注链接"
    assert link.fragment == "note"
    assert next(section for section in book.sections if section.source_path == link.path).anchors["note"] >= 0


def test_epub_pagebreaks_supply_page_navigation_when_page_list_is_absent(tmp_path):
    file = tmp_path / "pagebreaks.epub"
    file.write_bytes(epub_with_navigation(include_page_list=False))

    book = load_book(file)

    assert [(entry.label, entry.path, entry.fragment) for entry in book.page_list] == [
        ("12", "OEBPS/Text/one.xhtml", "page-12")
    ]


def test_epub2_ncx_preserves_nested_toc_and_printed_pages(tmp_path):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", '<container><rootfiles><rootfile full-path="book.opf"/></rootfiles></container>')
        archive.writestr("book.opf", '''<package><metadata><title>NCX</title></metadata>
          <manifest><item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/><item id="one" href="one.xhtml" media-type="application/xhtml+xml"/></manifest>
          <spine toc="ncx"><itemref idref="one"/></spine></package>''')
        archive.writestr("toc.ncx", '''<ncx><navMap><navPoint><navLabel><text>第一章</text></navLabel><content src="one.xhtml#start"/>
          <navPoint><navLabel><text>小节</text></navLabel><content src="one.xhtml#part"/></navPoint></navPoint></navMap>
          <pageList><pageTarget><navLabel><text>1</text></navLabel><content src="one.xhtml#page1"/></pageTarget></pageList></ncx>''')
        archive.writestr("one.xhtml", '<html><body><h1 id="start">第一章</h1><h2 id="part">小节</h2><span id="page1">1</span></body></html>')
    file = tmp_path / "ncx.epub"
    file.write_bytes(output.getvalue())

    book = load_book(file)

    assert getattr(book, "toc", [])[0].label == "第一章"
    assert book.toc[0].children[0].label == "小节"
    assert book.toc[0].children[0].fragment == "part"
    assert book.page_list[0].label == "1"
    assert book.page_list[0].fragment == "page1"


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
