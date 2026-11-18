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
    parser.add_argument("--exe", type=Path, help="Executable to verify; defaults to the latest successful build")
    parser.add_argument("--focus", action="store_true", help="Verify English preferences and keyboard focus entry/exit in the executable")
    parser.add_argument("--emergency", action="store_true", help="Verify global hide/show, emergency process exit and restart")
    args = parser.parse_args()
    if args.emergency and (args.focus or args.transparent):
        parser.error("Run the emergency scenario separately")
    if sys.platform != "win32":
        raise SystemExit("Windows only")
    root = Path(__file__).resolve().parents[1]
    latest = root / "artifacts" / "latest-build.txt"
    executable = args.exe or (Path(latest.read_text(encoding="utf-8").strip()) if latest.exists() else root / "dist" / "QuietReader" / "QuietReader.exe")
    user32 = ctypes.windll.user32
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [callback_type, wintypes.LPARAM]
    user32.EnumChildWindows.argtypes = [wintypes.HWND, callback_type, wintypes.LPARAM]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = wintypes.LONG
    with tempfile.TemporaryDirectory(prefix="quietreader-package-") as temp:
        directory = Path(temp)
        book = directory / "打包测试.txt"
        book.write_text("第一章\n独立可执行程序读取本地文字。\n" * 20, encoding="utf-8")
        data = directory / "state"
        data.mkdir()
        settings = {"close_to_tray": False}
        if args.transparent:
            settings.update(floating=True, opacity=0, background_color="#111111")
        if args.focus:
            settings.update(language="en", text_color="#123456", next_key="J", previous_key="K", focus_key="F8")
        if args.emergency:
            settings.update(close_to_tray=True, global_hotkey=True, hotkey="Ctrl+Alt+F9", emergency_key="Ctrl+Alt+F8")
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
            if args.focus:
                assert not args.transparent, "Run focus and transparent scenarios separately"

                def post_key(virtual_key):
                    user32.PostMessageW(windows[0], 0x0100, virtual_key, 1)
                    user32.PostMessageW(windows[0], 0x0101, virtual_key, 0xC0000001)

                def wait_caption(expected):
                    end = time.monotonic() + 5
                    while time.monotonic() < end:
                        windows.clear()
                        user32.EnumWindows(collect, 0)
                        if windows and bool(user32.GetWindowLongW(windows[0], -16) & 0x00C00000) == expected:
                            return
                        time.sleep(0.05)
                    raise AssertionError("Focus window style did not change as expected")

                wait_caption(True)
                first_section = state["positions"][state["last_book"]]["section_id"]
                post_key(0x77)  # F8
                wait_caption(False)
                post_key(ord("J"))
                time.sleep(0.1)
                post_key(0x1B)  # Escape
                wait_caption(True)
            emergency_seconds = None
            if args.emergency:
                def wait_visibility(expected):
                    end = time.monotonic() + 10
                    while time.monotonic() < end and process.poll() is None:
                        windows.clear()
                        user32.EnumWindows(collect, 0)
                        if bool(windows) == expected:
                            return
                        time.sleep(0.05)
                    raise AssertionError("Shortcut did not change window visibility")

                def dispatch(thread, identifier):
                    assert user32.PostThreadMessageW(thread, 0x0312, identifier, 0)

                thread = user32.GetWindowThreadProcessId(windows[0], None)
                dispatch(thread, 0x5152)
                wait_visibility(False)
                dispatch(thread, 0x5152)
                wait_visibility(True)
                dispatch(thread, 0x5152)
                wait_visibility(False)
                before_exit = time.monotonic()
                dispatch(thread, 0x5153)
                assert process.wait(timeout=3) == 0
                emergency_seconds = round(time.monotonic() - before_exit, 3)
                assert not (data / "quietreader.lock").exists()
                process = subprocess.Popen([str(executable), "--data-dir", str(data)], cwd=root)
                wait_visibility(True)
                thread = user32.GetWindowThreadProcessId(windows[0], None)
                dispatch(thread, 0x5153)
            else:
                user32.PostMessageW(windows[0], 0x0010, 0, 0)  # WM_CLOSE to this process only
            assert process.wait(timeout=15) == 0
            state = json.loads((data / "state.json").read_text(encoding="utf-8"))
            assert state["last_book"] in state["positions"]
            if args.transparent:
                assert state["settings"]["opacity"] == 0
                assert state["settings"]["background_color"] == "#111111"
            if args.focus:
                assert state["settings"]["language"] == "en"
                assert state["settings"]["text_color"] == "#123456"
                assert state["settings"]["next_key"] == "J"
                assert state["positions"][state["last_book"]]["section_id"] != first_section
            output = root / "artifacts"
            output.mkdir(exist_ok=True)
            report = {"executable_start": True, "book_import": True, "position_saved": True, "clean_exit": True, "transparent_startup": args.transparent, "focus_keyboard_and_english": args.focus, "global_visibility_emergency_restart": args.emergency, "emergency_exit_seconds": emergency_seconds, "startup_and_import_seconds": startup}
            (output / "packaged-smoke.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report))
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)


if __name__ == "__main__":
    main()
