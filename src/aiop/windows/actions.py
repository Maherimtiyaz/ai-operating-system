"""Controlled operating-system actions driven by recognized intent."""

import os
import re
from dataclasses import dataclass

from ..core import logging
from .clipboard import get_clipboard
from .win32_api import VirtualKey, get_win32_api

logger = logging.get_logger(__name__)


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

    def route(self, text: str) -> ActionResult:
        """Perform a known action or insert text into the focused app."""
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
            target_window = win32.get_foreground_window()
            if not target_window:
                return ActionResult(True, False, "No focused application")
            if not clipboard.set_text(normalized):
                return ActionResult(True, False, "Could not copy dictation")

            if not win32.set_foreground_window(target_window):
                return ActionResult(True, False, "Could not restore focused application")
            win32._send_key_down(VirtualKey.VK_CONTROL.value)
            win32._send_key(VirtualKey.VK_V.value)
            win32._send_key_up(VirtualKey.VK_CONTROL.value)
            return ActionResult(True, True, "Dictation inserted")
        except Exception as error:
            logger.error("Failed to insert dictation: %s", error)
            return ActionResult(True, False, "Could not insert dictation")