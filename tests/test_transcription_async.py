"""Final transcription must not block the caller.

`stop()` runs on the Qt main thread on every key release. When it called
whisper synchronously, the whole UI froze for as long as the model took
(measured >2.5 s), and the same call on the PortAudio callback thread
starved the capture buffer. The audio is now detached synchronously and
handed to a worker.
"""

import threading
import time

from aiop.speech.transcriber import (
    SpeechTranscriber,
    TranscriptionConfig,
    TranscriptionState,
)

WHISPER_SECONDS = 0.6
# Generous: a real regression blocks for the full whisper run.
MUST_RETURN_WITHIN = 0.3


class SlowWhisper:
    def __init__(self, text: str = "hello there") -> None:
        self.text = text
        self.calls = []

    def transcribe(self, audio_data, **kwargs):
        self.calls.append(len(audio_data))
        time.sleep(WHISPER_SECONDS)
        return self.text


def make_running_transcriber(text: str = "hello there"):
    t = SpeechTranscriber(config=TranscriptionConfig())
    model = SlowWhisper(text)
    t.whisper_model = model
    t._is_running = True
    t.state = TranscriptionState.LISTENING
    t._audio_buffer = [b"\x01\x00" * 512]
    t._speech_start_time = time.time()
    return t, model


def test_stop_returns_before_whisper_finishes():
    t, model = make_running_transcriber()

    started = time.monotonic()
    t.stop()
    elapsed = time.monotonic() - started

    assert elapsed < MUST_RETURN_WITHIN, (
        f"stop() blocked for {elapsed:.2f}s; the UI thread would freeze"
    )
    t.close()


def test_buffer_is_detached_before_stop_returns():
    t, model = make_running_transcriber()

    t.stop()

    # The next utterance must start on a clean buffer while whisper is still
    # working on the previous one.
    assert t._audio_buffer == []
    assert t._is_running is False
    t.close()


def test_final_result_is_still_delivered():
    t, model = make_running_transcriber(text="typed by the worker")

    seen = []
    done = threading.Event()
    t.add_callback(lambda r: (seen.append(r), done.set()))

    t.stop()
    assert done.wait(WHISPER_SECONDS * 4 + 2), "final transcription never arrived"
    assert seen[0].text == "typed by the worker"
    assert seen[0].is_final is True
    t.close()


def test_slow_result_does_not_block_a_second_stop():
    t, model = make_running_transcriber()

    t.stop()
    t._is_running = True
    t.state = TranscriptionState.LISTENING
    t._audio_buffer = [b"\x02\x00" * 512]

    started = time.monotonic()
    t.stop()
    elapsed = time.monotonic() - started

    assert elapsed < MUST_RETURN_WITHIN, f"second stop() blocked for {elapsed:.2f}s"
    t.close()


class IdleCapture:
    """Audio capture stub so start() never touches the real microphone."""

    def __init__(self) -> None:
        self.started = False

    def is_running(self) -> bool:
        return self.started

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False


def test_close_then_start_revives_the_workers():
    t, model = make_running_transcriber()
    t.audio_capture = IdleCapture()
    t.stop()
    t.close()

    t.start()
    assert t._is_running is True

    # The revived worker must actually accept work.
    done = threading.Event()
    t.add_callback(lambda r: done.set())
    t._audio_buffer = [b"\x03\x00" * 512]
    t.state = TranscriptionState.LISTENING
    t.stop()
    assert done.wait(WHISPER_SECONDS * 4 + 2), "revived worker never ran"
    t.close()
