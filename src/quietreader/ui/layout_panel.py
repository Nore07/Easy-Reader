from dataclasses import replace
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QFontComboBox, QLabel, QSpinBox, QVBoxLayout
from PySide6.QtGui import QFont
from quietreader.i18n import tr
from quietreader.ui.theme import colors, stylesheet
from quietreader.ui.settings import _PreferencesWheelFilter


class LayoutPanel(QDialog):
    preview = Signal(object)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.original = replace(settings)
        self.fields = {}
        self.setWindowTitle(tr("阅读界面", settings.language))
        self.setStyleSheet(stylesheet(colors(settings.theme)))
        self.resize(390, 440)
        outer = QVBoxLayout(self)
        note = QLabel(tr("调整会立即预览当前书页；保存后生效，取消恢复原设置。", settings.language))
        note.setWordWrap(True)
        outer.addWidget(note)
        form = QFormLayout()
        self.font = QFontComboBox()
        self.font.setCurrentFont(QFont(settings.font_family))
        form.addRow(tr("字体", settings.language), self.font)
        for key, label, low, high, step in [("font_size", "字号（像素）",14,42,1), ("line_height","行距倍数",1.2,2.5,0.1), ("letter_spacing","字距（像素）",0.0,5.0,0.1), ("paragraph_spacing","段距（像素）",0,40,1), ("padding","页边距（像素）",12,72,2)]:
            field = QDoubleSpinBox() if isinstance(step, float) else QSpinBox()
            field.setRange(low, high)
            field.setSingleStep(step)
            field.setValue(getattr(settings, key))
            self.fields[key] = field
            form.addRow(tr(label, settings.language), field)
            field.valueChanged.connect(self.changed)
        self.font.currentFontChanged.connect(self.changed)
        outer.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
        self.wheel_filter = _PreferencesWheelFilter(None, self)
        for field in [self.font] + list(self.fields.values()):
            field.installEventFilter(self.wheel_filter)
            if field.lineEdit():
                field.lineEdit().installEventFilter(self.wheel_filter)

    def values(self):
        return replace(self.original, font_family=self.font.currentFont().family(), **{key: field.value() for key, field in self.fields.items()})

    def changed(self, *args):
        self.preview.emit(self.values())
