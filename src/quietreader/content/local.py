"""Bounded local imports. No extraction, script execution or network access."""

from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
import posixpath
import re
from urllib.parse import unquote, urlsplit
import zipfile

from charset_normalizer import from_bytes
from defusedxml import ElementTree as ET

from quietreader.domain.models import Book, Section

MAX_FILE = 32 * 1024 * 1024
MAX_EXPANDED = 64 * 1024 * 1024
CHUNK_SIZE = 24000
ENCODINGS = ("auto", "utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "gb18030", "gbk")


class ImportError(ValueError):
    def __init__(self, message: str, encoding_choice=False):
        super().__init__(message)
        self.encoding_choice = encoding_choice


def _valid_text(text):
    if not text.strip():
        raise ImportError("这本书没有可阅读的文字。")
    controls = sum(ord(c) < 32 and c not in "\n\r\t\f" for c in text)
    if controls:
        raise ImportError("文件含有异常字符，请手动指定编码或检查文件。", True)
    return text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")


def decode_text(data: bytes, encoding="auto") -> tuple[str, str]:
    if encoding not in ENCODINGS:
        raise ImportError("不支持这个编码选项。", True)
    if not data:
        raise ImportError("这个文件是空的。")
    if encoding != "auto":
        try:
            return _valid_text(data.decode(encoding, errors="strict")), encoding
        except UnicodeError:
            raise ImportError("所选编码无法读取这个文件，请尝试其他编码。", True) from None
    for bom, codec in [(b"\xef\xbb\xbf", "utf-8-sig"), (b"\xff\xfe", "utf-16"), (b"\xfe\xff", "utf-16")]:
        if data.startswith(bom):
            return decode_text(data, codec)
    try:
        return _valid_text(data.decode("utf-8", errors="strict")), "utf-8"
    except UnicodeError:
        pass
    # BOM-less UTF-16 and legacy encodings remain ambiguous: offer an explicit choice.
    sample = data[:128000]
    guess = from_bytes(sample).best()
    if guess and guess.encoding in {"gb18030", "gb2312", "gbk", "cp936"} and guess.chaos < 0.05:
        try:
            text = data.decode("gb18030", errors="strict")
            if sum("\u3400" <= c <= "\u9fff" for c in text) / max(1, len(text)) > 0.15:
                return _valid_text(text), "gb18030"
        except UnicodeError:
            pass
    raise ImportError("无法可靠识别文字编码，请选择 GB18030、UTF-16 或其他编码重试。", True)


def split_section(key: str, title: str, text: str) -> list[Section]:
    parts = []
    start = 0
    while start < len(text):
        end = min(len(text), start + CHUNK_SIZE)
        if end < len(text):
            boundary = text.rfind("\n", start + CHUNK_SIZE // 2, end)
            if boundary >= 0:
                end = boundary + 1
        count = len(parts)
        parts.append(Section(f"{key}:{count}", title if not count else f"{title} · 续 {count}", text[start:end]))
        start = end
    return parts


def parse_txt(text: str) -> list[Section]:
    text = _valid_text(text)
    heading = re.compile(r"^\s*(第[零〇一二三四五六七八九十百千万两\d]+[章回节卷部篇].{0,60}|(?:chapter|part)\s+\d+.{0,60}|序章|序言|楔子|尾声|后记)\s*$", re.I)
    sections, lines, title, number = [], [], "正文", 0
    def flush():
        nonlocal number
        body = re.sub(r"\n[ \t\n]*\n", "\n", "\n".join(lines)).strip()
        if body:
            sections.extend(split_section(f"txt:{number}", title, body))
            number += 1
    for line in text.split("\n"):
        if heading.fullmatch(line):
            flush()
            lines = []
            title = line.strip()
        else:
            lines.append(line.rstrip())
    flush()
    if not sections:
        sections = split_section("txt:0", title, text)
    return sections


class TextExtractor(HTMLParser):
    """Retain text only; no widget ever receives book HTML."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.blocked = 0
        self.heading_depth = 0
        self.heading = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "head", "svg", "math", "iframe", "object"):
            self.blocked += 1
        if not self.blocked:
            if tag in ("h1", "h2", "h3"):
                self.heading_depth += 1
            if tag in ("p", "div", "br", "li", "h1", "h2", "h3", "section", "tr"):
                self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "head", "svg", "math", "iframe", "object"):
            self.blocked = max(0, self.blocked - 1)
        if not self.blocked:
            if tag in ("h1", "h2", "h3"):
                self.heading_depth = max(0, self.heading_depth - 1)
            if tag in ("p", "div", "li", "h1", "h2", "h3", "section", "tr"):
                self.parts.append("\n")

    def handle_data(self, data):
        if not self.blocked:
            self.parts.append(data)
            if self.heading_depth:
                self.heading.append(data)


def _tag(element):
    return element.tag.rsplit("}", 1)[-1]


def _zip_path(base: str, href: str) -> str:
    parsed = urlsplit(href)
    if parsed.scheme or parsed.netloc or "\\" in href:
        raise ImportError("EPUB 含有不支持的外部或异常资源路径。")
    path = unquote(parsed.path)
    joined = posixpath.normpath(posixpath.join(base, path))
    if joined.startswith(("../", "/")) or joined == ".." or "\x00" in joined:
        raise ImportError("EPUB 含有不安全的资源路径。")
    return joined


def _load_epub(path: Path) -> tuple[str, str, list[Section]]:
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > 4096 or sum(i.file_size for i in infos) > MAX_EXPANDED:
                raise ImportError("EPUB 解压后过大或资源过多，当前版本不支持。")
            for info in infos:
                if info.flag_bits & 1 or info.file_size > MAX_FILE or info.file_size > max(1, info.compress_size) * 500:
                    raise ImportError("EPUB 加密或压缩比例异常，无法安全读取。")
                if ".." in PurePosixPath(info.filename).parts or info.filename.startswith("/") or "\\" in info.filename:
                    raise ImportError("EPUB 含有不安全的资源路径。")
            names = set(archive.namelist())
            if len(names) != len(infos):
                raise ImportError("EPUB 存在重复资源，无法可靠读取。")
            if "META-INF/encryption.xml" in names:
                raise ImportError("此 EPUB 包含加密资源（可能是 DRM 或字体混淆），当前版本不支持。")
            if archive.read("mimetype").strip() != b"application/epub+zip":
                raise ImportError("这不是有效的 EPUB 文件。")
            container = ET.fromstring(archive.read("META-INF/container.xml"))
            rootfile = next(e for e in container.iter() if _tag(e) == "rootfile")
            opf_path = _zip_path("", rootfile.attrib["full-path"])
            opf = ET.fromstring(archive.read(opf_path))
            base = posixpath.dirname(opf_path)
            title = next((e.text.strip() for e in opf.iter() if _tag(e) == "title" and e.text and e.text.strip()), path.stem)
            author = next((e.text.strip() for e in opf.iter() if _tag(e) == "creator" and e.text and e.text.strip()), "")
            manifest = {e.attrib["id"]: e.attrib for e in opf.iter() if _tag(e) == "item" and "id" in e.attrib}
            labels = {}
            for item in manifest.values():
                if "nav" in item.get("properties", "").split() or item.get("media-type") == "application/x-dtbncx+xml":
                    nav_path = _zip_path(base, item["href"])
                    nav = ET.fromstring(archive.read(nav_path))
                    for node in nav.iter():
                        if _tag(node) == "a" and node.get("href"):
                            target = _zip_path(posixpath.dirname(nav_path), node.get("href"))
                            labels.setdefault(target, "".join(node.itertext()).strip())
                        elif _tag(node) == "navPoint":
                            content = next((e for e in node if _tag(e) == "content"), None)
                            label = next((e for e in node if _tag(e) == "navLabel"), None)
                            if content is not None and label is not None:
                                labels.setdefault(_zip_path(posixpath.dirname(nav_path), content.get("src", "")), "".join(label.itertext()).strip())
            sections = []
            for ref in (e for e in opf.iter() if _tag(e) == "itemref" and e.get("linear", "yes") != "no"):
                item = manifest[ref.attrib["idref"]]
                if item.get("media-type") not in ("application/xhtml+xml", "text/html"):
                    raise ImportError("EPUB 的阅读顺序包含不支持的内容类型。")
                item_path = _zip_path(base, item["href"])
                # XML decoding respects the document's declared encoding and rejects entities.
                element = ET.fromstring(archive.read(item_path))
                # Strip XML namespaces before the text-only HTML parser sees tags.
                for node in element.iter():
                    node.tag = _tag(node)
                parser = TextExtractor()
                parser.feed(ET.tostring(element, encoding="unicode"))
                text = re.sub(r"[ \t]+", " ", "".join(parser.parts))
                text = re.sub(r"\n\s*\n+", "\n", text).strip()
                if text:
                    chapter_title = labels.get(item_path) or "".join(parser.heading).strip() or f"章节 {len(sections) + 1}"
                    sections.extend(split_section("epub:" + item_path, chapter_title[:160], text))
            if not sections:
                raise ImportError("EPUB 中没有可阅读的文字章节。")
            return title[:300], author[:300], sections
    except ImportError:
        raise
    except Exception:
        raise ImportError("EPUB 结构损坏、内容缺失或 XML 不受支持，无法读取。") from None


def load_book(file: str | Path, encoding="auto") -> Book:
    path = Path(file)
    try:
        if path.suffix.lower() not in (".txt", ".epub"):
            raise ImportError("请选择 TXT 或未加密的 EPUB 文件。")
        if not path.is_file():
            raise ImportError("文件不存在或无法访问，请重新定位文件。")
        size = path.stat().st_size
        if size > MAX_FILE:
            raise ImportError("文件超过 32 MiB，当前版本暂不支持。")
        if size == 0:
            raise ImportError("这个文件是空的。")
        path = path.resolve()
        book_id = sha256(str(path).casefold().encode("utf-8")).hexdigest()[:24]
        if path.suffix.lower() == ".txt":
            with path.open("rb") as stream:
                data = stream.read(MAX_FILE + 1)
            if len(data) > MAX_FILE:
                raise ImportError("文件超过 32 MiB，当前版本暂不支持。")
            text, detected = decode_text(data, encoding)
            return Book(book_id, str(path), path.stem, sections=parse_txt(text), encoding=detected)
        title, author, sections = _load_epub(path)
        return Book(book_id, str(path), title, author, sections, "EPUB")
    except ImportError:
        raise
    except (OSError, ValueError):
        raise ImportError("读取文件失败，请检查权限，或重新定位文件。") from None
