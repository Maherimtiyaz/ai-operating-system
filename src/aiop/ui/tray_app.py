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
from ..windows.win32_api import VirtualKey
from ..core import config
from .onboarding import OnboardingDialog
from ..automation import WorkflowCommandRouter
from .workflow_editor import (
    get_workflow_engine,
    get_workflow_store,
    open_workflows_dialog,
)

logger = logging.get_logger(__name__)

# Enter finishes a dictation while one is armed. It is swallowed by the
# keyboard hook so the target application never sees the newline.
VK_RETURN = VirtualKey.VK_RETURN.value

# Failsafe: if a transcription result never arrives (whisper hang, dropped
# callback), the Enter swallow must not outlive the session.
ENTER_SWALLOW_FAILSAFE_MS = 15000

TRANSCRIPTION_STATUS_MESSAGES = {
    "no_speech": "I didn't hear anything. Tap the shortcut and speak.",
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
        # Virtual key of the dictation shortcut itself (used only to notice
        # its physical release in tap-once mode).
        self._tap_shortcut_vk = None
        # True between the shortcut's release and its next press. RegisterHotKey
        # repeats WM_HOTKEY while the chord is held, so consuming this flag on
        # the first delivery makes a held gesture toggle once instead of
        # flickering the session on and off.
        self._tap_armed_for_toggle = True
        self._hold_poll_timer = QTimer(self)
        self._hold_poll_timer.setInterval(30)
        self._hold_poll_timer.timeout.connect(self._poll_hold_to_talk)
        self._tap_poll_timer = QTimer(self)
        self._tap_poll_timer.setInterval(50)
        self._tap_poll_timer.timeout.connect(self._poll_tap_shortcut)
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
                if name == "dictation":
                    # Both modes need the hook: hold-to-talk watches the
                    # shortcut's key-up, tap-once watches Enter to finish.
                    self._hold_hotkey_id = hotkey_id
                    self._arm_release_detection(hotkey_id)
                logger.info("Registered %s hotkey (ID: %s)", name, hotkey_id)
            except Exception as error:
                logger.warning("Could not register %s hotkey (%s): %s", name, shortcut, error)

    def _arm_release_detection(self, hotkey_id: int) -> None:
        """Install the hook that ends a dictation from the keyboard.

        Hold-to-talk needs the shortcut's own key-up; tap-once watches the
        shortcut key only to notice its release (never to stop), so a held
        chord's repeated WM_HOTKEY cannot toggle the session off. Both modes
        watch Enter, which always finishes. Falls back to small poll timers
        when the hook is rejected (some sandboxed or elevated contexts).
        """
        hotkey = get_hotkey_manager().hotkeys.get(hotkey_id)
        if hotkey is None:
            return

        if self.overlay.is_hold_to_talk():
            self._tap_poll_timer.stop()
            self._tap_shortcut_vk = None
            self._hold_key_hook.watch(hotkey.key)
        else:
            # Tap-once: the release of the shortcut re-arms the next toggle;
            # its key-up alone must never end the recording.
            self._tap_shortcut_vk = hotkey.key
            self._hold_key_hook.watch(hotkey.key)
        self._hold_key_hook.watch(VK_RETURN)
        self._hold_key_hook.on_key = self._on_hold_key_event

        if self._hold_key_hook.start():
            self._hold_uses_hook = True
            self._tap_poll_timer.stop()
            logger.info(
                "Dictation stop uses the keyboard hook (Enter finishes a session)"
            )
        else:
            # Must be cleared explicitly: if this is a re-arm after an earlier
            # success, leaving it True would suppress the poll timer and leave
            # no release detection at all.
            self._hold_uses_hook = False
            self._hold_key_hook.unwatch(hotkey.key)
            self._hold_key_hook.unwatch(VK_RETURN)
            if not self.overlay.is_hold_to_talk():
                self._tap_poll_timer.start()
            logger.warning("Keyboard hook unavailable; Enter will not finish dictation")

    def _on_hold_key_event(self, vk: int, is_down: bool) -> None:
        """Keyboard-hook callback. Invoked on the hook thread, not Qt's."""
        if self.overlay.is_hold_to_talk():
            if not is_down or vk == VK_RETURN:
                self.hold_key_released.emit()
            return
        # Tap-once: Enter finishes (and its key is swallowed, so the focused
        # app gets no newline). The shortcut key only re-arms the toggle after
        # its physical release.
        if vk == VK_RETURN and is_down and self.transcriber.is_running():
            self.hold_key_released.emit()
            return
        if vk == self._tap_shortcut_vk and not is_down:
            self._tap_armed_for_toggle = True
    
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
        if not self._tap_armed_for_toggle:
            # RegisterHotKey repeats WM_HOTKEY while Ctrl+Shift+Space stays
            # held. Only the first delivery of a gesture may toggle, and only
            # after the key was physically released since the previous one.
            logger.debug("Ignoring held-hotkey repeat")
            return
        self._tap_armed_for_toggle = False
        if self.transcriber.is_running():
            self._stop_dictation()
        else:
            self._start_dictation()

    def _poll_tap_shortcut(self) -> None:
        """Fallback release detection when the keyboard hook is unavailable."""
        if not self._tap_shortcut_vk:
            self._tap_poll_timer.stop()
            return
        if not get_win32_api().is_key_pressed(self._tap_shortcut_vk):
            self._tap_armed_for_toggle = True

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

        win32 = get_win32_api()
        self._dictation_target_window = win32.get_foreground_window()
        logger.info(
            "Dictation target: hwnd=%s title=%r",
            self._dictation_target_window,
            win32.get_window_text(self._dictation_target_window or 0),
        )
        # Enter finishes the session from here on, so it must not reach the
        # target app as a newline.
        self._arm_enter_swatch()

        # Surface "Listening" before opening the microphone. A cold start costs
        # ~140 ms in the driver, and repaint() forces that feedback out now
        # instead of waiting for the event loop to come back around.
        self.overlay.set_listening(True)
        self.overlay.clear_live_preview()
        self.overlay.repaint()

        try:
            # Record every frame from the gesture until stop(), in both modes:
            # waiting for VAD to declare speech swallowed quiet openers and
            # produced empty buffers (nothing to type).
            self.transcriber.continuous_recording = True
            self.transcriber.start()
        except Exception as error:
            self._dictation_target_window = None
            self._unswallow_enter()
            logger.error("Could not start dictation: %s", error)
            self.overlay.set_feedback("Microphone unavailable", success=False)

    def _stop_dictation(self) -> None:
        if not self.transcriber.is_running():
            return
        self.overlay.set_state(OverlayState.PROCESSING, "Cleaning up...")
        self.transcriber.stop()
        # The transcription result releases Enter promptly; this is the
        # failsafe for a result that never arrives.
        self._unswallow_enter(delay_ms=ENTER_SWALLOW_FAILSAFE_MS)

    def _enter_hook(self):
        """Return the key hook when Enter is being managed, else None.

        Tests build partially constructed TrayApp instances, where the hook
        wiring was never installed; asking for it raises rather than missing.
        """
        try:
            if self._hold_uses_hook:
                return self._hold_key_hook
        except (AttributeError, RuntimeError):
            pass
        return None

    def _arm_enter_swatch(self) -> None:
        """Block Enter from reaching other apps until the session ends."""
        hook = self._enter_hook()
        if hook is not None:
            hook.swallow(VK_RETURN)

    def _unswallow_enter(self, delay_ms: int = 0) -> None:
        """Let Enter through again (immediately, or after ``delay_ms``).

        The delayed variant re-checks that no session re-armed the swallow in
        the meantime, so a quick back-to-back dictation is not left exposed.
        """
        hook = self._enter_hook()
        if hook is None:
            return

        def release() -> None:
            if not self.transcriber.is_running():
                hook.unswallow(VK_RETURN)

        if delay_ms:
            # Hold back briefly: the Enter key-up that follows the stop must
            # not slip through as a stray release, and a session that already
            # started again keeps the swallow.
            QTimer.singleShot(delay_ms, release)
        else:
            hook.unswallow(VK_RETURN)
    def _on_overlay_hotkey(self) -> None:
        """Handle overlay hotkey"""
        self.overlay.toggle()

    def _on_workflows_hotkey(self) -> None:
        """Open the workflow editor from the global hotkey."""
        open_workflows_dialog(self.window)

    def _on_transcription_result(self, result) -> None:
        """Route final speech to a workflow, an allowlisted action, or paste."""
        if not result.is_final:
            # Live preview: draw what whisper hears so far. Only the current
            # session may paint; a partial that lands after stop() belongs to
            # a finished utterance and would clobber the accepted text.
            text = (result.text or "").strip()
            transcriber = getattr(self, "transcriber", None)
            if text and transcriber is not None and transcriber.is_running():
                self.overlay.set_live_preview(text)
            return
        try:
            transcriber = getattr(self, "transcriber", None)
        except (AttributeError, RuntimeError):
            transcriber = None
        expected = getattr(transcriber, "generation", 0)
        if result.generation and result.generation != expected:
            # A slow whisper result for a session that has since started again.
            # Inserting it would paste into the *new* session's target window.
            logger.info(
                "Discarding transcription for an ended session "
                "(audio gen %d vs current gen %d)",
                result.generation,
                expected,
            )
            return
        # The session is over, so Enter can go back to the focused app.
        self._unswallow_enter(delay_ms=300)
        if not result.text or not result.text.strip():
            message = TRANSCRIPTION_STATUS_MESSAGES.get(
                result.status,
                "I didn't hear anything. Tap the shortcut and speak.",
            )
            logger.info("Dictation produced no text (status=%s)", result.status)
            self._dictation_target_window = None
            self.overlay.clear_live_preview()
            self.overlay.set_feedback(message, success=False)
            return
        logger.info("Dictation recognized: %r", result.text.strip())
        # Keep the accepted words up while processing and inserting, so the
        # user can confirm what was just placed at the cursor.
        self.overlay.set_live_preview(result.text.strip())
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
        logger.info(
            "Dictation action: handled=%s success=%s message=%s",
            action_result.handled,
            action_result.success,
            action_result.message,
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
