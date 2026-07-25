"""
Win32 API wrapper for AIOP
"""

import ctypes
import ctypes.wintypes
from typing import Optional, Tuple, List, Dict, Any, Union
from dataclasses import dataclass
from enum import Enum
from ..core import logging, exceptions

logger = logging.get_logger(__name__)


class VirtualKey(Enum):
    """Virtual key codes"""
    VK_LBUTTON = 0x01
    VK_RBUTTON = 0x02
    VK_CANCEL = 0x03
    VK_MBUTTON = 0x04
    VK_XBUTTON1 = 0x05
    VK_XBUTTON2 = 0x06
    VK_BACK = 0x08
    VK_TAB = 0x09
    VK_CLEAR = 0x0C
    VK_RETURN = 0x0D
    VK_SHIFT = 0x10
    VK_CONTROL = 0x11
    VK_MENU = 0x12
    VK_PAUSE = 0x13
    VK_CAPITAL = 0x14
    VK_KANA = 0x15
    VK_HANGEUL = 0x15
    VK_HANGUL = 0x15
    VK_JUNJA = 0x17
    VK_FINAL = 0x18
    VK_HANJA = 0x19
    VK_KANJI = 0x19
    VK_ESCAPE = 0x1B
    VK_CONVERT = 0x1C
    VK_NONCONVERT = 0x1D
    VK_ACCEPT = 0x1E
    VK_MODECHANGE = 0x1F
    VK_SPACE = 0x20
    VK_PRIOR = 0x21
    VK_NEXT = 0x22
    VK_END = 0x23
    VK_HOME = 0x24
    VK_LEFT = 0x25
    VK_UP = 0x26
    VK_RIGHT = 0x27
    VK_DOWN = 0x28
    VK_SELECT = 0x29
    VK_PRINT = 0x2A
    VK_EXECUTE = 0x2B
    VK_SNAPSHOT = 0x2C
    VK_INSERT = 0x2D
    VK_DELETE = 0x2E
    VK_HELP = 0x2F
    VK_0 = 0x30
    VK_1 = 0x31
    VK_2 = 0x32
    VK_3 = 0x33
    VK_4 = 0x34
    VK_5 = 0x35
    VK_6 = 0x36
    VK_7 = 0x37
    VK_8 = 0x38
    VK_9 = 0x39
    VK_A = 0x41
    VK_B = 0x42
    VK_C = 0x43
    VK_D = 0x44
    VK_E = 0x45
    VK_F = 0x46
    VK_G = 0x47
    VK_H = 0x48
    VK_I = 0x49
    VK_J = 0x4A
    VK_K = 0x4B
    VK_L = 0x4C
    VK_M = 0x4D
    VK_N = 0x4E
    VK_O = 0x4F
    VK_P = 0x50
    VK_Q = 0x51
    VK_R = 0x52
    VK_S = 0x53
    VK_T = 0x54
    VK_U = 0x55
    VK_V = 0x56
    VK_W = 0x57
    VK_X = 0x58
    VK_Y = 0x59
    VK_Z = 0x5A
    VK_LWIN = 0x5B
    VK_RWIN = 0x5C
    VK_APPS = 0x5D
    VK_SLEEP = 0x5F
    VK_NUMPAD0 = 0x60
    VK_NUMPAD1 = 0x61
    VK_NUMPAD2 = 0x62
    VK_NUMPAD3 = 0x63
    VK_NUMPAD4 = 0x64
    VK_NUMPAD5 = 0x65
    VK_NUMPAD6 = 0x66
    VK_NUMPAD7 = 0x67
    VK_NUMPAD8 = 0x68
    VK_NUMPAD9 = 0x69
    VK_MULTIPLY = 0x6A
    VK_ADD = 0x6B
    VK_SEPARATOR = 0x6C
    VK_SUBTRACT = 0x6D
    VK_DECIMAL = 0x6E
    VK_DIVIDE = 0x6F
    VK_F1 = 0x70
    VK_F2 = 0x71
    VK_F3 = 0x72
    VK_F4 = 0x73
    VK_F5 = 0x74
    VK_F6 = 0x75
    VK_F7 = 0x76
    VK_F8 = 0x77
    VK_F9 = 0x78
    VK_F10 = 0x79
    VK_F11 = 0x7A
    VK_F12 = 0x7B
    VK_F13 = 0x7C
    VK_F14 = 0x7D
    VK_F15 = 0x7E
    VK_F16 = 0x7F
    VK_F17 = 0x80
    VK_F18 = 0x81
    VK_F19 = 0x82
    VK_F20 = 0x83
    VK_F21 = 0x84
    VK_F22 = 0x85
    VK_F23 = 0x86
    VK_F24 = 0x87
    VK_NUMLOCK = 0x90
    VK_SCROLL = 0x91
    VK_OEM_NEC_EQUAL = 0x92
    VK_OEM_FJ_JISHO = 0x92
    VK_OEM_FJ_MASSHOU = 0x93
    VK_OEM_FJ_TOUROKU = 0x94
    VK_OEM_FJ_LOYA = 0x95
    VK_OEM_FJ_ROYA = 0x96
    VK_LSHIFT = 0xA0
    VK_RSHIFT = 0xA1
    VK_LCONTROL = 0xA2
    VK_RCONTROL = 0xA3
    VK_LMENU = 0xA4
    VK_RMENU = 0xA5
    VK_BROWSER_BACK = 0xA6
    VK_BROWSER_FORWARD = 0xA7
    VK_BROWSER_REFRESH = 0xA8
    VK_BROWSER_STOP = 0xA9
    VK_BROWSER_SEARCH = 0xAA
    VK_BROWSER_FAVORITES = 0xAB
    VK_BROWSER_HOME = 0xAC
    VK_VOLUME_MUTE = 0xAD
    VK_VOLUME_DOWN = 0xAE
    VK_VOLUME_UP = 0xAF
    VK_MEDIA_NEXT_TRACK = 0xB0
    VK_MEDIA_PREV_TRACK = 0xB1
    VK_MEDIA_STOP = 0xB2
    VK_MEDIA_PLAY_PAUSE = 0xB3
    VK_LAUNCH_MAIL = 0xB4
    VK_LAUNCH_MEDIA_SELECT = 0xB5
    VK_LAUNCH_APP1 = 0xB6
    VK_LAUNCH_APP2 = 0xB7
    VK_OEM_1 = 0xBA
    VK_OEM_PLUS = 0xBB
    VK_OEM_COMMA = 0xBC
    VK_OEM_MINUS = 0xBD
    VK_OEM_PERIOD = 0xBE
    VK_OEM_2 = 0xBF
    VK_OEM_3 = 0xC0
    VK_OEM_4 = 0xDB
    VK_OEM_5 = 0xDC
    VK_OEM_6 = 0xDD
    VK_OEM_7 = 0xDE
    VK_OEM_8 = 0xDF
    VK_OEM_AX = 0xE1
    VK_OEM_102 = 0xE2
    VK_ICO_HELP = 0xE3
    VK_ICO_00 = 0xE4
    VK_PROCESSKEY = 0xE5
    VK_ICO_CLEAR = 0xE6
    VK_PACKET = 0xE7
    VK_OEM_RESET = 0xE9
    VK_OEM_JUMP = 0xEA
    VK_OEM_PA1 = 0xEB
    VK_OEM_PA2 = 0xEC
    VK_OEM_PA3 = 0xED
    VK_OEM_WSCTRL = 0xEE
    VK_OEM_CUSEL = 0xEF
    VK_OEM_ATTN = 0xF0
    VK_OEM_FINISH = 0xF1
    VK_OEM_COPY = 0xF2
    VK_OEM_AUTO = 0xF3
    VK_OEM_ENLW = 0xF4
    VK_OEM_BACKTAB = 0xF5
    VK_ATTN = 0xF6
    VK_CRSEL = 0xF7
    VK_EXSEL = 0xF8
    VK_EREOF = 0xF9
    VK_PLAY = 0xFA
    VK_ZOOM = 0xFB
    VK_NONAME = 0xFC
    VK_PA1 = 0xFD
    VK_OEM_CLEAR = 0xFE


class ModifierKey(Enum):
    """Modifier key flags"""
    MOD_ALT = 0x0001
    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004
    MOD_WIN = 0x0008
    MOD_NOREPEAT = 0x4000


@dataclass
class WindowInfo:
    """Window information"""
    hwnd: int
    title: str
    class_name: str
    rect: Tuple[int, int, int, int]  # (left, top, right, bottom)
    is_visible: bool
    is_enabled: bool
    is_foreground: bool


class Win32API:
    """Win32 API wrapper"""
    
    def __init__(self):
        self.user32 = ctypes.WinDLL('user32', use_last_error=True)
        self.kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        self.shell32 = ctypes.WinDLL('shell32', use_last_error=True)
        
        # Set up function prototypes
        self._setup_prototypes()
    
    def _setup_prototypes(self) -> None:
        """Set up function prototypes for ctypes"""
        # User32 functions
        self.user32.GetForegroundWindow.argtypes = []
        self.user32.GetForegroundWindow.restype = ctypes.wintypes.HWND
        
        self.user32.GetWindowTextW.argtypes = [
            ctypes.wintypes.HWND,
            ctypes.wintypes.LPWSTR,
            ctypes.c_int,
        ]
        self.user32.GetWindowTextW.restype = ctypes.c_int
        
        self.user32.GetWindowTextLengthW.argtypes = [ctypes.wintypes.HWND]
        self.user32.GetWindowTextLengthW.restype = ctypes.c_int
        
        self.user32.GetClassNameW.argtypes = [
            ctypes.wintypes.HWND,
            ctypes.wintypes.LPWSTR,
            ctypes.c_int,
        ]
        self.user32.GetClassNameW.restype = ctypes.c_int
        
        self.user32.GetWindowRect.argtypes = [
            ctypes.wintypes.HWND,
            ctypes.POINTER(ctypes.wintypes.RECT),
        ]
        self.user32.GetWindowRect.restype = ctypes.c_bool
        
        self.user32.IsWindowVisible.argtypes = [ctypes.wintypes.HWND]
        self.user32.IsWindowVisible.restype = ctypes.c_bool
        
        self.user32.IsWindowEnabled.argtypes = [ctypes.wintypes.HWND]
        self.user32.IsWindowEnabled.restype = ctypes.c_bool
        
        self.user32.SetForegroundWindow.argtypes = [ctypes.wintypes.HWND]
        self.user32.SetForegroundWindow.restype = ctypes.c_bool
        
        self.user32.FindWindowW.argtypes = [
            ctypes.wintypes.LPCWSTR,
            ctypes.wintypes.LPCWSTR,
        ]
        self.user32.FindWindowW.restype = ctypes.wintypes.HWND
        
        self.user32.EnumWindows.argtypes = [
            ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM),
            ctypes.wintypes.LPARAM,
        ]
        self.user32.EnumWindows.restype = ctypes.c_bool
        
        self.user32.GetWindowThreadProcessId.argtypes = [
            ctypes.wintypes.HWND,
            ctypes.POINTER(ctypes.wintypes.DWORD),
        ]
        self.user32.GetWindowThreadProcessId.restype = ctypes.wintypes.DWORD
        
        # Keyboard functions
        self.user32.keybd_event.argtypes = [
            ctypes.c_ubyte,
            ctypes.c_ubyte,
            ctypes.wintypes.DWORD,
            ctypes.wintypes.ULONG_PTR,
        ]
        self.user32.keybd_event.restype = None
        
        self.user32.SendInput.argtypes = [
            ctypes.c_uint,
            ctypes.POINTER(ctypes.c_ubyte),
            ctypes.c_int,
        ]
        self.user32.SendInput.restype = ctypes.c_uint
        
        # Shell32 functions
        self.shell32.ShellExecuteW.argtypes = [
            ctypes.wintypes.HWND,
            ctypes.wintypes.LPCWSTR,
            ctypes.wintypes.LPCWSTR,
            ctypes.wintypes.LPCWSTR,
            ctypes.wintypes.LPCWSTR,
            ctypes.c_int,
        ]
        self.shell32.ShellExecuteW.restype = ctypes.wintypes.HINSTANCE
    
    def get_foreground_window(self) -> int:
        """Get handle to foreground window"""
        return self.user32.GetForegroundWindow()
    
    def get_window_text(self, hwnd: int) -> str:
        """Get window text"""
        length = self.user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return ""
        
        buff = ctypes.create_unicode_buffer(length + 1)
        self.user32.GetWindowTextW(hwnd, buff, length + 1)
        return buff.value
    
    def get_class_name(self, hwnd: int) -> str:
        """Get window class name"""
        buff = ctypes.create_unicode_buffer(256)
        self.user32.GetClassNameW(hwnd, buff, 256)
        return buff.value
    
    def get_window_rect(self, hwnd: int) -> Tuple[int, int, int, int]:
        """Get window rectangle (left, top, right, bottom)"""
        rect = ctypes.wintypes.RECT()
        self.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return (rect.left, rect.top, rect.right, rect.bottom)
    
    def get_window_info(self, hwnd: int) -> WindowInfo:
        """Get comprehensive window information"""
        title = self.get_window_text(hwnd)
        class_name = self.get_class_name(hwnd)
        rect = self.get_window_rect(hwnd)
        is_visible = self.user32.IsWindowVisible(hwnd)
        is_enabled = self.user32.IsWindowEnabled(hwnd)
        is_foreground = hwnd == self.get_foreground_window()
        
        return WindowInfo(
            hwnd=hwnd,
            title=title,
            class_name=class_name,
            rect=rect,
            is_visible=is_visible,
            is_enabled=is_enabled,
            is_foreground=is_foreground,
        )
    
    def set_foreground_window(self, hwnd: int) -> bool:
        """Set foreground window"""
        return self.user32.SetForegroundWindow(hwnd)
    
    def find_window(self, class_name: str = None, window_name: str = None) -> Optional[int]:
        """Find window by class name or window name"""
        hwnd = self.user32.FindWindowW(class_name, window_name)
        return hwnd if hwnd else None
    
    def enum_windows(self) -> List[WindowInfo]:
        """Enumerate all windows"""
        windows = []
        
        def callback(hwnd, lparam):
            if self.user32.IsWindowVisible(hwnd):
                try:
                    info = self.get_window_info(hwnd)
                    if info.title:  # Only include windows with titles
                        windows.append(info)
                except Exception as e:
                    logger.debug(f"Error getting window info: {e}")
            return True
        
        self.user32.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)(callback), 0)
        return windows
    
    def get_active_window(self) -> Optional[WindowInfo]:
        """Get information about the active window"""
        hwnd = self.get_foreground_window()
        if hwnd:
            return self.get_window_info(hwnd)
        return None
    
    def send_keys(self, keys: str) -> None:
        """Send keystrokes to the active window"""
        # This is a simplified version
        # In production, use SendInput for better reliability
        for key in keys:
            self._send_key(key)
    
    def _send_key(self, key: str) -> None:
        """Send a single key"""
        # Map character to virtual key
        vk = self._char_to_vk(key)
        if vk is None:
            return
        
        # Send key down and up
        self.user32.keybd_event(vk, 0, 0, 0)
        self.user32.keybd_event(vk, 0, 0x0002, 0)
    
    def _char_to_vk(self, char: str) -> Optional[int]:
        """Convert character to virtual key code"""
        if len(char) != 1:
            return None
        
        # Check for special keys
        key_map = {
            ' ': VirtualKey.VK_SPACE.value,
            '\t': VirtualKey.VK_TAB.value,
            '\n': VirtualKey.VK_RETURN.value,
            '\r': VirtualKey.VK_RETURN.value,
            '\b': VirtualKey.VK_BACK.value,
            '\x1b': VirtualKey.VK_ESCAPE.value,
        }
        
        if char in key_map:
            return key_map[char]
        
        # Check if it's a letter
        if 'A' <= char <= 'Z':
            return getattr(VirtualKey, f'VK_{char}').value
        elif 'a' <= char <= 'z':
            return getattr(VirtualKey, f'VK_{char.upper()}').value
        elif '0' <= char <= '9':
            return getattr(VirtualKey, f'VK_{char}').value
        
        return None
    
    def send_text(self, text: str) -> None:
        """Send text to the active window"""
        # Use clipboard method for reliability
        import pyperclip
        try:
            # Copy text to clipboard
            pyperclip.copy(text)
            
            # Send Ctrl+V
            self._send_key_down(VirtualKey.VK_CONTROL.value)
            self._send_key('v')
            self._send_key_up(VirtualKey.VK_CONTROL.value)
        except Exception as e:
            logger.error(f"Failed to send text: {e}")
            # Fallback to SendInput
            for char in text:
                self._send_key(char)
    
    def _send_key_down(self, vk: int) -> None:
        """Send key down event"""
        self.user32.keybd_event(vk, 0, 0, 0)
    
    def _send_key_up(self, vk: int) -> None:
        """Send key up event"""
        self.user32.keybd_event(vk, 0, 0x0002, 0)
    
    def run_command(self, command: str, show: bool = True) -> None:
        """Run a shell command"""
        result = self.shell32.ShellExecuteW(
            None,
            "open" if show else None,
            command,
            None,
            None,
            1 if show else 0,
        )
        
        if result <= 32:
            raise exceptions.WindowsError(f"Failed to run command: {command}")
    
    def open_file(self, file_path: str) -> None:
        """Open a file with its default application"""
        self.run_command(file_path)
    
    def open_url(self, url: str) -> None:
        """Open a URL in the default browser"""
        self.run_command(url)
    
    def get_screen_resolution(self) -> Tuple[int, int]:
        """Get screen resolution"""
        return (self.user32.GetSystemMetrics(0), self.user32.GetSystemMetrics(1))
    
    def get_cursor_position(self) -> Tuple[int, int]:
        """Get cursor position"""
        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        
        pt = POINT()
        self.user32.GetCursorPos(ctypes.byref(pt))
        return (pt.x, pt.y)
    
    def set_cursor_position(self, x: int, y: int) -> None:
        """Set cursor position"""
        self.user32.SetCursorPos(x, y)
    
    def get_process_id(self, hwnd: int) -> int:
        """Get process ID for a window"""
        pid = ctypes.wintypes.DWORD()
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value
    
    def get_process_name(self, pid: int) -> str:
        """Get process name by PID"""
        try:
            process = psutil.Process(pid)
            return process.name()
        except Exception:
            return ""


# Global Win32 API instance
_win32_api: Optional[Win32API] = None


def get_win32_api() -> Win32API:
    """Get the global Win32 API instance"""
    global _win32_api
    if _win32_api is None:
        _win32_api = Win32API()
    return _win32_api


def get_foreground_window() -> int:
    """Get the foreground window handle"""
    return get_win32_api().get_foreground_window()


def get_active_window() -> Optional[WindowInfo]:
    """Get information about the active window"""
    return get_win32_api().get_active_window()


def send_keys(keys: str) -> None:
    """Send keystrokes"""
    get_win32_api().send_keys(keys)


def send_text(text: str) -> None:
    """Send text"""
    get_win32_api().send_text(text)
