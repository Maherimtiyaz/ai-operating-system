"""Packaging support: frozen path resolution, first-run downloads, diagnostics."""

import hashlib
import sys
from pathlib import Path

from aiop.core import utils
from aiop.speech.model_manager import ModelInfo


# ------------------------------------------------------------- frozen paths
def test_frozen_project_root_is_the_executable_directory(monkeypatch):
    fake_exe = Path(r"C:\Program Files\AIOP\AIOP.exe")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)

    assert utils.get_project_root() == fake_exe.parent


def test_frozen_models_prefer_the_exe_dir(monkeypatch, tmp_path):
    exe_dir = tmp_path / "app"
    (exe_dir / "models").mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_dir / "AIOP.exe"))
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "internal"), raising=False)

    assert utils.get_bundled_models_dir() == exe_dir / "models"


def test_frozen_models_fall_back_to_the_internal_bundle(monkeypatch, tmp_path):
    internal = tmp_path / "internal"
    (internal / "models").mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "app" / "AIOP.exe"))
    monkeypatch.setattr(sys, "_MEIPASS", str(internal), raising=False)

    assert utils.get_bundled_models_dir() == internal / "models"


def test_unfrozen_paths_are_unchanged(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)

    assert utils.get_bundled_models_dir() == utils.get_project_root() / "models"


# ------------------------------------------------------------- model config
def test_default_model_name_maps_configured_paths(monkeypatch):
    from aiop.core import config as config_module
    from aiop.ui.model_download import default_model_name

    class Speech:
        model_path = None

    class Settings:
        speech = Speech()

    monkeypatch.setattr(config_module, "get_config", lambda: Settings())

    for configured, expected in [
        ("models/ggml-base.en.bin", "base.en"),
        ("ggml-small.en.bin", "small.en"),
        ("ggml-medium.bin", "medium"),
        ("base.en", "base.en"),
        ("large", "large"),
        (None, "base.en"),
    ]:
        Speech.model_path = configured
        assert default_model_name() == expected, configured


# --------------------------------------------------------------- downloads
def _fake_response(content: bytes):
    class FakeResponse:
        headers = {"content-length": str(len(content))}

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size=8192):
            yield content

    return FakeResponse()


def _make_manager(tmp_path, sha256=None):
    from aiop.speech.model_manager import ModelManager

    manager = ModelManager(models_dir=str(tmp_path))
    payload = b"A" * 64
    manager.models = {
        "fake": ModelInfo(
            name="fake",
            display_name="Fake",
            description="test",
            size="fake",
            parameters=1,
            file_size=len(payload),
            file_name="ggml-fake.bin",
            url="https://example.invalid/ggml-fake.bin",
            sha256=sha256 or hashlib.sha256(payload).hexdigest(),
            languages=["en"],
        )
    }
    manager.local_models = {}
    manager._payload = payload
    return manager


def test_download_writes_a_part_file_then_renames(tmp_path, monkeypatch):
    import requests

    manager = _make_manager(tmp_path)
    monkeypatch.setattr(requests, "get", lambda *a, **k: _fake_response(manager._payload))

    assert manager.download_model("fake") is True
    assert (tmp_path / "ggml-fake.bin").read_bytes() == manager._payload
    assert not (tmp_path / "ggml-fake.bin.part").exists()
    assert "fake" in manager.local_models


def test_download_reports_progress(tmp_path, monkeypatch):
    import requests

    manager = _make_manager(tmp_path)
    monkeypatch.setattr(requests, "get", lambda *a, **k: _fake_response(manager._payload))

    seen = []
    manager.download_model("fake", progress_callback=lambda d, t: seen.append((d, t)))

    assert seen and all(size == len(manager._payload) for _, size in seen)
    assert seen[-1][0] == len(manager._payload)


def test_checksum_mismatch_discards_the_download(tmp_path, monkeypatch):
    import requests

    manager = _make_manager(tmp_path, sha256="0" * 64)
    monkeypatch.setattr(requests, "get", lambda *a, **k: _fake_response(manager._payload))

    assert manager.download_model("fake") is False
    assert not (tmp_path / "ggml-fake.bin").exists()
    assert not (tmp_path / "ggml-fake.bin.part").exists()
    assert "fake" not in manager.local_models


def test_interrupted_download_leaves_no_part_file(tmp_path, monkeypatch):
    import requests

    manager = _make_manager(tmp_path)

    class BrokenResponse(_fake_response(manager._payload).__class__):
        def iter_content(self, chunk_size=8192):
            yield manager._payload
            raise requests.exceptions.ChunkedEncodingError("boom")

    monkeypatch.setattr(requests, "get", lambda *a, **k: BrokenResponse())

    assert manager.download_model("fake") is False
    assert not (tmp_path / "ggml-fake.bin.part").exists()
    assert "fake" not in manager.local_models


# ---------------------------------------------------- first run gating logic
def test_ensure_model_ready_downloads_when_nothing_resolves(monkeypatch):
    import aiop.speech.model_manager as manager_module
    from aiop.ui import model_download as md

    real_config = type("C", (), {"speech": type("S", (), {"model_path": "models/ggml-base.en.bin"})()})()
    manager = type(
        "M",
        (),
        {
            "get_model": lambda self, name: type(
                "X", (), {"file_size": 64}
            )() if name == "base.en" else None,
            "is_model_downloaded": lambda self, name: False,
        },
    )()

    monkeypatch.setattr(manager_module, "get_model_manager", lambda: manager)
    monkeypatch.setattr(manager_module, "resolve_model_path", lambda value: None)
    monkeypatch.setattr("aiop.core.config.get_config", lambda: real_config)
    monkeypatch.setattr(md, "default_model_name", lambda: "base.en")

    from PyQt6.QtWidgets import QDialog

    opened = []
    class FakeDialog:
        def __init__(self, model_name, file_size, parent=None):
            opened.append((model_name, file_size))

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(md, "ModelDownloadDialog", FakeDialog)

    assert md.ensure_model_ready() is True
    assert opened == [("base.en", 64)]


def test_ensure_model_ready_skips_when_a_model_file_exists(monkeypatch):
    import aiop.speech.model_manager as manager_module
    from aiop.ui import model_download as md

    manager = type(
        "M",
        (),
        {
            "get_model": lambda self, name: True,
            "is_model_downloaded": lambda self, name: True,
        },
    )()
    monkeypatch.setattr(manager_module, "get_model_manager", lambda: manager)
    monkeypatch.setattr(manager_module, "resolve_model_path", lambda value: "found")
    monkeypatch.setattr(
        "aiop.core.config.get_config",
        lambda: type("C", (), {"speech": None})(),
    )

    opened = []

    class FakeDialog:
        def __init__(self, *args, **kwargs):
            opened.append(args)

        def exec(self):
            return False

    monkeypatch.setattr(md, "ModelDownloadDialog", FakeDialog)

    assert md.ensure_model_ready() is True
    assert opened == []


def test_ensure_model_ready_survives_an_unknown_model_name(monkeypatch):
    import aiop.speech.model_manager as manager_module
    from aiop.ui import model_download as md

    manager = type(
        "M",
        (),
        {"get_model": lambda self, name: None, "is_model_downloaded": lambda self, n: False},
    )()
    monkeypatch.setattr(manager_module, "get_model_manager", lambda: manager)
    monkeypatch.setattr(manager_module, "resolve_model_path", lambda value: None)
    monkeypatch.setattr(md, "default_model_name", lambda: "no-such-model")
    monkeypatch.setattr(
        "aiop.core.config.get_config",
        lambda: type("C", (), {"speech": None})(),
    )

    assert md.ensure_model_ready() is True


# --------------------------------------------------------------- diagnostic
def test_check_flag_runs_the_diagnostic_without_holding_the_lock(monkeypatch, capsys):
    from aiop import main as main_module

    monkeypatch.setattr(sys, "argv", ["AIOP", "--check"])
    main_module.acquire_single_instance_lock = lambda: False  # the app is running

    assert main_module.main() == 0
    output = capsys.readouterr().out
    assert "application dir:" in output
    assert "backend:" in output