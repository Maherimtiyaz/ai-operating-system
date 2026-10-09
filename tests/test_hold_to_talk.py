"""Regression tests for how a dictation session ends.

Sessions end three ways: releasing the shortcut (hold-to-talk), pressing the
shortcut again (tap-once), or pressing Enter. All three funnel through the
queued ``hold_key_released`` signal into ``_stop_dictation``; the keyboard
hook additionally swallows Enter while a session is armed so the focused app
never sees a newline.

Release detection prefers the keyboard hook; the 30 ms poll timer only runs
as a fallback when the hook is rejected. These tests pin the wiring between
the hook, the queued signal, and ``_stop_dictation``.

They also pin overlay visibility: dictation is driven entirely from global
hotkeys while the workspace window stays hidden, so a control that disappears
takes the listening animation and every feedback message with it.
"""

import os

import pytest
from PyQt6.QtCore import QEvent

from aiop.ui.tray_app import TrayApp, VK_RETURN

VK_SPACE = 0x20


@pytest.fixture(scope="module")
def tray():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = TrayApp()
    yield app
    app._on_quit()


@pytest.fixture
def hold_to_talk(tray):
    """Run a test in press-and-hold mode, whatever the config says."""
    original = tray.overlay.is_hold_to_talk()
    tray.overlay.set_hold_to_talk(True)
    yield
    tray.overlay.set_hold_to_talk(original)


@pytest.fixture
def tap_once(tray):
    """Run a test in tap-once mode, whatever the config says."""
    original = tray.overlay.is_hold_to_talk()
    tray.overlay.set_hold_to_talk(False)
    yield
    tray.overlay.set_hold_to_talk(original)


@pytest.fixture(autouse=True)
def _never_leave_enter_swallowed(tray):
    """A test that arms dictation must not eat the developer's Enter key."""
    yield
    tray._hold_key_hook.unswallow(VK_RETURN)


class FakeTranscriber:
    def __init__(self) -> None:
        self.running = True
        self.stopped = 0

    def is_running(self) -> bool:
        return self.running

    def stop(self) -> None:
        self.running = False
        self.stopped += 1


@pytest.fixture
def fake_transcriber(tray):
    original = tray.transcriber
    fake = FakeTranscriber()
    tray.transcriber = fake
    yield fake
    tray.transcriber = original
    fake.stopped = 0


def test_key_down_does_not_release(tray, fake_transcriber, hold_to_talk):
    tray._on_hold_key_event(VK_SPACE, True)
    assert fake_transcriber.stopped == 0
    assert fake_transcriber.running is True


def test_key_up_reaches_stop_dictation(tray, fake_transcriber, hold_to_talk):
    tray._on_hold_key_event(VK_SPACE, False)
    assert fake_transcriber.stopped == 1
    assert fake_transcriber.running is False


def test_enter_key_down_finishes_the_session(tray, fake_transcriber, hold_to_talk):
    """Enter while recording stops dictation; the hook swallows the key."""
    tray._on_hold_key_event(VK_RETURN, True)
    assert fake_transcriber.stopped == 1


def test_release_is_ignored_when_dictation_is_not_running(tray, hold_to_talk):
    fake = FakeTranscriber()
    fake.running = False
    original = tray.transcriber
    tray.transcriber = fake
    try:
        tray._on_hold_key_event(VK_SPACE, False)
        tray._on_hold_key_event(VK_RETURN, True)
        assert fake.stopped == 0
    finally:
        tray.transcriber = original


def test_hold_hotkey_never_toggles_off(tray, monkeypatch, hold_to_talk):
    """In hold-to-talk a repeat of the hotkey must not stop the session."""
    assert tray.overlay.is_hold_to_talk() is True

    starts, stops = [], []
    monkeypatch.setattr(tray, "_start_dictation", lambda: starts.append(1))
    monkeypatch.setattr(tray, "_stop_dictation", lambda: stops.append(1))

    tray._on_dictation_hotkey()
    tray._on_dictation_hotkey()  # Windows auto-repeat

    assert len(starts) == 2
    assert stops == []


def test_tap_once_hotkey_toggles_the_session(tray, monkeypatch, tap_once):
    """Tap-once: the first press records, the next press finishes.

    RegisterHotKey repeats WM_HOTKEY while the chord is held, so the second
    toggle only fires after the shortcut key was physically released.
    """
    assert tray.overlay.is_hold_to_talk() is False
    fake = FakeTranscriber()
    fake.running = False
    original = tray.transcriber
    tray.transcriber = fake
    monkeypatch.setattr(tray, "_start_dictation", lambda: setattr(fake, "running", True))
    monkeypatch.setattr(tray, "_stop_dictation", lambda: setattr(fake, "running", False))
    tray._tap_armed_for_toggle = True
    try:
        tray._on_dictation_hotkey()
        assert fake.running is True
        tray._on_dictation_hotkey()  # Windows auto-repeat while still held
        assert fake.running is True, "a held repeat must not end the session"
        tray._on_hold_key_event(VK_SPACE, False)  # the physical release
        tray._on_dictation_hotkey()  # a real second press finishes
        assert fake.running is False
    finally:
        tray.transcriber = original


def test_tap_once_ignore_repeat_when_never_released(tray, monkeypatch, tap_once):
    """A held chord must not consume the toggle even without a prior gesture."""
    assert tray.overlay.is_hold_to_talk() is False
    fake = FakeTranscriber()
    fake.running = False
    original = tray.transcriber
    tray.transcriber = fake
    monkeypatch.setattr(tray, "_start_dictation", lambda: setattr(fake, "running", True))
    monkeypatch.setattr(tray, "_stop_dictation", lambda: setattr(fake, "running", False))
    tray._tap_armed_for_toggle = False
    try:
        tray._on_dictation_hotkey()
        assert fake.running is False, "repeat without release is ignored"
    finally:
        tray.transcriber = original


def test_arm_reports_hook_failure_and_falls_back(tray, monkeypatch):
    monkeypatch.setattr(tray._hold_key_hook, "start", lambda: False)
    tray._arm_release_detection(tray._hold_hotkey_id)

    assert tray._hold_uses_hook is False, (
        "a failed hook install must fall back to the poll timer"
    )
    tray._tap_poll_timer.stop()


def test_arm_reports_hook_success(tray, monkeypatch, hold_to_talk):
    monkeypatch.setattr(tray._hold_key_hook, "start", lambda: True)
    tray._arm_release_detection(tray._hold_hotkey_id)

    assert tray._hold_uses_hook is True
    from aiop.windows import get_hotkey_manager

    hotkey = get_hotkey_manager().hotkeys[tray._hold_hotkey_id]
    watched = tray._hold_key_hook.watched
    assert hotkey.key in watched
    assert VK_RETURN in watched, "Enter must always be able to finish a session"


def test_arm_in_tap_once_mode_watches_enter_and_the_shortcut(
    tray, monkeypatch, tap_once
):
    """Tap-once watches the shortcut key only to notice its release."""
    assert tray.overlay.is_hold_to_talk() is False
    monkeypatch.setattr(tray._hold_key_hook, "start", lambda: True)
    tray._arm_release_detection(tray._hold_hotkey_id)

    from aiop.windows import get_hotkey_manager

    hotkey = get_hotkey_manager().hotkeys[tray._hold_hotkey_id]
    watched = tray._hold_key_hook.watched
    assert hotkey.key in watched, "the release must re-arm the next toggle"
    assert VK_RETURN in watched, "Enter must always be able to finish a session"


def test_fallback_starts_the_poll_timer_but_the_hook_does_not(
    tray, monkeypatch, hold_to_talk
):
    monkeypatch.setattr(tray, "_start_dictation", lambda: None)

    monkeypatch.setattr(tray._hold_key_hook, "start", lambda: False)
    tray._arm_release_detection(tray._hold_hotkey_id)
    tray._on_dictation_hotkey()
    assert tray._hold_poll_timer.isActive()

    tray._hold_poll_timer.stop()

    monkeypatch.setattr(tray._hold_key_hook, "start", lambda: True)
    tray._arm_release_detection(tray._hold_hotkey_id)
    tray._on_dictation_hotkey()
    assert not tray._hold_poll_timer.isActive(), (
        "the hook path must not burn CPU on the 30 ms poll"
    )
    tray._hold_poll_timer.stop()


def test_start_dictation_shows_listening_before_touching_the_mic(tray):
    """The overlay must repaint before the ~200 ms microphone open."""
    calls = []

    class OrderingTranscriber:
        def is_running(self) -> bool:
            return False

        def start(self) -> None:
            calls.append("mic-open")

    original = tray.transcriber
    tray.transcriber = OrderingTranscriber()
    original_set_listening = tray.overlay.set_listening
    tray.overlay.set_listening = lambda v: (
        calls.append("listening"),
        original_set_listening(v),
    )[-1]
    try:
        tray._start_dictation()
    finally:
        tray.transcriber = original
        tray.overlay.set_listening = original_set_listening

    assert calls[0] == "listening", f"ordering was {calls}"
    assert "mic-open" in calls
    assert calls.index("listening") < calls.index("mic-open")
    tray.overlay.set_listening(False)


class IdleTranscriber:
    def is_running(self) -> bool:
        return False

    def start(self) -> None:
        pass


def test_dictation_start_brings_the_overlay_on_screen(tray):
    """A hotkey start must show the control, not just animate a hidden one."""
    original = tray.transcriber
    tray.transcriber = IdleTranscriber()
    tray.overlay.hide()
    try:
        tray._start_dictation()
        assert tray.overlay.isVisible()
        assert tray.overlay.is_listening() is True
    finally:
        tray.transcriber = original
        tray.overlay.set_listening(False)
        tray.overlay.hide()


def test_feedback_message_is_visible(tray):
    """Failure feedback is useless if the control it lives on is hidden."""
    tray.overlay.hide()
    tray.overlay.set_feedback(
        "I didn't hear anything. Hold the shortcut and speak.", success=False
    )
    assert tray.overlay.isVisible()
    tray.overlay.set_listening(False)
    tray.overlay.hide()


def test_listening_state_is_a_bare_microphone(tray):
    """While recording the control shows the icon only - no transcript text."""
    tray.overlay.set_listening(True)

    assert tray.overlay.width() == 72
    assert tray.overlay._status_label.isHidden()

    tray.overlay.set_listening(False)
    tray.overlay.hide()


def test_mouse_leave_keeps_the_microphone_control(tray):
    """The floating control is the app's only UI; it must not auto-hide."""
    tray.overlay.show()
    tray.overlay.leaveEvent(QEvent(QEvent.Type.Leave))
    tray.overlay._on_auto_hide()
    assert tray.overlay.isVisible()
    tray.overlay.hide()

