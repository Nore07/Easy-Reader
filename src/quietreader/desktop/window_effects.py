"""Native window effects that Qt does not expose across all platforms."""
import ctypes
import sys


_DWMWA_BORDER_COLOR = 34
_DWMWA_COLOR_DEFAULT = 0xFFFFFFFF
_DWMWA_COLOR_NONE = 0xFFFFFFFE


def set_window_border_hidden(window, hidden):
    """Suppress the Windows 11 DWM frame border while focus mode is active."""
    if sys.platform != "win32":
        return False
    handle = window.windowHandle()
    if handle is None:
        return False
    color = ctypes.c_uint32(_DWMWA_COLOR_NONE if hidden else _DWMWA_COLOR_DEFAULT)
    try:
        set_attribute = ctypes.windll.dwmapi.DwmSetWindowAttribute
        set_attribute.argtypes = (ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint)
        set_attribute.restype = ctypes.c_long
        result = set_attribute(
            ctypes.c_void_p(int(handle.winId())),
            _DWMWA_BORDER_COLOR,
            ctypes.byref(color),
            ctypes.sizeof(color),
        )
    except (AttributeError, OSError):
        return False
    return result == 0
