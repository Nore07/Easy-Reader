"""Lightweight non-interactive toast notice anchored inside the main window."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class ToastNotice(QFrame):
    """Single-slot auto-hiding notice that never steals focus or mouse input."""

    _MIN_DURATION_MS = 2500
    _MAX_DURATION_MS = 4500
    _HORIZONTAL_PADDING = 16
    _VERTICAL_PADDING = 9
    _BOTTOM_OFFSET = 42

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("toastNotice")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            self._HORIZONTAL_PADDING,
            self._VERTICAL_PADDING,
            self._HORIZONTAL_PADDING,
            self._VERTICAL_PADDING,
        )
        layout.setSpacing(0)

        self.label = QLabel("")
        self.label.setObjectName("toastLabel")
        self.label.setTextFormat(Qt.TextFormat.PlainText)
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)

        self._bottom_margin = self._BOTTOM_OFFSET
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.dismiss)
        self.hide()

    @classmethod
    def duration_for(cls, text: str) -> int:
        return max(cls._MIN_DURATION_MS, min(cls._MAX_DURATION_MS, 2200 + len(text) * 45))

    def show_message(self, text: str, duration_ms: int | None = None, bottom_margin: int | None = None):
        cleaned = (text or "").strip()
        if not cleaned:
            return
        if bottom_margin is not None:
            self._bottom_margin = max(self._BOTTOM_OFFSET, int(bottom_margin))
        self.label.setText(cleaned)
        self.reposition()
        self.show()
        self.raise_()
        timeout = self.duration_for(cleaned) if duration_ms is None else max(200, int(duration_ms))
        self.timer.start(timeout)

    def update_text(self, text: str):
        cleaned = (text or "").strip()
        if not cleaned:
            self.dismiss()
            return
        self.label.setText(cleaned)
        self.reposition()

    def reposition(self, bottom_margin: int | None = None):
        parent = self.parentWidget()
        if parent is None:
            return
        if bottom_margin is not None:
            self._bottom_margin = max(self._BOTTOM_OFFSET, int(bottom_margin))
        parent_width = max(200, parent.width())
        parent_height = max(120, parent.height())
        max_width = max(160, min(520, parent_width - 40))
        max_text_width = max(80, max_width - self._HORIZONTAL_PADDING * 2)
        self.label.ensurePolished()
        bounds = self.label.fontMetrics().boundingRect(
            0, 0, max_text_width, 1000,
            Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
            self.label.text(),
        )
        width = min(max_width, bounds.width() + self._HORIZONTAL_PADDING * 2 + 8)
        height = bounds.height() + self._VERTICAL_PADDING * 2 + 4
        x = max(12, (parent_width - width) // 2)
        y = max(12, parent_height - height - self._bottom_margin)
        self.setGeometry(x, y, width, height)

    def dismiss(self):
        self.timer.stop()
        self.hide()
