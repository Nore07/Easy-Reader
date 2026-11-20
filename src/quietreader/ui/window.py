from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
import os
import sys

from PySide6.QtCore import QEvent, QObject, QPoint, QRunnable, QThreadPool, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QGuiApplication, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QHBoxLayout, QLabel, QInputDialog, QMessageBox,
    QListWidget, QListWidgetItem, QMainWindow, QMenu, QPushButton, QSizePolicy, QStackedWidget,
    QSizeGrip, QProgressBar, QSlider, QSystemTrayIcon, QTabWidget, QVBoxLayout, QWidget,
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
from quietreader.ui.file_dialog import BookFileDialog, default_book_directory
from quietreader.ui.toast import ToastNotice
from quietreader.persistence.store import MAX_BOOKMARKS, MAX_BOOKMARK_NOTE, MAX_BOOK_RECORDS
from quietreader.library.shelf import SUPPORTED_SUFFIXES, ShelfError, ShelfManager, UNCLASSIFIED, book_id_for_path
from quietreader.ui.shelf import ShelfPanel


def classify_dropped_urls(urls, max_items=MAX_BOOK_RECORDS):
    """Split dropped URLs into valid local book paths and skipped unsupported entries."""
    valid_paths = []
    seen = set()
    skipped = max(0, len(urls) - max_items)
    has_local_file = False
    for url in urls[:max_items]:
        if not url.isLocalFile() or url.host():
            skipped += 1
            continue
        local_file = url.toLocalFile()
        if not local_file or local_file.startswith("\\\\"):
            skipped += 1
            continue
        has_local_file = True
        try:
            resolved = Path(local_file).resolve(strict=True)
        except (OSError, RuntimeError):
            skipped += 1
            continue
        if not resolved.is_file() or resolved.suffix.lower() not in SUPPORTED_SUFFIXES:
            skipped += 1
            continue
        key = str(resolved).casefold()
        if key in seen:
            continue
        seen.add(key)
        valid_paths.append(resolved)
    return valid_paths, skipped, has_local_file


def book_icon():
    if getattr(sys, "frozen", False):
        asset = Path(sys._MEIPASS) / "quietreader" / "assets" / "quietreader.png"
    else:
        asset = Path(__file__).resolve().parents[1] / "assets" / "quietreader.png"
    return QIcon(str(asset))


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


class WindowSurface(QWidget):
    """Surface with frameless-window resize hit zones along its outer padding."""

    _resize_margin = 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)

    def _edges_at(self, position):
        window = self.window()
        if window.isMaximized() or window.isFullScreen():
            return Qt.Edge(0)
        x, y = position.x(), position.y()
        width, height = self.width(), self.height()
        edges = Qt.Edge(0)
        if x < self._resize_margin:
            edges |= Qt.Edge.LeftEdge
        elif x >= width - self._resize_margin:
            edges |= Qt.Edge.RightEdge
        if y < self._resize_margin:
            edges |= Qt.Edge.TopEdge
        elif y >= height - self._resize_margin:
            edges |= Qt.Edge.BottomEdge
        return edges

    @staticmethod
    def _cursor_for_edges(edges):
        left = bool(edges & Qt.Edge.LeftEdge)
        right = bool(edges & Qt.Edge.RightEdge)
        top = bool(edges & Qt.Edge.TopEdge)
        bottom = bool(edges & Qt.Edge.BottomEdge)
        if (top and left) or (bottom and right):
            return Qt.CursorShape.SizeFDiagCursor
        if (top and right) or (bottom and left):
            return Qt.CursorShape.SizeBDiagCursor
        if left or right:
            return Qt.CursorShape.SizeHorCursor
        if top or bottom:
            return Qt.CursorShape.SizeVerCursor
        return None

    def mouseMoveEvent(self, event):
        if not getattr(self.window(), "focus_mode", False):
            cursor = self._cursor_for_edges(self._edges_at(event.position()))
            if cursor is None:
                self.unsetCursor()
            else:
                self.setCursor(cursor)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.unsetCursor()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not getattr(self.window(), "focus_mode", False):
            edges = self._edges_at(event.position())
            handle = self.window().windowHandle()
            if edges and handle and handle.startSystemResize(edges):
                event.accept()
                return
        super().mousePressEvent(event)


class MainWindow(QMainWindow):
    def __init__(self, store, enable_system=True):
        super().__init__()
        # Configure Qt's translucent backing store before the native HWND is
        # created; changing WA_TranslucentBackground after show is not reliable.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.store = store
        self.shelf_manager = ShelfManager(store.path.parent)
        self.settings = Settings.from_dict(store.state["settings"])
        self.enable_system = enable_system
        self.book = None
        self.section_index = 0
        self.loading = False
        self.pending_path = None
        self._last_browse_dir = store.state.get("last_browse_dir", "")
        self.quitting = False
        self.closed = False
        self.focus_mode = False
        self.sidebar_collapsed = False
        self._focus_opacity_override = None
        self._focus_adjust_active = False
        self._focus_adjust_drag = None
        self._focus_system_drag_active = False
        self._focus_cursor_override = False
        self._drag_hover_active = False
        self._drag_has_valid = False
        self._chrome_visibility = {}
        self.status_source = ("离线优先。添加书籍即可开始阅读。", {})
        self.tray = None
        self.hotkey = None
        self.emergency_hotkey = None
        self.worker = None
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(1)
        self.setWindowTitle("QuietReader · 静读")
        self.setMinimumSize(380, 360)
        self.setWindowIcon(book_icon())
        self.setAcceptDrops(True)
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(350)
        self.save_timer.timeout.connect(self.save_state)
        self._build_ui()
        app = QApplication.instance()
        if app:
            app.installEventFilter(self)
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

    def _window_control(self, text, callback, accessible_name, object_name="windowControl"):
        button = QPushButton(text)
        button.setObjectName(object_name)
        button.setToolTip(accessible_name)
        button.setAccessibleName(accessible_name)
        button.setFixedSize(34, 30)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.clicked.connect(callback)
        return button

    def _build_ui(self):
        self.surface = WindowSurface()
        self.surface.setObjectName("surface")
        self.surface.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setCentralWidget(self.surface)
        root = self.root_layout = QVBoxLayout(self.surface)
        root.setContentsMargins(14, 12, 14, 6)
        root.setSpacing(8)
        header = DragHeader()
        header.setObjectName("titleBar")
        top = QHBoxLayout(header)
        top.setContentsMargins(3, 1, 3, 2)
        brand = self.brand = self._label("静读", "brand")
        brand.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        top.addWidget(brand)
        self.eyebrow = self._label("QUIET READER", "eyebrow")
        self.eyebrow.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        top.addWidget(self.eyebrow)
        top.addStretch()
        self.layout_button = self._button("排版", self.show_layout_panel)
        self.config_button = self._button("配置", self.show_settings)
        top.addWidget(self.layout_button)
        top.addWidget(self.config_button)
        self.minimize_button = self._window_control("−", lambda: self.hide_or_minimize(), "隐藏 / 最小化")
        self.maximize_button = self._window_control("□", lambda: self.toggle_maximize(), "最大化窗口")
        self.close_button = self._window_control("×", lambda: self.close(), "关闭窗口", "windowClose")
        top.addWidget(self.minimize_button)
        top.addWidget(self.maximize_button)
        top.addWidget(self.close_button)
        root.addWidget(header)

        tools_widget = QWidget()
        tools = QHBoxLayout(tools_widget)
        tools.setContentsMargins(0, 0, 0, 0)
        self.page_navigation = QWidget()
        self.page_navigation.setObjectName("pageNavigation")
        page_navigation_layout = QHBoxLayout(self.page_navigation)
        page_navigation_layout.setContentsMargins(3, 3, 3, 3)
        page_navigation_layout.setSpacing(2)
        self.reading_button = self._button("阅读", self.show_reading_page, True)
        self.reading_button.setObjectName("pageNav")
        self.reading_button.setToolTip("进入阅读页面，查看目录、书签和资料")
        self.shelf_button = self._button("书架", self.show_shelf_page, True)
        self.shelf_button.setObjectName("pageNav")
        self.shelf_button.setToolTip("浏览最近阅读、所有书籍和分类")
        self.sidebar_toggle = self._window_control("<<<", self.toggle_sidebar, "收起目录栏", "sidebarToggle")
        self.sidebar_toggle.setFixedSize(22, 22)
        page_navigation_layout.addWidget(self.reading_button)
        page_navigation_layout.addWidget(self.shelf_button)
        page_navigation_layout.addWidget(self.sidebar_toggle)
        tools.addWidget(self.page_navigation)
        tools.addStretch(1)
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
        self.reading_tabs = QTabWidget()
        self.chapters = QListWidget()
        self.chapters.setAccessibleName("书籍目录")
        self.chapters.itemActivated.connect(self._chapter_activated)
        self.chapters.itemClicked.connect(self._chapter_activated)
        self.reading_tabs.addTab(self.chapters, "目录")
        bookmark_panel = QWidget()
        bookmark_layout = QVBoxLayout(bookmark_panel)
        bookmark_layout.setContentsMargins(4, 6, 4, 6)
        self.bookmarks = QListWidget()
        self.bookmarks.setAccessibleName("书签与笔记")
        self.bookmarks.itemActivated.connect(self._bookmark_activated)
        self.bookmarks.itemClicked.connect(self._bookmark_activated)
        bookmark_layout.addWidget(self.bookmarks, 1)
        bookmark_actions = QHBoxLayout()
        bookmark_actions.setContentsMargins(0, 0, 0, 0)
        bookmark_actions.setSpacing(3)
        self.bookmark_add_button = self._button("添加", self.add_bookmark)
        self.bookmark_note_button = self._button("编辑", self.edit_bookmark_note)
        self.bookmark_remove_button = self._button("删除", self.remove_bookmark)
        for button, label in (
            (self.bookmark_add_button, "添加书签"),
            (self.bookmark_note_button, "编辑笔记"),
            (self.bookmark_remove_button, "删除书签"),
        ):
            button.setObjectName("bookmarkAction")
            button.setMinimumWidth(0)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.setToolTip(label)
            button.setProperty("translation_tip", label)
            button.setAccessibleName(label)
            button.setProperty("translation_accessible", label)
            bookmark_actions.addWidget(button)
        bookmark_layout.addLayout(bookmark_actions)
        self.reading_tabs.addTab(bookmark_panel, "书签")
        self.book_info = BookInfoPanel()
        self.reading_tabs.addTab(self.book_info, "资料")
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
        self.reading_tabs.setTabVisible(2, True)
        self.reading_tabs.setTabVisible(3, False)
        self.reading_tabs.setTabVisible(4, False)
        side.addWidget(self.reading_tabs)
        self.book_progress_label = self._label("全书进度：--", "status")
        self.book_progress_label.setAccessibleName("全书阅读进度")
        side.addWidget(self.book_progress_label)
        self.book_progress_bar = QProgressBar()
        self.book_progress_bar.setObjectName("bookProgress")
        self.book_progress_bar.setRange(0, 1000)
        self.book_progress_bar.setTextVisible(False)
        self.book_progress_bar.setFixedHeight(5)
        self.book_progress_bar.setAccessibleName("全书阅读进度")
        side.addWidget(self.book_progress_bar)
        self.sidebar_status = self._label("本地阅读 · 无需联网", "status")
        side.addWidget(self.sidebar_status)
        self._update_sidebar_toggle()
        body.addWidget(self.sidebar)
        self.main_pages = QStackedWidget()
        self.reader_page = QWidget()
        reading = self.reading_layout = QVBoxLayout(self.reader_page)
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
        self.progress.setAccessibleName("本章阅读进度")
        self.progress.sliderReleased.connect(self._seek)
        self.progress.setEnabled(False)
        reading.addWidget(self.progress)
        self.reader_navigation = QWidget()
        self.reader_navigation.setObjectName("readerNavigation")
        self.reader_navigation_layout = QHBoxLayout(self.reader_navigation)
        navigation = self.reader_navigation_layout
        navigation.setContentsMargins(0, 0, 0, 0)
        navigation.setSpacing(2)
        self.previous_chapter = self._button("上一章", lambda: self.turn_chapter(-1))
        self.previous = self._button("← 上一页", lambda: self.turn_page(-1))
        self.next = self._button("下一页 →", lambda: self.turn_page(1))
        self.next_chapter = self._button("下一章", lambda: self.turn_chapter(1))
        self.page_label = self._label("PageUp / PageDown", "pageStatus")
        self.page_label.setMinimumWidth(0)
        self.page_label.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.page_label.setProperty("full_text", "PageUp / PageDown")
        self.page_label.setProperty("compact_text", "Pg")
        for button in (self.previous_chapter, self.previous, self.next, self.next_chapter):
            button.setObjectName("pageControl")
            button.setMinimumWidth(28)
            button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        navigation.addWidget(self.previous_chapter)
        navigation.addWidget(self.previous)
        navigation.addStretch()
        navigation.addWidget(self.page_label)
        navigation.addStretch()
        navigation.addWidget(self.next)
        navigation.addWidget(self.next_chapter)
        reading.addWidget(self.reader_navigation)
        self.main_pages.addWidget(self.reader_page)
        self.shelf = ShelfPanel()
        self.open_button = self.shelf.add_button
        self.shelf.add_requested.connect(self.choose_file)
        self.shelf.open_requested.connect(self.open_shelf_book)
        self.shelf.move_requested.connect(self.move_shelf_book)
        self.shelf.remove_requested.connect(self._confirm_remove_shelf_book)
        self.shelf.create_category_requested.connect(self.prompt_create_shelf_category)
        self.shelf.delete_category_requested.connect(self._confirm_delete_shelf_category)
        self.main_pages.addWidget(self.shelf)
        self.recent = self.shelf.recent
        body.addWidget(self.main_pages, 1)
        self._sync_page_navigation()
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
        self.chrome_widgets = [header, tools_widget, self.hotkey_notice, self.sidebar, self.book_title, self.chapter_title, self.progress, self.reader_navigation, bottom_widget, self.encoding_bar]
        self.open_shortcut = QShortcut(QKeySequence("Ctrl+O"), self)
        self.open_shortcut.activated.connect(self.choose_file)
        self.settings_shortcut = QShortcut(QKeySequence("Ctrl+,"), self)
        self.settings_shortcut.activated.connect(self.show_settings)
        self.focus_shortcut = QShortcut(QKeySequence(self.settings.focus_key), self)
        self.focus_shortcut.activated.connect(self.toggle_focus)
        self.focus_shortcut.setAutoRepeat(False)
        self.focus_opacity_shortcut = QShortcut(QKeySequence(self.settings.focus_opacity_key), self)
        self.focus_opacity_shortcut.activated.connect(self.toggle_focus_opacity)
        self.focus_opacity_shortcut.setAutoRepeat(False)
        self.escape_shortcut = QShortcut(QKeySequence("Esc"), self)
        self.escape_shortcut.activated.connect(lambda: self.toggle_focus() if self.focus_mode else None)
        self.escape_shortcut.setEnabled(False)
        self.visibility_shortcut = QShortcut(QKeySequence(self.settings.hotkey), self)
        self.visibility_shortcut.setAutoRepeat(False)
        self.visibility_shortcut.activated.connect(self.toggle_visible)
        self.emergency_shortcut = QShortcut(QKeySequence(self.settings.emergency_key), self)
        self.emergency_shortcut.setAutoRepeat(False)
        self.emergency_shortcut.activated.connect(self.emergency_exit)
        self.toast = ToastNotice(self.surface)
        self._update_progress()

    def _setup_system(self):
        app = QApplication.instance()
        self.hotkey = GlobalHotkey(app, self.toggle_visible)
        self.emergency_hotkey = GlobalHotkey(app, self.emergency_exit, identifier=0x5153)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(self.windowIcon(), self)
            self.tray.setToolTip("QuietReader · 静读")
            menu = QMenu(self)
            for label, callback in [("显示 / 隐藏", self.toggle_visible), ("添加书籍…", self.choose_file), ("配置…", self.show_settings)]:
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
        start_directory = default_book_directory(
            self.store.state["books"],
            self.shelf_manager,
            self._last_browse_dir,
        )
        dialog = BookFileDialog(start_directory, self.settings.language, self)
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        files = dialog.selected_files() if accepted else []
        remembered = Path(files[0]).parent if files else dialog.last_directory()
        if remembered is not None:
            self._last_browse_dir = str(remembered)
            self.store.state["last_browse_dir"] = self._last_browse_dir
            self.schedule_save()
        if files:
            self.add_book_paths(files)

    def add_book_paths(self, paths, open_after=False, skipped_count=0):
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
        if new_count and skipped_count:
            self.set_status("已添加 {count} 本书到书架，已跳过 {skipped} 个不支持的项目。", count=new_count, skipped=skipped_count)
        elif new_count:
            self.set_status("已添加 {count} 本书到书架。", count=new_count)
        elif added and skipped_count:
            self.set_status("所选书籍已在书架中，已跳过 {skipped} 个不支持的项目。", skipped=skipped_count)
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
            self.show_reading_page()
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
        self.set_status("已将《{title}》移动到“{category}”。", title=record["title"], category=self.t("未分类") if category == UNCLASSIFIED else category)

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
        self.page_label.setProperty("full_text", "PageUp / PageDown")
        self.page_label.setProperty("compact_text", "Pg")
        self.page_label.setToolTip("PageUp / PageDown")
        self.reading_tabs.setTabVisible(3, False)
        self.reading_tabs.setTabVisible(4, False)
        self.encoding_button.hide()
        self.encoding_bar.hide()
        self._update_progress()
        self._refresh_bookmarks()

    def _refresh_shelf(self):
        if not hasattr(self, "shelf"):
            return
        positions = self.store.state.get("positions", {})
        records = [
            {**record, "_has_saved_position": record.get("id") in positions}
            for record in self.store.state["books"]
        ]
        self.shelf.refresh(
            records, self.shelf_manager.categories(),
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
        self.set_status("正在后台导入书籍…", notify=False)
        self.worker = ImportTask(path, encoding)
        self.worker.signals.loaded.connect(self._loaded)
        self.worker.signals.failed.connect(self._failed)
        self.worker.signals.finished.connect(self._finished)
        self.pool.start(self.worker)

    def _loaded(self, book):
        if self.closed:
            return
        self.book = book
        self.show_reading_page()
        self.setWindowTitle(f"{book.title} · QuietReader")
        self.book_title.setText(book.title)
        self.book_title.setProperty("translation_source", None)
        self.book_info.set_book(book, self.settings.language)
        self.reading_tabs.setTabVisible(2, True)
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
        self.reading_tabs.setTabVisible(3, self.pages.count() > 0)
        self.reading_tabs.setTabVisible(4, self.landmarks.count() > 0)
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
        self._update_progress()
        self._refresh_shelf()
        self.set_status("{encoding} · {count} 个章节 / 分段 · 进度自动保存{author}", notify=False, encoding=book.encoding, count=len(book.sections), author=f" · {book.author}" if book.author else "")
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
            book_current = sum(len(s.text) for s in self.book.sections[:self.section_index]) + self.reader.offset
            book_fraction = book_current / max(1, total)
            if self.section_index == len(self.book.sections) - 1 and self.reader.page == self.reader.page_count - 1:
                book_fraction = 1

            identity = self._chapter_identity(self.book.sections[self.section_index])
            chapter_start = self.section_index
            while chapter_start > 0 and self._chapter_identity(self.book.sections[chapter_start - 1]) == identity:
                chapter_start -= 1
            chapter_end = self.section_index + 1
            while chapter_end < len(self.book.sections) and self._chapter_identity(self.book.sections[chapter_end]) == identity:
                chapter_end += 1
            chapter_sections = self.book.sections[chapter_start:chapter_end]
            chapter_total = sum(len(section.text) for section in chapter_sections)
            chapter_current = sum(len(section.text) for section in self.book.sections[chapter_start:self.section_index]) + self.reader.offset
            chapter_fraction = chapter_current / max(1, chapter_total)
            if self.section_index == chapter_end - 1 and self.reader.page == self.reader.page_count - 1:
                chapter_fraction = 1

            record = next((item for item in self.store.state["books"] if item.get("id") == self.book.id), None)
            if record is not None:
                record["reading_chapter"] = self.book.sections[chapter_start].title
                record["reading_progress"] = book_fraction

            self.page_label.setProperty("translation_source", None)
            full_label = tr("{page} / {pages} 页 · 本章 {progress}", self.settings.language, page=self.reader.page + 1, pages=self.reader.page_count, progress=f"{chapter_fraction:.0%}")
            compact_label = f"{self.reader.page + 1}/{self.reader.page_count}"
            self.page_label.setProperty("full_text", full_label)
            self.page_label.setProperty("compact_text", compact_label)
            self.page_label.setToolTip(full_label)
            if not self.progress.isSliderDown():
                self.progress.setValue(round(chapter_fraction * 1000))
            self.book_progress_label.setText(self.t("全书进度：{progress}", progress=f"{book_fraction:.0%}"))
            self.book_progress_bar.setValue(round(book_fraction * 1000))
        else:
            self.book_progress_label.setText(self.t("全书进度：--"))
            self.book_progress_bar.setValue(0)
        self._sync_reader_navigation_labels()

    def _seek(self):
        if not self.book:
            return
        identity = self._chapter_identity(self.book.sections[self.section_index])
        chapter_start = self.section_index
        while chapter_start > 0 and self._chapter_identity(self.book.sections[chapter_start - 1]) == identity:
            chapter_start -= 1
        chapter_end = self.section_index + 1
        while chapter_end < len(self.book.sections) and self._chapter_identity(self.book.sections[chapter_end]) == identity:
            chapter_end += 1
        sections = self.book.sections[chapter_start:chapter_end]
        total = sum(len(section.text) for section in sections)
        target = round(total * self.progress.value() / 1000)
        for index, section in enumerate(sections, start=chapter_start):
            if target < len(section.text) or index == chapter_end - 1:
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

    def _sync_page_navigation(self):
        if not hasattr(self, "main_pages"):
            return
        reading_active = self.main_pages.currentWidget() is self.reader_page
        if hasattr(self, "reading_button"):
            self.reading_button.setChecked(reading_active)
            self.shelf_button.setChecked(not reading_active)
        if hasattr(self, "sidebar"):
            if reading_active and not self.focus_mode and not self.sidebar_collapsed:
                width = max(150, min(220, int(self.width() * 0.30)))
                self.sidebar.setFixedWidth(width)
            self.sidebar.setVisible(reading_active and not self.focus_mode and not self.sidebar_collapsed)
        if hasattr(self, "sidebar_toggle"):
            self.sidebar_toggle.setVisible(reading_active and not self.focus_mode)

    def _update_sidebar_toggle(self):
        if not hasattr(self, "sidebar_toggle"):
            return
        self.sidebar_toggle.setText(">>>" if self.sidebar_collapsed else "<<<")
        label = "展开目录栏" if self.sidebar_collapsed else "收起目录栏"
        self.sidebar_toggle.setToolTip(self.t(label))
        self.sidebar_toggle.setAccessibleName(self.t(label))
        self._sync_page_navigation()

    def toggle_sidebar(self, checked=False):
        if self.focus_mode or self.main_pages.currentWidget() is not self.reader_page:
            return
        self.sidebar_collapsed = not self.sidebar_collapsed
        self._update_sidebar_toggle()

    def show_reading_page(self, checked=False):
        if self.focus_mode:
            return
        self.main_pages.setCurrentWidget(self.reader_page)
        self._sync_page_navigation()

    def show_shelf_page(self, checked=False):
        if self.focus_mode:
            return
        self._refresh_shelf()
        self.main_pages.setCurrentWidget(self.shelf)
        self._sync_page_navigation()

    def toggle_maximize(self):
        if self.focus_mode:
            return
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self._update_window_controls()

    def _update_window_controls(self):
        if not hasattr(self, "maximize_button"):
            return
        restore = self.isMaximized()
        label = "还原窗口" if restore else "最大化窗口"
        self.maximize_button.setText("❐" if restore else "□")
        self.maximize_button.setToolTip(self.t(label))
        self.maximize_button.setAccessibleName(self.t(label))

    def toggle_main_page(self):
        """Compatibility helper for existing shortcuts and automation scripts."""
        if self.main_pages.currentWidget() is self.reader_page:
            self.show_shelf_page()
        else:
            self.show_reading_page()

    def toggle_encoding(self):
        self.encoding_bar.setVisible(not self.encoding_bar.isVisible())

    def toggle_pin(self, checked):
        values = self.settings.to_dict()
        values["always_on_top"] = checked
        self.apply_settings(Settings.from_dict(values))

    def toggle_focus(self, checked=None):
        if not self.book:
            return
        entering = not self.focus_mode
        if entering:
            self.show_reading_page()
            self._pre_focus_maximized = self.isMaximized()
            self._chrome_visibility = {widget: not widget.isHidden() for widget in self.chrome_widgets}
        self._set_focus_adjust_active(False)
        self._drag_has_valid = False
        self._set_drag_hover_active(False)
        self._focus_opacity_override = None
        self.focus_mode = entering
        self.setAcceptDrops(not entering)
        self.reader.focus_mode = entering
        self.setMinimumSize(180 if entering else 380, 100 if entering else 360)
        self.reader.setMinimumSize(80 if entering else 160, 40 if entering else 140)
        if not entering:
            for widget, visible in self._chrome_visibility.items():
                widget.setVisible(visible)
        self.apply_settings(self.settings)
        if not entering and self._pre_focus_maximized:
            self.showMaximized()
        self.raise_()
        self.activateWindow()
        self.reader.setFocus()

    def toggle_focus_opacity(self):
        if not self.focus_mode:
            return
        current = self.settings.opacity if self._focus_opacity_override is None else self._focus_opacity_override
        self._focus_opacity_override = 0.0 if current > 0 else 1.0
        self._apply_window_style()

    def t(self, source, **values):
        return tr(source, self.settings.language, **values)

    def _toast_bottom_margin(self):
        if hasattr(self, "main_pages") and self.main_pages.currentWidget() is self.reader_page and hasattr(self, "progress") and not self.progress.isHidden():
            anchor_y = self.progress.mapTo(self.surface, QPoint(0, 0)).y()
            if anchor_y > 0:
                return max(44, self.surface.height() - anchor_y + 12)
            return 96
        if hasattr(self, "status") and not self.status.isHidden():
            anchor_y = self.status.mapTo(self.surface, QPoint(0, 0)).y()
            if anchor_y > 0:
                return max(44, self.surface.height() - anchor_y + 14)
        return 44

    def set_status(self, source, notify=True, **values):
        self.status_source = (source, values)
        self.status.setProperty("translation_source", None)
        text = self.t(source, **values)
        self.status.setText(text)
        if notify and hasattr(self, "toast") and not self.focus_mode and not self.closed:
            self.toast.show_message(text, bottom_margin=self._toast_bottom_margin())

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
        self.config_button.setText(self.t("配置"))
        self.reading_button.setText(self.t("阅读"))
        self.shelf_button.setText(self.t("书架"))
        self._update_window_controls()
        for index, source in enumerate(("目录", "书签", "资料", "页码", "位置")):
            self.reading_tabs.setTabText(index, self.t(source))
        self.shelf.retranslate(self.settings.language)
        self.book_info.set_book(self.book, self.settings.language)
        self._update_progress()
        self.encoding.setItemText(0, self.t("自动识别"))
        self.focus_button.setText(self.t("退出专注" if self.focus_mode else "专注"))
        self._update_sidebar_toggle()
        if hasattr(self, "tray_focus_action"):
            self.tray_focus_action.setText(self.t("退出专注模式" if self.focus_mode else "进入专注模式"))
            self.tray_focus_action.setChecked(self.focus_mode)
        if self.tray:
            self.tray.setToolTip("QuietReader")
        if not self.book:
            self.setWindowTitle("QuietReader")
        self.set_status(self.status_source[0], notify=False, **self.status_source[1])
        if hasattr(self, "toast") and not self.toast.isHidden():
            self.toast.update_text(self.status.text())

    def _apply_window_style(self):
        if self.focus_mode:
            opacity = self.settings.opacity if self._focus_opacity_override is None else self._focus_opacity_override
            if self._focus_adjust_active and opacity == 0:
                # A fully transparent surface can miss mouse input. Make only
                # that case hit-testable while Alt is held; preserve every
                # already-visible opacity and restore zero on key release.
                alpha = 255 * 0.01
            else:
                alpha = round(opacity * 255)
        else:
            alpha = 255
        background_color = self.settings.background_color if self.focus_mode else ""
        self.setStyleSheet(stylesheet(
            colors(self.settings.theme, background_color), alpha,
            borderless=self.focus_mode,
            resize_outline=self.focus_mode and self._focus_adjust_active,
            drop_highlight=self._drag_hover_active and not self.focus_mode,
        ))

    def apply_settings(self, settings):
        self.settings = Settings.from_dict(settings.to_dict())
        settings = self.settings
        was_visible = self.isVisible()
        bounds = self.geometry()
        flags = Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint if self.focus_mode else Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint
        if self.focus_mode:
            flags |= Qt.WindowType.NoDropShadowWindowHint
        if settings.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        mask = Qt.WindowType.WindowType_Mask | Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.NoDropShadowWindowHint
        if self.windowFlags() & mask != flags & mask:
            self.setWindowFlags(flags)
        self.setGeometry(bounds)
        self._apply_window_style()
        self.pin_button.setChecked(settings.always_on_top)
        self.reader.apply_settings(settings)
        self._sync_page_navigation()
        self.brand.setVisible(not self.focus_mode)
        self.eyebrow.setVisible(self.width() >= 700 and not self.focus_mode)
        self.focus_button.setChecked(self.focus_mode)
        self.focus_shortcut.setKey(QKeySequence(settings.focus_key))
        self.focus_opacity_shortcut.setKey(QKeySequence(settings.focus_opacity_key))
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
            if hasattr(self, "toast"):
                self.toast.dismiss()
        self.schedule_save()

    def _sync_reader_navigation_labels(self):
        if not hasattr(self, "reader_navigation"):
            return

        controls = (
            (self.previous_chapter, "上一章", "«"),
            (self.previous, "← 上一页", "‹"),
            (self.next, "下一页 →", "›"),
            (self.next_chapter, "下一章", "»"),
        )
        for button, source, _ in controls:
            label = self.t(source)
            button.setText(label)
            button.setToolTip(label)
            button.setAccessibleName(label)

        full_page_label = self.page_label.property("full_text") or self.page_label.text()
        compact_page_label = self.page_label.property("compact_text") or "Pg"
        self.page_label.setText(full_page_label)
        self.page_label.setToolTip(full_page_label)
        spacing = self.reader_navigation_layout.spacing()
        full_width = (
            sum(button.sizeHint().width() for button, _, _ in controls)
            + self.page_label.sizeHint().width()
            + max(0, self.reader_navigation_layout.count() - 1) * spacing
            + 8
        )
        compact = self.reader_navigation.width() < full_width
        if compact:
            for button, _, symbol in controls:
                button.setText(symbol)
            self.page_label.setText(compact_page_label)
        self.reader_navigation.setProperty("compact", compact)

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
        self.store.state["last_browse_dir"] = self._last_browse_dir
        if not self.isMinimized() and not self.isMaximized():
            bounds = self.geometry()
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
            self._sync_page_navigation()
            self.eyebrow.setVisible(self.width() >= 700 and not self.focus_mode)
            self.brand.setVisible(not self.focus_mode)
            self._update_window_controls()
            self._sync_reader_navigation_labels()
        if hasattr(self, "toast") and not self.toast.isHidden():
            self.toast.reposition(self._toast_bottom_margin())

    def showEvent(self, event):
        super().showEvent(event)
        if hasattr(self, "toast") and not self.toast.isHidden():
            self.toast.reposition(self._toast_bottom_margin())

    def hideEvent(self, event):
        if hasattr(self, "toast"):
            self.toast.dismiss()
        super().hideEvent(event)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            self._update_window_controls()

    def moveEvent(self, event):
        super().moveEvent(event)
        if hasattr(self, "save_timer"):
            self.schedule_save()

    def _focus_adjust_key(self):
        return {
            "Alt": Qt.Key.Key_Alt,
            "Ctrl": Qt.Key.Key_Control,
            "Shift": Qt.Key.Key_Shift,
        }.get(self.settings.focus_adjust_key, Qt.Key.Key_Alt)

    def _focus_edges_at(self, global_position):
        if self.isMaximized() or self.isFullScreen():
            return Qt.Edge(0)
        position = self.mapFromGlobal(global_position)
        margin = 9
        edges = Qt.Edge(0)
        if position.x() < margin:
            edges |= Qt.Edge.LeftEdge
        elif position.x() >= self.width() - margin:
            edges |= Qt.Edge.RightEdge
        if position.y() < margin:
            edges |= Qt.Edge.TopEdge
        elif position.y() >= self.height() - margin:
            edges |= Qt.Edge.BottomEdge
        return edges

    @staticmethod
    def _focus_cursor_for_edges(edges):
        left = bool(edges & Qt.Edge.LeftEdge)
        right = bool(edges & Qt.Edge.RightEdge)
        top = bool(edges & Qt.Edge.TopEdge)
        bottom = bool(edges & Qt.Edge.BottomEdge)
        if (top and left) or (bottom and right):
            return Qt.CursorShape.SizeFDiagCursor
        if (top and right) or (bottom and left):
            return Qt.CursorShape.SizeBDiagCursor
        if left or right:
            return Qt.CursorShape.SizeHorCursor
        if top or bottom:
            return Qt.CursorShape.SizeVerCursor
        return Qt.CursorShape.ArrowCursor

    def _set_focus_adjust_active(self, active):
        active = bool(active and self.focus_mode)
        if active == self._focus_adjust_active:
            return
        self._focus_adjust_active = active
        self._focus_adjust_drag = None
        self._focus_system_drag_active = False
        if active:
            QApplication.setOverrideCursor(Qt.CursorShape.ArrowCursor)
            self._focus_cursor_override = True
        elif self._focus_cursor_override:
            QApplication.restoreOverrideCursor()
            self._focus_cursor_override = False
        self._apply_window_style()

    def _update_focus_adjust_cursor(self, global_position):
        if not self._focus_cursor_override:
            return
        cursor = self._focus_cursor_for_edges(self._focus_edges_at(global_position))
        QApplication.changeOverrideCursor(cursor)

    def _resize_focus_geometry(self, global_position):
        if not self._focus_adjust_drag:
            return
        origin, geometry, edges = self._focus_adjust_drag
        dx = global_position.x() - origin.x()
        dy = global_position.y() - origin.y()
        left, top, width, height = geometry.x(), geometry.y(), geometry.width(), geometry.height()
        minimum_width, minimum_height = self.minimumWidth(), self.minimumHeight()
        if edges & Qt.Edge.LeftEdge:
            left += dx
            width -= dx
            if width < minimum_width:
                left -= minimum_width - width
                width = minimum_width
        elif edges & Qt.Edge.RightEdge:
            width = max(minimum_width, width + dx)
        if edges & Qt.Edge.TopEdge:
            top += dy
            height -= dy
            if height < minimum_height:
                top -= minimum_height - height
                height = minimum_height
        elif edges & Qt.Edge.BottomEdge:
            height = max(minimum_height, height + dy)
        self.setGeometry(left, top, width, height)

    def _set_drag_hover_active(self, active):
        active = bool(active and not self.focus_mode)
        if active == self._drag_hover_active:
            return
        self._drag_hover_active = active
        self._apply_window_style()
        if active:
            will_open = self.book is None and self.main_pages.currentWidget() is self.reader_page
            prompt = "松开鼠标添加并打开书籍。" if will_open else "松开鼠标添加到书架。"
            self.status.setText(self.t(prompt))
        else:
            self.status.setText(self.t(self.status_source[0], **self.status_source[1]))

    def dragEnterEvent(self, event):
        if self.focus_mode or self.loading or self.closed or self.store.read_only or not event.mimeData().hasUrls():
            event.ignore()
            return
        valid_paths, _skipped, _has_local = classify_dropped_urls(event.mimeData().urls())
        if not valid_paths:
            event.ignore()
            return
        self._drag_has_valid = True
        self._set_drag_hover_active(True)
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()

    def dragMoveEvent(self, event):
        if self.focus_mode or self.loading or self.closed or not self._drag_has_valid or not event.mimeData().hasUrls():
            event.ignore()
            return
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()

    def dragLeaveEvent(self, event):
        self._drag_has_valid = False
        self._set_drag_hover_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self._drag_has_valid = False
        self._set_drag_hover_active(False)
        if self.focus_mode or self.loading or self.closed or not event.mimeData().hasUrls():
            event.ignore()
            return
        valid_paths, skipped, has_local = classify_dropped_urls(event.mimeData().urls())
        if not has_local:
            event.ignore()
            return
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()
        if self.store.read_only:
            self.set_status("保存数据来自不支持的版本。已保护原文件，本次不会保存更改。")
            return
        if not valid_paths:
            self.set_status("拖放仅支持本地 TXT 或 EPUB 文件。")
            return
        open_after = self.book is None and self.main_pages.currentWidget() is self.reader_page
        added = self.add_book_paths(valid_paths, open_after=open_after, skipped_count=skipped)
        if added and not open_after and self.main_pages.currentWidget() is self.shelf:
            self.shelf.reveal_book(added[-1]["id"])

    def eventFilter(self, watched, event):
        event_type = event.type()
        if event_type == QEvent.Type.ApplicationDeactivate or (event_type == QEvent.Type.WindowDeactivate and watched is self):
            self._set_focus_adjust_active(False)
            self._drag_has_valid = False
            self._set_drag_hover_active(False)
            return False
        if not self.focus_mode:
            return super().eventFilter(watched, event)

        if (
            isinstance(watched, QWidget)
            and watched.window() is self
            and event_type in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease)
            and event.key() == self._focus_adjust_key()
        ):
            self._set_focus_adjust_active(event_type == QEvent.Type.KeyPress)
            return False

        if not isinstance(watched, QWidget) or watched.window() is not self:
            return super().eventFilter(watched, event)

        if event_type == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton and self._focus_adjust_active:
            global_position = event.globalPosition().toPoint()
            edges = self._focus_edges_at(global_position)
            handle = self.windowHandle()
            if edges and handle and handle.startSystemResize(edges):
                self._focus_system_drag_active = True
            elif not edges and handle and handle.startSystemMove():
                self._focus_system_drag_active = True
            else:
                self._focus_adjust_drag = (global_position, self.geometry(), edges)
            event.accept()
            return True

        if event_type == QEvent.Type.MouseMove and self._focus_adjust_active:
            global_position = event.globalPosition().toPoint()
            if self._focus_adjust_drag and event.buttons() & Qt.MouseButton.LeftButton:
                self._resize_focus_geometry(global_position)
                event.accept()
                return True
            if not event.buttons() & Qt.MouseButton.LeftButton:
                self._focus_system_drag_active = False
            if not self._focus_system_drag_active:
                self._update_focus_adjust_cursor(global_position)
        elif event_type == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            self._focus_adjust_drag = None
            self._focus_system_drag_active = False
        return super().eventFilter(watched, event)

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
        self._set_focus_adjust_active(False)
        app = QApplication.instance()
        if app:
            app.removeEventFilter(self)
        self.save_state()
        self.save_timer.stop()
        if hasattr(self, "toast"):
            self.toast.dismiss()
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
