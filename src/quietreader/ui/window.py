from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
import os

from PySide6.QtCore import QObject, QPoint, QRunnable, QThreadPool, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QGuiApplication, QIcon, QKeySequence, QPainter, QPen, QPixmap, QPolygon, QShortcut
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QMainWindow, QMenu, QPushButton,
    QSizeGrip, QSlider, QSystemTrayIcon, QTabWidget, QVBoxLayout, QWidget,
)

from quietreader.content.local import ENCODINGS, ImportError as BookImportError, load_book
from quietreader.desktop.geometry import visible_bounds
from quietreader.desktop.hotkey import GlobalHotkey
from quietreader.domain.models import Position, Settings, restore_position
from quietreader.ui.reader import PageView
from quietreader.ui.settings import SettingsDialog
from quietreader.ui.theme import colors, stylesheet
from quietreader.i18n import tr, install_qt_translator
from quietreader.ui.layout_panel import LayoutPanel


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
        self.status_source = ("离线优先。打开文件即可开始阅读。", {})
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
        self.open_button = self._button("打开", self.choose_file)
        self.open_button.setObjectName("primary")
        self.open_button.setToolTip("打开本地 TXT / EPUB · Ctrl+O")
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
        tools.addWidget(self._button("目录 / 最近", self.toggle_sidebar))
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
        self.chapters = QListWidget()
        self.chapters.setAccessibleName("书籍目录")
        self.chapters.itemActivated.connect(self._chapter_activated)
        self.chapters.itemClicked.connect(self._chapter_activated)
        self.recent = QListWidget()
        self.recent.setAccessibleName("最近阅读")
        self.recent.itemActivated.connect(self._recent_activated)
        self.recent.itemClicked.connect(self._recent_activated)
        tabs.addTab(self.chapters, "目录")
        tabs.addTab(self.recent, "最近")
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
        self.previous = self._button("← 上一页", lambda: self.turn_page(-1))
        self.next = self._button("下一页 →", lambda: self.turn_page(1))
        self.page_label = self._label("PageUp / PageDown", "status")
        navigation.addWidget(self.previous)
        navigation.addStretch()
        navigation.addWidget(self.page_label)
        navigation.addStretch()
        navigation.addWidget(self.next)
        reading.addWidget(navigation_widget)
        body.addLayout(reading, 1)
        root.addLayout(body, 1)
        bottom_widget = QWidget()
        bottom = QHBoxLayout(bottom_widget)
        bottom.setContentsMargins(0, 0, 0, 0)
        self.status = self._label("离线优先。打开文件即可开始阅读。", "status")
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
            for label, callback in [("显示 / 隐藏", self.toggle_visible), ("打开本地文件…", self.choose_file), ("阅读偏好…", self.show_settings)]:
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
        file, _ = QFileDialog.getOpenFileName(self, self.t("打开本地书籍"), "", self.t("阅读文件 (*.txt *.epub);;TXT (*.txt);;EPUB (*.epub)"), options=QFileDialog.Option.DontUseNativeDialog)
        if file:
            self.load_path(file)

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
        self.chapters.clear()
        for section in book.sections:
            self.chapters.addItem(section.title)
        raw = self.store.state["positions"].get(book.id, {})
        index, offset = restore_position(book.sections, Position(raw.get("section_id", ""), raw.get("offset", 0)))
        self.open_section(index, offset)
        record = {"id": book.id, "path": book.path, "title": book.title, "author": book.author, "encoding": book.encoding, "last_read": datetime.now(timezone.utc).isoformat()}
        self.store.state["books"] = [record] + [b for b in self.store.state["books"] if b["id"] != book.id][:49]
        self.store.state["last_book"] = book.id
        self._refresh_recent()
        self.set_status("{encoding} · {count} 个章节 / 分段 · 进度自动保存{author}", encoding=book.encoding, count=len(book.sections), author=f" · {book.author}" if book.author else "")
        self.encoding_bar.hide()
        self.encoding_button.setVisible(book.encoding != "EPUB")
        self.encoding.setCurrentIndex(max(0, self.encoding.findData(book.encoding)))
        self.save_state()
        self.reader.setFocus()

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
        self.chapters.setCurrentRow(index)
        self.reader.set_text(section.text, offset, section.images)
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
        self.open_section(self.chapters.row(item))
        self.reader.setFocus()

    def _recent_activated(self, item):
        record = item.data(Qt.ItemDataRole.UserRole)
        encoding = record.get("encoding", "auto")
        self.load_path(record["path"], encoding if encoding in ENCODINGS else "auto")

    def _refresh_recent(self):
        self.recent.clear()
        for record in self.store.state["books"]:
            item = QListWidgetItem(record["title"])
            item.setData(Qt.ItemDataRole.UserRole, record)
            self.recent.addItem(item)

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
        self.tabs.setTabText(0, self.t("目录"))
        self.tabs.setTabText(1, self.t("最近"))
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
        self._configure_hotkeys()
        if self.focus_mode:
            for widget in self.chrome_widgets:
                widget.hide()
        self.schedule_save()

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
