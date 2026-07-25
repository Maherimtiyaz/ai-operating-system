"""
Clipboard management for AIOP
"""

import ctypes
import ctypes.wintypes
from typing import Optional, Union, List
from ..core import logging, exceptions

logger = logging.get_logger(__name__)


class ClipboardFormat:
    """Clipboard format constants"""
    CF_TEXT = 1
    CF_UNICODETEXT = 13
    CF_HDROP = 15
    CF_BITMAP = 2
    CF_DIB = 8
    CF_PALETTE = 9
    CF_DIBV5 = 17


class Clipboard:
    """Windows clipboard manager"""
    
    def __init__(self):
        self.user32 = ctypes.WinDLL('user32', use_last_error=True)
        self.kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        
        # Set up function prototypes
        self.user32.OpenClipboard.argtypes = [ctypes.wintypes.HWND]
        self.user32.OpenClipboard.restype = ctypes.c_bool
        
        self.user32.CloseClipboard.argtypes = []
        self.user32.CloseClipboard.restype = ctypes.c_bool
        
        self.user32.EmptyClipboard.argtypes = []
        self.user32.EmptyClipboard.restype = ctypes.c_bool
        
        self.user32.IsClipboardFormatAvailable.argtypes = [ctypes.c_uint]
        self.user32.IsClipboardFormatAvailable.restype = ctypes.c_bool
        
        self.user32.GetClipboardData.argtypes = [ctypes.c_uint]
        self.user32.GetClipboardData.restype = ctypes.wintypes.HANDLE
        
        self.user32.SetClipboardData.argtypes = [
            ctypes.c_uint,
            ctypes.wintypes.HANDLE,
        ]
        self.user32.SetClipboardData.restype = ctypes.wintypes.HANDLE
        
        self.kernel32.GlobalLock.argtypes = [ctypes.wintypes.HGLOBAL]
        self.kernel32.GlobalLock.restype = ctypes.wintypes.LPVOID
        
        self.kernel32.GlobalUnlock.argtypes = [ctypes.wintypes.HGLOBAL]
        self.kernel32.GlobalUnlock.restype = ctypes.c_bool
        
        self.kernel32.GlobalAlloc.argtypes = [
            ctypes.c_uint,
            ctypes.c_size_t,
        ]
        self.kernel32.GlobalAlloc.restype = ctypes.wintypes.HGLOBAL
        
        self.kernel32.GlobalFree.argtypes = [ctypes.wintypes.HGLOBAL]
        self.kernel32.GlobalFree.restype = ctypes.wintypes.HGLOBAL
    
    def get_text(self) -> Optional[str]:
        """Get clipboard text (Unicode)"""
        try:
            self.user32.OpenClipboard(None)
            try:
                if not self.user32.IsClipboardFormatAvailable(ClipboardFormat.CF_UNICODETEXT):
                    return None
                
                handle = self.user32.GetClipboardData(ClipboardFormat.CF_UNICODETEXT)
                if not handle:
                    return None
                
                # Lock the memory
                text_ptr = self.kernel32.GlobalLock(handle)
                if not text_ptr:
                    return None
                
                # Convert to Python string
                text = ctypes.wstring_at(text_ptr)
                return text
                
            finally:
                self.user32.CloseClipboard()
                
        except Exception as e:
            logger.error(f"Failed to get clipboard text: {e}")
            return None
    
    def set_text(self, text: str) -> bool:
        """Set clipboard text (Unicode)"""
        try:
            # Allocate global memory
            text_unicode = text.encode('utf-16le')
            size = len(text_unicode) + 2  # +2 for null terminator
            
            handle = self.kernel32.GlobalAlloc(0x0040, size)  # GMEM_MOVEABLE
            if not handle:
                return False
            
            # Lock and copy
            ptr = self.kernel32.GlobalLock(handle)
            if not ptr:
                self.kernel32.GlobalFree(handle)
                return False
            
            ctypes.memmove(ptr, text_unicode, size)
            self.kernel32.GlobalUnlock(handle)
            
            # Open clipboard and set data
            self.user32.OpenClipboard(None)
            try:
                self.user32.EmptyClipboard()
                result = self.user32.SetClipboardData(ClipboardFormat.CF_UNICODETEXT, handle)
                return result is not None
            finally:
                self.user32.CloseClipboard()
                
        except Exception as e:
            logger.error(f"Failed to set clipboard text: {e}")
            return False
    
    def get_text_list(self) -> List[str]:
        """Get clipboard text as list of lines"""
        text = self.get_text()
        if text:
            return text.split('\n')
        return []
    
    def has_text(self) -> bool:
        """Check if clipboard contains text"""
        try:
            self.user32.OpenClipboard(None)
            try:
                return self.user32.IsClipboardFormatAvailable(ClipboardFormat.CF_UNICODETEXT)
            finally:
                self.user32.CloseClipboard()
        except Exception:
            return False
    
    def has_files(self) -> bool:
        """Check if clipboard contains files"""
        try:
            self.user32.OpenClipboard(None)
            try:
                return self.user32.IsClipboardFormatAvailable(ClipboardFormat.CF_HDROP)
            finally:
                self.user32.CloseClipboard()
        except Exception:
            return False
    
    def get_files(self) -> List[str]:
        """Get files from clipboard (if available)"""
        try:
            self.user32.OpenClipboard(None)
            try:
                if not self.user32.IsClipboardFormatAvailable(ClipboardFormat.CF_HDROP):
                    return []
                
                handle = self.user32.GetClipboardData(ClipboardFormat.CF_HDROP)
                if not handle:
                    return []
                
                # Get the HDROP handle
                hdrop = ctypes.cast(handle, ctypes.POINTER(ctypes.c_void_p)).contents
                
                # Get the number of files
                num_files = self._get_hdrop_file_count(hdrop)
                files = []
                
                for i in range(num_files):
                    file_path = self._get_hdrop_file_path(hdrop, i)
                    if file_path:
                        files.append(file_path)
                
                return files
                
            finally:
                self.user32.CloseClipboard()
                
        except Exception as e:
            logger.error(f"Failed to get files from clipboard: {e}")
            return []
    
    def _get_hdrop_file_count(self, hdrop: ctypes.c_void_p) -> int:
        """Get the number of files in HDROP"""
        try:
            # Use DragQueryFile to get file count
            shell32 = ctypes.WinDLL('shell32', use_last_error=True)
            shell32.DragQueryFileW.argtypes = [
                ctypes.wintypes.HDROP,
                ctypes.c_uint,
                ctypes.wintypes.LPWSTR,
                ctypes.c_uint,
            ]
            shell32.DragQueryFileW.restype = ctypes.c_uint
            
            return shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
        except Exception:
            return 0
    
    def _get_hdrop_file_path(self, hdrop: ctypes.c_void_p, index: int) -> Optional[str]:
        """Get a file path from HDROP by index"""
        try:
            shell32 = ctypes.WinDLL('shell32', use_last_error=True)
            shell32.DragQueryFileW.argtypes = [
                ctypes.wintypes.HDROP,
                ctypes.c_uint,
                ctypes.wintypes.LPWSTR,
                ctypes.c_uint,
            ]
            shell32.DragQueryFileW.restype = ctypes.c_uint
            
            # First get the required buffer size
            size = shell32.DragQueryFileW(hdrop, index, None, 0)
            if size == 0:
                return None
            
            # Allocate buffer and get the path
            buffer = ctypes.create_unicode_buffer(size + 1)
            shell32.DragQueryFileW(hdrop, index, buffer, size + 1)
            return buffer.value
            
        except Exception:
            return None
    
    def clear(self) -> bool:
        """Clear the clipboard"""
        try:
            self.user32.OpenClipboard(None)
            try:
                return self.user32.EmptyClipboard()
            finally:
                self.user32.CloseClipboard()
        except Exception as e:
            logger.error(f"Failed to clear clipboard: {e}")
            return False
    
    def copy(self, text: str) -> bool:
        """Copy text to clipboard (alias for set_text)"""
        return self.set_text(text)
    
    def paste(self) -> Optional[str]:
        """Paste text from clipboard (alias for get_text)"""
        return self.get_text()


# Global clipboard instance
_clipboard: Optional[Clipboard] = None


def get_clipboard() -> Clipboard:
    """Get the global clipboard instance"""
    global _clipboard
    if _clipboard is None:
        _clipboard = Clipboard()
    return _clipboard


def get_clipboard_text() -> Optional[str]:
    """Get clipboard text"""
    return get_clipboard().get_text()


def set_clipboard_text(text: str) -> bool:
    """Set clipboard text"""
    return get_clipboard().set_text(text)


def copy_to_clipboard(text: str) -> bool:
    """Copy text to clipboard"""
    return get_clipboard().copy(text)


def paste_from_clipboard() -> Optional[str]:
    """Paste text from clipboard"""
    return get_clipboard().paste()


def clipboard_has_text() -> bool:
    """Check if clipboard contains text"""
    return get_clipboard().has_text()


def clipboard_has_files() -> bool:
    """Check if clipboard contains files"""
    return get_clipboard().has_files()


def get_clipboard_files() -> List[str]:
    """Get files from clipboard"""
    return get_clipboard().get_files()
