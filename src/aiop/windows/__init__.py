"""
Windows integration for AIOP
"""

from .win32_api import Win32API, get_win32_api
from .clipboard import Clipboard, get_clipboard
from .hotkeys import HotkeyManager, HotkeyCallback, get_hotkey_manager, register_hotkey
from .actions import ActionResult, ActionRouter
from .key_hook import KeyHook, get_key_hook

__all__ = [
    "Win32API",
    "get_win32_api",
    "Clipboard",
    "get_clipboard",
    "HotkeyManager",
    "get_hotkey_manager",
    "HotkeyCallback",
    "register_hotkey",
    "ActionResult",
    "ActionRouter",
    "HotkeyEventFilter",
    "KeyHook",
    "get_key_hook",
]


def get_hotkey_event_filter():
    """Import the Qt-backed hotkey filter lazily.

    Keeping this out of module scope lets the Windows integration layer be
    imported on machines without Qt installed.
    """
    from .event_filter import HotkeyEventFilter

    return HotkeyEventFilter
