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
    
    def is_speech(self, audio_chunk: AudioChunk) -> bool:
        """Check if audio chunk contains speech"""
        try:
            # Convert to 16-bit PCM if needed
            if audio_chunk.format != AudioFormat.INT16:
                audio_data = self._convert_format(audio_chunk)
            else:
                audio_data = audio_chunk.data
            
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
        # Simplified conversion - in practice, use proper audio conversion
        if audio_chunk.format == AudioFormat.FLOAT32:
            # Convert float32 to int16
            samples = np.frombuffer(audio_chunk.data, dtype=np.float32)
            samples = np.clip(samples * 32767, -32768, 32767).astype(np.int16)
            return samples.tobytes()
        elif audio_chunk.format == AudioFormat.INT8:
            # Convert int8 to int16
            samples = np.frombuffer(audio_chunk.data, dtype=np.int8)
            samples = (samples.astype(np.int16) * 256).tobytes()
            return samples
        else:
            return audio_chunk.data
    
    def process(self, audio_chunk: AudioChunk) -> ProcessingResult:
        """Process audio chunk and return detailed result"""
        is_speech = self.is_speech(audio_chunk)
        
        # Calculate RMS
        if audio_chunk.format == AudioFormat.INT16:
            samples = np.frombuffer(audio_chunk.data, dtype=np.int16)
        else:
            samples = np.frombuffer(audio_chunk.data, dtype=np.float32)
        
        rms = np.sqrt(np.mean(samples ** 2))
        energy = np.sum(samples ** 2) / len(samples)
        
        return ProcessingResult(
            is_speech=is_speech,
            is_noise=not is_speech and rms > 0.01,
            is_silent=rms <= 0.01,
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
        if audio_chunk.format == AudioFormat.INT16:
            samples = np.frombuffer(audio_chunk.data, dtype=np.int16)
        else:
            samples = np.frombuffer(audio_chunk.data, dtype=np.float32)
        
        rms = np.sqrt(np.mean(samples ** 2))
        energy = np.sum(samples ** 2) / len(samples)
        
        return ProcessingResult(
            is_speech=rms > 0.05,  # Simple threshold
            is_noise=rms > 0.01 and rms <= 0.05,
            is_silent=rms <= 0.01,
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
