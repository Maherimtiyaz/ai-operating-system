"""
Global hotkey management for AIOP
"""

import ctypes
import ctypes.wintypes
from typing import Callable, Dict, Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum
from ..core import logging, exceptions
from .win32_api import VirtualKey, ModifierKey, get_win32_api

logger = logging.get_logger(__name__)


# Hotkey callback type
HotkeyCallback = Callable[[], None]


@dataclass
class Hotkey:
    """Hotkey information"""
    id: int
    modifiers: int
    key: int
    callback: HotkeyCallback
    enabled: bool = True


class HotkeyManager:
    """Global hotkey manager"""
    
    def __init__(self):
        # Check if running on Windows
        import sys
        if sys.platform != 'win32':
            logger.warning("Hotkey features are only available on Windows")
            self.user32 = None
            self.hotkeys: Dict[int, Hotkey] = {}
            self.next_id = 1
            self._window_class = "AIOPHotkeyWindow"
            self._window_proc = None
            self._hwnd = None
            return
        
        self.user32 = ctypes.WinDLL('user32', use_last_error=True)
        self.hotkeys: Dict[int, Hotkey] = {}
        self.next_id = 1
        self._window_class = "AIOPHotkeyWindow"
        self._window_proc = None
        self._hwnd = None
        self._setup_window()
    
    def _setup_window(self) -> None:
        """Set up a message-only window for hotkey handling"""
        try:
            # Create a message-only window
            wc = ctypes.wintypes.WNDCLASSW()
            wc.lpfnWndProc = self._window_proc_type(self._window_proc_impl)
            wc.hInstance = self.user32.GetModuleHandleW(None)
            wc.lpszClassName = self._window_class
            
            if not self.user32.RegisterClassW(ctypes.byref(wc)):
                logger.warning("Failed to register hotkey window class")
                return
            
            self._hwnd = self.user32.CreateWindowExW(
                0,
                self._window_class,
                "AIOP Hotkey Window",
                0,
                0, 0, 0, 0,
                0, 0,
                None,
                None,
                self.user32.GetModuleHandleW(None),
                None,
            )
            
            if not self._hwnd:
                logger.warning("Failed to create hotkey window")
                
        except Exception as e:
            logger.error(f"Failed to setup hotkey window: {e}")
    
    def _window_proc_impl(self, hwnd, msg, wparam, lparam):
        """Window procedure implementation"""
        if msg == 0x0312:  # WM_HOTKEY
            hotkey_id = wparam
            if hotkey_id in self.hotkeys:
                hotkey = self.hotkeys[hotkey_id]
                if hotkey.enabled:
                    try:
                        hotkey.callback()
                    except Exception as e:
                        logger.error(f"Error in hotkey callback: {e}")
            return 0
        
        return self.user32.DefWindowProcW(hwnd, msg, wparam, lparam)
    
    @staticmethod
    def _window_proc_type(func):
        """Window procedure type decorator"""
        def wrapper(hwnd, msg, wparam, lparam):
            return func(hwnd, msg, wparam, lparam)
        
        wrapper.argtypes = [
            ctypes.wintypes.HWND,
            ctypes.c_uint,
            ctypes.wintypes.WPARAM,
            ctypes.wintypes.LPARAM,
        ]
        wrapper.restype = ctypes.wintypes.LRESULT
        return wrapper
    
    def register_hotkey(
        self,
        modifiers: List[str],
        key: str,
        callback: HotkeyCallback,
    ) -> int:
        """
        Register a global hotkey
        
        Args:
            modifiers: List of modifier keys ('Ctrl', 'Shift', 'Alt', 'Win')
            key: Key name ('A', 'B', 'F1', 'Space', etc.)
            callback: Function to call when hotkey is pressed
        
        Returns:
            Hotkey ID
        """
        # Parse modifiers
        mod_flags = 0
        for mod in modifiers:
            mod_upper = mod.upper()
            if mod_upper == 'CTRL' or mod_upper == 'CONTROL':
                mod_flags |= ModifierKey.MOD_CONTROL.value
            elif mod_upper == 'SHIFT':
                mod_flags |= ModifierKey.MOD_SHIFT.value
            elif mod_upper == 'ALT':
                mod_flags |= ModifierKey.MOD_ALT.value
            elif mod_upper == 'WIN' or mod_upper == 'WINDOWS':
                mod_flags |= ModifierKey.MOD_WIN.value
        
        # Parse key
        key_code = self._parse_key(key)
        if key_code is None:
            raise exceptions.WindowsError(f"Unknown key: {key}")
        
        # Generate hotkey ID
        hotkey_id = self.next_id
        self.next_id += 1
        
        # Register hotkey
        if not self.user32.RegisterHotKey(
            self._hwnd if self._hwnd else None,
            hotkey_id,
            mod_flags,
            key_code,
        ):
            error = ctypes.get_last_error()
            raise exceptions.WindowsError(f"Failed to register hotkey: error {error}")
        
        # Store hotkey
        self.hotkeys[hotkey_id] = Hotkey(
            id=hotkey_id,
            modifiers=mod_flags,
            key=key_code,
            callback=callback,
            enabled=True,
        )
        
        logger.info(f"Registered hotkey: {modifiers}+{key} (ID: {hotkey_id})")
        return hotkey_id
    
    def _parse_key(self, key: str) -> Optional[int]:
        """Parse key name to virtual key code"""
        key_upper = key.upper()
        
        # Check for special keys
        special_keys = {
            'SPACE': VirtualKey.VK_SPACE.value,
            'ENTER': VirtualKey.VK_RETURN.value,
            'RETURN': VirtualKey.VK_RETURN.value,
            'TAB': VirtualKey.VK_TAB.value,
            'ESCAPE': VirtualKey.VK_ESCAPE.value,
            'ESC': VirtualKey.VK_ESCAPE.value,
            'BACKSPACE': VirtualKey.VK_BACK.value,
            'DELETE': VirtualKey.VK_DELETE.value,
            'INSERT': VirtualKey.VK_INSERT.value,
            'HOME': VirtualKey.VK_HOME.value,
            'END': VirtualKey.VK_END.value,
            'PAGEUP': VirtualKey.VK_PRIOR.value,
            'PAGEDOWN': VirtualKey.VK_NEXT.value,
            'UP': VirtualKey.VK_UP.value,
            'DOWN': VirtualKey.VK_DOWN.value,
            'LEFT': VirtualKey.VK_LEFT.value,
            'RIGHT': VirtualKey.VK_RIGHT.value,
            'F1': VirtualKey.VK_F1.value,
            'F2': VirtualKey.VK_F2.value,
            'F3': VirtualKey.VK_F3.value,
            'F4': VirtualKey.VK_F4.value,
            'F5': VirtualKey.VK_F5.value,
            'F6': VirtualKey.VK_F6.value,
            'F7': VirtualKey.VK_F7.value,
            'F8': VirtualKey.VK_F8.value,
            'F9': VirtualKey.VK_F9.value,
            'F10': VirtualKey.VK_F10.value,
            'F11': VirtualKey.VK_F11.value,
            'F12': VirtualKey.VK_F12.value,
        }
        
        if key_upper in special_keys:
            return special_keys[key_upper]
        
        # Check for letters
        if len(key) == 1 and 'A' <= key_upper <= 'Z':
            return getattr(VirtualKey, f'VK_{key_upper}').value
        
        # Check for numbers
        if len(key) == 1 and '0' <= key <= '9':
            return getattr(VirtualKey, f'VK_{key}').value
        
        return None
    
    def unregister_hotkey(self, hotkey_id: int) -> bool:
        """Unregister a hotkey"""
        if hotkey_id not in self.hotkeys:
            return False
        
        try:
            result = self.user32.UnregisterHotKey(
                self._hwnd if self._hwnd else None,
                hotkey_id,
            )
            if result:
                del self.hotkeys[hotkey_id]
                logger.info(f"Unregistered hotkey: {hotkey_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to unregister hotkey {hotkey_id}: {e}")
            return False
    
    def unregister_all(self) -> None:
        """Unregister all hotkeys"""
        for hotkey_id in list(self.hotkeys.keys()):
            self.unregister_hotkey(hotkey_id)
    
    def enable_hotkey(self, hotkey_id: int) -> bool:
        """Enable a hotkey"""
        if hotkey_id in self.hotkeys:
            self.hotkeys[hotkey_id].enabled = True
            return True
        return False
    
    def disable_hotkey(self, hotkey_id: int) -> bool:
        """Disable a hotkey"""
        if hotkey_id in self.hotkeys:
            self.hotkeys[hotkey_id].enabled = False
            return True
        return False
    
    def list_hotkeys(self) -> List[Hotkey]:
        """List all registered hotkeys"""
        return list(self.hotkeys.values())
    
    def parse_hotkey_string(self, hotkey_str: str) -> Tuple[int, int]:
        """
        Parse hotkey string to modifiers and key code
        
        Args:
            hotkey_str: Hotkey string (e.g., "Ctrl+Shift+Space")
        
        Returns:
            Tuple of (modifiers, virtual key code)
        """
        parts = hotkey_str.split('+')
        modifiers = []
        key = None
        
        for part in parts:
            part_upper = part.upper().strip()
            if part_upper in ['CTRL', 'CONTROL', 'SHIFT', 'ALT', 'WIN', 'WINDOWS']:
                modifiers.append(part_upper)
            else:
                key = part
        
        if not key:
            raise exceptions.WindowsError(f"Invalid hotkey string: {hotkey_str}")
        
        mod_flags = 0
        for mod in modifiers:
            if mod in ['CTRL', 'CONTROL']:
                mod_flags |= ModifierKey.MOD_CONTROL.value
            elif mod == 'SHIFT':
                mod_flags |= ModifierKey.MOD_SHIFT.value
            elif mod == 'ALT':
                mod_flags |= ModifierKey.MOD_ALT.value
            elif mod in ['WIN', 'WINDOWS']:
                mod_flags |= ModifierKey.MOD_WIN.value
        
        key_code = self._parse_key(key)
        if key_code is None:
            raise exceptions.WindowsError(f"Unknown key: {key}")
        
        return (mod_flags, key_code)
    
    def register_from_string(self, hotkey_str: str, callback: HotkeyCallback) -> int:
        """
        Register a hotkey from string
        
        Args:
            hotkey_str: Hotkey string (e.g., "Ctrl+Shift+Space")
            callback: Function to call when hotkey is pressed
        
        Returns:
            Hotkey ID
        """
        parts = hotkey_str.split('+')
        modifiers = []
        key = None
        
        for part in parts:
            part_upper = part.upper().strip()
            if part_upper in ['CTRL', 'CONTROL', 'SHIFT', 'ALT', 'WIN', 'WINDOWS']:
                modifiers.append(part_upper)
            else:
                key = part
        
        if not key:
            raise exceptions.WindowsError(f"Invalid hotkey string: {hotkey_str}")
        
        return self.register_hotkey(modifiers, key, callback)
    
    def __del__(self):
        """Cleanup"""
        self.unregister_all()


# Global hotkey manager instance
_hotkey_manager: Optional[HotkeyManager] = None


def get_hotkey_manager() -> HotkeyManager:
    """Get the global hotkey manager instance"""
    global _hotkey_manager
    if _hotkey_manager is None:
        _hotkey_manager = HotkeyManager()
    return _hotkey_manager


def register_hotkey(
    hotkey_str: str,
    callback: HotkeyCallback,
) -> int:
    """
    Register a global hotkey from string
    
    Args:
        hotkey_str: Hotkey string (e.g., "Ctrl+Shift+Space")
        callback: Function to call when hotkey is pressed
    
    Returns:
        Hotkey ID
    """
    return get_hotkey_manager().register_from_string(hotkey_str, callback)


def unregister_hotkey(hotkey_id: int) -> bool:
    """Unregister a hotkey"""
    return get_hotkey_manager().unregister_hotkey(hotkey_id)


def unregister_all_hotkeys() -> None:
    """Unregister all hotkeys"""
    get_hotkey_manager().unregister_all()
