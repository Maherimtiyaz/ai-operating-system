"""Regression tests for the low-level keyboard hook.

Hold-to-talk releases are detected by a WH_KEYBOARD_LL hook on a dedicated
pump thread. Two real bugs landed here:

* ``GetModuleHandleW`` defaulted to a 32-bit ``c_int`` return, truncating the
  module handle so ``SetWindowsHookExW`` failed with ERROR_MOD_NOT_FOUND (126)
  and the app silently fell back to 30 ms polling.
* an earlier revision swallowed or dropped key events, which made release
  detection unreliable.
"""

import ctypes
import sys
import threading
import time

import pytest

from aiop.windows.key_hook import KeyHook

VK_F24 = 0x87  # a key nothing else on the system cares about
VK_F23 = 0x86

pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="Windows-only tests"
)


def send_key(vk: int, down: bool) -> None:
    from aiop.windows.win32_api import get_win32_api

    api = get_win32_api()
    (api._send_key_down if down else api._send_key_up)(vk)


def wait_for(predicate, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


@pytest.fixture
def hook():
    instance = KeyHook()
    yield instance
    instance.stop()


def test_watch_unwatch_roundtrip(hook):
    assert hook.watched == set()
    hook.watch(VK_F24)
    assert hook.watched == {VK_F24}
    hook.watch(VK_F24)  # idempotent
    assert hook.watched == {VK_F24}
    hook.unwatch(VK_F24)
    assert hook.watched == set()
    hook.unwatch(VK_F24)  # absent key is not an error
    assert hook.watched == set()


def test_stop_before_start_is_safe(hook):
    hook.stop()
    assert hook.available is False


def test_hook_installs_and_reports_available(hook):
    """Guards the GetModuleHandleW restype fix (ERROR_MOD_NOT_FOUND=126)."""
    assert hook.available is False
    assert hook.start() is True, "SetWindowsHookExW failed to install"
    assert hook.available is True
    assert hook.start() is True  # second start is a no-op, not a double hook
    hook.stop()
    assert hook.available is False


def test_only_watched_keys_are_delivered_in_order(hook):
    events = []
    delivered = threading.Event()
    hook.watch(VK_F24)
    hook.on_key = lambda vk, is_down: (
        events.append((vk, is_down)),
        delivered.set(),
    )

    assert hook.start() is True

    send_key(VK_F23, True)  # not watched: must be ignored
    send_key(VK_F23, False)

    send_key(VK_F24, True)
    assert delivered.wait(2.0), "watched key-down never reached the callback"
    send_key(VK_F24, False)
    assert wait_for(lambda: len(events) == 2), f"unexpected events: {events}"

    assert events == [(VK_F24, True), (VK_F24, False)]
    assert VK_F23 not in {vk for vk, _ in events}


def test_stop_stops_delivery_and_is_idempotent(hook):
    events = []
    hook.watch(VK_F24)
    hook.on_key = lambda vk, is_down: events.append((vk, is_down))

    assert hook.start() is True
    hook.stop()
    assert hook.available is False

    send_key(VK_F24, True)
    send_key(VK_F24, False)
    time.sleep(0.3)
    assert events == [], f"uninstalled hook still delivered {events}"

    hook.stop()  # repeated stop must not raise
    assert hook.available is False


def test_restart_after_stop_reinstalls(hook):
    events = []
    hook.watch(VK_F24)
    hook.on_key = lambda vk, is_down: events.append((vk, is_down))

    assert hook.start() is True
    hook.stop()
    assert hook.start() is True, "hook could not be reinstalled"

    send_key(VK_F24, True)
    assert wait_for(lambda: (VK_F24, True) in events), "no event after restart"
    send_key(VK_F24, False)
    assert wait_for(lambda: (VK_F24, False) in events)


def test_swallowed_key_is_still_delivered_but_blocked(hook):
    """Swallowing must hide Enter from the app, not from the callback."""
    from aiop.windows.key_hook import KBDLLHOOKSTRUCT, WM_KEYDOWN

    events = []
    hook.watch(VK_F24)
    hook.on_key = lambda vk, is_down: events.append((vk, is_down))
    hook.swallow(VK_F24)
    assert hook.swallowed == {VK_F24}

    info = KBDLLHOOKSTRUCT(vkCode=VK_F24)
    blocked = hook._hook_proc(0, WM_KEYDOWN, ctypes.pointer(info))

    assert blocked == 1, "a swallowed key must not reach other applications"
    assert events == [(VK_F24, True)], "the callback must still see the key"

    hook.unswallow(VK_F24)
    assert hook.swallowed == set()
    hook.unswallow(VK_F24)  # absent key is not an error


def test_stop_clears_swallowed_keys(hook):
    """A reinstalled hook must not keep eating keys from an old session."""
    hook.watch(VK_F24)
    hook.swallow(VK_F24)
    assert hook.start() is True

    hook.stop()

    assert hook.swallowed == set()
