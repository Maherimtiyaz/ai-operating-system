"""Tests for model and backend path resolution.

Regression coverage: every path used by the speech stack must resolve from
absolute location data rather than the process working directory.
"""

import pytest
from pathlib import Path

from aiop.core import utils
from aiop.speech import ModelManager
from aiop.speech.model_manager import resolve_model_path
from aiop.speech.whisper_cpp import WhisperCPP


class TestModelDirectoryLayout:
    def test_model_manager_defaults_to_writable_app_dir(self):
        manager = ModelManager()

        assert manager.models_dir.is_absolute()
        assert manager.models_dir == utils.get_models_dir()

    def test_model_manager_searches_bundled_dir_by_default(self):
        manager = ModelManager()

        assert utils.get_bundled_models_dir() in manager.search_dirs

    def test_explicit_model_dir_constrains_search(self):
        manager = ModelManager(models_dir="custom-models")

        assert manager.search_dirs == [Path("custom-models")]
        assert not manager.search_dirs[0].is_absolute()

    def test_bundled_model_is_discovered_from_absolute_path(self):
        manager = ModelManager()
        path = manager.get_model_path("base.en")

        if path is None:
            pytest.skip("no bundled model in this checkout")

        assert path.is_absolute()
        assert path.exists()
        assert path.parent in manager.search_dirs


class TestModelResolver:
    @pytest.mark.parametrize(
        "value",
        [
            "models/ggml-base.en.bin",
            "ggml-base.en.bin",
            "base.en",
        ],
    )
    def test_resolves_each_supported_input_form(self, value):
        if not utils.get_bundled_models_dir().exists():
            pytest.skip("no bundled models in this checkout")

        resolved = resolve_model_path(value)

        assert resolved is not None
        assert resolved.is_absolute()
        assert resolved.name == "ggml-base.en.bin"

    def test_absolute_path_resolves_when_file_exists(self):
        candidate = utils.get_bundled_models_dir() / "ggml-base.en.bin"
        if not candidate.exists():
            pytest.skip("no bundled model in this checkout")

        assert resolve_model_path(str(candidate)) == candidate

    def test_missing_model_returns_none_not_exception(self):
        assert resolve_model_path("totally-made-up-model") is None
        assert resolve_model_path("nope.bin") is None

    def test_empty_values_return_none(self):
        assert resolve_model_path(None) is None
        assert resolve_model_path("") is None

    def test_truncated_model_is_not_reported_available(self, tmp_path):
        """A 0-byte or partial .bin must never count as ready."""
        manager = ModelManager(models_dir=str(tmp_path))
        info = manager.models["tiny"]

        (tmp_path / info.file_name).write_bytes(b"")

        assert manager.get_model_path("tiny") is None

        (tmp_path / info.file_name).write_bytes(b"x")
        assert manager.get_model_path("tiny") is None


class TestBackendResolution:
    def test_cli_backend_resolves_absolutely(self):
        cli = WhisperCPP._find_cli(None)

        if cli is None:
            pytest.skip("whisper-cli not bundled in this checkout")

        assert cli.is_absolute()
        assert cli.parent in utils.get_model_search_dirs()

    def test_library_resolution_falls_back_to_known_dirs(self):
        path = WhisperCPP._find_library(None)

        assert isinstance(path, str)
        if path.endswith((".dll", ".so", ".dylib")):
            assert Path(path).is_absolute()


class TestTranscriberConfigFromSettings:
    def test_reads_speech_settings(self):
        from aiop.speech.transcriber import SpeechTranscriber

        tc = SpeechTranscriber._config_from_settings()

        assert tc.language == "en"
        assert tc.vad_aggressiveness == 3
        # Settings ship a .bin path; the transcriber wants a bare model name.
        assert tc.model_name == "base.en"

    def test_accepts_bare_model_name(self, monkeypatch):
        from aiop.core import config as app_config
        from aiop.speech.transcriber import SpeechTranscriber

        settings = app_config.get_config().speech
        monkeypatch.setattr(settings, "model_path", "tiny.en")

        tc = SpeechTranscriber._config_from_settings()

        assert tc.model_name == "tiny.en"
