from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from quietreader.i18n import tr


class BookInfoPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("bookInfoPanel")
        self.book = None
        self.language = "system"
        self.cover_image = None
        self.cover = QLabel()
        self.cover.setObjectName("bookCoverLabel")
        self.cover.setAccessibleName("书籍封面")
        self.cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover.setMinimumHeight(140)
        self.cover.setMaximumHeight(280)
        self.details = QLabel()
        self.details.setObjectName("bookInfoDetails")
        self.details.setTextFormat(Qt.TextFormat.PlainText)
        self.details.setWordWrap(True)
        self.details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        content = QWidget()
        content.setObjectName("bookInfoContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.cover)
        layout.addWidget(self.details)
        layout.addStretch()
        scroll = QScrollArea()
        scroll.setObjectName("bookInfoScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.viewport().setObjectName("bookInfoViewport")
        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        self.set_book(None)

    def set_book(self, book, language=None):
        self.book = book
        if language is not None:
            self.language = language
        image = QImage.fromData(book.cover) if book and book.cover else QImage()
        self.cover_image = image if not image.isNull() else None
        self._update_cover()
        if not book:
            self.details.setText(tr("打开书籍以查看资料。", self.language))
            return
        rows = [("书名", book.title), ("作者", book.author), ("语言", book.language),
                ("出版者", book.publisher), ("出版日期", book.publication_date),
                ("标识符", book.identifier), ("简介", book.description)]
        text = "\n\n".join(tr(f"{label}：{{value}}", self.language, value=value) for label, value in rows if value)
        self.details.setText(text or tr("暂无书籍资料。", self.language))

    def _update_cover(self):
        if self.cover_image is None:
            self.cover.setPixmap(QPixmap())
            self.cover.setText(tr("没有可用封面", self.language))
            return
        width = max(64, min(200, self.width() - 24))
        pixmap = QPixmap.fromImage(self.cover_image).scaled(
            width, 260, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self.cover.setText("")
        self.cover.setPixmap(pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_cover()
