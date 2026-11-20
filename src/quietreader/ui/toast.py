"""Lightweight auto-hiding notice with an optional action button."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton


class ToastNotice(QFrame):
    """Single-slot status notice that can optionally offer a click action."""

    _MIN_DURATION_MS = 2500
    _MAX_DURATION_MS = 4500
    _ACTION_DURATION_MS = 8000
    _HORIZONTAL_PADDING = 16
    _VERTICAL_PADDING = 9
    _BOTTOM_OFFSET = 42

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("toastNotice")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._action = None
        self._text = ""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            self._HORIZONTAL_PADDING,
            self._VERTICAL_PADDING,
            self._HORIZONTAL_PADDING,
            self._VERTICAL_PADDING,
        )
        layout.setSpacing(8)

        self.label = QLabel("")
        self.label.setObjectName("toastLabel")
        self.label.setTextFormat(Qt.TextFormat.PlainText)
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)

        self.action_button = QPushButton(self)
        self.action_button.setObjectName("toastAction")
        self.action_button.setMinimumWidth(0)
        self.action_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.action_button.clicked.connect(self._activate_action)
        self.action_button.hide()
        layout.addWidget(self.action_button, 0, Qt.AlignmentFlag.AlignVCenter)

        self._bottom_margin = self._BOTTOM_OFFSET
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.dismiss)
        self.hide()

    @classmethod
    def duration_for(cls, text: str) -> int:
        return max(cls._MIN_DURATION_MS, min(cls._MAX_DURATION_MS, 2200 + len(text) * 45))

    def show_message(
        self, text: str, duration_ms: int | None = None, bottom_margin: int | None = None,
        action_text: str | None = None, action=None,
    ):
        cleaned = (text or "").strip()
        if not cleaned:
            return
        if bottom_margin is not None:
            self._bottom_margin = max(self._BOTTOM_OFFSET, int(bottom_margin))
        self._text = cleaned
        self._set_action(action_text, action)
        self.reposition()
        self.show()
        self.raise_()
        timeout = self.duration_for(cleaned) if duration_ms is None else max(200, int(duration_ms))
        if self._action is not None:
            timeout = max(timeout, self._ACTION_DURATION_MS)
        self.timer.start(timeout)

    def update_text(self, text: str, action_text: str | None = None, action=None):
        cleaned = (text or "").strip()
        if not cleaned:
            self.dismiss()
            return
        self._text = cleaned
        self._set_action(action_text, action)
        self.reposition()

    def _set_action(self, text, action):
        self._action = action if text and callable(action) else None
        self.action_button.setText(text or "")
        self.action_button.setVisible(self._action is not None)
        self.label.setWordWrap(self._action is None)
        self.label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
            if self._action is None
            else Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            self._action is None,
        )

    def _activate_action(self):
        action = self._action
        self.dismiss()
        if action is not None:
            action()

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
        if self._action is not None:
            self.action_button.ensurePolished()
            metrics = self.label.fontMetrics()
            spacing = self.layout().spacing()
            button_natural_width = self.action_button.sizeHint().width()
            text_natural_width = metrics.horizontalAdvance(self._text) + 4
            preferred_width = (
                text_natural_width + button_natural_width + spacing
                + self._HORIZONTAL_PADDING * 2
            )
            width = min(max_width, max(160, preferred_width))
            available_width = width - self._HORIZONTAL_PADDING * 2 - spacing
            button_width = min(button_natural_width, max(40, available_width - 40))
            label_width = max(1, available_width - button_width)
            self.action_button.setFixedWidth(button_width)
            self.label.setFixedWidth(label_width)
            self.label.setText(metrics.elidedText(
                self._text, Qt.TextElideMode.ElideRight, label_width,
            ))
            content_height = max(metrics.height(), self.action_button.sizeHint().height())
            height = content_height + self._VERTICAL_PADDING * 2 + 4
        else:
            self.label.setText(self._text)
            bounds = self.label.fontMetrics().boundingRect(
                0, 0, max_text_width, 1000,
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                self._text,
            )
            width = min(max_width, bounds.width() + self._HORIZONTAL_PADDING * 2 + 8)
            self.label.setFixedWidth(max(1, width - self._HORIZONTAL_PADDING * 2))
            height = bounds.height() + self._VERTICAL_PADDING * 2 + 4
        x = max(12, (parent_width - width) // 2)
        y = max(12, parent_height - height - self._bottom_margin)
        self.setGeometry(x, y, width, height)

    def dismiss(self):
        self.timer.stop()
        self._set_action(None, None)
        self.hide()
