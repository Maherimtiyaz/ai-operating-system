"""Route Win32 WM_HOTKEY messages into HotkeyManager.

Qt owns the thread message loop, so a plain hidden window with a WndProc never
receives WM_HOTKEY on its own: nothing pumps the queue. Installing a native
event filter lets Qt's dispatcher hand those messages to HotkeyManager.
"""

import ctypes
import ctypes.wintypes

from PyQt6.QtCore import QAbstractNativeEventFilter

from ..core import logging
from .hotkeys import WM_HOTKEY, HotkeyManager

logger = logging.get_logger(__name__)


class MSG(ctypes.Structure):
    """Win32 MSG as laid out in memory for the native event filter."""

    _fields_ = [
        ("hwnd", ctypes.wintypes.HWND),
        ("message", ctypes.wintypes.UINT),
        ("wParam", ctypes.wintypes.WPARAM),
        ("lParam", ctypes.wintypes.LPARAM),
        ("time", ctypes.wintypes.DWORD),
        ("pt", ctypes.wintypes.POINT),
    ]


class HotkeyEventFilter(QAbstractNativeEventFilter):
    """Forward WM_HOTKEY notifications to a HotkeyManager."""

    def __init__(self, manager: HotkeyManager):
        super().__init__()
        self._manager = manager

    def nativeEventFilter(self, event_type, message):
        """Return (handled, result) after dispatching any hotkey message."""
        try:
            msg = MSG.from_address(int(message))
        except (TypeError, ValueError):
            return False, 0

        if msg.message == WM_HOTKEY:
            self._manager.dispatch_hotkey(msg.wParam)
            # Let Qt keep processing the message normally.
            return False, 0

        return False, 0