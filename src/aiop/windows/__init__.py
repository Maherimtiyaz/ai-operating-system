"""
Windows integration for AIOP
"""

from .win32_api import Win32API
from .clipboard import Clipboard
from .hotkeys import HotkeyManager, HotkeyCallback
from . import system

__all__ = [
    "Win32API",
    "Clipboard",
    "HotkeyManager",
    "HotkeyCallback",
    "system",
]
