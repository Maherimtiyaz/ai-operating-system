"""
Tray application for AIOP
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from typing import Optional
from ..core import logging
from .main_window import MainWindow, get_main_window
from .overlay import get_overlay
from ..speech import get_transcriber
from ..windows import register_hotkey, get_hotkey_manager

logger = logging.get_logger(__name__)


class TrayApp:
    """Tray application wrapper"""
    
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("AI Operating Platform")
        self.app.setApplicationVersion("0.1.0")
        self.app.setOrganizationName("AIOP")
        
        # Set application icon
        self.app.setWindowIcon(QIcon(":/assets/icon.png"))
        
        # Components
        self.window = get_main_window()
        self.overlay = get_overlay()
        self.transcriber = get_transcriber()
        
        # Setup hotkeys
        self._setup_hotkeys()
        
        # Connect signals
        self._connect_signals()
    
    def _setup_hotkeys(self) -> None:
        """Set up global hotkeys"""
        try:
            # Register dictation hotkey
            hotkey_manager = get_hotkey_manager()
            hotkey_id = hotkey_manager.register_from_string(
                "Ctrl+Shift+Space",
                self._on_dictation_hotkey,
            )
            logger.info(f"Registered dictation hotkey (ID: {hotkey_id})")
            
            # Register overlay hotkey
            hotkey_id = hotkey_manager.register_from_string(
                "Ctrl+Shift+O",
                self._on_overlay_hotkey,
            )
            logger.info(f"Registered overlay hotkey (ID: {hotkey_id})")
            
        except Exception as e:
            logger.error(f"Failed to register hotkeys: {e}")
    
    def _connect_signals(self) -> None:
        """Connect application signals"""
        # Connect aboutToQuit signal
        self.app.aboutToQuit.connect(self._on_quit)
    
    def _on_dictation_hotkey(self) -> None:
        """Handle dictation hotkey"""
        if self.transcriber.is_running():
            self.transcriber.stop()
            self.overlay.set_listening(False)
            self.overlay.hide()
        else:
            self.transcriber.start()
            self.overlay.set_listening(True)
            self.overlay.show()
    
    def _on_overlay_hotkey(self) -> None:
        """Handle overlay hotkey"""
        self.overlay.toggle()
    
    def _on_quit(self) -> None:
        """Handle application quit"""
        logger.info("Application quitting...")
        
        # Stop transcription
        if self.transcriber:
            self.transcriber.stop()
        
        # Cleanup hotkeys
        try:
            hotkey_manager = get_hotkey_manager()
            hotkey_manager.unregister_all()
        except Exception as e:
            logger.error(f"Error cleaning up hotkeys: {e}")
    
    def run(self) -> int:
        """Run the application"""
        # Show main window or just tray
        if len(sys.argv) > 1 and sys.argv[1] == "--tray-only":
            # Only show tray icon
            self.window.hide()
        else:
            self.window.show()
        
        return self.app.exec()


# Global tray app instance
_tray_app: Optional[TrayApp] = None


def get_tray_app() -> TrayApp:
    """Get the global tray app instance"""
    global _tray_app
    if _tray_app is None:
        _tray_app = TrayApp()
    return _tray_app


def run_tray_app() -> int:
    """Run the tray application"""
    app = get_tray_app()
    return app.run()
