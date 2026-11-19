from math import isfinite
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton,
    QTabWidget, QVBoxLayout, QWidget,
)

from quietreader.i18n import tr
from quietreader.library.shelf import UNCLASSIFIED


class ShelfPanel(QWidget):
    add_requested = Signal()
    open_requested = Signal(str)
    move_requested = Signal(str, str)
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

        heading = QWidget()
        heading.setObjectName("shelfHeading")
        heading_layout = QHBoxLayout(heading)
        heading_layout.setContentsMargins(2, 0, 2, 0)
        self.title = QLabel()
        self.title.setObjectName("shelfTitle")
        heading_layout.addWidget(self.title)
        heading_layout.addStretch(1)
        self.add_button = QPushButton()
        self.add_button.setObjectName("primary")
        self.add_button.clicked.connect(self.add_requested.emit)
        self.category_create = QPushButton()
        self.category_create.setObjectName("secondaryAction")
        self.category_create.clicked.connect(self.create_category_requested.emit)
        self.category_delete = QPushButton()
        self.category_delete.setObjectName("quietAction")
        self.category_delete.clicked.connect(self._delete_selected_category)
        heading_layout.addWidget(self.add_button)
        heading_layout.addWidget(self.category_create)
        heading_layout.addWidget(self.category_delete)
        outer.addWidget(heading)

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
        self.all_target_label = QLabel()
        self.all_target_label.setObjectName("toolbarLabel")
        self.all_target = QComboBox()
        self.all_target.setMinimumWidth(150)
        self.all_move = QPushButton()
        self.all_move.clicked.connect(lambda: self._move_selected(self.all_books, self.all_target))
        self.all_remove = QPushButton()
        self.all_remove.setObjectName("quietAction")
        self.all_remove.clicked.connect(lambda: self._remove_selected(self.all_books))
        all_actions.addWidget(self.all_target_label)
        all_actions.addWidget(self.all_target)
        all_actions.addWidget(self.all_move)
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
        self.category_target_label = QLabel()
        self.category_target_label.setObjectName("toolbarLabel")
        self.category_target = QComboBox()
        self.category_target.setMinimumWidth(150)
        self.category_move = QPushButton()
        self.category_move.clicked.connect(lambda: self._move_selected(self.category_books, self.category_target))
        self.category_remove = QPushButton()
        self.category_remove.setObjectName("quietAction")
        self.category_remove.clicked.connect(lambda: self._remove_selected(self.category_books))
        category_actions.addWidget(self.category_target_label)
        category_actions.addWidget(self.category_target)
        category_actions.addWidget(self.category_move)
        category_actions.addWidget(self.category_remove)
        category_actions.addStretch(1)
        category_layout.addWidget(category_toolbar)

        category_content = QHBoxLayout()
        category_content.setContentsMargins(0, 0, 0, 0)
        category_content.setSpacing(12)
        self.category_list = self._book_list("书籍分类", openable=False)
        self.category_list.setMinimumWidth(150)
        self.category_list.setMaximumWidth(235)
        self.category_list.currentRowChanged.connect(self._refresh_category_books)
        self.category_books = self._book_list("分类中的书籍")
        category_content.addWidget(self.category_list)
        category_content.addWidget(self.category_books, 1)
        category_layout.addLayout(category_content, 1)
        self.tabs.addTab(category_page, "分类")

        outer.addWidget(self.tabs, 1)
        self.retranslate("system")

    def _book_list(self, accessible_name, openable=True):
        widget = QListWidget()
        widget.setObjectName("shelfList")
        widget.setAccessibleName(accessible_name)
        widget.setWordWrap(True)
        if openable:
            widget.itemActivated.connect(self._open_item)
        return widget

    def retranslate(self, language):
        self.language = language
        self.title.setText(tr("书架", language))
        self.add_button.setText(tr("添加书籍", language))
        self.add_button.setToolTip(tr("添加本地 TXT / EPUB 到书架 · Ctrl+O", language))
        self.add_button.setAccessibleName(tr("添加书籍", language))
        self.all_target_label.setText(tr("移动到分类", language))
        self.category_target_label.setText(tr("移动到分类", language))
        for index, source in enumerate(("最近阅读", "所有书籍", "分类")):
            self.tabs.setTabText(index, tr(source, language))
        self.category_create.setText(tr("新建分类", language))
        self.category_delete.setText(tr("删除分类", language))
        self.all_move.setText(tr("移动", language))
        self.all_move.setToolTip(tr("移动到分类", language))
        self.all_move.setAccessibleName(tr("移动到分类", language))
        self.all_remove.setText(tr("移除", language))
        self.all_remove.setToolTip(tr("从书架移除", language))
        self.all_remove.setAccessibleName(tr("从书架移除", language))
        self.category_move.setText(tr("移动", language))
        self.category_move.setToolTip(tr("移动到分类", language))
        self.category_move.setAccessibleName(tr("移动到分类", language))
        self.category_remove.setText(tr("移除", language))
        self.category_remove.setToolTip(tr("从书架移除", language))
        self.category_remove.setAccessibleName(tr("从书架移除", language))
        self.all_target.setToolTip(tr("移动到分类", language))
        self.category_target.setToolTip(tr("移动到分类", language))
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

    def _refresh_lists(self):
        if not hasattr(self, "all_books"):
            return
        target_data = self.all_target.currentData() if self.all_target.count() else None
        category_target_data = self.category_target.currentData() if self.category_target.count() else None
        category_name = self.category_list.currentItem().data(Qt.ItemDataRole.UserRole) if self.category_list.currentItem() else UNCLASSIFIED
        recent_records = sorted((r for r in self.records if r.get("last_read")), key=lambda r: r.get("last_read", ""), reverse=True)
        all_records = sorted(self.records, key=lambda r: r.get("title", "").casefold())
        self._fill(self.recent, recent_records[:100])
        self._fill(self.all_books, all_records)
        self.all_target.clear()
        self.category_target.clear()
        targets = [UNCLASSIFIED, *self.categories]
        for combo in (self.all_target, self.category_target):
            for name in targets:
                combo.addItem(tr("未分类", self.language) if name == UNCLASSIFIED else name, name)
        if target_data in targets:
            self.all_target.setCurrentIndex(self.all_target.findData(target_data))
        if category_target_data in targets:
            self.category_target.setCurrentIndex(self.category_target.findData(category_target_data))
        self.category_list.clear()
        for name in targets:
            item = QListWidgetItem(tr("未分类", self.language) if name == UNCLASSIFIED else name)
            item.setData(Qt.ItemDataRole.UserRole, name)
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
            if isinstance(chapter, str) and chapter.strip() and type(progress) in (int, float) and isfinite(progress):
                percentage = f"{max(0, min(1, progress)):.0%}"
                detail = tr("{chapter} · 全书 {progress}", self.language, chapter=chapter, progress=percentage)
            elif record.get("_has_saved_position") or record.get("last_read"):
                detail = tr("打开书籍后更新进度", self.language)
            else:
                detail = tr("尚未开始阅读 · 全书 0%", self.language)
            item = QListWidgetItem(f"{title}\n{detail}")
            item.setSizeHint(QSize(0, 64))
            if record.get("author"):
                item.setToolTip(f"{record['author']}\n{detail}\n{record['path']}")
            else:
                item.setToolTip(f"{detail}\n{record['path']}")
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

    def _move_selected(self, widget, target):
        item = widget.currentItem()
        if item is not None and target.currentData():
            self.move_requested.emit(item.data(Qt.ItemDataRole.UserRole), target.currentData())

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
