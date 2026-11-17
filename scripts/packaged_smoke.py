"""Launch the built executable, verify import/state, and close its own window."""
import ctypes
import argparse
from ctypes import wintypes
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--transparent", action="store_true", help="Verify startup with a fully transparent floating window")
    args = parser.parse_args()
    if sys.platform != "win32":
        raise SystemExit("Windows only")
    root = Path(__file__).resolve().parents[1]
    executable = root / "dist" / "QuietReader" / "QuietReader.exe"
    user32 = ctypes.windll.user32
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumChildWindows.argtypes = [wintypes.HWND, callback_type, wintypes.LPARAM]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    with tempfile.TemporaryDirectory(prefix="quietreader-package-") as temp:
        directory = Path(temp)
        book = directory / "打包测试.txt"
        book.write_text("第一章\n独立可执行程序读取本地文字。\n" * 20, encoding="utf-8")
        data = directory / "state"
        data.mkdir()
        settings = {"close_to_tray": False}
        if args.transparent:
            settings.update(floating=True, opacity=0, background_color="#111111")
        (data / "state.json").write_text(json.dumps({"version": 1, "settings": settings, "books": [], "positions": {}}), encoding="utf-8")
        started = time.monotonic()
        process = subprocess.Popen([str(executable), "--data-dir", str(data), str(book)], cwd=root)
        windows = []
        observed_titles = []
        error_text = []

        @callback_type
        def collect_error(hwnd, _):
            value = ctypes.create_unicode_buffer(4096)
            user32.GetWindowTextW(hwnd, value, 4096)
            if value.value:
                error_text.append(value.value)
            return True

        @callback_type
        def collect(hwnd, _):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value == process.pid and user32.IsWindowVisible(hwnd):
                title = ctypes.create_unicode_buffer(1024)
                user32.GetWindowTextW(hwnd, title, 1024)
                observed_titles.append(title.value)
                if title.value == "Unhandled exception in script":
                    user32.EnumChildWindows(hwnd, collect_error, 0)
                if "打包测试" in title.value and "QuietReader" in title.value:
                    windows.append(hwnd)
            return True

        try:
            deadline = time.monotonic() + 25
            imported = False
            while time.monotonic() < deadline and process.poll() is None:
                windows.clear()
                user32.EnumWindows(collect, 0)
                try:
                    state = json.loads((data / "state.json").read_text(encoding="utf-8"))
                    imported = bool(state.get("books"))
                except (OSError, ValueError):
                    pass
                if imported and windows:
                    break
                time.sleep(0.1)
            assert imported and windows, f"Packaged smoke failed: imported={imported}, exit={process.poll()}, titles={observed_titles[-5:]}, details={error_text[-5:]}"
            startup = round(time.monotonic() - started, 3)
            user32.PostMessageW(windows[0], 0x0010, 0, 0)  # WM_CLOSE to this process only
            assert process.wait(timeout=15) == 0
            state = json.loads((data / "state.json").read_text(encoding="utf-8"))
            assert state["last_book"] in state["positions"]
            if args.transparent:
                assert state["settings"]["opacity"] == 0
                assert state["settings"]["background_color"] == "#111111"
            output = root / "artifacts"
            output.mkdir(exist_ok=True)
            report = {"executable_start": True, "book_import": True, "position_saved": True, "clean_exit": True, "transparent_startup": args.transparent, "startup_and_import_seconds": startup}
            (output / "packaged-smoke.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report))
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)


if __name__ == "__main__":
    main()
