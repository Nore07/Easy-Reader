import argparse
from pathlib import Path
import sys

from PySide6.QtCore import QLockFile, QStandardPaths, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

from quietreader.persistence.store import StateStore
from quietreader.ui.window import MainWindow
from quietreader.i18n import tr


def main():
    parser = argparse.ArgumentParser(description="QuietReader 本地 TXT / EPUB 阅读器")
    parser.add_argument("file", nargs="?", help="打开的 TXT / EPUB 文件")
    parser.add_argument("--data-dir", type=Path, help="指定独立的本地用户数据目录")
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName("QuietReader")
    app.setOrganizationName("QuietReader")
    app.setQuitOnLastWindowClosed(False)
    directory = args.data_dir or Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation))
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        QMessageBox.critical(None, tr("无法启动"), tr("无法创建用户数据目录，请检查权限或使用 --data-dir 指定目录。"))
        return 1
    lock = QLockFile(str(directory / "quietreader.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.information(None, tr("QuietReader 已在运行"), tr("同一数据目录的阅读器已在运行，请从托盘显示窗口。"))
        return 0
    app._quietreader_release_lock = lock.unlock
    window = MainWindow(StateStore(directory))
    app.aboutToQuit.connect(window.shutdown)
    app.commitDataRequest.connect(lambda *_: window.save_state())
    window.show()
    QTimer.singleShot(0, lambda: window.add_book_paths([args.file], open_after=True) if args.file else window.restore_last())
    code = app.exec()
    lock.unlock()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
