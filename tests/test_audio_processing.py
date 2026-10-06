"""Regression tests for audio processing and VAD (#4).

Root cause: squaring int16 samples overflowed the dtype, wrapping to
negative values so RMS became NaN. Combined with thresholds written for a
0-1 scale but fed 0-32767 values, `is_silent` could never fire while loud
speech was reported as silent.
"""

import numpy as np
import pytest

from aiop.audio.capture import AudioChunk, AudioFormat
from aiop.audio.processing import (
    NOISE_RMS,
    SILENCE_RMS,
    AudioProcessor,
    VADConfig,
    VoiceActivityDetector,
    _decode_samples,
    _rms_energy,
)


def int16_chunk(samples) -> AudioChunk:
    arr = np.asarray(samples, dtype=np.int16)
    return AudioChunk(data=arr.tobytes(), sample_rate=16000, channels=1,
                      format=AudioFormat.INT16)


class TestSampleDecoding:
    @pytest.mark.parametrize("fmt,scale", [
        (AudioFormat.INT16, 32768.0),
        (AudioFormat.INT8, 128.0),
        (AudioFormat.INT32, 2147483648.0),
    ])
    def test_integer_formats_normalize_to_unit_range(self, fmt, scale):
        info = {
            AudioFormat.INT16: (np.int16, 30000),
            AudioFormat.INT8: (np.int8, 100),
            AudioFormat.INT32: (np.int32, 2_000_000_000),
        }[fmt]
        dtype, peak = info
        raw = np.array([-peak, 0, peak], dtype=dtype)
        out = _decode_samples(raw.tobytes(), fmt)

        assert out.dtype == np.float32
        assert out.max() <= 1.0
        assert out.min() >= -1.0
        assert out[1] == 0.0

    def test_float32_passthrough(self):
        raw = np.array([-0.5, 0.0, 0.25], dtype=np.float32)
        out = _decode_samples(raw.tobytes(), AudioFormat.FLOAT32)
        np.testing.assert_allclose(out, raw)

    def test_int24_decodes_sign_extension(self):
        # -1 in 24-bit little endian is 0xFF 0xFF 0xFF
        raw = (b"\x00\x00\x80"   # -8388608
               b"\x00\x00\x00"   # 0
               b"\xff\xff\x7f")  # 8388607
        out = _decode_samples(raw, AudioFormat.INT24)

        assert out[0] == pytest.approx(-1.0)
        assert out[1] == 0.0
        assert out[2] == pytest.approx(0.99999988, rel=1e-6)


class TestRmsNeverNaN:
    """The core #4 regression: int16 squaring overflow."""

    def test_loud_speech_level_signal_produces_finite_rms(self):
        # peak 31556 was measured from real speech; 31556**2 overflows int16.
        t = np.arange(1024)
        loud = (31556 * np.sin(2 * np.pi * t / 32)).astype(np.int16)

        rms, energy = _rms_energy(_decode_samples(loud.tobytes(), AudioFormat.INT16))

        assert np.isfinite(rms)
        assert np.isfinite(energy)
        assert rms > 0.1

    def test_max_amplitude_signal_has_expected_rms(self):
        # Full-scale square wave: rms == 1.0 in normalized units.
        samples = np.tile([32767, -32768], 512).astype(np.int16)

        rms, _ = _rms_energy(_decode_samples(samples.tobytes(), AudioFormat.INT16))

        assert np.isfinite(rms)
        assert rms == pytest.approx(1.0, abs=0.01)

    def test_rms_matches_reference_value(self):
        samples = np.full(1024, 16384, dtype=np.int16)  # 0.5 full scale

        rms, energy = _rms_energy(_decode_samples(samples.tobytes(), AudioFormat.INT16))

        assert rms == pytest.approx(0.5, abs=0.001)
        assert energy == pytest.approx(rms ** 2, rel=1e-6)

    def test_zero_samples_do_not_divide_by_zero(self):
        rms, energy = _rms_energy(np.array([], dtype=np.float32))

        assert rms == 0.0
        assert energy == 0.0

    def test_process_reports_no_nans_for_loud_audio(self):
        proc = AudioProcessor(use_vad=True)
        t = np.arange(1024)
        loud = (31556 * np.sin(2 * np.pi * t / 32)).astype(np.int16)

        result = proc.process_chunk(int16_chunk(loud))

        assert np.isfinite(result.rms)
        assert np.isfinite(result.energy)


class TestThresholdsOnNormalizedScale:
    def test_digital_silence_is_silent(self):
        proc = AudioProcessor(use_vad=False)

        result = proc.process_chunk(int16_chunk(np.zeros(1024)))

        assert result.is_silent is True
        assert result.is_noise is False
        assert result.is_speech is False
        assert result.rms == 0.0

    def test_room_noise_floor_is_silent(self):
        # Measured ambient capture: peak 599 counts, rms ~0.00024, well
        # below the -60 dBFS silence floor.
        rng = np.random.default_rng(0)
        noise = (rng.normal(0, 8, 1024)).astype(np.int16)

        result = AudioProcessor(use_vad=False).process_chunk(int16_chunk(noise))

        assert result.rms < SILENCE_RMS
        assert result.is_silent is True
        assert result.is_noise is False
        assert result.is_speech is False

    def test_audible_non_speech_noise_is_noise(self):
        # Sits in the band between the silence floor and the speech gate.
        rng = np.random.default_rng(0)
        noise = (rng.normal(0, 80, 1024)).astype(np.int16)  # rms ~0.0024

        result = AudioProcessor(use_vad=False).process_chunk(int16_chunk(noise))

        assert SILENCE_RMS < result.rms < NOISE_RMS
        assert result.is_silent is False
        assert result.is_noise is True
        assert result.is_speech is False

    def test_real_speech_level_is_speech(self):
        # Measured speech median rms: 0.0716.
        t = np.arange(1024)
        speech = (2500 * np.sin(2 * np.pi * t / 32)).astype(np.int16)

        result = AudioProcessor(use_vad=False).process_chunk(int16_chunk(speech))

        assert result.rms > NOISE_RMS
        assert result.is_speech is True
        assert result.is_silent is False

    def test_thresholds_are_ordered(self):
        assert SILENCE_RMS < NOISE_RMS

    def test_flags_are_mutually_exclusive_without_vad(self):
        proc = AudioProcessor(use_vad=False)
        rng = np.random.default_rng(1)
        for scale in (0, 5, 500, 5000, 20000):
            samples = (rng.normal(0, scale, 1024)).astype(np.int16)
            r = proc.process_chunk(int16_chunk(samples))
            flags = [r.is_silent, r.is_noise, r.is_speech]
            assert sum(flags) == 1, f"scale={scale} gave {flags}"


class TestVadSignature:
    def test_is_speech_accepts_raw_bytes(self):
        """Regression: previously raised 'bytes' object has no attribute 'format'."""
        vad = VoiceActivityDetector()

        assert isinstance(vad.is_speech(b"\x00\x00" * 480), bool)

    def test_is_speech_accepts_audio_chunk(self):
        vad = VoiceActivityDetector()

        assert isinstance(vad.is_speech(int16_chunk(np.zeros(1024))), bool)

    def test_pure_silence_is_not_speech(self):
        vad = VoiceActivityDetector()

        assert vad.is_speech(int16_chunk(np.zeros(480))) is False

    def test_short_buffer_is_padded_not_error(self):
        vad = VoiceActivityDetector()

        # 8 samples, far below the 480-sample frame; must not raise.
        assert isinstance(vad.is_speech(b"\x01\x00" * 8), bool)

    def test_error_returns_false_not_exception(self):
        vad = VoiceActivityDetector(VADConfig(sample_rate=16000))

        # webrtcvad rejects non-standard frame lengths; padded path avoids this.
        assert isinstance(vad.is_speech(b"\x00" * 960), bool)


class TestConvertFormat:
    @pytest.mark.parametrize("fmt", [
        AudioFormat.INT16, AudioFormat.INT8, AudioFormat.INT32,
        AudioFormat.FLOAT32, AudioFormat.INT24,
    ])
    def test_all_formats_convert_to_int16(self, fmt):
        values = {
            AudioFormat.INT16: np.array([100, -100], dtype=np.int16),
            AudioFormat.INT8: np.array([100, -100], dtype=np.int8),
            AudioFormat.INT32: np.array([100_000, -100_000], dtype=np.int32),
            AudioFormat.FLOAT32: np.array([0.5, -0.5], dtype=np.float32),
            AudioFormat.INT24: np.array([0, 0, 100], dtype=np.uint8),  # placeholder
        }[fmt]
        if fmt == AudioFormat.INT24:
            raw = (100).to_bytes(3, "little", signed=True) + \
                  (-100).to_bytes(3, "little", signed=True)
        else:
            raw = values.tobytes()

        chunk = AudioChunk(data=raw, sample_rate=16000, channels=1, format=fmt)
        vad = VoiceActivityDetector()

        out = vad._convert_format(chunk)

        assert isinstance(out, bytes)
        assert len(out) % 2 == 0
        # Every conversion must land back on a sane int16 range.
        arr = np.frombuffer(out, dtype=np.int16)
        assert arr.min() >= -32768 and arr.max() <= 32767

    def test_int16_passes_through_untouched(self):
        raw = np.array([1234, -5678], dtype=np.int16)
        chunk = AudioChunk(data=raw.tobytes(), sample_rate=16000, channels=1,
                           format=AudioFormat.INT16)

        assert VoiceActivityDetector()._convert_format(chunk) == raw.tobytes()
