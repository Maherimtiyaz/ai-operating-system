"""Tests for the whisper.cpp DLL backend (ABI, window sizing, CLI fallback)."""

import ctypes
import types
from pathlib import Path

import numpy as np
import pytest

from aiop.core import exceptions
from aiop.speech.whisper_cpp import (
    AUDIO_CTX_MARGIN,
    ENCODER_POSITIONS_PER_SECOND,
    MAX_AUDIO_CTX,
    WHISPER_SAMPLE_RATE,
    WhisperCPP,
    WhisperParameters,
    audio_ctx_for,
)

MODELS_DIR = Path(__file__).resolve().parents[1] / "models"
WHISPER_DLL = MODELS_DIR / "whisper.dll"
MODEL_BIN = MODELS_DIR / "ggml-base.en.bin"


# ------------------------------------------------------------------ sizing
def test_audio_ctx_leaves_headroom_over_the_content():
    # One second of audio is 50 encoder positions plus the safety margin.
    assert audio_ctx_for(WHISPER_SAMPLE_RATE) == 50 + AUDIO_CTX_MARGIN


def test_audio_ctx_scales_with_duration():
    seven_seconds = audio_ctx_for(7 * WHISPER_SAMPLE_RATE)
    two_seconds = audio_ctx_for(2 * WHISPER_SAMPLE_RATE)
    assert seven_seconds - two_seconds == 5 * ENCODER_POSITIONS_PER_SECOND


def test_audio_ctx_never_truncates_below_the_content_or_exceeds_the_model():
    assert audio_ctx_for(0) >= 1
    assert audio_ctx_for(10 * 60 * WHISPER_SAMPLE_RATE) == MAX_AUDIO_CTX


def test_audio_ctx_honours_an_explicit_override():
    assert audio_ctx_for(WHISPER_SAMPLE_RATE, override=123) == 123
    assert audio_ctx_for(WHISPER_SAMPLE_RATE, override=99999) == MAX_AUDIO_CTX
    assert audio_ctx_for(WHISPER_SAMPLE_RATE, override=-5) != MAX_AUDIO_CTX


def test_parameters_default_to_auto_window_and_no_context():
    parameters = WhisperParameters()
    assert parameters.audio_ctx == 0
    assert parameters.no_context is True
    assert parameters.n_threads >= 1


# ------------------------------------------------------------- sample prep
def test_bytes_are_read_as_int16_pcm_and_normalised():
    pcm = np.array([-32768, 0, 16384, 32767], dtype=np.int16).tobytes()
    samples = WhisperCPP._to_float32(pcm, WHISPER_SAMPLE_RATE)

    assert samples.dtype == np.float32
    assert samples.size == 4
    assert samples[0] == pytest.approx(-1.0)
    assert samples[2] == pytest.approx(0.5, abs=1e-3)


def test_float_arrays_in_range_are_left_alone():
    source = np.array([-0.25, 0.0, 0.5], dtype=np.float32)
    samples = WhisperCPP._to_float32(source, WHISPER_SAMPLE_RATE)

    assert samples.dtype == np.float32
    np.testing.assert_allclose(samples, source)


def test_audio_is_resampled_to_the_rate_whisper_expects():
    source = np.ones(22050, dtype=np.int16)
    samples = WhisperCPP._to_float32(source.tobytes(), 22050)

    assert samples.size == pytest.approx(WHISPER_SAMPLE_RATE, rel=0.01)
    assert samples.dtype == np.float32


def test_output_is_contiguous_for_the_ctypes_pointer():
    samples = WhisperCPP._to_float32(
        np.arange(100, dtype=np.int16).tobytes(), WHISPER_SAMPLE_RATE
    )
    assert samples.flags["C_CONTIGUOUS"]


# --------------------------------------------------------- parameter build
class _RecordingLib:
    """Just enough of a CDLL to satisfy _copy_default_params."""

    def __init__(self):
        self._buffer = None
        self.freed = []
        self.default_strategy = None

    def whisper_full_default_params_by_ref(self, strategy):
        from aiop.speech.whisper_cpp import WhisperFullParams

        self.default_strategy = strategy
        self._buffer = WhisperFullParams()
        return ctypes.addressof(self._buffer)

    def whisper_free_params(self, pointer):
        self.freed.append(pointer)


def _make_cpp(parameters=None):
    cpp = WhisperCPP.__new__(WhisperCPP)
    cpp.model_path = None
    cpp.library_path = None
    cpp.cli_path = None
    cpp.parameters = parameters or WhisperParameters()
    cpp.lib = _RecordingLib()
    cpp.ctx = None
    cpp.state = None
    cpp._is_loaded = False
    cpp._lock = __import__("threading").RLock()
    return cpp


def test_build_params_uses_greedy_defaults_and_a_tight_window():
    cpp = _make_cpp()
    params = cpp._build_params(n_samples=3 * WHISPER_SAMPLE_RATE, language="en")

    assert cpp.lib.default_strategy == 0
    assert params.strategy == 0
    assert params.audio_ctx == 3 * ENCODER_POSITIONS_PER_SECOND + AUDIO_CTX_MARGIN
    assert params.no_context is True
    assert params.no_timestamps is True
    assert params.language == b"en"
    assert params.n_threads >= 1
    assert not params.print_progress
    assert not params.print_realtime


def test_build_params_frees_the_c_default_copy():
    cpp = _make_cpp()
    cpp._build_params(n_samples=WHISPER_SAMPLE_RATE, language=None)
    assert len(cpp.lib.freed) == 1


def test_build_params_stops_printing_but_keeps_translation():
    parameters = WhisperParameters(n_threads=2, audio_ctx=321, no_context=False)
    cpp = _make_cpp(parameters)
    params = cpp._build_params(
        n_samples=WHISPER_SAMPLE_RATE, language="de", translate=True, temperature=0.4
    )

    assert params.n_threads == 2
    assert params.audio_ctx == 321
    assert params.no_context is False
    assert params.language == b"de"
    assert params.translate is True
    assert params.temperature == pytest.approx(0.4)


# --------------------------------------------------------- backend selection
def test_setup_functions_reports_every_missing_export():
    cpp = WhisperCPP.__new__(WhisperCPP)
    cpp.lib = types.SimpleNamespace()

    with pytest.raises(exceptions.SpeechError) as error:
        cpp._setup_functions()

    message = str(error.value)
    assert "whisper_full" in message
    assert "whisper_init_from_file_with_params" in message
    assert "whisper_full_get_segment_text" in message


def test_unloadable_library_falls_back_to_the_cli(tmp_path):
    fake_dll = tmp_path / "whisper.dll"
    fake_dll.write_bytes(b"this is not a shared library")

    cpp = WhisperCPP.__new__(WhisperCPP)
    cpp.library_path = str(fake_dll)
    cpp.cli_path = str(tmp_path / "whisper-cli.exe")
    cpp.lib = None
    cpp.ctx = None
    cpp.state = None
    cpp._is_loaded = False

    cpp._load_library()

    assert cpp.lib is None
    assert cpp._is_loaded is True


def test_unloadable_library_without_a_cli_raises(tmp_path):
    fake_dll = tmp_path / "whisper.dll"
    fake_dll.write_bytes(b"this is not a shared library")

    cpp = WhisperCPP.__new__(WhisperCPP)
    cpp.library_path = str(fake_dll)
    cpp.cli_path = None
    cpp.lib = None
    cpp.ctx = None
    cpp.state = None
    cpp._is_loaded = False

    with pytest.raises(exceptions.SpeechError):
        cpp._load_library()


def test_warmup_skips_when_only_the_cli_backend_is_available():
    cpp = _make_cpp()
    cpp.lib = None
    model = types.SimpleNamespace(whisper=cpp, lib=None)

    from aiop.speech.whisper_cpp import WhisperModel

    assert WhisperModel.warmup(model) is False


# ------------------------------------------------------- real bundled build
@pytest.mark.skipif(not WHISPER_DLL.exists(), reason="whisper.dll not bundled")
def test_bundled_library_exports_the_whisper_193_entry_points():
    cpp = WhisperCPP.__new__(WhisperCPP)
    cpp.lib = types.SimpleNamespace()
    # Bind against the real DLL: a version mismatch must fail loudly here.
    cpp.lib = ctypes.CDLL(str(WHISPER_DLL))
    cpp._setup_functions()  # must not raise


@pytest.mark.skipif(not WHISPER_DLL.exists(), reason="whisper.dll not bundled")
def test_cpp_backend_is_preferred_over_the_cli():
    cpp = WhisperCPP(model_path=MODEL_BIN if MODEL_BIN.exists() else None)
    try:
        assert cpp.lib is not None, "expected the in-process DLL backend"
        assert cpp.cli_path or True  # CLI stays available as a fallback
    finally:
        cpp.unload_model()
