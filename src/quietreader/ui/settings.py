from PySide6.QtGui import QColor, QFont
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFontComboBox, QFormLayout, QLabel, QMessageBox, QHBoxLayout, QPushButton,
    QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from quietreader.domain.models import Settings
from quietreader.desktop.color_picker import DesktopColorPicker
from quietreader.i18n import tr, install_qt_translator
from quietreader.keys import BINDING_FIELDS, binding_error
from quietreader.ui.key_capture import KeyBindingButton


class SettingsDialog(QDialog):
    capture_started = Signal()
    capture_finished = Signal()

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.resize(710, 790)
        self.original_language = settings.language
        self.texts = []
        self.fields = {}
        self.background_color = settings.background_color
        self.text_color = settings.text_color
        outer = QVBoxLayout(self)
        self.title = self.label("让阅读适合你")
        self.title.setObjectName("bookTitle")
        outer.addWidget(self.title)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        self.form = QFormLayout(content)
        self.form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.form.setVerticalSpacing(10)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self.language = QComboBox()
        for label, code in [("跟随系统", "system"), ("简体中文", "zh_CN"), ("English", "en")]:
            self.language.addItem(label, code)
        self.language.setCurrentIndex(self.language.findData(settings.language))
        self.row("界面语言", self.language)
        self.theme = QComboBox()
        for label, code in [("跟随系统", "system"), ("纸白", "light"), ("暖纸", "sepia"), ("夜读", "dark")]:
            self.theme.addItem(label, code)
        self.theme.setCurrentIndex(self.theme.findData(settings.theme))
        self.row("配色", self.theme)
        self.font = QFontComboBox()
        self.font.setCurrentFont(QFont(settings.font_family))
        self.row("字体", self.font)
        self.color_label = QLabel()
        self.text_color_label = QLabel()
        self.picker = DesktopColorPicker(self)
        self.picker.selected.connect(self.set_background_color)
        self.picker.failed.connect(lambda message: QMessageBox.warning(self, self.t("桌面取色"), self.t(message)))
        color_row = QHBoxLayout()
        color_row.addWidget(self.color_label)
        for label, callback in [("选择颜色", self.choose_background_color), ("桌面取色", self.picker.begin), ("跟随主题", self.reset_background_color)]:
            color_row.addWidget(self.button(label, callback))
        self.row("浮窗背景色", color_row)
        text_row = QHBoxLayout()
        text_row.addWidget(self.text_color_label)
        text_row.addWidget(self.button("选择颜色", self.choose_text_color))
        text_row.addWidget(self.button("自动文字颜色", self.reset_text_color))
        self.row("文字颜色", text_row)
        for key, label, low, high, step in [
            ("font_size", "字号（像素）", 14, 42, 1), ("line_height", "行距倍数", 1.2, 2.5, 0.1),
            ("letter_spacing", "字距（像素）", 0.0, 5.0, 0.1), ("paragraph_spacing", "段距（像素）", 0, 40, 1),
            ("padding", "页边距（像素）", 12, 72, 2), ("opacity", "浮窗背景不透明度", 0.0, 1.0, 0.05),
        ]:
            field = QDoubleSpinBox() if isinstance(step, float) else QSpinBox()
            field.setRange(low, high)
            field.setSingleStep(step)
            field.setValue(getattr(settings, key))
            self.row(label, field)
            self.fields[key] = field
        self.note("设为 0 即全透明，文字保持不透明；仅在浮窗生效。\n取色时窗口会暂时消失，单击选择，Esc / 右键取消。\n取色结果仅保存在本机；背景变化后可重新取色。")
        for key, label in [("floating", "使用阅读浮窗"), ("always_on_top", "窗口始终置顶"), ("close_to_tray", "关闭窗口时隐藏至托盘"), ("global_hotkey", "启用全局显示 / 隐藏和紧急退出快捷键")]:
            field = QCheckBox()
            self.texts.append((field, label))
            field.setChecked(getattr(settings, key))
            self.fields[key] = field
            self.form.addRow(field)
        for key, label in [("next_key", "下一页（正文聚焦时）"), ("previous_key", "上一页（正文聚焦时）"), ("focus_key", "切换专注模式"), ("hotkey", "显示 / 隐藏快捷键"), ("emergency_key", "紧急退出快捷键")]:
            field = KeyBindingButton(getattr(settings, key), settings.language)
            field.capture_started.connect(self.capture_started.emit)
            field.capture_finished.connect(self.capture_finished.emit)
            self.fields[key] = field
            self.row(label, field)
        self.hotkey = self.fields["hotkey"]
        self.note("点击修改，然后按下一个按键或组合键。Esc 取消录入。\nEsc 固定退出专注模式；打开、偏好和复制的快捷键保留。")
        self.note("专注模式仅显示正文，F10（可修改）或 Esc 退出，也可从托盘或正文右键菜单退出。")
        self.note("同一按键切换隐藏和显示。启用全局快捷键后，窗口隐藏或失去焦点时也可使用。\n紧急退出直接关闭程序，不隐藏到托盘，也不等待后台导入；会尝试保存当前位置。")
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.RestoreDefaults)
        for role, source in [(QDialogButtonBox.StandardButton.Save, "保存偏好"), (QDialogButtonBox.StandardButton.Cancel, "取消"), (QDialogButtonBox.StandardButton.RestoreDefaults, "恢复默认")]:
            self.texts.append((self.buttons.button(role), source))
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(self.reset_defaults)
        outer.addWidget(self.buttons)
        self.language.currentIndexChanged.connect(self.retranslate)
        self.retranslate()

    def t(self, source):
        return tr(source, self.language.currentData())

    def label(self, source):
        label = QLabel()
        label.setWordWrap(True)
        self.texts.append((label, source))
        return label

    def row(self, source, field):
        self.form.addRow(self.label(source), field)

    def button(self, source, callback):
        button = QPushButton()
        button.clicked.connect(callback)
        self.texts.append((button, source))
        return button

    def note(self, source):
        label = self.label(source)
        label.setObjectName("status")
        self.form.addRow(label)

    def retranslate(self, *args):
        install_qt_translator(QApplication.instance(), self.language.currentData())
        self.setWindowTitle(self.t("阅读偏好 · QuietReader"))
        for widget, source in self.texts:
            widget.setText(self.t(source))
        self.language.setItemText(0, self.t("跟随系统"))
        for index, source in enumerate(("跟随系统", "纸白", "暖纸", "夜读")):
            self.theme.setItemText(index, self.t(source))
        for field in self.fields.values():
            if isinstance(field, KeyBindingButton):
                field.language = self.language.currentData()
                field.refresh()
        self._update_color_label()

    def reset_defaults(self):
        defaults = Settings()
        self.theme.setCurrentIndex(0)
        self.language.setCurrentIndex(0)
        self.font.setCurrentFont(QFont(defaults.font_family))
        self.reset_background_color()
        self.reset_text_color()
        for key, field in self.fields.items():
            value = getattr(defaults, key)
            if isinstance(field, QCheckBox):
                field.setChecked(value)
            elif isinstance(field, KeyBindingButton):
                field.set_sequence(value)
            else:
                field.setValue(value)

    def values(self):
        data = {"theme": self.theme.currentData(), "language": self.language.currentData(), "background_color": self.background_color, "text_color": self.text_color, "font_family": self.font.currentFont().family()}
        for key, field in self.fields.items():
            if isinstance(field, QCheckBox):
                data[key] = field.isChecked()
            elif isinstance(field, KeyBindingButton):
                data[key] = field.sequence
            else:
                data[key] = field.value()
        return Settings.from_dict(data)

    def _update_color_label(self):
        self.color_label.setText(self.background_color.upper() or self.t("主题色"))
        self.text_color_label.setText(self.text_color.upper() or self.t("自动文字颜色"))

    def set_background_color(self, color):
        if color.isValid():
            self.background_color = color.name()
            self._update_color_label()

    def set_text_color(self, color):
        if color.isValid():
            self.text_color = color.name()
            self._update_color_label()

    def choose_background_color(self):
        self.set_background_color(QColorDialog.getColor(QColor(self.background_color or "#f5f3eb"), self, self.t("选择浮窗背景色"), QColorDialog.ColorDialogOption.DontUseNativeDialog))

    def choose_text_color(self):
        self.set_text_color(QColorDialog.getColor(QColor(self.text_color or "#283c33"), self, self.t("选择文字颜色"), QColorDialog.ColorDialogOption.DontUseNativeDialog))

    def reset_background_color(self):
        self.background_color = ""
        self._update_color_label()

    def reset_text_color(self):
        self.text_color = ""
        self._update_color_label()

    def done(self, result):
        self.picker.cancel()
        if result != QDialog.DialogCode.Accepted:
            install_qt_translator(QApplication.instance(), self.original_language)
        super().done(result)

    def accept(self):
        error = binding_error({key: self.fields[key].sequence for key in BINDING_FIELDS})
        if error:
            QMessageBox.warning(self, self.t("快捷键冲突"), self.t(error))
            return
        super().accept()
