"""Global low-level keyboard hook for true key press/release detection.

``RegisterHotKey`` only ever reports the *press*. Hold-to-talk therefore had to
guess at release time by polling ``GetAsyncKeyState`` every 30 ms, which ties
release latency to Qt's event loop: if the loop stalls the key-up is missed
entirely and the recording hangs until ``max_speech_duration``.

``WH_KEYBOARD_LL`` delivers both edges as they happen. The hook is installed
on its own thread with its own message pump so delivery never depends on Qt.

The hook is observe-only: it never swallows input. ``RegisterHotKey`` remains
responsible for capturing the combo, so there is no change to what reaches
the focused application.
"""

import ctypes
import threading
from ctypes import wintypes
from typing import Callable, Optional, Set

from ..core import logging

logger = logging.get_logger(__name__)

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012

DOWN_MESSAGES = frozenset({WM_KEYDOWN, WM_SYSKEYDOWN})
UP_MESSAGES = frozenset({WM_KEYUP, WM_SYSKEYUP})

# Windows silently uninstalls a low-level hook that blocks its timeout.
_HOOK_TIMEOUT_MS = 300

LRESULT = ctypes.c_ssize_t
HOOKPROC = ctypes.WINFUNCTYPE(
    LRESULT,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM,
)


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


KeyCallback = Callable[[int, bool], None]


class KeyHook:
    """Observe global key transitions for an explicit set of virtual keys.

    Usage::

        hook = KeyHook()
        hook.watch(vk_code)
        hook.on_key = lambda vk, down: ...
        hook.start()
        ...
        hook.stop()
    """

    def __init__(self) -> None:
        self.on_key: Optional[KeyCallback] = None
        self._watched: Set[int] = set()
        self._watch_lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._thread_id: Optional[int] = None
        self._hook = None
        self._proc = None
        self._ready = threading.Event()
        self._installed = False
        self._stopping = False

        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        self._user32.SetWindowsHookExW.restype = ctypes.c_void_p
        self._user32.SetWindowsHookExW.argtypes = [
            ctypes.c_int, HOOKPROC, ctypes.c_void_p, wintypes.DWORD,
        ]
        self._user32.CallNextHookEx.restype = LRESULT
        self._user32.CallNextHookEx.argtypes = [
            ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM,
        ]
        self._user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
        self._user32.GetMessageW.restype = ctypes.c_int
        self._user32.GetMessageW.argtypes = [
            ctypes.POINTER(MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT,
        ]
        self._user32.PostThreadMessageW.argtypes = [
            wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
        ]

        # A handle is 64-bit; the c_int default truncates it to a negative
        # value that SetWindowsHookExW rejects with ERROR_MOD_NOT_FOUND.
        self._kernel32.GetModuleHandleW.restype = ctypes.c_void_p
        self._kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        self._kernel32.GetCurrentThreadId.restype = wintypes.DWORD
        self._user32.UnhookWindowsHookEx.restype = wintypes.BOOL
        self._user32.PostThreadMessageW.restype = wintypes.BOOL

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def available(self) -> bool:
        """True while the hook is installed and receiving events."""
        return self._installed and self._thread is not None and self._thread.is_alive()

    @property
    def watched(self) -> Set[int]:
        with self._watch_lock:
            return set(self._watched)

    def watch(self, vk_code: int) -> None:
        with self._watch_lock:
            self._watched.add(int(vk_code))

    def unwatch(self, vk_code: int) -> None:
        with self._watch_lock:
            self._watched.discard(int(vk_code))

    def start(self) -> bool:
        """Install the hook on a dedicated thread. Returns success."""
        if self.available:
            return True

        self._stopping = False
        self._ready.clear()
        self._installed = False

        self._proc = HOOKPROC(self._hook_proc)
        self._thread = threading.Thread(
            target=self._run, name="aiop-keyhook", daemon=True
        )
        self._thread.start()

        if not self._ready.wait(timeout=3.0):
            logger.error("Keyboard hook thread did not start within 3s")
            return False

        if not self._installed:
            logger.warning("Keyboard hook installation failed")
            self._thread = None
            return False

        logger.info("Keyboard hook installed (watching %s)", sorted(self._watched))
        return True

    def stop(self) -> None:
        """Uninstall the hook and join the pump thread."""
        thread = self._thread
        self._stopping = True

        if thread is not None and thread.is_alive() and self._thread_id:
            self._user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
            thread.join(timeout=3.0)

        self._thread = None
        self._thread_id = None
        self._hook = None
        self._installed = False
        self._ready.clear()

    # ------------------------------------------------------------------
    # Hook thread
    # ------------------------------------------------------------------
    def _run(self) -> None:
        self._thread_id = self._kernel32.GetCurrentThreadId()
        hmod = self._kernel32.GetModuleHandleW(None)

        try:
            hook = self._user32.SetWindowsHookExW(
                WH_KEYBOARD_LL, self._proc, hmod, 0
            )
        except Exception as error:  # pragma: no cover - defensive
            logger.error("SetWindowsHookExW failed: %s", error)
            hook = None

        if not hook:
            error = ctypes.get_last_error()
            logger.error(
                "Keyboard hook not installed (GetLastError=%s%s)",
                error,
                ", ERROR_MOD_NOT_FOUND" if error == 126 else "",
            )
            self._installed = False
            self._ready.set()
            return

        self._hook = hook
        self._installed = True
        self._ready.set()

        msg = MSG()
        try:
            while True:
                result = self._user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if result == 0 or result == -1:  # WM_QUIT or error
                    break
        finally:
            self._user32.UnhookWindowsHookEx(hook)
            self._installed = False
            logger.info("Keyboard hook uninstalled")

    # ------------------------------------------------------------------
    # Hook procedure - must never block
    # ------------------------------------------------------------------
    def _hook_proc(self, n_code: int, w_param, l_param) -> int:
        try:
            if n_code >= 0:
                message = int(w_param)
                if message in DOWN_MESSAGES or message in UP_MESSAGES:
                    info = ctypes.cast(
                        l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)
                    ).contents
                    vk = int(info.vkCode)

                    with self._watch_lock:
                        watched = vk in self._watched

                    if watched and self.on_key is not None:
                        # Deliver outside the lock and swallow nothing.
                        try:
                            self.on_key(vk, message in DOWN_MESSAGES)
                        except Exception as error:
                            logger.error("Key callback failed: %s", error)
        except Exception as error:  # pragma: no cover - a raising hook proc
            logger.error("Keyboard hook error: %s", error)  # would be fatal

        return self._user32.CallNextHookEx(self._hook, n_code, w_param, l_param)


_hook: Optional[KeyHook] = None


def get_key_hook() -> KeyHook:
    """Return the process-wide key hook."""
    global _hook
    if _hook is None:
        _hook = KeyHook()
    return _hook
