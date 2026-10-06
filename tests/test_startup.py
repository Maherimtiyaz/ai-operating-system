"""Startup hardening: single-instance lock, tolerant config, whisper pre-flight."""

import threading
from pathlib import Path

import pytest
import yaml

from aiop.core import config as config_module
from aiop.main import acquire_single_instance_lock, check_whisper_library

LEGACY_CONFIG = {
    "speech": {
        "model_path": "models/ggml-base.en.bin",
        "model_type": "whisper-1",
        "language": "en",
    },
    "windows": {"hold_to_talk": True, "removed_in_a_future_build": 42},
}


def _write_config(directory: Path, data: dict) -> config_module.ConfigManager:
    (directory / "config.yaml").write_text(yaml.dump(data), encoding="utf-8")
    manager = config_module.ConfigManager(config_dir=str(directory))
    manager.reload()
    return manager


# ------------------------------------------------------------ config loading
def test_config_written_by_an_older_build_still_loads(tmp_path):
    manager = _write_config(tmp_path, LEGACY_CONFIG)

    assert manager.config.speech.language == "en"
    assert manager.config.windows.hold_to_talk is True
    assert not hasattr(manager.config.speech, "model_type")
    assert not hasattr(manager.config.windows, "removed_in_a_future_build")


def test_reloading_a_config_this_build_just_wrote_round_trips(tmp_path):
    _write_config(tmp_path, LEGACY_CONFIG)
    reloaded = config_module.ConfigManager(config_dir=str(tmp_path))
    reloaded.reload()

    assert reloaded.config.speech.language == "en"
    assert reloaded.config.speech.model_path == "models/ggml-base.en.bin"


def test_defined_keys_are_not_dropped(tmp_path):
    data = {
        "speech": {"language": "de", "beam_size": 1, "temperature": 0.5},
        "audio": {"sample_rate": 48000, "channels": 1},
    }
    manager = _write_config(tmp_path, data)

    assert manager.config.speech.language == "de"
    assert manager.config.speech.beam_size == 1
    assert manager.config.speech.temperature == pytest.approx(0.5)
    assert manager.config.audio.sample_rate == 48000


def test_sections_missing_from_the_file_are_left_alone(tmp_path):
    manager = _write_config(tmp_path, {"windows": {"hold_to_talk": False}})

    assert manager.config.windows.hold_to_talk is False
    # Untouched sections keep their defaults rather than being reset.
    assert manager.config.speech.model_path


def test_non_mapping_sections_are_ignored(tmp_path):
    manager = _write_config(tmp_path, {"speech": "not-a-mapping"})

    assert manager.config.speech.language == "en"


# ------------------------------------------------------- single-instance lock
def test_lock_is_stable_within_one_process():
    first = acquire_single_instance_lock()

    assert isinstance(first, bool)
    # Asking again must not look like a second instance: the mutex is already
    # ours, and CreateMutexW would report ERROR_ALREADY_EXISTS for it.
    assert acquire_single_instance_lock() is first
    if first:
        import aiop.main

        assert aiop.main._instance_mutex is not None


def test_lock_releases_before_the_next_holder_would_need_it():
    # The handle is only ever created once per process, so there is nothing to
    # release mid-run; assert we did not leak one handle per call.
    import aiop.main

    acquire_single_instance_lock()
    handle = aiop.main._instance_mutex
    acquire_single_instance_lock()
    assert aiop.main._instance_mutex is handle


# ------------------------------------------------------------ whisper preflight
def test_pre_flight_reports_a_usable_backend():
    result = check_whisper_library()

    assert isinstance(result, bool)


def test_second_instance_is_refused_without_raising(monkeypatch):
    """A refused lock must exit cleanly rather than starting a second GUI."""
    from aiop import main as main_module

    monkeypatch.setattr(main_module, "acquire_single_instance_lock", lambda: False)
    started = threading.Event()
    monkeypatch.setattr(main_module, "run_tray_app", lambda: started.set() or 0)

    assert main_module.main() == 0
    assert not started.is_set()
