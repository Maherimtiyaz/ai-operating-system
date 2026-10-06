"""Controlled operating-system actions driven by recognized intent."""

import os
import re
import time
from dataclasses import dataclass

from ..core import logging
from .clipboard import get_clipboard
from .win32_api import VirtualKey, get_win32_api

logger = logging.get_logger(__name__)

# Windows refuses SetForegroundWindow focus changes that happen in the same
# tick as the user gesture. A short settle delay lets the target app take
# focus before we synthesize the paste.
PASTE_SETTLE_SECONDS = 0.12


@dataclass
class ActionResult:
    """Result of a controlled action."""

    handled: bool
    success: bool
    message: str


class ActionRouter:
    """Route recognized speech to a small allowlisted action set."""

    FILE_MANAGER_PATTERN = re.compile(
        r"\b(open|launch|start)\s+(my\s+)?(file\s+manager|file\s+explorer|explorer)\b",
        re.IGNORECASE,
    )

    def route(self, text: str, target_window: int = None) -> ActionResult:
        """Perform a known action or insert text into the captured target app."""
        normalized = text.strip()
        if not normalized:
            return ActionResult(False, False, "No speech recognized")

        if self.FILE_MANAGER_PATTERN.search(normalized):
            try:
                os.startfile("explorer.exe")
                return ActionResult(True, True, "File manager opened")
            except OSError as error:
                logger.error("Failed to open file manager: %s", error)
                return ActionResult(True, False, "Could not open file manager")

        try:
            clipboard = get_clipboard()
            win32 = get_win32_api()
            if target_window is None:
                target_window = win32.get_foreground_window()
            if not target_window:
                return ActionResult(True, False, "No focused application")
            if not clipboard.set_text(normalized):
                return ActionResult(True, False, "Could not copy dictation")

            if not win32.set_foreground_window(target_window):
                return ActionResult(True, False, "Could not restore focused application")
            time.sleep(PASTE_SETTLE_SECONDS)
            win32.send_vk_combo(
                VirtualKey.VK_CONTROL.value,
                VirtualKey.VK_V.value,
            )
            return ActionResult(True, True, "Dictation inserted")
        except Exception as error:
            logger.error("Failed to insert dictation: %s", error)
            return ActionResult(True, False, "Could not insert dictation")


def paste_into_foreground(text: str, settle_seconds: float = PASTE_SETTLE_SECONDS) -> None:
    """Insert text into the currently focused window via clipboard + Ctrl+V.

    Raises an OSError-backed exception when there is no focused window or the
    focus cannot be restored.
    """
    win32 = get_win32_api()
    target_window = win32.get_foreground_window()
    if not target_window:
        raise RuntimeError("No focused application to paste into")
    clipboard = get_clipboard()
    if not clipboard.set_text(text):
        raise RuntimeError("Could not copy text to the clipboard")
    if not win32.set_foreground_window(target_window):
        raise RuntimeError("Could not restore focus to paste into")
    time.sleep(settle_seconds)
    win32.send_vk_combo(VirtualKey.VK_CONTROL.value, VirtualKey.VK_V.value)