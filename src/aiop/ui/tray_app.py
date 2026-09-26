"""
Tray application for AIOP
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon
from typing import Optional
from ..core import logging
from .main_window import MainWindow, get_main_window
from .overlay import get_overlay
from .overlay import OverlayState
from ..speech import get_transcriber
from ..windows import register_hotkey, get_hotkey_manager, get_win32_api
from ..windows import ActionRouter
from ..core import config
from .onboarding import OnboardingDialog

logger = logging.get_logger(__name__)

TRANSCRIPTION_STATUS_MESSAGES = {
    "no_speech": "I didn't hear anything. Hold the shortcut and speak.",
    "too_short": "That was too short. Keep speaking a little longer.",
    "transcription_error": "I couldn't transcribe that. Please try again.",
}


class TrayApp(QObject):
    """Tray application wrapper"""

    transcription_ready = pyqtSignal(object)
    
    def __init__(self):
        super().__init__()
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("AI Operating Platform")
        self.app.setApplicationVersion("0.1.0")
        self.app.setOrganizationName("AIOP")
        
        # Set application icon
        self.app.setWindowIcon(QIcon(":/assets/icon.png"))
        
        # Components
        self.window = get_main_window()
        self.overlay = get_overlay()
        self.overlay.set_hold_to_talk(config.get_config().windows.hold_to_talk)
        self._hold_hotkey_id = None
        self._hold_poll_timer = QTimer(self)
        self._hold_poll_timer.setInterval(30)
        self._hold_poll_timer.timeout.connect(self._poll_hold_to_talk)
        self._dictation_target_window = None
        self.transcriber = get_transcriber()
        self.action_router = ActionRouter()
        
        # Setup hotkeys
        self._setup_hotkeys()
        
        # Connect signals
        self._connect_signals()
        self.overlay.add_toggle_callback(self._on_dictation_hotkey)
        self.overlay.add_press_callback(self._start_dictation)
        self.overlay.add_release_callback(self._stop_dictation)
        self.transcription_ready.connect(self._on_transcription_result)
        self.transcriber.add_callback(self._queue_transcription_result)
    
    def _setup_hotkeys(self) -> None:
        """Set up global hotkeys"""
        hotkey_manager = get_hotkey_manager()
        hotkeys = [
            ("Ctrl+Shift+Space", self._on_dictation_hotkey, "dictation"),
            ("Ctrl+Shift+O", self._on_overlay_hotkey, "overlay"),
        ]
        for shortcut, callback, name in hotkeys:
            try:
                hotkey_id = hotkey_manager.register_from_string(shortcut, callback)
                if name == "dictation" and config.get_config().windows.hold_to_talk:
                    self._hold_hotkey_id = hotkey_id
                logger.info("Registered %s hotkey (ID: %s)", name, hotkey_id)
            except Exception as error:
                logger.warning("Could not register %s hotkey (%s): %s", name, shortcut, error)
    
    def _connect_signals(self) -> None:
        """Connect application signals"""
        # Connect aboutToQuit signal
        self.app.aboutToQuit.connect(self._on_quit)
    
    def _on_dictation_hotkey(self) -> None:
        """Handle dictation hotkey"""
        if self.overlay.is_hold_to_talk():
            self._start_dictation()
            self._hold_poll_timer.start()
            return
        if self.transcriber.is_running():
            self._stop_dictation()
        else:
            self._start_dictation()

    def _poll_hold_to_talk(self) -> None:
        if not self._hold_hotkey_id:
            self._hold_poll_timer.stop()
            return
        hotkey_manager = get_hotkey_manager()
        if not hotkey_manager.is_hotkey_pressed(self._hold_hotkey_id):
            self._hold_poll_timer.stop()
            self._stop_dictation()

    def _start_dictation(self) -> None:
        if self.transcriber.is_running():
            return
        try:
            self._dictation_target_window = get_win32_api().get_foreground_window()
            self.transcriber.start()
        except Exception as error:
            self._dictation_target_window = None
            logger.error("Could not start dictation: %s", error)
            self.overlay.set_feedback("Microphone unavailable", success=False)
            return
        self.overlay.set_listening(True)

    def _stop_dictation(self) -> None:
        if not self.transcriber.is_running():
            return
        self.overlay.set_state(OverlayState.PROCESSING, "Cleaning up...")
        self.transcriber.stop()
    
    def _on_overlay_hotkey(self) -> None:
        """Handle overlay hotkey"""
        self.overlay.toggle()

    def _on_transcription_result(self, result) -> None:
        """Route final speech to an allowlisted action or focused app."""
        if not result.is_final:
            self.overlay.set_partial_text(result.text)
            return
        if not result.text or not result.text.strip():
            message = TRANSCRIPTION_STATUS_MESSAGES.get(
                result.status,
                "I didn't hear anything. Hold the shortcut and speak.",
            )
            self._dictation_target_window = None
            self.overlay.set_feedback(message, success=False)
            return
        self.overlay.set_state(OverlayState.PROCESSING, "Transcribing")
        self.app.processEvents()
        if self.action_router.FILE_MANAGER_PATTERN.search(result.text):
            self.overlay.set_state(OverlayState.PROCESSING, "Opening File Manager")
            self.app.processEvents()
        action_result = self.action_router.route(
            result.text,
            target_window=self._dictation_target_window,
        )
        self._dictation_target_window = None
        self.overlay.set_feedback(action_result.message, action_result.success)

    def _queue_transcription_result(self, result) -> None:
        """Move transcription results from the audio thread to Qt's UI thread."""
        self.transcription_ready.emit(result)

    def _show_onboarding(self) -> None:
        profile = config.get_config().profile
        if profile.completed:
            return
        dialog = OnboardingDialog()
        if dialog.exec() == OnboardingDialog.DialogCode.Accepted:
            profile.name = dialog.name_input.text().strip()
            profile.email = dialog.email_input.text().strip()
            profile.completed = True
            config.get_config_manager()._save_config()
    
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
        # Keep the workspace out of the way; the listening control is the primary UI.
        self.window.hide()
        self._show_onboarding()
        self.overlay.show()
        
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
