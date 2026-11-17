from bisect import bisect_right

from PySide6.QtCore import QPointF, QRectF, QSizeF, Qt, Signal
from PySide6.QtGui import (
    QAbstractTextDocumentLayout, QColor, QFont, QGuiApplication, QKeySequence,
    QPainter, QPalette, QTextBlockFormat, QTextCharFormat, QTextCursor, QTextDocument,
)
from PySide6.QtWidgets import QMenu, QWidget

from quietreader.domain.models import Settings
from quietreader.ui.theme import colors


def qt_offset(text: str, python_offset: int) -> int:
    return len(text[:python_offset].encode("utf-16-le")) // 2


def python_offset(text: str, utf16_offset: int) -> int:
    return len(text.encode("utf-16-le")[:utf16_offset * 2].decode("utf-16-le", errors="ignore"))


class PageView(QWidget):
    turned = Signal(int)
    reflowed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = Settings()
        self.text = ""
        self.offset = 0
        self.page = 0
        self.page_count = 1
        self.page_offsets = [0]
        self.document = QTextDocument(self)
        self.selection = QTextCursor(self.document)
        self.page_height = 400
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("阅读正文")
        self.setMinimumSize(160, 140)
        self.setMouseTracking(True)

    def set_text(self, text: str, offset=0):
        self.text = text
        self.offset = max(0, min(len(text), offset))
        self.document.setPlainText(text)
        self.selection = QTextCursor(self.document)
        self.reflow()

    def apply_settings(self, settings):
        self.settings = settings
        self.reflow()

    def reflow(self):
        padding = self.settings.padding
        width = max(80, self.width() - padding * 2)
        self.page_height = max(60, self.height() - padding * 2)
        font = QFont(self.settings.font_family)
        font.setPixelSize(self.settings.font_size)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, self.settings.letter_spacing)
        self.document.setDefaultFont(font)
        self.document.setDocumentMargin(0)
        cursor = QTextCursor(self.document)
        cursor.select(QTextCursor.SelectionType.Document)
        block = QTextBlockFormat()
        block.setLineHeight(self.settings.line_height * 100, QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
        block.setBottomMargin(self.settings.paragraph_spacing)
        cursor.mergeBlockFormat(block)
        self.document.setPageSize(QSizeF(width, self.page_height))
        self.page_count = max(1, self.document.pageCount())
        offsets = [None] * self.page_count
        offsets[0] = 0
        current = self.document.begin()
        layout = self.document.documentLayout()
        while current.isValid():
            block_y = layout.blockBoundingRect(current).top()
            text_layout = current.layout()
            for i in range(text_layout.lineCount()):
                line = text_layout.lineAt(i)
                page = min(self.page_count - 1, int((block_y + line.y() + 0.1) // self.page_height))
                if offsets[page] is None:
                    offsets[page] = python_offset(self.text, current.position() + line.textStart())
            current = current.next()
        self.page_offsets = [value if value is not None else len(self.text) for value in offsets]
        self.page = min(self.page_count - 1, max(0, bisect_right(self.page_offsets, self.offset) - 1))
        self.update()
        self.reflowed.emit()

    def go_page(self, page):
        self.page = max(0, min(self.page_count - 1, page))
        self.offset = self.page_offsets[self.page]
        self.selection.clearSelection()
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reflow()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        c = colors(self.settings.theme, self.settings.background_color if self.settings.floating else "")
        painter.setPen(QColor(c["ink"]))
        if not self.text:
            box = QRectF(self.rect()).adjusted(25, 10, -25, -10)
            painter.setFont(QFont("Microsoft YaHei", 11))
            painter.setPen(QColor(c["muted"]))
            painter.drawText(box.adjusted(0, 0, 0, -130), Qt.AlignmentFlag.AlignCenter, "一 段 留 给 自 己 的 时 间")
            painter.setFont(QFont("Microsoft YaHei", 23))
            painter.setPen(QColor(c["ink"]))
            painter.drawText(box, Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, "把喧闹\n留在书页之外。")
            painter.setFont(QFont("Microsoft YaHei", 10))
            painter.setPen(QColor(c["muted"]))
            painter.drawText(box.adjusted(0, 160, 0, 0), Qt.AlignmentFlag.AlignCenter, "打开一本 TXT 或 EPUB\n文件与进度，只保存在这台电脑。")
            return
        pad = self.settings.padding
        painter.setClipRect(QRectF(pad, pad, max(1, self.width() - 2 * pad), self.page_height))
        painter.translate(pad, pad - self.page * self.page_height)
        context = QAbstractTextDocumentLayout.PaintContext()
        context.clip = QRectF(0, self.page * self.page_height, self.document.pageSize().width(), self.page_height)
        context.palette.setColor(QPalette.ColorRole.Text, QColor(c["ink"]))
        if self.selection.hasSelection():
            selected = QAbstractTextDocumentLayout.Selection()
            selected.cursor = self.selection
            selected.format = QTextCharFormat()
            selected.format.setBackground(QColor(c["selected"]))
            context.selections = [selected]
        self.document.documentLayout().draw(painter, context)

    def _hit(self, point):
        p = QPointF(point.x() - self.settings.padding, point.y() - self.settings.padding + self.page * self.page_height)
        return max(0, self.document.documentLayout().hitTest(p, Qt.HitTestAccuracy.FuzzyHit))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setFocus()
            self.selection.setPosition(self._hit(event.position()))
            self.update()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.selection.setPosition(self._hit(event.position()), QTextCursor.MoveMode.KeepAnchor)
            self.update()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        action = menu.addAction("复制选中文字", self.copy)
        action.setEnabled(self.selection.hasSelection())
        menu.exec(event.globalPos())

    def copy(self):
        QGuiApplication.clipboard().setText(self.selection.selectedText().replace("\u2029", "\n"))

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Copy):
            self.copy()
        elif QKeySequence(event.key()).toString() == self.settings.next_key:
            self.turned.emit(1)
        elif QKeySequence(event.key()).toString() == self.settings.previous_key:
            self.turned.emit(-1)
        else:
            super().keyPressEvent(event)
