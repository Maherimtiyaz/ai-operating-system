"""Regression tests for the hold-to-talk release path in TrayApp.

Release detection prefers the keyboard hook; the 30 ms poll timer only runs
as a fallback when the hook is rejected. These tests pin the wiring between
the hook, the queued ``hold_key_released`` signal, and ``_stop_dictation``.
"""

import os

import pytest

from aiop.ui.tray_app import TrayApp


@pytest.fixture(scope="module")
def tray():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = TrayApp()
    yield app
    app._on_quit()


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


def test_key_down_does_not_release(tray, fake_transcriber):
    tray._on_hold_key_event(0x20, True)
    assert fake_transcriber.stopped == 0
    assert fake_transcriber.running is True


def test_key_up_reaches_stop_dictation(tray, fake_transcriber):
    tray._on_hold_key_event(0x20, False)
    assert fake_transcriber.stopped == 1
    assert fake_transcriber.running is False


def test_release_is_ignored_when_dictation_is_not_running(tray):
    fake = FakeTranscriber()
    fake.running = False
    original = tray.transcriber
    tray.transcriber = fake
    try:
        tray._on_hold_key_event(0x20, False)
        assert fake.stopped == 0
    finally:
        tray.transcriber = original


def test_hold_hotkey_never_toggles_off(tray, monkeypatch):
    """In hold-to-talk a repeat of the hotkey must not stop the session."""
    assert tray.overlay.is_hold_to_talk() is True

    starts, stops = [], []
    monkeypatch.setattr(tray, "_start_dictation", lambda: starts.append(1))
    monkeypatch.setattr(tray, "_stop_dictation", lambda: stops.append(1))

    tray._on_dictation_hotkey()
    tray._on_dictation_hotkey()  # Windows auto-repeat

    assert len(starts) == 2
    assert stops == []


def test_arm_reports_hook_failure_and_falls_back(tray, monkeypatch):
    monkeypatch.setattr(tray._hold_key_hook, "start", lambda: False)
    tray._arm_release_detection(tray._hold_hotkey_id)

    assert tray._hold_uses_hook is False, (
        "a failed hook install must fall back to the poll timer"
    )


def test_arm_reports_hook_success(tray, monkeypatch):
    monkeypatch.setattr(tray._hold_key_hook, "start", lambda: True)
    tray._arm_release_detection(tray._hold_hotkey_id)

    assert tray._hold_uses_hook is True
    from aiop.windows import get_hotkey_manager

    hotkey = get_hotkey_manager().hotkeys[tray._hold_hotkey_id]
    assert hotkey.key in tray._hold_key_hook.watched


def test_fallback_starts_the_poll_timer_but_the_hook_does_not(
    tray, monkeypatch
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
