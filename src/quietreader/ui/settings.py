from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFontComboBox, QFormLayout, QLabel, QLineEdit, QMessageBox,
    QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from quietreader.domain.models import Settings, valid_hotkey


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("阅读偏好 · QuietReader")
        self.resize(510, 680)
        outer = QVBoxLayout(self)
        title = QLabel("让阅读适合你")
        title.setObjectName("bookTitle")
        outer.addWidget(title)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        form = QFormLayout(content)
        form.setVerticalSpacing(12)
        scroll.setWidget(content)
        outer.addWidget(scroll)
        self.fields = {}
        self.theme = QComboBox()
        for label, value in [("跟随系统", "system"), ("纸白", "light"), ("暖纸", "sepia"), ("夜读", "dark")]:
            self.theme.addItem(label, value)
        self.theme.setCurrentIndex(self.theme.findData(settings.theme))
        form.addRow("配色", self.theme)
        self.font = QFontComboBox()
        self.font.setCurrentFont(QFont(settings.font_family))
        form.addRow("字体", self.font)
        for key, label, low, high, step in [
            ("font_size", "字号（像素）", 14, 42, 1),
            ("line_height", "行距倍数", 1.2, 2.5, 0.1),
            ("letter_spacing", "字距（像素）", 0.0, 5.0, 0.1),
            ("paragraph_spacing", "段距（像素）", 0, 40, 1),
            ("padding", "页边距（像素）", 12, 72, 2),
            ("opacity", "浮窗背景不透明度", 0.55, 1.0, 0.05),
        ]:
            field = QDoubleSpinBox() if isinstance(step, float) else QSpinBox()
            field.setRange(low, high)
            field.setSingleStep(step)
            field.setValue(getattr(settings, key))
            form.addRow(label, field)
            self.fields[key] = field
        note = QLabel("半透明仅用于浮窗；文字保持不透明。\n若背景复杂，建议提高背景不透明度。")
        note.setObjectName("status")
        form.addRow(note)
        for key, label in [("floating", "使用阅读浮窗"), ("always_on_top", "窗口始终置顶"), ("close_to_tray", "关闭窗口时隐藏至托盘"), ("global_hotkey", "启用全局显示 / 隐藏快捷键")]:
            field = QCheckBox(label)
            field.setChecked(getattr(settings, key))
            self.fields[key] = field
            form.addRow(field)
        self.hotkey = QLineEdit(settings.hotkey)
        self.hotkey.setMaxLength(20)
        self.hotkey.setPlaceholderText("Ctrl+Alt+R")
        form.addRow("全局快捷键", self.hotkey)
        note = QLabel("支持 Ctrl+Alt / Ctrl+Shift / Alt+Shift + 单个字母或数字。\n注册冲突会在主窗口提示；可取消启用。")
        note.setObjectName("status")
        form.addRow(note)
        for key, label in [("next_key", "下一页（正文聚焦时）"), ("previous_key", "上一页（正文聚焦时）")]:
            field = QComboBox()
            for text, value in [("PageDown", "PgDown"), ("PageUp", "PgUp"), ("→", "Right"), ("←", "Left"), ("空格", "Space")]:
                field.addItem(text, value)
            field.setCurrentIndex(field.findData(getattr(settings, key)))
            self.fields[key] = field
            form.addRow(label, field)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.RestoreDefaults)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("保存偏好")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).setText("恢复默认")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(self.reset_defaults)
        outer.addWidget(buttons)

    def reset_defaults(self):
        defaults = Settings()
        self.theme.setCurrentIndex(0)
        self.font.setCurrentFont(QFont(defaults.font_family))
        self.hotkey.setText(defaults.hotkey)
        for key, field in self.fields.items():
            value = getattr(defaults, key)
            if isinstance(field, QCheckBox):
                field.setChecked(value)
            elif isinstance(field, QComboBox):
                field.setCurrentIndex(field.findData(value))
            else:
                field.setValue(value)

    def values(self):
        data = {"theme": self.theme.currentData(), "font_family": self.font.currentFont().family(), "hotkey": self.hotkey.text().strip()}
        for key, field in self.fields.items():
            if isinstance(field, QCheckBox):
                data[key] = field.isChecked()
            elif isinstance(field, QComboBox):
                data[key] = field.currentData()
            else:
                data[key] = field.value()
        return Settings.from_dict(data)

    def accept(self):
        if not valid_hotkey(self.hotkey.text().strip()):
            QMessageBox.warning(self, "快捷键格式", "请使用例如 Ctrl+Alt+R 的组合。")
            return
        if self.fields["next_key"].currentData() == self.fields["previous_key"].currentData():
            QMessageBox.warning(self, "快捷键冲突", "上一页和下一页不能使用同一个按键。")
            return
        super().accept()
