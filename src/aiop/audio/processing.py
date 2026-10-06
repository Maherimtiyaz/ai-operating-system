"""
Audio processing for AIOP
"""

import numpy as np
import webrtcvad
from typing import Optional, Tuple, List
from dataclasses import dataclass
from ..core import logging, exceptions
from .capture import AudioChunk, AudioFormat

logger = logging.get_logger(__name__)

# Normalized amplitude thresholds (samples are decoded to [-1.0, 1.0]).
# Measured against real captures: room noise floors near 0.0002 RMS, speech
# medians near 0.07 RMS, so the bands below separate them by a wide margin.
SILENCE_RMS = 0.001  # ~ -60 dBFS
NOISE_RMS = 0.005    # ~ -46 dBFS

_INT16_SCALE = 32768.0


def _decode_samples(data: bytes, fmt: AudioFormat) -> np.ndarray:
    """Decode PCM bytes to float32 samples normalized to [-1.0, 1.0].

    Squaring int16 samples directly overflows the dtype, which silently
    wraps to negative values and makes RMS NaN. Decoding once here keeps
    every consumer on a single, consistent linear scale.
    """
    if fmt == AudioFormat.FLOAT32:
        return np.frombuffer(data, dtype=np.float32).astype(np.float32)
    if fmt == AudioFormat.INT8:
        return np.frombuffer(data, dtype=np.int8).astype(np.float32) / 128.0
    if fmt == AudioFormat.INT32:
        return np.frombuffer(data, dtype=np.int32).astype(np.float32) / 2147483648.0
    if fmt == AudioFormat.INT24:
        if len(data) % 3:
            data = data[: len(data) - (len(data) % 3)]
        unpacked = np.frombuffer(data, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        values = (unpacked[:, 0] | (unpacked[:, 1] << 8) | (unpacked[:, 2] << 16))
        values = np.where(values & 0x800000, values - 0x1000000, values)
        return values.astype(np.float32) / 8388608.0
    # Default: little-endian signed 16-bit
    return np.frombuffer(data, dtype=np.int16).astype(np.float32) / _INT16_SCALE


def _rms_energy(samples: np.ndarray) -> Tuple[float, float]:
    """Return (rms, energy) for normalized samples. Both are linear in [-1, 1]."""
    if samples.size == 0:
        return 0.0, 0.0
    squared = samples.astype(np.float64) ** 2
    energy = float(np.mean(squared))
    return float(np.sqrt(energy)), energy


@dataclass
class VADConfig:
    """Voice Activity Detection configuration"""
    aggressiveness: int = 3  # 0-3, higher is more aggressive
    sample_rate: int = 16000
    frame_duration_ms: int = 30  # 10, 20, or 30 ms


@dataclass
class ProcessingResult:
    """Audio processing result"""
    is_speech: bool
    is_noise: bool
    is_silent: bool
    rms: float
    energy: float
    

class VoiceActivityDetector:
    """Voice Activity Detection using WebRTC VAD"""
    
    def __init__(self, config: VADConfig = None):
        self.config = config or VADConfig()
        self.vad = webrtcvad.Vad(self.config.aggressiveness)
        self.sample_rate = self.config.sample_rate
        self.frame_duration_ms = self.config.frame_duration_ms
        self.frame_length = int(self.sample_rate * self.frame_duration_ms / 1000)
    
    def is_speech(self, audio_chunk: AudioChunk | bytes) -> bool:
        """Check if audio chunk contains speech.

        Accepts either an :class:`AudioChunk` or raw little-endian int16 PCM.
        """
        try:
            if isinstance(audio_chunk, AudioChunk):
                if audio_chunk.format != AudioFormat.INT16:
                    audio_data = self._convert_format(audio_chunk)
                else:
                    audio_data = audio_chunk.data
            else:
                audio_data = bytes(audio_chunk)

            # Check frame length
            if len(audio_data) < self.frame_length * 2:  # 2 bytes per sample for int16
                # Pad with zeros if too short
                audio_data += b'\x00' * (self.frame_length * 2 - len(audio_data))
            
            # Check multiple frames
            frames = [audio_data[i:i + self.frame_length * 2] 
                     for i in range(0, len(audio_data), self.frame_length * 2)]
            
            for frame in frames:
                if len(frame) == self.frame_length * 2:
                    if self.vad.is_speech(frame, self.sample_rate):
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error in VAD: {e}")
            return False
    
    def _convert_format(self, audio_chunk: AudioChunk) -> bytes:
        """Convert audio to 16-bit PCM"""
        if audio_chunk.format == AudioFormat.INT16:
            return audio_chunk.data
        samples = _decode_samples(audio_chunk.data, audio_chunk.format)
        samples = np.clip(samples * 32767, -32768, 32767).astype(np.int16)
        return samples.tobytes()
    
    def process(self, audio_chunk: AudioChunk) -> ProcessingResult:
        """Process audio chunk and return detailed result"""
        is_speech = self.is_speech(audio_chunk)

        samples = _decode_samples(audio_chunk.data, audio_chunk.format)
        rms, energy = _rms_energy(samples)

        return ProcessingResult(
            is_speech=is_speech,
            is_noise=not is_speech and rms > SILENCE_RMS,
            is_silent=rms <= SILENCE_RMS,
            rms=float(rms),
            energy=float(energy),
        )


class AudioProcessor:
    """Audio processing pipeline"""
    
    def __init__(
        self,
        sample_rate: int = 16000,
        use_vad: bool = True,
        vad_config: VADConfig = None,
    ):
        self.sample_rate = sample_rate
        self.use_vad = use_vad
        self.vad = VoiceActivityDetector(vad_config) if use_vad else None
        self._audio_buffer: List[bytes] = []
        self._buffer_size = sample_rate  # 1 second buffer
        self._last_was_speech = False
    
    def process_chunk(self, audio_chunk: AudioChunk) -> ProcessingResult:
        """Process an audio chunk"""
        if self.use_vad and self.vad:
            return self.vad.process(audio_chunk)
        
        # Basic processing without VAD
        samples = _decode_samples(audio_chunk.data, audio_chunk.format)
        rms, energy = _rms_energy(samples)

        return ProcessingResult(
            is_speech=rms > NOISE_RMS,  # Simple energy gate
            is_noise=SILENCE_RMS < rms <= NOISE_RMS,
            is_silent=rms <= SILENCE_RMS,
            rms=float(rms),
            energy=float(energy),
        )
    
    def add_to_buffer(self, audio_chunk: AudioChunk) -> None:
        """Add audio chunk to buffer"""
        self._audio_buffer.append(audio_chunk.data)
        
        # Limit buffer size
        total_samples = sum(len(chunk) // 2 for chunk in self._audio_buffer)  # 2 bytes per int16 sample
        if total_samples > self._buffer_size:
            # Remove oldest chunks
            while self._audio_buffer and total_samples > self._buffer_size:
                removed = self._audio_buffer.pop(0)
                total_samples -= len(removed) // 2
    
    def get_buffer(self) -> bytes:
        """Get all buffered audio data"""
        return b''.join(self._audio_buffer)
    
    def clear_buffer(self) -> None:
        """Clear audio buffer"""
        self._audio_buffer = []
    
    def get_buffer_duration(self) -> float:
        """Get buffer duration in seconds"""
        total_samples = sum(len(chunk) // 2 for chunk in self._audio_buffer)
        return total_samples / self.sample_rate
    
    def detect_speech_start(self, audio_chunk: AudioChunk) -> bool:
        """Detect speech start (transition from silence to speech)"""
        result = self.process_chunk(audio_chunk)
        
        # Simple state-based detection
        if result.is_speech and not self._last_was_speech:
            self._last_was_speech = True
            return True
        
        self._last_was_speech = result.is_speech
        return False
    
    def detect_speech_end(self, audio_chunk: AudioChunk, silence_threshold: float = 0.5) -> bool:
        """Detect speech end (transition from speech to silence)"""
        result = self.process_chunk(audio_chunk)
        
        if not result.is_speech and self._last_was_speech:
            # Check if we've had enough silence
            if self.get_buffer_duration() >= silence_threshold:
                self._last_was_speech = False
                return True
        
        self._last_was_speech = result.is_speech
        return False


# Global audio processor instance
_audio_processor: Optional[AudioProcessor] = None


def get_audio_processor(**kwargs) -> AudioProcessor:
    """Get the global audio processor instance"""
    global _audio_processor
    if _audio_processor is None:
        _audio_processor = AudioProcessor(**kwargs)
    return _audio_processor
