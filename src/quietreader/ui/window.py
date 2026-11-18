from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
import os

from PySide6.QtCore import QObject, QPoint, QRunnable, QThreadPool, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QGuiApplication, QIcon, QKeySequence, QPainter, QPen, QPixmap, QPolygon, QShortcut
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel, QInputDialog, QMessageBox,
    QListWidget, QListWidgetItem, QMainWindow, QMenu, QPushButton,
    QSizeGrip, QSlider, QSystemTrayIcon, QTabWidget, QVBoxLayout, QWidget,
)

from quietreader.content.local import ENCODINGS, ImportError as BookImportError, load_book
from quietreader.desktop.geometry import visible_bounds
from quietreader.desktop.hotkey import GlobalHotkey
from quietreader.desktop.window_effects import set_window_border_hidden
from quietreader.domain.models import Bookmark, Position, Settings, restore_position
from quietreader.ui.reader import PageView
from quietreader.ui.settings import SettingsDialog
from quietreader.ui.theme import colors, stylesheet
from quietreader.i18n import tr, install_qt_translator
from quietreader.ui.layout_panel import LayoutPanel
from quietreader.ui.book_info import BookInfoPanel
from quietreader.persistence.store import MAX_BOOKMARKS, MAX_BOOKMARK_NOTE, MAX_BOOK_RECORDS
from quietreader.library.shelf import ShelfError, ShelfManager, UNCLASSIFIED, book_id_for_path
from quietreader.ui.shelf import ShelfPanel


def book_icon():
    image = QPixmap(64, 64)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#315743"))
    painter.drawRoundedRect(2, 2, 60, 60, 14, 14)
    painter.setPen(QPen(QColor("#f5f3eb"), 3))
    painter.drawLine(32, 19, 32, 47)
    points = [(13, 18), (25, 18), (32, 23), (39, 18), (51, 18), (51, 44), (39, 44), (32, 49), (25, 44), (13, 44), (13, 18)]
    painter.drawPolyline(QPolygon([QPoint(x, y) for x, y in points]))
    painter.end()
    return QIcon(image)


class ImportSignals(QObject):
    loaded = Signal(object)
    failed = Signal(str, bool)
    finished = Signal()


class ImportTask(QRunnable):
    def __init__(self, path, encoding):
        super().__init__()
        self.path, self.encoding = path, encoding
        self.signals = ImportSignals()

    def run(self):
        try:
            self.signals.loaded.emit(load_book(self.path, self.encoding))
        except BookImportError as error:
            self.signals.failed.emit(str(error), error.encoding_choice)
        except Exception:
            self.signals.failed.emit("导入失败，文件结构可能不受支持。请检查文件后重试。", False)
        finally:
            self.signals.finished.emit()


class DragHeader(QWidget):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.window().windowHandle():
            self.window().windowHandle().startSystemMove()
        else:
            super().mousePressEvent(event)


class DragHandle(QPushButton):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.window().windowHandle():
            self.window().windowHandle().startSystemMove()
        else:
            super().mousePressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self, store, enable_system=True):
        super().__init__()
        self.store = store
        self.shelf_manager = ShelfManager(store.path.parent)
        self.settings = Settings.from_dict(store.state["settings"])
        self.enable_system = enable_system
        self.book = None
        self.section_index = 0
        self.loading = False
        self.pending_path = None
        self.quitting = False
        self.closed = False
        self.focus_mode = False
        self._chrome_visibility = {}
        self.status_source = ("离线优先。添加书籍即可开始阅读。", {})
        self.sidebar_requested = True
        self.sidebar_manual = False
        self.tray = None
        self.hotkey = None
        self.emergency_hotkey = None
        self.worker = None
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.setWindowTitle("QuietReader · 静读")
        self.setMinimumSize(380, 360)
        self.setWindowIcon(book_icon())
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(350)
        self.save_timer.timeout.connect(self.save_state)
        self._build_ui()
        if enable_system:
            self._setup_system()
        self.apply_settings(self.settings)
        screens = [s.availableGeometry().getRect() for s in QGuiApplication.screens()]
        self.setGeometry(*visible_bounds(store.state["window"], screens))
        QGuiApplication.styleHints().colorSchemeChanged.connect(self._system_theme_changed)
        QGuiApplication.instance().screenRemoved.connect(self._screen_removed)
        self._refresh_recent()
        if store.warning:
            self.set_status(store.warning)

    @staticmethod
    def _label(text="", name=""):
        label = QLabel(text)
        label.setTextFormat(Qt.TextFormat.PlainText)
        if name:
            label.setObjectName(name)
        if text:
            label.setProperty("translation_source", text)
        return label

    def _button(self, text, callback, checkable=False):
        button = QPushButton(text)
        button.setProperty("translation_source", text)
        button.setCheckable(checkable)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.clicked.connect(callback)
        return button

    def _build_ui(self):
        self.surface = QWidget()
        self.surface.setObjectName("surface")
        self.setCentralWidget(self.surface)
        root = self.root_layout = QVBoxLayout(self.surface)
        root.setContentsMargins(14, 12, 14, 6)
        root.setSpacing(9)
        header = DragHeader()
        top = QHBoxLayout(header)
        top.setContentsMargins(2, 0, 0, 6)
        brand = self.brand = self._label("静读", "brand")
        brand.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        top.addWidget(brand)
        self.eyebrow = self._label("QUIET READER", "eyebrow")
        self.eyebrow.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        top.addWidget(self.eyebrow)
        top.addStretch()
        self.drag_handle = DragHandle("⠿")
        self.drag_handle.setToolTip("按住拖动浮窗（全透明时也可使用）")
        self.drag_handle.setAccessibleName("拖动浮窗")
        self.drag_handle.setFixedWidth(32)
        top.addWidget(self.drag_handle)
        self.open_button = self._button("添加书籍", self.choose_file)
        self.open_button.setObjectName("primary")
        self.open_button.setToolTip("添加本地 TXT / EPUB 到书架 · Ctrl+O")
        top.addWidget(self.open_button)
        top.addWidget(self._button("排版", self.show_layout_panel))
        top.addWidget(self._button("偏好", self.show_settings))
        top.addWidget(self._button("隐藏", self.hide_or_minimize))
        self.close_button = self._button("×", self.close)
        self.close_button.setToolTip("关闭窗口（可在偏好中设置隐藏至托盘或退出）")
        self.close_button.setAccessibleName("关闭窗口")
        top.addWidget(self.close_button)
        root.addWidget(header)
        tools_widget = QWidget()
        tools = QHBoxLayout(tools_widget)
        tools.setContentsMargins(0, 0, 0, 0)
        tools.addWidget(self._button("阅读 / 书架", self.toggle_sidebar))
        self.float_button = self._button("浮窗", self.toggle_floating, True)
        tools.addWidget(self.float_button)
        self.pin_button = self._button("置顶", self.toggle_pin, True)
        tools.addWidget(self.pin_button)
        self.encoding_button = self._button("编码", self.toggle_encoding)
        self.encoding_button.setToolTip("TXT 乱码时，手动选择编码重新读取")
        self.encoding_button.hide()
        tools.addWidget(self.encoding_button)
        self.focus_button = self._button("专注", self.toggle_focus, True)
        tools.addWidget(self.focus_button)
        tools.addStretch()
        root.addWidget(tools_widget)
        self.hotkey_notice = self._label("", "status")
        self.hotkey_notice.setWordWrap(True)
        self.hotkey_notice.hide()
        root.addWidget(self.hotkey_notice)
        body = self.body_layout = QHBoxLayout()
        body.setSpacing(22)
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(220)
        side = QVBoxLayout(self.sidebar)
        side.setContentsMargins(10, 12, 10, 12)
        side.addWidget(self._label("我的阅读", "eyebrow"))
        tabs = self.tabs = QTabWidget()
        reading_module = QWidget()
        reading_module_layout = QVBoxLayout(reading_module)
        reading_module_layout.setContentsMargins(0, 0, 0, 0)
        self.reading_tabs = QTabWidget()
        self.chapters = QListWidget()
        self.chapters.setAccessibleName("书籍目录")
        self.chapters.itemActivated.connect(self._chapter_activated)
        self.chapters.itemClicked.connect(self._chapter_activated)
        self.reading_tabs.addTab(self.chapters, "目录")
        bookmark_panel = QWidget()
        bookmark_layout = QVBoxLayout(bookmark_panel)
        self.bookmarks = QListWidget()
        self.bookmarks.setAccessibleName("书签与笔记")
        self.bookmarks.itemActivated.connect(self._bookmark_activated)
        self.bookmarks.itemClicked.connect(self._bookmark_activated)
        bookmark_layout.addWidget(self.bookmarks, 1)
        bookmark_actions = QHBoxLayout()
        self.bookmark_add_button = self._button("添加书签", self.add_bookmark)
        self.bookmark_note_button = self._button("编辑笔记", self.edit_bookmark_note)
        self.bookmark_remove_button = self._button("删除书签", self.remove_bookmark)
        bookmark_actions.addWidget(self.bookmark_add_button)
        bookmark_actions.addWidget(self.bookmark_note_button)
        bookmark_actions.addWidget(self.bookmark_remove_button)
        bookmark_layout.addLayout(bookmark_actions)
        self.reading_tabs.addTab(bookmark_panel, "书签")
        self.pages = QListWidget()
        self.pages.setAccessibleName("书中页码")
        self.pages.itemActivated.connect(self._page_activated)
        self.pages.itemClicked.connect(self._page_activated)
        self.reading_tabs.addTab(self.pages, "页码")
        self.landmarks = QListWidget()
        self.landmarks.setAccessibleName("书中位置")
        self.landmarks.itemActivated.connect(self._page_activated)
        self.landmarks.itemClicked.connect(self._page_activated)
        self.reading_tabs.addTab(self.landmarks, "位置")
        self.reading_tabs.setTabVisible(2, False)
        self.reading_tabs.setTabVisible(3, False)
        reading_module_layout.addWidget(self.reading_tabs)
        tabs.addTab(reading_module, "阅读")
        self.shelf = ShelfPanel()
        self.shelf.open_requested.connect(self.open_shelf_book)
        self.shelf.move_requested.connect(self.move_shelf_book)
        self.shelf.remove_requested.connect(self._confirm_remove_shelf_book)
        self.shelf.create_category_requested.connect(self.prompt_create_shelf_category)
        self.shelf.delete_category_requested.connect(self._confirm_delete_shelf_category)
        tabs.addTab(self.shelf, "书架")
        self.recent = self.shelf.recent
        self.book_info = BookInfoPanel()
        tabs.addTab(self.book_info, "资料")
        tabs.setTabVisible(2, False)
        side.addWidget(tabs)
        side.addWidget(self._label("本地阅读 · 无需联网", "status"))
        body.addWidget(self.sidebar)
        reading = self.reading_layout = QVBoxLayout()
        reading.setSpacing(4)
        self.book_title = self._label("一本书，一处安静", "bookTitle")
        self.book_title.setWordWrap(True)
        reading.addWidget(self.book_title)
        self.chapter_title = self._label("从你的本地书籍开始", "chapterTitle")
        self.chapter_title.setWordWrap(True)
        reading.addWidget(self.chapter_title)
        self.reader = PageView()
        self.reader.turned.connect(self.turn_page)
        self.reader.chapter_turned.connect(self.turn_chapter)
        self.reader.link_activated.connect(self.open_epub_link)
        self.reader.exit_focus.connect(lambda: self.toggle_focus() if self.focus_mode else None)
        self.reader.focus_requested.connect(self.toggle_focus)
        self.reader.visibility_requested.connect(self.toggle_visible)
        self.reader.emergency_requested.connect(self.emergency_exit)
        self.reader.reflowed.connect(self._update_progress)
        reading.addWidget(self.reader, 1)
        self.progress = QSlider(Qt.Orientation.Horizontal)
        self.progress.setRange(0, 1000)
        self.progress.setAccessibleName("全书阅读进度")
        self.progress.sliderReleased.connect(self._seek)
        self.progress.setEnabled(False)
        reading.addWidget(self.progress)
        navigation_widget = QWidget()
        navigation = QHBoxLayout(navigation_widget)
        navigation.setContentsMargins(0, 0, 0, 0)
        self.previous_chapter = self._button("上一章", lambda: self.turn_chapter(-1))
        self.previous_chapter.setToolTip("上一章")
        self.previous = self._button("← 上一页", lambda: self.turn_page(-1))
        self.next = self._button("下一页 →", lambda: self.turn_page(1))
        self.next_chapter = self._button("下一章", lambda: self.turn_chapter(1))
        self.next_chapter.setToolTip("下一章")
        self.page_label = self._label("PageUp / PageDown", "status")
        navigation.addWidget(self.previous_chapter)
        navigation.addWidget(self.previous)
        navigation.addStretch()
        navigation.addWidget(self.page_label)
        navigation.addStretch()
        navigation.addWidget(self.next)
        navigation.addWidget(self.next_chapter)
        reading.addWidget(navigation_widget)
        body.addLayout(reading, 1)
        root.addLayout(body, 1)
        bottom_widget = QWidget()
        bottom = QHBoxLayout(bottom_widget)
        bottom.setContentsMargins(0, 0, 0, 0)
        self.status = self._label("离线优先。添加书籍即可开始阅读。", "status")
        self.status.setWordWrap(True)
        bottom.addWidget(self.status, 1)
        self.grip = QSizeGrip(self)
        bottom.addWidget(self.grip, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)
        root.addWidget(bottom_widget)
        self.encoding_bar = QWidget()
        encoding_layout = QHBoxLayout(self.encoding_bar)
        encoding_layout.setContentsMargins(0, 0, 0, 0)
        encoding_layout.addWidget(self._label("TXT 编码"))
        self.encoding = QComboBox()
        for value in ENCODINGS:
            self.encoding.addItem("自动识别" if value == "auto" else value.upper(), value)
        encoding_layout.addWidget(self.encoding)
        encoding_layout.addWidget(self._button("按此编码重试", self.retry_encoding))
        encoding_layout.addStretch()
        self.encoding_bar.hide()
        root.addWidget(self.encoding_bar)
        self.chrome_widgets = [header, tools_widget, self.hotkey_notice, self.sidebar, self.book_title, self.chapter_title, self.progress, navigation_widget, bottom_widget, self.encoding_bar]
        self.open_shortcut = QShortcut(QKeySequence("Ctrl+O"), self)
        self.open_shortcut.activated.connect(self.choose_file)
        self.settings_shortcut = QShortcut(QKeySequence("Ctrl+,"), self)
        self.settings_shortcut.activated.connect(self.show_settings)
        self.focus_shortcut = QShortcut(QKeySequence(self.settings.focus_key), self)
        self.focus_shortcut.activated.connect(self.toggle_focus)
        self.focus_shortcut.setAutoRepeat(False)
        self.escape_shortcut = QShortcut(QKeySequence("Esc"), self)
        self.escape_shortcut.activated.connect(lambda: self.toggle_focus() if self.focus_mode else None)
        self.escape_shortcut.setEnabled(False)
        self.visibility_shortcut = QShortcut(QKeySequence(self.settings.hotkey), self)
        self.visibility_shortcut.setAutoRepeat(False)
        self.visibility_shortcut.activated.connect(self.toggle_visible)
        self.emergency_shortcut = QShortcut(QKeySequence(self.settings.emergency_key), self)
        self.emergency_shortcut.setAutoRepeat(False)
        self.emergency_shortcut.activated.connect(self.emergency_exit)
        self._update_progress()

    def _setup_system(self):
        app = QApplication.instance()
        self.hotkey = GlobalHotkey(app, self.toggle_visible)
        self.emergency_hotkey = GlobalHotkey(app, self.emergency_exit, identifier=0x5153)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(self.windowIcon(), self)
            self.tray.setToolTip("QuietReader · 静读")
            menu = QMenu(self)
            for label, callback in [("显示 / 隐藏", self.toggle_visible), ("添加书籍…", self.choose_file), ("阅读偏好…", self.show_settings)]:
                action = QAction(label, self)
                action.setProperty("translation_source", label)
                action.triggered.connect(callback)
                menu.addAction(action)
            menu.addSeparator()
            self.tray_focus_action = QAction("进入专注模式", self)
            self.tray_focus_action.setCheckable(True)
            self.tray_focus_action.triggered.connect(self.toggle_focus)
            self.tray_focus_action.setEnabled(False)
            menu.addAction(self.tray_focus_action)
            action = QAction("退出 QuietReader", self)
            action.setProperty("translation_source", "退出 QuietReader")
            action.triggered.connect(self.quit_app)
            menu.addAction(action)
            self.tray.setContextMenu(menu)
            self.tray.activated.connect(lambda reason: self.toggle_visible() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
            self.tray.show()

    def choose_file(self):
        if self.loading:
            return
        self.reveal()
        files, _ = QFileDialog.getOpenFileNames(self, self.t("添加本地书籍"), "", self.t("阅读文件 (*.txt *.epub);;TXT (*.txt);;EPUB (*.epub)"), options=QFileDialog.Option.DontUseNativeDialog)
        if files:
            self.add_book_paths(files)

    def add_book_paths(self, paths, open_after=False):
        if self.loading or self.store.read_only:
            if self.store.read_only:
                self.set_status("保存数据来自不支持的版本。已保护原文件，本次不会保存更改。")
            return []
        added = []
        new_count = 0
        try:
            for source in paths:
                try:
                    source_path = Path(source).expanduser().resolve(strict=True)
                except (OSError, RuntimeError):
                    raise ShelfError("书籍文件不存在或无法访问。") from None
                source_key = str(source_path).casefold()
                existing = next((
                    record for record in self.store.state["books"]
                    if str(record.get("source_path", "")).casefold() == source_key
                ), None)
                if existing and self.shelf_manager.is_managed(existing["path"]):
                    added.append(existing)
                    continue
                if existing:
                    managed_path = self.shelf_manager.add_book(source_path)
                    self._remap_shelf_book(existing, managed_path)
                    existing["source_path"] = str(source_path)
                    added.append(existing)
                    new_count += 1
                    continue
                existing = next((
                    record for record in self.store.state["books"]
                    if str(Path(record["path"]).expanduser().resolve()).casefold() == source_key
                ), None)
                if existing and self.shelf_manager.is_managed(existing["path"]):
                    added.append(existing)
                    continue
                managed_path = self.shelf_manager.add_book(source_path)
                if existing:
                    self._remap_shelf_book(existing, managed_path)
                    existing["source_path"] = str(source_path)
                    added.append(existing)
                    new_count += 1
                    continue
                book_id = book_id_for_path(managed_path)
                record = {
                    "id": book_id,
                    "path": str(managed_path),
                    "title": managed_path.stem,
                    "author": "",
                    "encoding": "EPUB" if managed_path.suffix.lower() == ".epub" else "auto",
                    "last_read": "",
                    "source_path": str(source_path),
                }
                current = next((item for item in self.store.state["books"] if item["id"] == book_id), None)
                if current:
                    current.update(record)
                    record = current
                else:
                    self.store.state["books"].insert(0, record)
                    self.store.state["books"] = self.store.state["books"][:MAX_BOOK_RECORDS]
                new_count += 1
                added.append(record)
        except (OSError, ShelfError) as error:
            self._refresh_shelf()
            self.save_state()
            self._set_shelf_error(error)
            return added
        self._refresh_shelf()
        self.save_state()
        if new_count:
            self.set_status("已添加 {count} 本书到书架。", count=new_count)
        elif added:
            self.set_status("所选书籍已在书架中。")
        if open_after and added:
            record = added[-1]
            encoding = record.get("encoding", "auto")
            self.load_path(record["path"], encoding if encoding in ENCODINGS else "auto")
        return added

    def open_shelf_book(self, book_id):
        record = next((item for item in self.store.state["books"] if item["id"] == book_id), None)
        if record:
            encoding = record.get("encoding", "auto")
            self.load_path(record["path"], encoding if encoding in ENCODINGS else "auto")

    def create_shelf_category(self, name):
        if self.store.read_only:
            self.set_status("保存数据来自不支持的版本。已保护原文件，本次不会保存更改。")
            return None
        if self.loading:
            return None
        try:
            path = self.shelf_manager.create_category(name)
        except ShelfError as error:
            self._set_shelf_error(error)
            return None
        self._refresh_shelf()
        self.save_state()
        self.set_status("已创建分类“{name}”。", name=path.name)
        return path

    def prompt_create_shelf_category(self):
        name, accepted = QInputDialog.getText(self, self.t("新建分类"), self.t("分类名称"))
        if accepted:
            self.create_shelf_category(name)

    def _remap_shelf_book(self, record, new_path):
        old_id = record["id"]
        new_id = book_id_for_path(new_path)
        record["id"] = new_id
        record["path"] = str(new_path)
        positions = self.store.state.setdefault("positions", {})
        bookmarks = self.store.state.setdefault("bookmarks", {})
        for mapping in (positions, bookmarks):
            if old_id in mapping:
                previous = mapping.pop(old_id)
                mapping.setdefault(new_id, previous)
        if self.store.state.get("last_book") == old_id:
            self.store.state["last_book"] = new_id
        if self.book and self.book.id == old_id:
            self.book.id = new_id
            self.book.path = str(new_path)
        return new_id

    def move_shelf_book(self, book_id, category):
        if self.store.read_only or self.loading:
            if self.store.read_only:
                self.set_status("保存数据来自不支持的版本。已保护原文件，本次不会保存更改。")
            return
        record = next((item for item in self.store.state["books"] if item["id"] == book_id), None)
        if record is None:
            return
        try:
            self.save_state()
            was_managed = self.shelf_manager.is_managed(record["path"])
            old_path = record["path"]
            new_path = self.shelf_manager.move_book(record["path"], category)
        except (OSError, ShelfError) as error:
            self._set_shelf_error(error)
            return
        self._remap_shelf_book(record, new_path)
        if not was_managed:
            record.setdefault("source_path", old_path)
        self._refresh_shelf()
        self.save_state()
        self.set_status("已将《{title}》移动到“{category}”。", title=record["title"], category=self.t(category) if category == UNCLASSIFIED else category)

    def remove_shelf_book(self, book_id):
        if self.store.read_only or self.loading:
            if self.store.read_only:
                self.set_status("保存数据来自不支持的版本。已保护原文件，本次不会保存更改。")
            return False
        record = next((item for item in self.store.state["books"] if item["id"] == book_id), None)
        if record is None:
            return False
        if self.book and self.book.id == book_id:
            self.save_state()
        try:
            self.shelf_manager.remove_book(record["path"])
        except (OSError, ShelfError) as error:
            self._set_shelf_error(error)
            return False
        self.store.state["books"] = [item for item in self.store.state["books"] if item["id"] != book_id]
        self.store.state.get("positions", {}).pop(book_id, None)
        self.store.state.get("bookmarks", {}).pop(book_id, None)
        if self.store.state.get("last_book") == book_id:
            self.store.state["last_book"] = ""
        if self.book and self.book.id == book_id:
            self._clear_current_book()
        self._refresh_shelf()
        self.save_state()
        self.set_status("已从书架移除《{title}》。", title=record["title"])
        return True

    def _confirm_remove_shelf_book(self, book_id):
        record = next((item for item in self.store.state["books"] if item["id"] == book_id), None)
        if not record:
            return
        answer = QMessageBox.question(
            self, self.t("从书架移除"),
            self.t("确定从书架移除《{title}》吗？书架中的副本会被删除。", title=record["title"]),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.remove_shelf_book(book_id)

    def _confirm_delete_shelf_category(self, category):
        dialog = QMessageBox(self)
        dialog.setWindowTitle(self.t("删除分类"))
        dialog.setText(self.t("删除分类“{name}”时，如何处理其中的书籍？", name=category))
        delete_books = dialog.addButton(self.t("删除分类及书籍"), QMessageBox.ButtonRole.DestructiveRole)
        keep_books = dialog.addButton(self.t("仅删除分类，书籍移回未分类"), QMessageBox.ButtonRole.AcceptRole)
        cancel = dialog.addButton(self.t("取消"), QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(cancel)
        dialog.setEscapeButton(cancel)
        dialog.exec()
        if dialog.clickedButton() is delete_books:
            self.delete_shelf_category(category, delete_books=True)
        elif dialog.clickedButton() is keep_books:
            self.delete_shelf_category(category, delete_books=False)

    def delete_shelf_category(self, category, delete_books=False):
        if self.store.read_only or self.loading:
            if self.store.read_only:
                self.set_status("保存数据来自不支持的版本。已保护原文件，本次不会保存更改。")
            return False
        self.save_state()
        try:
            mapping = self.shelf_manager.delete_category(category, delete_books)
        except (OSError, ShelfError) as error:
            self._set_shelf_error(error)
            return False
        for record in list(self.store.state["books"]):
            old_path = Path(record["path"]).expanduser()
            try:
                resolved = old_path.resolve()
            except OSError:
                resolved = old_path
            if resolved not in mapping:
                continue
            new_path = mapping[resolved]
            if new_path is None:
                book_id = record["id"]
                self.store.state["books"].remove(record)
                self.store.state.get("positions", {}).pop(book_id, None)
                self.store.state.get("bookmarks", {}).pop(book_id, None)
                if self.store.state.get("last_book") == book_id:
                    self.store.state["last_book"] = ""
                if self.book and self.book.id == book_id:
                    self._clear_current_book()
            else:
                self._remap_shelf_book(record, new_path)
        self._refresh_shelf()
        self.save_state()
        self.set_status("已删除分类“{name}”。", name=category)
        return True

    def _clear_current_book(self):
        if self.focus_mode:
            self.toggle_focus()
        self.book = None
        self.section_index = 0
        self.reader.set_text("")
        self.book_title.setText(self.t("一本书，一处安静"))
        self.book_title.setProperty("translation_source", "一本书，一处安静")
        self.chapter_title.setText(self.t("从你的本地书籍开始"))
        self.chapter_title.setProperty("translation_source", "从你的本地书籍开始")
        self.setWindowTitle("QuietReader · 静读")
        self.chapters.clear()
        self.pages.clear()
        self.landmarks.clear()
        self.bookmarks.clear()
        self.book_info.set_book(None, self.settings.language)
        self.progress.setValue(0)
        self.page_label.setText("PageUp / PageDown")
        self.page_label.setProperty("translation_source", None)
        self.reading_tabs.setTabVisible(2, False)
        self.reading_tabs.setTabVisible(3, False)
        self.encoding_button.hide()
        self.encoding_bar.hide()
        self._update_progress()
        self._refresh_bookmarks()

    def _refresh_shelf(self):
        if not hasattr(self, "shelf"):
            return
        self.shelf.refresh(
            self.store.state["books"], self.shelf_manager.categories(),
            self.shelf_manager.category_for_path, self.settings.language,
        )

    def _recent_activated(self, item):
        book_id = item.data(Qt.ItemDataRole.UserRole)
        if book_id:
            self.open_shelf_book(book_id)

    def load_path(self, path, encoding="auto"):
        if self.loading or self.closed:
            return
        self.save_state()
        self.pending_path = Path(path)
        self.loading = True
        self.open_button.setEnabled(False)
        self.set_status("正在后台导入书籍…")
        self.worker = ImportTask(path, encoding)
        self.worker.signals.loaded.connect(self._loaded)
        self.worker.signals.failed.connect(self._failed)
        self.worker.signals.finished.connect(self._finished)
        self.pool.start(self.worker)

    def _loaded(self, book):
        if self.closed:
            return
        self.book = book
        self.setWindowTitle(f"{book.title} · QuietReader")
        self.book_title.setText(book.title)
        self.book_title.setProperty("translation_source", None)
        self.book_info.set_book(book, self.settings.language)
        self.tabs.setTabVisible(2, True)
        self._refresh_bookmarks()
        self.chapters.clear()
        self.pages.clear()
        self.landmarks.clear()
        if book.toc:
            for entry in book.toc:
                self._add_navigation_items(self.chapters, entry)
        if not self.chapters.count():
            for index, section in enumerate(book.sections):
                item = QListWidgetItem(section.title)
                item.setData(Qt.ItemDataRole.UserRole, (index, 0))
                self.chapters.addItem(item)
        for entry in book.page_list:
            target = self._resolve_navigation_target(entry.path, entry.fragment, entry.source_offset)
            if target is not None:
                item = QListWidgetItem(entry.label)
                item.setData(Qt.ItemDataRole.UserRole, target)
                self.pages.addItem(item)
        for entry in book.landmarks:
            target = self._resolve_navigation_target(entry.path, entry.fragment, entry.source_offset)
            if target is not None:
                item = QListWidgetItem(entry.label)
                item.setData(Qt.ItemDataRole.UserRole, target)
                self.landmarks.addItem(item)
        self.reading_tabs.setTabVisible(2, self.pages.count() > 0)
        self.reading_tabs.setTabVisible(3, self.landmarks.count() > 0)
        self.tabs.setCurrentIndex(0)
        self.reading_tabs.setCurrentIndex(0)
        raw = self.store.state["positions"].get(book.id, {})
        index, offset = restore_position(book.sections, Position(raw.get("section_id", ""), raw.get("offset", 0)))
        self.open_section(index, offset)
        record = next((item for item in self.store.state["books"] if item["id"] == book.id), None)
        if record is None:
            record = {"id": book.id, "path": book.path, "title": book.title, "author": book.author, "encoding": book.encoding, "last_read": ""}
        record.update({"id": book.id, "path": book.path, "title": book.title, "author": book.author, "encoding": book.encoding, "last_read": datetime.now(timezone.utc).isoformat()})
        self.store.state["books"] = [record] + [item for item in self.store.state["books"] if item["id"] != book.id][:MAX_BOOK_RECORDS - 1]
        self.store.state["last_book"] = book.id
        self._refresh_shelf()
        self.set_status("{encoding} · {count} 个章节 / 分段 · 进度自动保存{author}", encoding=book.encoding, count=len(book.sections), author=f" · {book.author}" if book.author else "")
        self.encoding_bar.hide()
        self.encoding_button.setVisible(book.encoding != "EPUB")
        self.encoding.setCurrentIndex(max(0, self.encoding.findData(book.encoding)))
        self.save_state()
        self.reader.setFocus()

    def _add_navigation_items(self, widget, entry, depth=0):
        target = self._resolve_navigation_target(entry.path, entry.fragment, entry.source_offset)
        if target is None and not entry.children:
            return
        item = QListWidgetItem(("　" * depth) + entry.label)
        item.setData(Qt.ItemDataRole.UserRole, target)
        widget.addItem(item)
        for child in entry.children:
            self._add_navigation_items(widget, child, depth + 1)

    def _resolve_navigation_target(self, path, fragment="", source_offset=-1):
        if not self.book or not path:
            return None
        candidates = [(index, section) for index, section in enumerate(self.book.sections) if section.source_path == path]
        if fragment:
            for index, section in candidates:
                if fragment in section.anchors:
                    return index, section.anchors[fragment]
            return None
        if source_offset >= 0:
            for position, (index, section) in enumerate(candidates):
                if source_offset < len(section.text) or position == len(candidates) - 1:
                    return index, min(source_offset, len(section.text))
            return None
        return (candidates[0][0], 0) if candidates else None

    def _activate_navigation_item(self, item):
        target = item.data(Qt.ItemDataRole.UserRole)
        if target is not None:
            self.open_section(*target)
            self.reader.setFocus()

    def _page_activated(self, item):
        self._activate_navigation_item(item)

    def open_epub_link(self, link):
        target = self._resolve_navigation_target(link.path, link.fragment)
        if target is None:
            self.set_status("书内链接目标不可用。")
            return False
        self.open_section(*target)
        self.reader.setFocus()
        return True

    def _failed(self, message, encoding_choice):
        if self.focus_mode:
            self.toggle_focus()
        self.set_status(message)
        self.encoding_bar.setVisible(encoding_choice)

    def _finished(self):
        self.loading = False
        self.open_button.setEnabled(True)
        self.worker = None

    def retry_encoding(self):
        if self.pending_path:
            self.load_path(self.pending_path, self.encoding.currentData())

    def restore_last(self):
        last = self.store.state.get("last_book")
        record = next((b for b in self.store.state["books"] if b["id"] == last), None)
        if record:
            encoding = record.get("encoding", "auto")
            self.load_path(record["path"], encoding if encoding in ENCODINGS else "auto")

    def open_section(self, index, offset=0):
        if not self.book or not 0 <= index < len(self.book.sections):
            return
        self.section_index = index
        section = self.book.sections[index]
        self.chapter_title.setText(section.title)
        self.chapter_title.setProperty("translation_source", None)
        self._select_toc_target(index, offset)
        self.reader.set_text(section.text, offset, section.images, section.links, section.formats)
        self._update_progress()
        self.schedule_save()

    def _select_toc_target(self, section_index, offset):
        best_row = -1
        best_offset = -1
        for row in range(self.chapters.count()):
            target = self.chapters.item(row).data(Qt.ItemDataRole.UserRole)
            if target and target[0] == section_index and target[1] <= offset and target[1] >= best_offset:
                best_row, best_offset = row, target[1]
        self.chapters.setCurrentRow(best_row)

    @staticmethod
    def _chapter_identity(section):
        if section.source_path:
            return section.source_path
        return section.id.rpartition(":")[0] or section.id

    def _chapter_destination(self, direction):
        if not self.book or direction not in (-1, 1):
            return None
        identity = self._chapter_identity(self.book.sections[self.section_index])
        candidate = self.section_index + direction
        while 0 <= candidate < len(self.book.sections) and self._chapter_identity(self.book.sections[candidate]) == identity:
            candidate += direction
        if not 0 <= candidate < len(self.book.sections):
            return None
        if direction < 0:
            target_identity = self._chapter_identity(self.book.sections[candidate])
            while candidate > 0 and self._chapter_identity(self.book.sections[candidate - 1]) == target_identity:
                candidate -= 1
        return candidate

    def turn_chapter(self, direction):
        target = self._chapter_destination(direction)
        if target is None:
            return
        self.open_section(target)
        self.reader.setFocus()
        self._update_progress()
        self.schedule_save()

    def turn_page(self, direction):
        if not self.book:
            return
        destination = self.reader.page + direction
        if destination < 0:
            if self.section_index > 0:
                self.open_section(self.section_index - 1)
                self.reader.go_page(self.reader.page_count - 1)
        elif destination >= self.reader.page_count:
            if self.section_index + 1 < len(self.book.sections):
                self.open_section(self.section_index + 1)
        else:
            self.reader.go_page(destination)
        self._update_progress()
        self.schedule_save()

    def _update_progress(self):
        ready = self.book is not None
        if not hasattr(self, "previous"):
            return
        self.previous.setEnabled(ready and (self.section_index > 0 or self.reader.page > 0))
        self.next.setEnabled(ready and (self.section_index + 1 < len(self.book.sections) or self.reader.page + 1 < self.reader.page_count))
        self.previous_chapter.setEnabled(ready and self._chapter_destination(-1) is not None)
        self.next_chapter.setEnabled(ready and self._chapter_destination(1) is not None)
        self.progress.setEnabled(ready)
        self.focus_button.setEnabled(ready)
        if hasattr(self, "tray_focus_action"):
            self.tray_focus_action.setEnabled(ready)
        if ready:
            total = sum(len(s.text) for s in self.book.sections)
            current = sum(len(s.text) for s in self.book.sections[:self.section_index]) + self.reader.offset
            fraction = current / max(1, total)
            if self.section_index == len(self.book.sections) - 1 and self.reader.page == self.reader.page_count - 1:
                fraction = 1
            self.page_label.setProperty("translation_source", None)
            self.page_label.setText(tr("{page} / {pages} 页 · 全书 {progress}", self.settings.language, page=self.reader.page + 1, pages=self.reader.page_count, progress=f"{fraction:.0%}"))
            if not self.progress.isSliderDown():
                self.progress.setValue(round(fraction * 1000))

    def _seek(self):
        if not self.book:
            return
        total = sum(len(s.text) for s in self.book.sections)
        target = round(total * self.progress.value() / 1000)
        for index, section in enumerate(self.book.sections):
            if target < len(section.text) or index == len(self.book.sections) - 1:
                self.open_section(index, min(target, len(section.text)))
                break
            target -= len(section.text)
        self.reader.setFocus()

    def _chapter_activated(self, item):
        self._activate_navigation_item(item)

    def _refresh_bookmarks(self):
        self.bookmarks.clear()
        if not self.book:
            self.bookmark_note_button.setEnabled(False)
            self.bookmark_remove_button.setEnabled(False)
            return
        records = self.store.state.get("bookmarks", {}).get(self.book.id, [])
        for index, record in enumerate(records):
            title = self.t("书签名称：{label}", label=record["label"])
            note = record.get("note", "")
            item = QListWidgetItem(title + (f"\n{note}" if note else ""))
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.bookmarks.addItem(item)
        self.bookmark_note_button.setEnabled(bool(records))
        self.bookmark_remove_button.setEnabled(bool(records))

    def add_bookmark(self):
        if not self.book:
            return
        all_records = self.store.state.setdefault("bookmarks", {})
        records = all_records.setdefault(self.book.id, [])
        section = self.book.sections[self.section_index]
        offset = self.reader.offset
        for index, record in enumerate(records):
            if record.get("section_id") == section.id and record.get("offset") == offset:
                self.bookmarks.setCurrentRow(index)
                self.set_status("书签已存在。")
                return
        if sum(len(values) for values in all_records.values()) >= MAX_BOOKMARKS:
            self.set_status("书签数量已达上限。")
            return
        record = asdict(Bookmark(
            section_id=section.id,
            offset=offset,
            label=f"{section.title} · {self.t('第 {page} 页', page=self.reader.page + 1)}",
            note="",
            created=datetime.now(timezone.utc).isoformat(),
        ))
        records.insert(0, record)
        self._refresh_bookmarks()
        self.bookmarks.setCurrentRow(0)
        self.tabs.setCurrentIndex(0)
        self.reading_tabs.setCurrentIndex(1)
        self.set_status("书签已添加。")
        self.schedule_save()

    def set_bookmark_note(self, index, note):
        if not self.book:
            return
        records = self.store.state.get("bookmarks", {}).get(self.book.id, [])
        if not 0 <= index < len(records):
            return
        records[index]["note"] = str(note).replace("\x00", "")[:MAX_BOOKMARK_NOTE]
        self._refresh_bookmarks()
        self.bookmarks.setCurrentRow(index)
        self.schedule_save()

    def edit_bookmark_note(self):
        index = self.bookmarks.currentRow()
        if not self.book or index < 0:
            return
        records = self.store.state.get("bookmarks", {}).get(self.book.id, [])
        if index >= len(records):
            return
        note, accepted = QInputDialog.getMultiLineText(self, self.t("编辑笔记"), self.t("笔记"), records[index].get("note", ""))
        if accepted:
            self.set_bookmark_note(index, note)

    def remove_bookmark(self):
        index = self.bookmarks.currentRow()
        if not self.book or index < 0:
            return
        records = self.store.state.get("bookmarks", {}).get(self.book.id, [])
        if index < len(records):
            records.pop(index)
            self._refresh_bookmarks()
            self.set_status("书签已删除。")
            self.schedule_save()

    def _bookmark_activated(self, item):
        if not self.book or item is None:
            return
        index = item.data(Qt.ItemDataRole.UserRole)
        records = self.store.state.get("bookmarks", {}).get(self.book.id, [])
        if not isinstance(index, int) or not 0 <= index < len(records):
            return
        record = records[index]
        target_index = next((i for i, section in enumerate(self.book.sections) if section.id == record["section_id"]), None)
        if target_index is None:
            self.set_status("书签目标不可用。")
            return
        self.open_section(target_index, record["offset"])
        self.reader.setFocus()

    def _refresh_recent(self):
        self._refresh_shelf()

    def toggle_sidebar(self):
        self.sidebar_manual = True
        self.sidebar_requested = not self.sidebar.isVisible()
        self.sidebar.setVisible(not self.sidebar.isVisible())

    def toggle_encoding(self):
        self.encoding_bar.setVisible(not self.encoding_bar.isVisible())

    def toggle_floating(self, checked):
        self.sidebar_manual = False
        values = self.settings.to_dict()
        values["floating"] = checked
        self.apply_settings(Settings.from_dict(values))

    def toggle_pin(self, checked):
        values = self.settings.to_dict()
        values["always_on_top"] = checked
        self.apply_settings(Settings.from_dict(values))

    def toggle_focus(self, checked=None):
        if not self.book:
            return
        entering = not self.focus_mode
        if entering:
            self._pre_focus_geometry = self.geometry()
            self._pre_focus_maximized = self.isMaximized()
            self._chrome_visibility = {widget: not widget.isHidden() for widget in self.chrome_widgets}
        self.focus_mode = entering
        self.reader.focus_mode = entering
        self.setMinimumSize(180 if entering else 380, 100 if entering else 360)
        self.reader.setMinimumSize(80 if entering else 160, 40 if entering else 140)
        if not entering:
            for widget, visible in self._chrome_visibility.items():
                widget.setVisible(visible)
        self.apply_settings(self.settings)
        if not entering:
            self.setGeometry(self._pre_focus_geometry)
            if self._pre_focus_maximized:
                self.showMaximized()
        self.raise_()
        self.activateWindow()
        self.reader.setFocus()

    def t(self, source, **values):
        return tr(source, self.settings.language, **values)

    def set_status(self, source, **values):
        self.status_source = (source, values)
        self.status.setProperty("translation_source", None)
        self.status.setText(self.t(source, **values))

    def _set_shelf_error(self, error):
        message = str(error)
        dynamic = (
            ("无法创建分类：", "无法创建分类：{error}"),
            ("复制书籍失败：", "复制书籍失败：{error}"),
            ("移动书籍失败：", "移动书籍失败：{error}"),
            ("删除书架书籍失败：", "删除书架书籍失败：{error}"),
            ("删除分类失败：", "删除分类失败：{error}"),
            ("移动分类书籍失败：", "移动分类书籍失败：{error}"),
        )
        for prefix, source in dynamic:
            if message.startswith(prefix):
                self.set_status(source, error=message[len(prefix):])
                return
        rollback_prefix = "分类移动失败，回滚也未完成："
        if message.startswith(rollback_prefix):
            details = message[len(rollback_prefix):]
            reason, separator, rollback = details.partition("; ")
            if separator:
                self.set_status("分类移动失败，回滚也未完成：{error}; {rollback}", error=reason, rollback=rollback)
                return
        self.set_status(message)

    def _retranslate(self):
        install_qt_translator(QApplication.instance(), self.settings.language)
        for widget in self.findChildren(QWidget) + self.findChildren(QAction):
            source = widget.property("translation_source")
            if source:
                widget.setText(self.t(source))
            if isinstance(widget, QWidget):
                for getter, setter, key in [("toolTip", "setToolTip", "translation_tip"), ("accessibleName", "setAccessibleName", "translation_accessible")]:
                    original = widget.property(key)
                    if original is None:
                        original = getattr(widget, getter)()
                        widget.setProperty(key, original)
                    if original:
                        getattr(widget, setter)(self.t(original))
        self.open_button.setText(self.t("添加书籍"))
        self.tabs.setTabText(0, self.t("阅读"))
        self.tabs.setTabText(1, self.t("书架"))
        self.tabs.setTabText(2, self.t("资料"))
        for index, source in enumerate(("目录", "书签", "页码", "位置")):
            self.reading_tabs.setTabText(index, self.t(source))
        self.shelf.retranslate(self.settings.language)
        self.book_info.set_book(self.book, self.settings.language)
        self._sync_chapter_button_labels()
        self.encoding.setItemText(0, self.t("自动识别"))
        self.focus_button.setText(self.t("退出专注" if self.focus_mode else "专注"))
        if hasattr(self, "tray_focus_action"):
            self.tray_focus_action.setText(self.t("退出专注模式" if self.focus_mode else "进入专注模式"))
            self.tray_focus_action.setChecked(self.focus_mode)
        if self.tray:
            self.tray.setToolTip("QuietReader")
        if not self.book:
            self.setWindowTitle("QuietReader")
        self.set_status(self.status_source[0], **self.status_source[1])

    def _apply_window_style(self):
        floating = self.settings.floating or self.focus_mode
        alpha = 0 if self.focus_mode else round(self.settings.opacity * 255) if floating else 255
        self.setStyleSheet(stylesheet(colors(self.settings.theme, self.settings.background_color if floating else ""), alpha))

    def apply_settings(self, settings):
        self.settings = Settings.from_dict(settings.to_dict())
        settings = self.settings
        floating = settings.floating or self.focus_mode
        was_visible = self.isVisible()
        bounds = self.geometry()
        flags = Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint if floating else Qt.WindowType.Window
        if floating:
            flags |= Qt.WindowType.NoDropShadowWindowHint
        if settings.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        mask = Qt.WindowType.WindowType_Mask | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.NoDropShadowWindowHint
        if self.windowFlags() & mask != flags & mask:
            self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, floating)
        self.setGeometry(bounds)
        self._apply_window_style()
        self.float_button.setChecked(settings.floating)
        self.pin_button.setChecked(settings.always_on_top)
        self.close_button.setVisible(settings.floating)
        self.drag_handle.setVisible(settings.floating)
        self.reader.apply_settings(replace(settings, floating=floating))
        self.sidebar.setVisible(self.sidebar_requested and not self.focus_mode and (self.sidebar_manual or not floating and self.width() >= 700))
        self.brand.setVisible(self.width() >= 700 and not self.focus_mode)
        self.eyebrow.setVisible(self.width() >= 700 and not self.focus_mode)
        self.focus_button.setChecked(self.focus_mode)
        self.focus_shortcut.setKey(QKeySequence(settings.focus_key))
        self.visibility_shortcut.setKey(QKeySequence(settings.hotkey))
        self.emergency_shortcut.setKey(QKeySequence(settings.emergency_key))
        self.escape_shortcut.setEnabled(self.focus_mode)
        self.root_layout.setContentsMargins(*((0, 0, 0, 0) if self.focus_mode else (14, 12, 14, 6)))
        self.root_layout.setSpacing(0 if self.focus_mode else 9)
        self.body_layout.setSpacing(0 if self.focus_mode else 22)
        self.reading_layout.setSpacing(0 if self.focus_mode else 4)
        self._retranslate()
        if was_visible:
            self.show()
            self.activateWindow()
            self.reader.setFocus()
        set_window_border_hidden(self, self.focus_mode)
        self._configure_hotkeys()
        if self.focus_mode:
            for widget in self.chrome_widgets:
                widget.hide()
        self.schedule_save()

    def _sync_chapter_button_labels(self):
        if not hasattr(self, "previous_chapter"):
            return
        compact = self.width() < 620
        self.previous_chapter.setText("‹" if compact else self.t("上一章"))
        self.next_chapter.setText("›" if compact else self.t("下一章"))
        self.previous_chapter.setToolTip(self.t("上一章"))
        self.next_chapter.setToolTip(self.t("下一章"))

    def _configure_hotkeys(self, enabled=None):
        settings = self.settings
        enabled = settings.global_hotkey if enabled is None else enabled
        if self.hotkey:
            warning = self.hotkey.configure(enabled, settings.hotkey)
            warnings = [self.t("显示 / 隐藏：{message}", message=self.t(warning))] if warning else []
            if self.emergency_hotkey:
                error = self.emergency_hotkey.configure(enabled, settings.emergency_key)
                if error:
                    warnings.append(self.t("紧急退出：{message}", message=self.t(error)))
            self.hotkey_notice.setText("\n".join(warnings))
            self.hotkey_notice.setVisible(bool(warnings))
            if self.focus_mode:
                self.hotkey_notice.hide()

    def show_settings(self):
        if self.focus_mode:
            self.toggle_focus()
        self.reveal()
        dialog = SettingsDialog(self.settings, self)
        dialog.capture_started.connect(lambda: self._configure_hotkeys(False))
        dialog.capture_finished.connect(lambda: self._configure_hotkeys())
        dialog.layout_requested.connect(self.show_layout_panel)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.apply_settings(dialog.values())

    def create_layout_panel(self):
        if self.focus_mode:
            self.toggle_focus()
        panel = LayoutPanel(self.settings, self)
        area = self.screen().availableGeometry()
        x = self.frameGeometry().right() + 12
        if x + panel.width() > area.right():
            x = self.frameGeometry().left() - panel.width() - 12
        panel.move(max(area.left(), min(x, area.right() - panel.width())), max(area.top(), min(self.y(), area.bottom() - panel.height())))
        def merged(values):
            return replace(self.settings, font_family=values.font_family, **{key: getattr(values, key) for key in panel.fields})
        panel.preview.connect(lambda values: self.reader.apply_settings(merged(values)))
        panel.accepted.connect(lambda: self.apply_settings(merged(panel.values())))
        panel.rejected.connect(lambda: self.reader.apply_settings(self.settings))
        return panel

    def show_layout_panel(self):
        if getattr(self, "layout_panel", None) and self.layout_panel.isVisible():
            self.layout_panel.raise_()
            return
        self.layout_panel = self.create_layout_panel()
        self.layout_panel.show()

    def _system_theme_changed(self, *args):
        if self.settings.theme == "system":
            self._apply_window_style()
            self.reader.update()

    def _screen_removed(self, *args):
        screens = [s.availableGeometry().getRect() for s in QGuiApplication.screens()]
        self.setGeometry(*visible_bounds(self.geometry().getRect(), screens))

    def reveal(self):
        self._screen_removed()
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def toggle_visible(self):
        if self.isVisible() and not self.isMinimized():
            self.hide_or_minimize()
        else:
            self.reveal()

    def hide_or_minimize(self):
        self.save_state()
        if self.tray and self.tray.isVisible():
            self.hide()
        else:
            self.showMinimized()

    def schedule_save(self):
        if not self.closed:
            self.save_timer.start()

    def save_state(self):
        if self.closed:
            return
        self.store.state["settings"] = self.settings.to_dict()
        if not self.isMinimized() and not self.isMaximized():
            bounds = self._pre_focus_geometry if self.focus_mode else self.geometry()
            self.store.state["window"] = list(bounds.getRect())
        if self.book:
            section = self.book.sections[self.section_index]
            self.store.state["positions"][self.book.id] = asdict(Position(section.id, self.reader.offset))
        try:
            self.store.save()
        except OSError:
            self.set_status("保存失败，请检查用户数据目录的权限和可用空间。")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "save_timer"):
            self.schedule_save()
        if hasattr(self, "sidebar"):
            self.sidebar.setVisible(self.sidebar_requested and not self.focus_mode and (self.sidebar_manual or not self.settings.floating and self.width() >= 700))
            self.eyebrow.setVisible(self.width() >= 700 and not self.focus_mode)
            self.brand.setVisible(self.width() >= 700 and not self.focus_mode)
            self._sync_chapter_button_labels()

    def moveEvent(self, event):
        super().moveEvent(event)
        if hasattr(self, "save_timer"):
            self.schedule_save()

    def mousePressEvent(self, event):
        if (self.settings.floating or self.focus_mode) and event.button() == Qt.MouseButton.LeftButton:
            x, y = event.position().x(), event.position().y()
            edges = Qt.Edge(0)
            if x < 8:
                edges |= Qt.Edge.LeftEdge
            elif x > self.width() - 8:
                edges |= Qt.Edge.RightEdge
            if y < 8:
                edges |= Qt.Edge.TopEdge
            elif y > self.height() - 8:
                edges |= Qt.Edge.BottomEdge
            if edges and self.windowHandle():
                self.windowHandle().startSystemResize(edges)
                return
        super().mousePressEvent(event)

    def closeEvent(self, event):
        if not self.quitting and self.settings.close_to_tray and self.tray and self.tray.isVisible():
            self.save_state()
            self.hide()
            event.ignore()
            return
        self.shutdown()
        event.accept()
        if self.enable_system:
            QApplication.instance().quit()

    def shutdown(self):
        if self.closed:
            return
        self.save_state()
        self.save_timer.stop()
        self.closed = True
        self.pool.waitForDone()
        if self.hotkey:
            self.hotkey.close()
        if self.emergency_hotkey:
            self.emergency_hotkey.close()
        if self.tray:
            self.tray.hide()
        self.hide()

    def quit_app(self):
        self.quitting = True
        self.close()

    def emergency_exit(self):
        """Exit this process without a tray close or waiting for import workers."""
        self.quitting = True
        try:
            self.hide()
            if self.tray:
                self.tray.hide()
            self.save_timer.stop()
            self.save_state()
        except Exception:
            # An unavailable disk must not turn emergency exit into a dialog.
            pass
        finally:
            self.closed = True
            try:
                if self.hotkey:
                    self.hotkey.close()
                if self.emergency_hotkey:
                    self.emergency_hotkey.close()
                release_lock = getattr(QApplication.instance(), "_quietreader_release_lock", None)
                if release_lock:
                    release_lock()
            except Exception:
                pass
            os._exit(0)
