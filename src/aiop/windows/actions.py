"""Controlled operating-system actions driven by recognized intent."""

import os
import re
import time
from dataclasses import dataclass
from typing import Optional

from ..core import logging
from .clipboard import get_clipboard
from .win32_api import get_win32_api

logger = logging.get_logger(__name__)

# Windows refuses SetForegroundWindow focus changes that happen in the same
# tick as the user gesture. A short settle delay lets the target app take
# focus before we synthesize input.
PASTE_SETTLE_SECONDS = 0.12

# SetForegroundWindow can report success while another window keeps focus
# (foreground-lock races), which silently pasted dictation into the wrong
# place. Verify, then retry before giving up.
FOCUS_ATTEMPTS = 3
FOCUS_RETRY_SECONDS = 0.05


@dataclass
class ActionResult:
    """Result of a controlled action."""

    handled: bool
    success: bool
    message: str


def _window_label(win32, hwnd: Optional[int]) -> str:
    """Human-readable identity of a window, for the log."""
    if not hwnd:
        return "<none>"
    try:
        pid = win32.get_process_id(hwnd)
        name = win32.get_process_name(pid) or "?"
        return f"hwnd={hwnd} process={name} title={win32.get_window_text(hwnd)!r}"
    except Exception:
        return f"hwnd={hwnd}"


def resolve_target_window(win32, target_window: Optional[int]) -> Optional[int]:
    """Return the window dictation should insert into.

    The overlay and workspace windows belong to this process. If one of them
    was foreground when the hotkey fired (the user had just clicked the
    microphone), pasting into it would claim success while nothing reached an
    application, so fall back to the topmost window that is not ours.
    """
    if not target_window:
        return target_window
    try:
        if win32.get_process_id(target_window) != os.getpid():
            return target_window
    except Exception:
        return target_window

    logger.info(
        "Captured one of our own windows (%s); using the topmost other window",
        _window_label(win32, target_window),
    )
    for info in win32.enum_windows():
        try:
            if win32.get_process_id(info.hwnd) != os.getpid():
                return info.hwnd
        except Exception:
            continue
    return target_window


def focus_window(win32, target_window: int) -> bool:
    """Focus ``target_window`` and verify it actually took focus.

    SetForegroundWindow is unreliable under the foreground lock: it can report
    success while focus never moves. We verify against the real foreground,
    and fall back to force_foreground (attach-thread-input + ALT nudge) before
    giving up. The common dictation case - the target is already foreground -
    short-circuits so we never disturb it.
    """
    if win32.get_foreground_window() == target_window:
        return True
    for attempt in range(FOCUS_ATTEMPTS):
        if win32.set_foreground_window(target_window):
            time.sleep(PASTE_SETTLE_SECONDS)
            if win32.get_foreground_window() == target_window:
                return True
            logger.debug(
                "Focus attempt %d did not stick (foreground is %s)",
                attempt + 1,
                _window_label(win32, win32.get_foreground_window()),
            )
        force = getattr(win32, "force_foreground", None)
        if force is not None:
            try:
                force(target_window)
            except Exception:
                logger.debug("force_foreground failed", exc_info=True)
            time.sleep(PASTE_SETTLE_SECONDS)
            if win32.get_foreground_window() == target_window:
                return True
        time.sleep(FOCUS_RETRY_SECONDS)
    return False


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

        return self.insert_text(normalized, target_window)

    def insert_text(self, text: str, target_window: int = None) -> ActionResult:
        """Paste ``text`` into ``target_window``, typing it as a fallback.

        Every step logs what it saw, because a "success" that landed in the
        wrong window is indistinguishable from a real insertion otherwise.
        """
        try:
            win32 = get_win32_api()
            if target_window is None:
                target_window = win32.get_foreground_window()
            target_window = resolve_target_window(win32, target_window)
            if not target_window:
                return ActionResult(True, False, "No focused application")

            logger.info(
                "Inserting %r into %s (foreground is %s)",
                text,
                _window_label(win32, target_window),
                _window_label(win32, win32.get_foreground_window()),
            )

            clipboard_ok = bool(get_clipboard().set_text(text))

            if not focus_window(win32, target_window):
                logger.warning(
                    "Could not focus %s; foreground is %s",
                    _window_label(win32, target_window),
                    _window_label(win32, win32.get_foreground_window()),
                )
                return ActionResult(True, False, "Could not restore focused application")

            if clipboard_ok:
                try:
                    win32.send_paste()
                    logger.info("Paste sent to %s", _window_label(win32, target_window))
                    return ActionResult(True, True, "Dictation inserted")
                except Exception as error:
                    logger.warning("Paste failed (%s); typing instead", error)

            try:
                win32.type_text(text + " ")
                logger.info("Typed into %s", _window_label(win32, target_window))
                return ActionResult(True, True, "Dictation typed")
            except Exception as error:
                logger.error("Could not insert dictation: %s", error)
                return ActionResult(True, False, "Could not insert dictation")
        except Exception as error:
            logger.error("Failed to insert dictation: %s", error)
            return ActionResult(True, False, "Could not insert dictation")


def paste_into_foreground(text: str, settle_seconds: float = PASTE_SETTLE_SECONDS) -> None:
    """Insert text into the currently focused window via clipboard + Ctrl+V.

    Raises when there is no focused window or the focus cannot be restored.
    """
    win32 = get_win32_api()
    target_window = win32.get_foreground_window()
    if not target_window:
        raise RuntimeError("No focused application to paste into")
    clipboard_ok = bool(get_clipboard().set_text(text))
    if not focus_window(win32, target_window):
        raise RuntimeError("Could not restore focus to paste into")
    if clipboard_ok:
        try:
            win32.send_paste()
            return
        except Exception as error:
            logger.warning("Paste failed (%s); typing instead", error)
    try:
        win32.type_text(text + " ")
    except Exception as error:
        raise RuntimeError("Could not insert dictation") from error
