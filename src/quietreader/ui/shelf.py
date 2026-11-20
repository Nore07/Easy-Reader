import json
from math import isfinite
from pathlib import Path

from PySide6.QtCore import QMimeData, QRect, QSize, Qt, Signal
from PySide6.QtGui import QDrag, QFont, QFontMetrics, QPalette
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QStyle, QStyleOptionViewItem,
    QStyledItemDelegate, QTabWidget, QVBoxLayout, QWidget,
)

from quietreader.i18n import tr
from quietreader.library.shelf import UNCLASSIFIED


_BOOK_IDS_MIME_TYPE = "application/x-quietreader-book-ids"
_BOOK_TITLE_ROLE = Qt.ItemDataRole.UserRole + 1
_BOOK_DETAIL_ROLE = Qt.ItemDataRole.UserRole + 2
_BOOK_PROGRESS_ROLE = Qt.ItemDataRole.UserRole + 3


class BookItemDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        style_option = QStyleOptionViewItem(option)
        self.initStyleOption(style_option, index)
        style_option.text = ""
        widget = style_option.widget
        style = widget.style() if widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, style_option, painter, widget)

        title = index.data(_BOOK_TITLE_ROLE) or ""
        detail = index.data(_BOOK_DETAIL_ROLE) or ""
        progress = index.data(_BOOK_PROGRESS_ROLE) or ""
        painter.save()
        painter.setClipRect(option.rect)
        painter.setPen(option.palette.color(QPalette.ColorRole.Text))

        title_font = QFont(option.font)
        detail_font = QFont(option.font)
        if detail_font.pointSize() > 0:
            detail_font.setPointSize(max(8, detail_font.pointSize() - 1))
        elif detail_font.pixelSize() > 0:
            detail_font.setPixelSize(max(10, detail_font.pixelSize() - 1))

        title_metrics = QFontMetrics(title_font)
        detail_metrics = QFontMetrics(detail_font)
        content = option.rect.adjusted(12, 5, -12, -5)
        text_height = title_metrics.height() + detail_metrics.height() + 2
        top = content.top() + max(0, (content.height() - text_height) // 2)
        title_rect = QRect(content.left(), top, content.width(), title_metrics.height())
        detail_rect = QRect(
            content.left(), top + title_metrics.height() + 2,
            content.width(), detail_metrics.height(),
        )

        painter.setFont(title_font)
        visible_title = title_metrics.elidedText(
            title, Qt.TextElideMode.ElideRight, title_rect.width(),
        )
        painter.drawText(
            title_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            visible_title,
        )

        painter.setFont(detail_font)
        if progress:
            progress_width = detail_metrics.horizontalAdvance(progress)
            gap = detail_metrics.horizontalAdvance("  ")
            progress_rect = QRect(
                detail_rect.right() - progress_width + 1,
                detail_rect.top(),
                progress_width,
                detail_rect.height(),
            )
            detail_width = max(0, detail_rect.width() - progress_width - gap)
            detail_rect.setWidth(detail_width)
            painter.drawText(
                detail_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                detail_metrics.elidedText(detail, Qt.TextElideMode.ElideRight, detail_width),
            )
            painter.drawText(
                progress_rect,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                progress,
            )
        else:
            painter.drawText(
                detail_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                detail_metrics.elidedText(detail, Qt.TextElideMode.ElideRight, detail_rect.width()),
            )
        painter.restore()


class DraggableBookListWidget(QListWidget):
    def startDrag(self, supported_actions):
        book_ids = [
            item.data(Qt.ItemDataRole.UserRole)
            for item in self.selectedItems()
            if item.data(Qt.ItemDataRole.UserRole)
        ]
        if not book_ids:
            return
        mime_data = QMimeData()
        mime_data.setData(_BOOK_IDS_MIME_TYPE, json.dumps(book_ids).encode("utf-8"))
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.exec(Qt.DropAction.MoveAction)


class CategoryDropListWidget(QListWidget):
    books_dropped = Signal(list, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)
        self.setDropIndicatorShown(True)

    @staticmethod
    def _book_ids(mime_data):
        if not mime_data.hasFormat(_BOOK_IDS_MIME_TYPE):
            return []
        try:
            values = json.loads(bytes(mime_data.data(_BOOK_IDS_MIME_TYPE)).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return []
        if not isinstance(values, list):
            return []
        return list(dict.fromkeys(value for value in values if isinstance(value, str) and value))

    def _drop_target(self, event):
        book_ids = self._book_ids(event.mimeData())
        item = self.itemAt(event.position().toPoint())
        if not book_ids or item is None:
            return None
        category = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(category, str) or not category:
            return None
        return item, book_ids, category

    def dragEnterEvent(self, event):
        if self._drop_target(event) is None:
            event.ignore()
            return
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()

    def dragMoveEvent(self, event):
        if self._drop_target(event) is None:
            event.ignore()
            return
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()

    def dropEvent(self, event):
        target = self._drop_target(event)
        if target is None:
            event.ignore()
            return
        _item, book_ids, category = target
        event.setDropAction(Qt.DropAction.MoveAction)
        event.accept()
        self.books_dropped.emit(book_ids, category)


class ShelfPanel(QWidget):
    add_requested = Signal()
    open_requested = Signal(str)
    move_books_requested = Signal(list, str)
    remove_requested = Signal(str)
    create_category_requested = Signal()
    delete_category_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.language = "system"
        self.records = []
        self.categories = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(12)

        action_holder = QWidget(self)
        action_holder.hide()
        self.add_button = QPushButton(action_holder)
        self.add_button.setObjectName("primary")
        self.add_button.clicked.connect(self.add_requested.emit)
        self.category_create = QPushButton(action_holder)
        self.category_create.setObjectName("secondaryAction")
        self.category_create.clicked.connect(self.create_category_requested.emit)
        self.category_delete = QPushButton(action_holder)
        self.category_delete.setObjectName("quietAction")
        self.category_delete.clicked.connect(self._delete_selected_category)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("shelfTabs")
        self.tabs.currentChanged.connect(self._refresh_category_books)

        recent_page = QWidget()
        recent_layout = QVBoxLayout(recent_page)
        recent_layout.setContentsMargins(0, 8, 0, 0)
        self.recent = self._book_list("最近阅读")
        recent_layout.addWidget(self.recent)
        self.tabs.addTab(recent_page, "最近阅读")

        all_page = QWidget()
        all_layout = QVBoxLayout(all_page)
        all_layout.setContentsMargins(0, 8, 0, 0)
        all_layout.setSpacing(10)
        all_toolbar = QWidget()
        all_toolbar.setObjectName("shelfToolbar")
        all_actions = QHBoxLayout(all_toolbar)
        all_actions.setContentsMargins(0, 0, 0, 0)
        all_actions.setSpacing(8)
        self.all_remove = QPushButton()
        self.all_remove.setObjectName("quietAction")
        self.all_remove.clicked.connect(lambda: self._remove_selected(self.all_books))
        all_actions.addWidget(self.all_remove)
        all_actions.addStretch(1)
        all_layout.addWidget(all_toolbar)
        self.all_books = self._book_list("所有书籍")
        all_layout.addWidget(self.all_books, 1)
        self.tabs.addTab(all_page, "所有书籍")

        category_page = QWidget()
        category_layout = QVBoxLayout(category_page)
        category_layout.setContentsMargins(0, 8, 0, 0)
        category_layout.setSpacing(10)
        category_toolbar = QWidget()
        category_toolbar.setObjectName("shelfToolbar")
        category_actions = QHBoxLayout(category_toolbar)
        category_actions.setContentsMargins(0, 0, 0, 0)
        category_actions.setSpacing(8)
        self.category_remove = QPushButton()
        self.category_remove.setObjectName("quietAction")
        self.category_remove.clicked.connect(lambda: self._remove_selected(self.category_books))
        category_actions.addWidget(self.category_remove)
        category_actions.addStretch(1)
        category_layout.addWidget(category_toolbar)

        category_content = QHBoxLayout()
        category_content.setContentsMargins(0, 0, 0, 0)
        category_content.setSpacing(12)
        self.category_list = self._book_list(
            "书籍分类", openable=False, widget_type=CategoryDropListWidget,
        )
        self.category_list.books_dropped.connect(self.move_books_requested)
        self.category_list.setMinimumWidth(150)
        self.category_list.setMaximumWidth(235)
        self.category_list.currentRowChanged.connect(self._refresh_category_books)
        self.category_books = self._book_list(
            "分类中的书籍", widget_type=DraggableBookListWidget,
        )
        self.category_books.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.category_books.setDragEnabled(True)
        self.category_books.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        category_content.addWidget(self.category_list)
        category_content.addWidget(self.category_books, 1)
        category_layout.addLayout(category_content, 1)
        self.tabs.addTab(category_page, "分类")

        outer.addWidget(self.tabs, 1)
        self.retranslate("system")

    def _book_list(self, accessible_name, openable=True, widget_type=QListWidget):
        widget = widget_type()
        widget.setObjectName("shelfList")
        widget.setAccessibleName(accessible_name)
        if openable:
            widget.setWordWrap(False)
            widget.setItemDelegate(BookItemDelegate(widget))
            widget.itemActivated.connect(self._open_item)
        else:
            widget.setWordWrap(True)
        return widget

    def retranslate(self, language):
        self.language = language
        self.add_button.setText(tr("添加书籍", language))
        self.add_button.setToolTip(tr("添加本地 TXT / EPUB 到书架 · Ctrl+O", language))
        self.add_button.setAccessibleName(tr("添加书籍", language))
        for index, source in enumerate(("最近阅读", "所有书籍", "分类")):
            self.tabs.setTabText(index, tr(source, language))
        self.category_create.setText(tr("新建分类", language))
        self.category_delete.setText(tr("删除分类", language))
        self.category_list.setToolTip(tr("将右侧书籍拖到分类上即可快速移动。", language))
        self.category_books.setToolTip(tr("按住 Ctrl 或 Shift 多选，再拖到左侧分类。", language))
        self.all_remove.setText(tr("移除", language))
        self.all_remove.setToolTip(tr("从书架移除", language))
        self.all_remove.setAccessibleName(tr("从书架移除", language))
        self.category_remove.setText(tr("移除", language))
        self.category_remove.setToolTip(tr("从书架移除", language))
        self.category_remove.setAccessibleName(tr("从书架移除", language))
        self._set_accessible_names(language)
        self._refresh_lists()

    def _set_accessible_names(self, language):
        self.all_books.setAccessibleName(tr("所有书籍", language))
        self.recent.setAccessibleName(tr("最近阅读", language))
        self.category_list.setAccessibleName(tr("书籍分类", language))
        self.category_books.setAccessibleName(tr("分类中的书籍", language))

    def refresh(self, records, categories, category_for_path, language=None):
        if language is not None:
            self.language = language
        self.records = list(records)
        self.categories = list(categories)
        self._category_for_path = category_for_path
        self._refresh_lists()

    def reveal_book(self, book_id):
        if not book_id or not hasattr(self, "all_books"):
            return False
        self.tabs.setCurrentIndex(1)
        for row in range(self.all_books.count()):
            item = self.all_books.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == book_id:
                self.all_books.setCurrentRow(row)
                self.all_books.scrollToItem(item)
                return True
        return False

    def select_category(self, category):
        self.tabs.setCurrentIndex(2)
        for row in range(self.category_list.count()):
            item = self.category_list.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == category:
                self.category_list.setCurrentRow(row)
                self.category_list.scrollToItem(item)
                return True
        return False

    def _refresh_lists(self):
        if not hasattr(self, "all_books"):
            return
        category_name = self.category_list.currentItem().data(Qt.ItemDataRole.UserRole) if self.category_list.currentItem() else UNCLASSIFIED
        recent_records = sorted((r for r in self.records if r.get("last_read")), key=lambda r: r.get("last_read", ""), reverse=True)
        all_records = sorted(self.records, key=lambda r: r.get("title", "").casefold())
        self._fill(self.recent, recent_records[:100])
        self._fill(self.all_books, all_records)
        targets = [UNCLASSIFIED, *self.categories]
        self.category_list.clear()
        for name in targets:
            item = QListWidgetItem(tr("未分类", self.language) if name == UNCLASSIFIED else name)
            item.setData(Qt.ItemDataRole.UserRole, name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDropEnabled)
            self.category_list.addItem(item)
        row = next((i for i in range(self.category_list.count()) if self.category_list.item(i).data(Qt.ItemDataRole.UserRole) == category_name), 0)
        self.category_list.setCurrentRow(row)
        self._refresh_category_books()

    def _fill(self, widget, records):
        widget.clear()
        for record in records:
            title = record.get("title") or Path(record["path"]).stem
            chapter = record.get("reading_chapter")
            progress = record.get("reading_progress")
            has_progress = type(progress) in (int, float) and isfinite(progress)
            if has_progress:
                percentage = f"{max(0, min(1, progress)):.0%}"
                progress_label = tr("全书 {progress}", self.language, progress=percentage)
            else:
                percentage = "0%"
                progress_label = ""
            if isinstance(chapter, str) and chapter.strip():
                detail = chapter.strip()
            elif record.get("_has_saved_position") or record.get("last_read") or (has_progress and progress > 0):
                detail = tr("打开书籍后更新进度", self.language)
            else:
                detail = tr("尚未开始阅读", self.language)
                if not has_progress:
                    progress_label = tr("全书 {progress}", self.language, progress=percentage)
            summary = " · ".join(part for part in (detail, progress_label) if part)
            item = QListWidgetItem(f"{title}\n{summary}")
            item.setSizeHint(QSize(0, 64))
            item.setData(_BOOK_TITLE_ROLE, title)
            item.setData(_BOOK_DETAIL_ROLE, detail)
            item.setData(_BOOK_PROGRESS_ROLE, progress_label)
            if record.get("author"):
                item.setToolTip(f"{record['author']}\n{summary}\n{record['path']}")
            else:
                item.setToolTip(f"{summary}\n{record['path']}")
            item.setData(Qt.ItemDataRole.UserRole, record.get("id", ""))
            widget.addItem(item)

    def _refresh_category_books(self, *_):
        if not hasattr(self, "category_books"):
            return
        item = self.category_list.currentItem()
        category = item.data(Qt.ItemDataRole.UserRole) if item else UNCLASSIFIED
        records = [record for record in self.records if self._category_for_path(record["path"]) == category]
        records.sort(key=lambda r: r.get("title", "").casefold())
        self._fill(self.category_books, records)
        self.category_delete.setEnabled(
            self.tabs.currentIndex() == 2 and category != UNCLASSIFIED and category in self.categories
        )

    def _open_item(self, item):
        book_id = item.data(Qt.ItemDataRole.UserRole)
        if book_id:
            self.open_requested.emit(book_id)

    def _remove_selected(self, widget):
        item = widget.currentItem()
        if item is not None:
            self.remove_requested.emit(item.data(Qt.ItemDataRole.UserRole))

    def _delete_selected_category(self):
        item = self.category_list.currentItem()
        if item is not None:
            category = item.data(Qt.ItemDataRole.UserRole)
            if category != UNCLASSIFIED:
                self.delete_category_requested.emit(category)
