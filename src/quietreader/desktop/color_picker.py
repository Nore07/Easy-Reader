"""User-initiated, in-memory screen sampling. Images are never saved or sent."""
from dataclasses import dataclass

from PySide6.QtCore import QObject, QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget


@dataclass
class ScreenSample:
    image: QImage
    geometry: QRect

    def color_at(self, global_point: QPoint) -> QColor:
        if self.image.isNull() or not self.geometry.contains(global_point):
            return QColor()
        # Screen coordinates are logical pixels; captures can use a different DPR.
        point = global_point - self.geometry.topLeft()
        x = min(self.image.width() - 1, point.x() * self.image.width() // self.geometry.width())
        y = min(self.image.height() - 1, point.y() * self.image.height() // self.geometry.height())
        return self.image.pixelColor(x, y)


def capture_screens():
    samples = []
    for screen in QGuiApplication.screens():
        image = screen.grabWindow(0).toImage()
        if image.isNull():
            raise RuntimeError("screen capture unavailable")
        samples.append(ScreenSample(image, screen.geometry()))
    if not samples:
        raise RuntimeError("no screens")
    return samples


class ColorOverlay(QWidget):
    chosen = Signal(QColor)
    canceled = Signal()

    def __init__(self, sample, parent):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.sample = sample
        self.point = QPoint(20, 20)
        self.setGeometry(sample.geometry)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("桌面取色：单击选择，Esc 或右键取消")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawImage(self.rect(), self.sample.image)
        color = self.sample.color_at(self.sample.geometry.topLeft() + self.point)
        box = QRect(min(self.width() - 260, max(0, self.point.x() + 20)), min(self.height() - 74, max(0, self.point.y() + 20)), 260, 74)
        painter.fillRect(box, QColor("#f5f3eb"))
        painter.setPen(QPen(QColor("#315743"), 1))
        painter.drawRect(box)
        painter.fillRect(box.adjusted(10, 12, -220, -32), color)
        painter.drawText(box.adjusted(46, 9, -8, -30), Qt.AlignmentFlag.AlignVCenter, color.name().upper())
        painter.drawText(box.adjusted(10, 38, -8, -4), Qt.AlignmentFlag.AlignVCenter, "单击取色 · Esc / 右键取消")

    def mouseMoveEvent(self, event):
        self.point = event.position().toPoint()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            color = self.sample.color_at(self.sample.geometry.topLeft() + event.position().toPoint())
            if color.isValid():
                self.chosen.emit(color)
        elif event.button() == Qt.MouseButton.RightButton:
            self.canceled.emit()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.canceled.emit()
        else:
            super().keyPressEvent(event)


class DesktopColorPicker(QObject):
    selected = Signal(QColor)
    failed = Signal(str)

    def __init__(self, owner, capture=capture_screens):
        super().__init__(owner)
        self.owner = owner
        self.capture = capture
        self.overlays = []
        self.windows = []
        self.active = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(180)
        self.timer.timeout.connect(self._capture)

    def begin(self):
        if self.active:
            return
        self.active = True
        self.windows = []
        parent = self.owner.parentWidget()
        # Opacity hides the windows visually without ending a modal QDialog.exec().
        for window in ([parent.window()] if parent else []) + [self.owner]:
            self.windows.append((window, window.windowOpacity()))
            window.setWindowOpacity(0)
        self.timer.start()

    def _capture(self):
        if not self.active:
            return
        try:
            samples = self.capture()  # Capture every screen before showing any overlay.
            if not samples:
                raise RuntimeError("no captures")
            for sample in samples:
                overlay = ColorOverlay(sample, self.owner)
                overlay.chosen.connect(self._finish)
                overlay.canceled.connect(self.cancel)
                self.overlays.append(overlay)
            for overlay in self.overlays:
                overlay.show()
            focused = next((o for o in self.overlays if o.geometry().contains(QCursor.pos())), self.overlays[0])
            focused.activateWindow()
            focused.setFocus()
        except Exception:
            self.cancel()
            self.failed.emit("无法获取桌面颜色，请使用“选择颜色”手动设置。")

    def _finish(self, color=None):
        if not self.active:
            return
        self.active = False
        self.timer.stop()
        for overlay in self.overlays:
            overlay.hide()
            overlay.sample.image = QImage()
            overlay.deleteLater()
        self.overlays.clear()
        for window, opacity in self.windows:
            window.setWindowOpacity(opacity)
        self.windows.clear()
        self.owner.activateWindow()
        self.owner.raise_()
        if color is not None and color.isValid():
            self.selected.emit(color)

    def cancel(self):
        self._finish()
