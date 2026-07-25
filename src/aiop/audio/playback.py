"""
Audio playback for AIOP
"""

import pyaudio
import numpy as np
from typing import Optional, Union, List
from dataclasses import dataclass
from pathlib import Path
from ..core import logging, exceptions
from .capture import AudioFormat, AudioParameters

logger = logging.get_logger(__name__)


@dataclass
class PlaybackParameters:
    """Audio playback parameters"""
    sample_rate: int = 44100
    channels: int = 2
    format: AudioFormat = AudioFormat.INT16
    chunk_size: int = 1024
    device_index: Optional[int] = None


class AudioPlayback:
    """Audio playback manager"""
    
    def __init__(self, parameters: PlaybackParameters = None):
        self.parameters = parameters or PlaybackParameters()
        self.pyaudio = pyaudio.PyAudio()
        self.stream: Optional[pyaudio.Stream] = None
        self.is_playing = False
    
    def play(self, audio_data: Union[bytes, np.ndarray]) -> None:
        """Play audio data"""
        if not isinstance(audio_data, bytes):
            audio_data = audio_data.tobytes()
        
        try:
            self._ensure_stream()
            self.stream.write(audio_data)
        except Exception as e:
            raise exceptions.AudioError(f"Failed to play audio: {e}")
    
    def play_file(self, file_path: Union[str, Path]) -> None:
        """Play audio file"""
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise exceptions.AudioError(f"Audio file not found: {file_path}")
            
            # Read file based on extension
            ext = file_path.suffix.lower()
            if ext == '.wav':
                audio_data = self._read_wav(file_path)
            elif ext == '.raw':
                with open(file_path, 'rb') as f:
                    audio_data = f.read()
            else:
                raise exceptions.AudioError(f"Unsupported audio format: {ext}")
            
            self.play(audio_data)
            
        except Exception as e:
            raise exceptions.AudioError(f"Failed to play file {file_path}: {e}")
    
    def _read_wav(self, file_path: Path) -> bytes:
        """Read WAV file"""
        import wave
        with wave.open(str(file_path), 'rb') as wav_file:
            return wav_file.readframes(wav_file.getnframes())
    
    def _ensure_stream(self) -> None:
        """Ensure playback stream is open"""
        if self.stream is None or not self.is_playing:
            self._open_stream()
    
    def _open_stream(self) -> None:
        """Open playback stream"""
        try:
            self.stream = self.pyaudio.open(
                format=self.parameters.format.value,
                channels=self.parameters.channels,
                rate=self.parameters.sample_rate,
                output=True,
                frames_per_buffer=self.parameters.chunk_size,
                output_device_index=self.parameters.device_index,
            )
            self.is_playing = True
        except Exception as e:
            raise exceptions.AudioError(f"Failed to open playback stream: {e}")
    
    def stop(self) -> None:
        """Stop playback"""
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                logger.error(f"Error stopping playback: {e}")
            finally:
                self.stream = None
                self.is_playing = False
    
    def play_beep(self, frequency: float = 440.0, duration: float = 0.1) -> None:
        """Play a simple beep sound"""
        sample_rate = self.parameters.sample_rate
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        
        # Generate sine wave
        wave = np.sin(2 * np.pi * frequency * t)
        
        # Convert to int16
        if self.parameters.format == AudioFormat.INT16:
            wave = (wave * 32767).astype(np.int16)
        
        # Stereo
        if self.parameters.channels == 2:
            wave = np.column_stack([wave, wave])
        
        self.play(wave.tobytes())
    
    def play_tone(self, frequency: float, duration: float, volume: float = 0.5) -> None:
        """Play a tone with specified frequency and duration"""
        sample_rate = self.parameters.sample_rate
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        
        # Generate sine wave
        wave = np.sin(2 * np.pi * frequency * t) * volume
        
        # Convert to int16
        if self.parameters.format == AudioFormat.INT16:
            wave = (wave * 32767).astype(np.int16)
        
        # Stereo
        if self.parameters.channels == 2:
            wave = np.column_stack([wave, wave])
        
        self.play(wave.tobytes())
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        if self.pyaudio:
            self.pyaudio.terminate()


# Global audio playback instance
_audio_playback: Optional[AudioPlayback] = None


def get_audio_playback(**kwargs) -> AudioPlayback:
    """Get the global audio playback instance"""
    global _audio_playback
    if _audio_playback is None:
        _audio_playback = AudioPlayback(**kwargs)
    return _audio_playback


def play_audio(audio_data: Union[bytes, np.ndarray]) -> None:
    """Play audio data using global playback"""
    playback = get_audio_playback()
    playback.play(audio_data)


def play_file(file_path: Union[str, Path]) -> None:
    """Play audio file using global playback"""
    playback = get_audio_playback()
    playback.play_file(file_path)


def play_beep(frequency: float = 440.0, duration: float = 0.1) -> None:
    """Play a beep sound"""
    playback = get_audio_playback()
    playback.play_beep(frequency, duration)
