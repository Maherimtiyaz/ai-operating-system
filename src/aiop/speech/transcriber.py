"""
Speech transcriber for AIOP
"""

import re
import time
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Callable, List
from dataclasses import dataclass
from enum import Enum
import numpy as np
from ..core import logging, exceptions
from ..audio import AudioCapture, AudioChunk, get_audio_processor
from .whisper_cpp import WhisperModel, get_whisper_model

logger = logging.get_logger(__name__)

# Whisper renders non-speech as bracketed action tokens. They carry no words,
# so they are filtered out of live previews instead of being drawn like text.
_PLACEHOLDER_RE = re.compile(r"^\([a-z ]+\)$", re.IGNORECASE)


class TranscriptionState(Enum):
    """Transcription states"""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"


@dataclass
class TranscriptionResult:
    """Transcription result"""
    text: str
    start_time: float = 0.0
    end_time: float = 0.0
    confidence: float = 0.0
    language: Optional[str] = None
    is_final: bool = False
    status: Optional[str] = None
    # Monotonic session counter captured when the audio was buffered. A final
    # result carrying an older generation belongs to a session that has since
    # been replaced; consumers use it to avoid pasting into the wrong window.
    generation: int = 0
    

@dataclass
class TranscriptionConfig:
    """Configuration for speech transcription"""
    model_name: str = "base.en"
    language: str = "en"
    sample_rate: int = 16000
    chunk_size: int = 1024
    vad_enabled: bool = True
    vad_aggressiveness: int = 1  # 0-3, lower is more sensitive
    silence_threshold: float = 0.01  # RMS threshold
    min_speech_duration: float = 0.1  # seconds
    max_speech_duration: float = 30.0
    silence_end_frames: int = 10  # frames of silence to end
    translate: bool = False
    temperature: float = 0.0
    use_streaming: bool = True


class SpeechTranscriber:
    """Real-time speech transcriber"""
    
    def __init__(self, config: TranscriptionConfig = None):
        self.config = config or self._config_from_settings()
        self.audio_capture: Optional[AudioCapture] = None
        self.whisper_model: Optional[WhisperModel] = None
        self.audio_processor = get_audio_processor()
        self.state = TranscriptionState.IDLE
        self._audio_buffer: List[bytes] = []
        self._speech_start_time: Optional[float] = None
        self._silence_frames = 0
        self._speech_frames = 0
        self._last_transcription: Optional[TranscriptionResult] = None
        self._callbacks: List[Callable[[TranscriptionResult], None]] = []
        self._is_running = False
        self._partial_interval = 1.0
        self._last_partial_at = 0.0
        self._partial_generation = 0
        # Sliding window for live previews: buffers grow for the whole session,
        # and re-transcribing all of it every interval would scale badly.
        self._partial_preview_seconds = 6.0
        self._transcription_lock = threading.Lock()
        self._partial_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="aiop-partial")
        # Final transcription runs here instead of on whichever thread called
        # stop(). whisper takes seconds; on the Qt main thread that froze the
        # whole UI on every release, and on the PortAudio callback thread it
        # starved the capture buffer.
        self._final_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="aiop-final")
        self._closed = False
        # Bumped on every start(); finals capture the value at buffer time so a
        # slow whisper result for an ended session cannot be pasted into the
        # target window of a session that has started since.
        self._generation = 0
        # Hold-to-talk records from the first frame to the release instead of
        # waiting for VAD to declare speech; VAD gating was swallowing quiet
        # openers and producing empty buffers (nothing to type).
        self.continuous_recording = False
        self._setup_components()

    @staticmethod
    def _config_from_settings() -> TranscriptionConfig:
        """Build a transcriber config from the persisted app settings.

        Falls back to dataclass defaults when settings are unavailable so
        constructing a transcriber never fails at import time.
        """
        defaults = TranscriptionConfig()
        try:
            from ..core import config as app_config

            settings = app_config.get_config().speech
        except Exception as error:
            logger.debug("Could not read speech settings: %s", error)
            return defaults

        model_value = settings.model_path
        if not model_value:
            return defaults

        # Accept either a bare name ("base.en") or a path to a .bin file.
        model_path = Path(model_value).expanduser()
        if model_path.suffix == ".bin":
            model_name = model_path.stem.removeprefix("ggml-")
        else:
            model_name = model_value

        return TranscriptionConfig(
            model_name=model_name,
            language=settings.language,
            sample_rate=defaults.sample_rate,
            vad_enabled=settings.use_vad,
            vad_aggressiveness=settings.vad_aggressiveness,
            temperature=settings.temperature,
        )
    
    def _setup_components(self) -> None:
        """Set up audio capture and whisper model"""
        # Initialize audio capture
        self.audio_capture = AudioCapture(
            sample_rate=self.config.sample_rate,
            channels=1,
            chunk_size=self.config.chunk_size,
        )
        
        # Add callback for audio processing
        self.audio_capture.add_callback(self._process_audio_chunk)
        
        # Initialize whisper model
        try:
            self.whisper_model = get_whisper_model(self.config.model_name)
        except Exception as e:
            logger.warning(f"Failed to load whisper model: {e}")
            self.whisper_model = None

        if self.whisper_model:
            # Load the weights at startup rather than on the first release.
            try:
                self.whisper_model.warmup()
            except Exception as e:
                logger.debug("Whisper warmup skipped: %s", e)
    
    def _process_audio_chunk(self, audio_chunk: AudioChunk) -> None:
        """Process incoming audio chunk"""
        if not self._is_running:
            # The stream stays warm between utterances so the next keypress
            # records instantly; only capture while a dictation is armed.
            return

        if self.state == TranscriptionState.IDLE:
            if self.continuous_recording:
                # Hold-to-talk: record every frame while the key is down and
                # decide on the buffer when stop() arrives.
                self._speech_start_time = time.time()
                self._audio_buffer = [audio_chunk.data]
                self._silence_frames = 0
                self._speech_frames = 1
                self.state = TranscriptionState.LISTENING
                logger.debug("Continuous recording started (hold-to-talk)")
                return

            # Check for speech start
            result = self.audio_processor.process_chunk(audio_chunk)

            if result.is_speech and not result.is_silent:
                self._speech_start_time = time.time()
                self._audio_buffer = [audio_chunk.data]
                self._silence_frames = 0
                self._speech_frames = 1
                self.state = TranscriptionState.LISTENING
                logger.debug("Speech detected - started recording")

        elif self.state == TranscriptionState.LISTENING:
            # Continue recording
            self._audio_buffer.append(audio_chunk.data)
            # Both modes show a live preview of what whisper hears so far;
            # partials update the overlay while the user keeps speaking.
            self._maybe_emit_partial()

            # Check for speech end
            result = self.audio_processor.process_chunk(audio_chunk)

            if result.is_speech and not result.is_silent:
                # webrtcvad hangs over into the first frames of silence, so
                # require real energy as well before calling a chunk voiced.
                self._silence_frames = 0
                self._speech_frames += 1
            else:
                # VAD flickers on breaths and mid-sentence pauses, so require
                # sustained silence before treating the utterance as finished.
                self._silence_frames += 1

            duration = time.time() - (self._speech_start_time or time.time())

            # Check for max duration
            if duration >= self.config.max_speech_duration:
                logger.debug(f"Max duration reached ({duration:.2f}s) - processing")
                self.state = TranscriptionState.PROCESSING
                self._process_buffer()
                return

            if self.continuous_recording:
                # Hold-to-talk: never auto-finalize mid-hold; stop() decides.
                if duration >= self.config.max_speech_duration:
                    self.state = TranscriptionState.PROCESSING
                    self._process_buffer()
                return

            if self._silence_frames < self.config.silence_end_frames:
                return

            # Sustained silence: decide on the voiced duration actually heard,
            # not wall-clock time, so trailing silence cannot pad a noise blip.
            speech_duration = self._speech_frames * (
                self.config.chunk_size / self.config.sample_rate
            )
            if speech_duration >= self.config.min_speech_duration:
                self.state = TranscriptionState.PROCESSING
                logger.debug(
                    f"Speech ended after {speech_duration:.2f}s "
                    f"({self._speech_frames} voiced chunks) - processing"
                )
                self._process_buffer()
            else:
                # Not enough speech, reset
                self._emit_status("too_short", self._generation)
                self._reset_buffer()
        
        elif self.state == TranscriptionState.PROCESSING:
            # Wait for processing to complete
            pass
    
    def _process_buffer(self) -> None:
        """Hand the buffered audio to the transcription worker.

        The buffer is detached synchronously, so the next utterance starts
        collecting immediately and can never be mixed into this one.
        """
        audio_data = b"".join(self._audio_buffer)
        start_time = self._speech_start_time or 0.0
        generation = self._generation
        self._reset_buffer()

        if not audio_data:
            self._emit_status("no_speech", generation)
            return

        if not self.whisper_model:
            logger.error("Cannot transcribe: Whisper model is unavailable")
            self._emit_status("transcription_error", generation)
            return

        self._final_executor.submit(
            self._run_final_transcription, audio_data, start_time, generation
        )

    @staticmethod
    def _trim_silence(audio_data: bytes, sample_rate: int) -> bytes:
        """Drop leading and trailing silence before whisper sees the audio.

        Tap-once (and hold-to-talk) record from the gesture, so the buffer
        always opens with dead air; whisper treats long silence as a cue to
        hallucinate a greeting or a foreign-language aside. Only voiced
        frames plus a short margin survive.
        """
        samples = np.frombuffer(audio_data, dtype=np.int16)
        frame = max(1, int(sample_rate * 0.03))
        frames = samples.size // frame
        if frames < 2:
            return audio_data

        grid = samples[: frames * frame].reshape(frames, frame).astype(np.float64)
        rms = np.sqrt(np.mean(grid * grid, axis=1))
        peak = float(rms.max())
        if peak <= 0.0:
            return audio_data

        voiced = np.flatnonzero(rms > max(peak * 0.1, 50.0))
        if voiced.size == 0:
            return audio_data

        margin = 5  # 150 ms of context on each side of the voiced span
        start = max(0, int(voiced[0]) - margin) * frame
        end = min(samples.size, (int(voiced[-1]) + margin + 1) * frame)
        return samples[start:end].tobytes()

    def _run_final_transcription(
        self, audio_data: bytes, start_time: float, generation: int
    ) -> None:
        """Transcribe detached audio and notify callbacks. Worker thread only."""
        try:
            trimmed = self._trim_silence(audio_data, self.config.sample_rate)
            if trimmed != audio_data:
                logger.debug(
                    "Trimmed silence before transcription: %.2fs -> %.2fs",
                    len(audio_data) / 2 / self.config.sample_rate,
                    len(trimmed) / 2 / self.config.sample_rate,
                )
            with self._transcription_lock:
                text = self.whisper_model.transcribe(
                    trimmed,
                    sample_rate=self.config.sample_rate,
                    language=self.config.language,
                    translate=self.config.translate,
                    temperature=self.config.temperature,
                )

            result = TranscriptionResult(
                text=text,
                start_time=start_time,
                end_time=time.time(),
                confidence=0.9,  # Placeholder
                language=self.config.language,
                is_final=True,
                status="complete",
                generation=generation,
            )

            self._last_transcription = result

            for callback in self._callbacks:
                try:
                    callback(result)
                except Exception as e:
                    logger.error(f"Error in transcription callback: {e}")

            logger.debug(f"Transcription: {text}")

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            self._emit_status("transcription_error", generation)

    def _emit_status(self, status: str, generation: int = 0) -> None:
        result = TranscriptionResult(
            text="", is_final=True, status=status, generation=generation
        )
        for callback in self._callbacks:
            try:
                callback(result)
            except Exception as error:
                logger.error("Error in transcription status callback: %s", error)

    def _maybe_emit_partial(self) -> None:
        """Schedule a throttled preview without blocking audio capture."""
        if not self.config.use_streaming or not self.whisper_model:
            return

        now = time.monotonic()
        if now - self._last_partial_at < self._partial_interval:
            return

        # Only the recent window is transcribed: the buffer spans the whole
        # session, and feeding all of it to whisper every interval would grow
        # quadratically and delay the final result.
        chunk = self.config.chunk_size
        window_chunks = max(
            1, int(self._partial_preview_seconds * self.config.sample_rate // chunk)
        )
        audio_data = b"".join(self._audio_buffer[-window_chunks:])
        duration = len(audio_data) / 2 / self.config.sample_rate
        if duration < self._partial_interval:
            return

        self._last_partial_at = now
        generation = self._partial_generation
        speech_start_time = self._speech_start_time or time.time()
        self._partial_executor.submit(
            self._run_partial,
            audio_data,
            speech_start_time,
            generation,
        )

    def _run_partial(
        self,
        audio_data: bytes,
        speech_start_time: float,
        generation: int,
    ) -> None:
        """Transcribe a preview and emit it only if the utterance is current."""
        try:
            trimmed = self._trim_silence(audio_data, self.config.sample_rate)
            if not trimmed:
                return
            with self._transcription_lock:
                text = self.whisper_model.transcribe(
                    trimmed,
                    sample_rate=self.config.sample_rate,
                    language=self.config.language,
                    translate=self.config.translate,
                    temperature=self.config.temperature,
                )

            if not text or not self._is_running or generation != self._partial_generation:
                return

            # A window of pure silence decodes to a bracketed placeholder;
            # previews should only ever show words.
            if _PLACEHOLDER_RE.match(text.strip()):
                return

            result = TranscriptionResult(
                text=text,
                start_time=speech_start_time,
                end_time=time.time(),
                confidence=0.9,
                language=self.config.language,
                is_final=False,
            )
            for callback in self._callbacks:
                try:
                    callback(result)
                except Exception as error:
                    logger.error("Error in partial transcription callback: %s", error)
        except Exception as error:
            logger.debug("Partial transcription unavailable: %s", error)
    
    def _reset_buffer(self) -> None:
        """Reset audio buffer"""
        self._audio_buffer = []
        self._speech_start_time = None
        self._silence_frames = 0
        self._speech_frames = 0
        self._last_partial_at = 0.0
        self._partial_generation += 1
        self.state = TranscriptionState.IDLE

    def start(self) -> None:
        """Start transcription.

        The audio stream is opened on first use and then kept warm; closing
        and reopening the device costs ~140 ms and ~90 ms respectively, which
        would truncate the opening syllable of every hold-to-talk utterance.
        """
        if self._is_running:
            return

        if self._closed:
            # close() shuts the workers down; revive them so the transcriber
            # stays reusable instead of raising on the next submit.
            self._closed = False
            self._partial_executor = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="aiop-partial"
            )
            self._final_executor = ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="aiop-final"
            )

        try:
            if not self.audio_capture.is_running():
                self.audio_capture.start()
        except Exception:
            self._is_running = False
            self._reset_buffer()
            raise

        self._is_running = True
        self._generation += 1
        logger.info("Transcription started (session %d)", self._generation)

    def stop(self) -> None:
        """Stop transcription.

        Deliberately leaves the audio stream open; call :meth:`close` to
        release the microphone. The final transcription is dispatched to a
        worker, so this returns immediately instead of blocking the caller
        for the whole whisper run.
        """
        if not self._is_running:
            return

        self._is_running = False
        # If we have audio buffer but state is IDLE (speech never triggered VAD
        # strongly enough), still try to process it - be lenient for hold-to-talk.
        if self._audio_buffer and self.state == TranscriptionState.IDLE:
            self._process_buffer()
            logger.info("Transcription stopped (processing buffered audio)")
            return
        self._process_buffer()
        logger.info("Transcription stopped")

    def close(self) -> None:
        """Stop transcription, drop pending work, and release the microphone."""
        if self._is_running:
            self._is_running = False
            self._reset_buffer()
        self._closed = True
        try:
            self.audio_capture.stop()
        except Exception as error:
            logger.error("Error releasing microphone: %s", error)
        # Nothing is listening anymore, so a queued whisper run is pointless.
        self._final_executor.shutdown(wait=False, cancel_futures=True)
        self._partial_executor.shutdown(wait=False, cancel_futures=True)
    
    def pause(self) -> None:
        """Pause transcription"""
        self.audio_capture.stop()
        logger.info("Transcription paused")
    
    def resume(self) -> None:
        """Resume transcription"""
        self.audio_capture.start()
        logger.info("Transcription resumed")
    
    def add_callback(self, callback: Callable[[TranscriptionResult], None]) -> None:
        """Add a callback for transcription results"""
        self._callbacks.append(callback)
    
    def remove_callback(self, callback: Callable[[TranscriptionResult], None]) -> None:
        """Remove a callback"""
        if callback in self._callbacks:
            self._callbacks.remove(callback)
    
    def get_last_result(self) -> Optional[TranscriptionResult]:
        """Get the last transcription result"""
        return self._last_transcription
    
    def transcribe_once(self, timeout: float = 10.0) -> Optional[TranscriptionResult]:
        """
        Transcribe a single utterance
        
        Args:
            timeout: Maximum time to wait for speech
        
        Returns:
            Transcription result or None if timeout
        """
        self._reset_buffer()
        self.start()
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self._last_transcription:
                result = self._last_transcription
                self._last_transcription = None
                return result
            time.sleep(0.1)
        
        self.stop()
        return None
    
    def transcribe_audio(self, audio_data: bytes) -> str:
        """
        Transcribe audio data directly
        
        Args:
            audio_data: Audio data bytes
        
        Returns:
            Transcribed text
        """
        if not self.whisper_model:
            raise exceptions.SpeechError("Whisper model not loaded")
        
        return self.whisper_model.transcribe(
            audio_data,
            sample_rate=self.config.sample_rate,
            language=self.config.language,
        )
    
    def set_language(self, language_code: str) -> None:
        """Set transcription language"""
        self.config.language = language_code
        if self.whisper_model:
            self.whisper_model.set_language(language_code)
    
    def set_model(self, model_name: str) -> None:
        """Set whisper model"""
        self.config.model_name = model_name
        self.whisper_model = get_whisper_model(model_name)
    
    def is_running(self) -> bool:
        """Check if transcription is running"""
        return self._is_running

    @property
    def generation(self) -> int:
        """Session counter of the most recently started dictation."""
        return self._generation
    
    def get_state(self) -> TranscriptionState:
        """Get current transcription state"""
        return self.state
    
    def get_config(self) -> TranscriptionConfig:
        """Get current configuration"""
        return self.config
    
    def set_config(self, **kwargs) -> None:
        """Set configuration values"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
    
    def __enter__(self):
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


# Global transcriber instance
_transcriber: Optional[SpeechTranscriber] = None


def get_transcriber(config: TranscriptionConfig = None) -> SpeechTranscriber:
    """Get the global speech transcriber instance"""
    global _transcriber
    if _transcriber is None:
        _transcriber = SpeechTranscriber(config)
    return _transcriber


def start_transcription(**kwargs) -> SpeechTranscriber:
    """Start global transcription"""
    transcriber = get_transcriber()
    if kwargs:
        transcriber.set_config(**kwargs)
    transcriber.start()
    return transcriber


def stop_transcription() -> None:
    """Stop global transcription"""
    global _transcriber
    if _transcriber:
        _transcriber.stop()


def transcribe_audio(audio_data: bytes, **kwargs) -> str:
    """Transcribe audio data"""
    transcriber = get_transcriber()
    return transcriber.transcribe_audio(audio_data)
