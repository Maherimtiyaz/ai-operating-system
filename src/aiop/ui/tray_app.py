"""
Tray application for AIOP
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon
from typing import Optional
from ..core import logging
from .main_window import get_main_window
from .overlay import get_overlay
from .overlay import OverlayState
from ..speech import get_transcriber
from ..audio.capture import get_pyaudio, terminate_pyaudio
from ..windows import get_hotkey_manager, get_win32_api
from ..windows import ActionRouter
from ..windows import get_hotkey_event_filter
from ..windows import get_key_hook
from ..core import config
from .onboarding import OnboardingDialog
from ..automation import WorkflowCommandRouter
from .workflow_editor import (
    get_workflow_engine,
    get_workflow_store,
    open_workflows_dialog,
)

logger = logging.get_logger(__name__)

TRANSCRIPTION_STATUS_MESSAGES = {
    "no_speech": "I didn't hear anything. Hold the shortcut and speak.",
    "too_short": "That was too short. Keep speaking a little longer.",
    "transcription_error": "I couldn't transcribe that. Please try again.",
}


class TrayApp(QObject):
    """Tray application wrapper"""

    transcription_ready = pyqtSignal(object)
    # Emitted from the keyboard-hook thread; queued onto the UI thread.
    hold_key_released = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        # Reuse an existing QApplication: run_tray_app() creates one first so
        # the first-run model download can show a dialog before this launches.
        self.app = QApplication.instance() or QApplication(sys.argv)
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
        self._hold_key_hook = get_key_hook()
        self._hold_uses_hook = False
        self._hold_poll_timer = QTimer(self)
        self._hold_poll_timer.setInterval(30)
        self._hold_poll_timer.timeout.connect(self._poll_hold_to_talk)
        self._dictation_target_window = None
        self.transcriber = get_transcriber()
        self.action_router = ActionRouter()
        self.workflow_router = WorkflowCommandRouter(
            store=get_workflow_store(),
            engine=get_workflow_engine(),
        )
        self._hotkey_filter = None

        # Setup hotkeys
        self._setup_hotkeys()
        
        # Connect signals
        self._connect_signals()
        self.overlay.add_toggle_callback(self._on_dictation_hotkey)
        self.overlay.add_press_callback(self._start_dictation)
        self.overlay.add_release_callback(self._stop_dictation)
        self.transcription_ready.connect(self._on_transcription_result)
        self.hold_key_released.connect(self._stop_dictation)
        self.transcriber.add_callback(self._queue_transcription_result)
    
    def _setup_hotkeys(self) -> None:
        """Set up global hotkeys"""
        hotkey_manager = get_hotkey_manager()

        # Qt owns the message loop, so WM_HOTKEY has to be pulled out of it by
        # a native event filter; otherwise the registrations never fire.
        HotkeyEventFilter = get_hotkey_event_filter()
        self._hotkey_filter = HotkeyEventFilter(hotkey_manager)
        self.app.installNativeEventFilter(self._hotkey_filter)

        hotkeys = [
            ("Ctrl+Shift+Space", self._on_dictation_hotkey, "dictation"),
            ("Ctrl+Shift+O", self._on_overlay_hotkey, "overlay"),
            (config.get_config().windows.hotkey_workflows or "Ctrl+Shift+W", self._on_workflows_hotkey, "workflows"),
        ]
        for shortcut, callback, name in hotkeys:
            try:
                hotkey_id = hotkey_manager.register_from_string(shortcut, callback)
                if name == "dictation" and config.get_config().windows.hold_to_talk:
                    self._hold_hotkey_id = hotkey_id
                    self._arm_release_detection(hotkey_id)
                logger.info("Registered %s hotkey (ID: %s)", name, hotkey_id)
            except Exception as error:
                logger.warning("Could not register %s hotkey (%s): %s", name, shortcut, error)

    def _arm_release_detection(self, hotkey_id: int) -> None:
        """Prefer true key-up events over polling for hold-to-talk release.

        Falls back to the 30 ms poll timer if the hook cannot be installed
        (it is rejected in some sandboxed or elevated contexts).
        """
        hotkey = get_hotkey_manager().hotkeys.get(hotkey_id)
        if hotkey is None:
            return

        self._hold_key_hook.watch(hotkey.key)
        self._hold_key_hook.on_key = self._on_hold_key_event

        if self._hold_key_hook.start():
            self._hold_uses_hook = True
            logger.info("Hold-to-talk release uses the keyboard hook")
        else:
            # Must be cleared explicitly: if this is a re-arm after an earlier
            # success, leaving it True would suppress the poll timer and leave
            # no release detection at all.
            self._hold_uses_hook = False
            self._hold_key_hook.unwatch(hotkey.key)
            logger.warning("Keyboard hook unavailable; hold-to-talk will poll")

    def _on_hold_key_event(self, vk: int, is_down: bool) -> None:
        """Keyboard-hook callback. Invoked on the hook thread, not Qt's."""
        if not is_down:
            self.hold_key_released.emit()
    
    def _connect_signals(self) -> None:
        """Connect application signals"""
        # Connect aboutToQuit signal
        self.app.aboutToQuit.connect(self._on_quit)
    
    def _on_dictation_hotkey(self) -> None:
        """Handle dictation hotkey"""
        if self.overlay.is_hold_to_talk():
            self._start_dictation()
            if not self._hold_uses_hook:
                # Polling is only the fallback path for when the hook failed
                # to install; with the hook this timer would just burn CPU.
                self._hold_poll_timer.start()
            return
        if self.transcriber.is_running():
            self._stop_dictation()
        else:
            self._start_dictation()

    def _poll_hold_to_talk(self) -> None:
        """Fallback release detection when the keyboard hook is unavailable."""
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

        self._dictation_target_window = get_win32_api().get_foreground_window()

        # Surface "Listening" before opening the microphone. A cold start costs
        # ~140 ms in the driver, and repaint() forces that feedback out now
        # instead of waiting for the event loop to come back around.
        self.overlay.set_listening(True)
        self.overlay.repaint()

        try:
            self.transcriber.start()
        except Exception as error:
            self._dictation_target_window = None
            logger.error("Could not start dictation: %s", error)
            self.overlay.set_feedback("Microphone unavailable", success=False)

    def _stop_dictation(self) -> None:
        if not self.transcriber.is_running():
            return
        self.overlay.set_state(OverlayState.PROCESSING, "Cleaning up...")
        self.transcriber.stop()
    
    def _on_overlay_hotkey(self) -> None:
        """Handle overlay hotkey"""
        self.overlay.toggle()

    def _on_workflows_hotkey(self) -> None:
        """Open the workflow editor from the global hotkey."""
        open_workflows_dialog(self.window)

    def _on_transcription_result(self, result) -> None:
        """Route final speech to a workflow, an allowlisted action, or paste."""
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
        workflow_feedback = self.workflow_router.dispatch(
            result.text,
            {"text": result.text, "window": self._dictation_target_window},
        )
        if workflow_feedback is not None:
            self._dictation_target_window = None
            self.overlay.set_feedback(workflow_feedback["message"], workflow_feedback["ok"])
            return
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
        
        # Stop transcription and release the microphone; the stream stays warm
        # between utterances for instant hold-to-talk response.
        if self.transcriber:
            close = getattr(self.transcriber, "close", None)
            if callable(close):
                close()
            else:
                self.transcriber.stop()
        
        # Cleanup hotkeys
        try:
            hotkey_manager = get_hotkey_manager()
            hotkey_manager.unregister_all()
        except Exception as e:
            logger.error(f"Error cleaning up hotkeys: {e}")

        if self._hotkey_filter is not None:
            self.app.removeNativeEventFilter(self._hotkey_filter)
            self._hotkey_filter = None

        try:
            self._hold_poll_timer.stop()
            if self._hold_key_hook is not None:
                self._hold_key_hook.stop()
                self._hold_uses_hook = False
        except Exception as e:
            logger.error(f"Error cleaning up key hook: {e}")

        terminate_pyaudio()
    
    def run(self) -> int:
        """Run the application"""
        # Keep the workspace out of the way; the listening control is the primary UI.
        self.window.hide()
        self._show_onboarding()
        self.overlay.show()
        # Boot PortAudio now rather than on the first keypress. It costs
        # ~280 ms and does not open the microphone, so the first dictation
        # only pays for the ~150 ms stream open.
        get_pyaudio()

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
    # The packaged build ships no weights: fetch the default model (with a
    # progress dialog) before the transcriber tries to build and warm up.
    QApplication.instance() or QApplication(sys.argv)
    try:
        from .model_download import ensure_model_ready

        ensure_model_ready()
    except Exception as error:
        logger.warning("Could not ensure the speech model is ready: %s", error)

    tray = get_tray_app()
    return tray.run()
