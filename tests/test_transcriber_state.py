"""Regression tests for the transcriber speech state machine (#4).

Previously a single non-speech chunk closed the utterance. Combined with the
RMS overflow (which made loud speech look silent), every utterance was either
discarded as "too_short" or truncated.
"""

import numpy as np
import pytest

from aiop.audio.capture import AudioChunk, AudioFormat
from aiop.speech.transcriber import (
    SpeechTranscriber,
    TranscriptionConfig,
    TranscriptionState,
)

CHUNK = 1024
SR = 16000


def make_transcriber(**overrides) -> SpeechTranscriber:
    cfg = TranscriptionConfig(**overrides)
    t = SpeechTranscriber(config=cfg)
    # Never run a real model during unit tests, but preserve the real
    # behaviour of releasing the buffer and returning to IDLE.
    t._process_buffer = lambda: t._reset_buffer()
    return t


def silence(seconds: float) -> np.ndarray:
    return np.zeros(int(SR * seconds), dtype=np.int16)


def speech_tone(seconds: float, amplitude: int = 4000) -> np.ndarray:
    t = np.arange(int(SR * seconds))
    return (amplitude * np.sin(2 * np.pi * t / 40)).astype(np.int16)


def feed(t: SpeechTranscriber, samples: np.ndarray):
    t.state = TranscriptionState.IDLE
    t._audio_buffer = []
    t._speech_start_time = None
    t._silence_frames = 0
    t._speech_frames = 0
    # The transcriber keeps the audio stream warm and gates on _is_running.
    t._is_running = True

    statuses = []
    buffer_calls = []
    orig_buffer = t._process_buffer
    orig_status = t._emit_status

    def spy_buffer():
        buffer_calls.append(len(t._audio_buffer))
        return orig_buffer()

    def spy_status(msg):
        statuses.append(msg)
        return orig_status(msg)

    t._process_buffer = spy_buffer
    t._emit_status = spy_status

    transitions = []
    prev = t.state
    for i in range(0, len(samples) - CHUNK, CHUNK):
        ac = AudioChunk(data=samples[i:i + CHUNK].tobytes(), sample_rate=SR,
                        channels=1, format=AudioFormat.INT16)
        t._process_audio_chunk(ac)
        if t.state != prev:
            transitions.append(f"{prev.name}->{t.state.name}")
        prev = t.state
    return transitions, statuses, buffer_calls


class TestSilenceHandling:
    def test_digital_silence_starts_nothing(self):
        t = make_transcriber()
        trans, status, calls = feed(t, silence(2.0))

        assert calls == []
        assert t.state is TranscriptionState.IDLE

    def test_room_noise_starts_nothing(self):
        t = make_transcriber()
        rng = np.random.default_rng(0)
        trans, status, calls = feed(t, (rng.normal(0, 8, SR * 2)).astype(np.int16))

        assert calls == []
        assert t.state is TranscriptionState.IDLE


class TestNoiseBlips:
    def test_short_blip_is_rejected_as_too_short(self):
        t = make_transcriber()
        samples = silence(2.0)
        samples[2000:2400] = np.random.default_rng(1).normal(0, 6000, 400) \
            .astype(np.int16)

        trans, status, calls = feed(t, samples)

        assert calls == [], "a noise blip must not be transcribed"
        assert "too_short" in status
        assert t.state is TranscriptionState.IDLE

    def test_single_silent_chunk_does_not_end_utterance(self):
        """The core #4 state-machine regression."""
        t = make_transcriber(silence_end_frames=4)
        samples = np.concatenate([speech_tone(1.0),
                                  silence(CHUNK / SR),      # one dropped frame
                                  speech_tone(1.0),
                                  silence(1.0)])

        trans, status, calls = feed(t, samples)

        assert len(calls) == 1, f"utterance split into {len(calls)} pieces"
        assert "too_short" not in status

    def test_sustained_silence_closes_the_utterance(self):
        t = make_transcriber(silence_end_frames=4)
        samples = np.concatenate([speech_tone(1.0), silence(1.0)])

        trans, status, calls = feed(t, samples)

        assert len(calls) == 1


class TestSilenceEndFrames:
    @pytest.mark.parametrize("frames,split", [(1, True), (8, False)])
    def test_frames_control_split_sensitivity(self, frames, split):
        t = make_transcriber(silence_end_frames=frames)
        # 5 chunks (0.32s) of silence between two speech runs.
        samples = np.concatenate([speech_tone(1.0), silence(0.32),
                                  speech_tone(1.0), silence(1.0)])

        _, status, calls = feed(t, samples)

        assert (len(calls) > 1) is split


class TestSpeechAccepted:
    def test_real_speech_run_is_transcribed(self):
        t = make_transcriber()
        samples = np.concatenate([speech_tone(2.0), silence(1.0)])

        trans, status, calls = feed(t, samples)

        assert len(calls) == 1
        assert calls[0] > 0, "buffered audio must not be empty"
        assert "too_short" not in status
        assert t.state is TranscriptionState.IDLE, "must reset after processing"

    def test_voiced_duration_excludes_trailing_silence(self):
        """Trailing silence must not pad a sub-minimum blip up to accept."""
        t = make_transcriber(min_speech_duration=0.3, silence_end_frames=4)
        # 0.13s of "speech" (2 voiced chunks) then long silence.
        samples = np.concatenate([speech_tone(0.13), silence(2.0)])

        _, status, calls = feed(t, samples)

        assert calls == []
        assert "too_short" in status

    def test_speech_just_over_minimum_is_accepted(self):
        t = make_transcriber(min_speech_duration=0.3, silence_end_frames=4)
        # 0.38s > 0.3s minimum.
        samples = np.concatenate([speech_tone(0.38), silence(2.0)])

        _, status, calls = feed(t, samples)

        assert len(calls) == 1


class TestBufferReset:
    def test_counters_reset_between_runs(self):
        t = make_transcriber()
        feed(t, np.concatenate([speech_tone(1.0), silence(1.0)]))
        assert t._silence_frames == 0
        assert t._speech_frames == 0
        assert t._audio_buffer == []

    def test_partial_emission_does_not_disturb_state(self):
        t = make_transcriber()
        t._partial_interval = 0.0
        samples = np.concatenate([speech_tone(1.5), silence(1.0)])

        _, status, calls = feed(t, samples)

        assert len(calls) == 1
