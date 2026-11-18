"""Run image/layout fixtures against native Qt and retain app-only captures."""
from pathlib import Path
import sys
import tempfile

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / "src"), str(root / "tests")]
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from test_illustrations_live import test_epub_inline_image_order_and_render, test_layout_panel_live_preview_cancel_and_save
from quietreader.persistence.store import StateStore
from quietreader.ui.window import MainWindow
from quietreader.domain.models import Book, Section


app = QApplication([])
app.setQuitOnLastWindowClosed(False)
output = root / "artifacts"
output.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix="quietreader-images-") as temp:
    folder = Path(temp)
    test_epub_inline_image_order_and_render(app, folder, output / "epub-illustration.png")
    test_layout_panel_live_preview_cancel_and_save(app, folder / "preview")
    window = MainWindow(StateStore(folder / "capture"), enable_system=False)
    window.show()
    window._loaded(Book("demo", "none.txt", "阅读界面实时预览", sections=[Section("one", "示例章节", "清晨的风穿过树林，落在安静的书页上。\n" * 100)]))
    panel = window.create_layout_panel()
    panel.show()
    panel.fields["font_size"].setValue(28)
    panel.fields["line_height"].setValue(2)
    QTest.qWait(150)
    assert window.reader.settings.font_size == 28
    window.grab().save(str(output / "live-layout-reader.png"))
    panel.grab().save(str(output / "live-layout-panel.png"))
    panel.reject()
    assert window.reader.settings.font_size == window.settings.font_size
    window.shutdown()
print("Native EPUB image pixels, live layout preview, cancel and save: PASS")
