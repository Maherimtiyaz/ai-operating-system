"""
Speech transcriber for AIOP
"""

import time
import numpy as np
from typing import Optional, Generator, Callable, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from ..core import logging, exceptions, utils
from ..audio import AudioCapture, AudioChunk, get_audio_processor, VoiceActivityDetector
from .whisper_cpp import WhisperModel, get_whisper_model
from .language import get_language

logger = logging.get_logger(__name__)


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
    

@dataclass
class TranscriptionConfig:
    """Transcription configuration"""
    model_name: str = "base.en"
    language: Optional[str] = None
    sample_rate: int = 16000
    chunk_size: int = 1024
    vad_enabled: bool = True
    vad_aggressiveness: int = 3
    silence_threshold: float = 0.5  # seconds
    min_speech_duration: float = 0.3  # seconds
    max_speech_duration: float = 30.0  # seconds
    translate: bool = False
    temperature: float = 0.0
    use_streaming: bool = True


class SpeechTranscriber:
    """Real-time speech transcriber"""
    
    def __init__(self, config: TranscriptionConfig = None):
        self.config = config or TranscriptionConfig()
        self.audio_capture: Optional[AudioCapture] = None
        self.whisper_model: Optional[WhisperModel] = None
        self.audio_processor = get_audio_processor()
        self.state = TranscriptionState.IDLE
        self._audio_buffer: List[bytes] = []
        self._speech_start_time: Optional[float] = None
        self._last_transcription: Optional[TranscriptionResult] = None
        self._callbacks: List[Callable[[TranscriptionResult], None]] = []
        self._is_running = False
        self._setup_components()
    
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
    
    def _process_audio_chunk(self, audio_chunk: AudioChunk) -> None:
        """Process incoming audio chunk"""
        if self.state == TranscriptionState.IDLE:
            # Check for speech start
            result = self.audio_processor.process_chunk(audio_chunk)
            
            if result.is_speech:
                self._speech_start_time = time.time()
                self._audio_buffer = [audio_chunk.data]
                self.state = TranscriptionState.LISTENING
                logger.debug("Speech detected - started recording")
        
        elif self.state == TranscriptionState.LISTENING:
            # Continue recording
            self._audio_buffer.append(audio_chunk.data)
            
            # Check for speech end
            result = self.audio_processor.process_chunk(audio_chunk)
            
            if not result.is_speech:
                # Check if we have enough speech
                duration = time.time() - self._speech_start_time
                if duration >= self.config.min_speech_duration:
                    self.state = TranscriptionState.PROCESSING
                    logger.debug(f"Speech ended after {duration:.2f}s - processing")
                    self._process_buffer()
                else:
                    # Not enough speech, reset
                    self._reset_buffer()
            
            # Check for max duration
            duration = time.time() - self._speech_start_time
            if duration >= self.config.max_speech_duration:
                self.state = TranscriptionState.PROCESSING
                logger.debug(f"Max duration reached ({duration:.2f}s) - processing")
                self._process_buffer()
        
        elif self.state == TranscriptionState.PROCESSING:
            # Wait for processing to complete
            pass
    
    def _process_buffer(self) -> None:
        """Process buffered audio"""
        if not self._audio_buffer:
            self._reset_buffer()
            return
        
        # Combine audio chunks
        audio_data = b''.join(self._audio_buffer)
        
        # Transcribe
        try:
            text = self.whisper_model.transcribe(
                audio_data,
                sample_rate=self.config.sample_rate,
                language=self.config.language,
                translate=self.config.translate,
                temperature=self.config.temperature,
            )
            
            # Create result
            result = TranscriptionResult(
                text=text,
                start_time=self._speech_start_time or 0.0,
                end_time=time.time(),
                confidence=0.9,  # Placeholder
                language=self.config.language,
                is_final=True,
            )
            
            self._last_transcription = result
            
            # Notify callbacks
            for callback in self._callbacks:
                try:
                    callback(result)
                except Exception as e:
                    logger.error(f"Error in transcription callback: {e}")
            
            logger.debug(f"Transcription: {text}")
            
        except Exception as e:
            logger.error(f"Transcription error: {e}")
        
        finally:
            self._reset_buffer()
    
    def _reset_buffer(self) -> None:
        """Reset audio buffer"""
        self._audio_buffer = []
        self._speech_start_time = None
        self.state = TranscriptionState.IDLE
    
    def start(self) -> None:
        """Start transcription"""
        if self._is_running:
            return
        
        self._is_running = True
        self.audio_capture.start()
        logger.info("Transcription started")
    
    def stop(self) -> None:
        """Stop transcription"""
        if not self._is_running:
            return
        
        self._is_running = False
        self.audio_capture.stop()
        self._reset_buffer()
        logger.info("Transcription stopped")
    
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
