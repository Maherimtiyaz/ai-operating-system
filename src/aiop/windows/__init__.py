"""
Windows integration for AIOP
"""

from .win32_api import Win32API, get_win32_api
from .clipboard import Clipboard, get_clipboard
from .hotkeys import HotkeyManager, HotkeyCallback, get_hotkey_manager, register_hotkey

__all__ = [
    "Win32API",
    "get_win32_api",
    "Clipboard",
    "get_clipboard",
    "HotkeyManager",
    "get_hotkey_manager",
    "HotkeyCallback",
    "register_hotkey",
]
